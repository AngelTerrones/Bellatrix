from nmigen import Cat
from nmigen import Mux
from nmigen import Repl
from nmigen import Module
from nmigen import Record
from nmigen import Signal
from nmigen import Elaboratable
from nmigen.utils import log2_int
from nmigen.build import Platform
from nmigen.lib.fifo import SyncFIFOBuffered
from nmigen_soc.wishbone.bus import CycleType
from nmigen_soc.wishbone.bus import Interface
from bellatrix.gateware.isa import Funct3
from bellatrix.gateware.cache import Cache
from bellatrix.gateware.wishbone import Arbiter


class DataFormat(Elaboratable):
    def __init__(self) -> None:
        self.x_funct3     = Signal(Funct3)   # inputs
        self.x_offset     = Signal(2)   # inputs
        self.m_offset     = Signal(2)   # inputs
        self.x_store_data = Signal(32)  # inputs  (raw data to store)
        self.m_data_r     = Signal(32)  # inputs  (raw data from load)
        self.m_funct3     = Signal(Funct3)   # inputs
        self.x_byte_sel   = Signal(4)   # outputs
        self.x_data_w     = Signal(32)  # outputs (formatted data to bus)
        self.x_misaligned = Signal()    # outputs
        self.m_load_data  = Signal(32)  # outputs (formatted data to pipeline)

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        # create the byte selector
        with m.Switch(self.x_funct3):
            with m.Case(Funct3.B):
                m.d.comb += self.x_byte_sel.eq(0b0001 << self.x_offset)
            with m.Case(Funct3.H):
                m.d.comb += self.x_byte_sel.eq(0b0011 << self.x_offset)
            with m.Case(Funct3.W):
                m.d.comb += self.x_byte_sel.eq(0b1111)

        # format output data
        with m.Switch(self.x_funct3):
            with m.Case(Funct3.B):
                m.d.comb += self.x_data_w.eq(Repl(self.x_store_data[:8], 4))
            with m.Case(Funct3.H):
                m.d.comb += self.x_data_w.eq(Repl(self.x_store_data[:16], 2))
            with m.Case(Funct3.W):
                m.d.comb += self.x_data_w.eq(self.x_store_data)

        # format input data
        _byte = Signal((8, True))
        _half = Signal((16, True))

        m.d.comb += [
            _byte.eq(self.m_data_r.word_select(self.m_offset, 8)),
            _half.eq(self.m_data_r.word_select(self.m_offset[1], 16)),
        ]

        with m.Switch(self.m_funct3):
            with m.Case(Funct3.B):
                m.d.comb += self.m_load_data.eq(_byte)
            with m.Case(Funct3.BU):
                m.d.comb += self.m_load_data.eq(Cat(_byte, 0))  # make sign bit = 0
            with m.Case(Funct3.H):
                m.d.comb += self.m_load_data.eq(_half)
            with m.Case(Funct3.HU):
                m.d.comb += self.m_load_data.eq(Cat(_half, 0))  # make sign bit = 0
            with m.Case(Funct3.W):
                m.d.comb += self.m_load_data.eq(self.m_data_r)

        # misalignment
        with m.Switch(self.x_funct3):
            with m.Case(Funct3.H, Funct3.HU):
                m.d.comb += self.x_misaligned.eq(self.x_offset[0])
            with m.Case(Funct3.W):
                m.d.comb += self.x_misaligned.eq(self.x_offset != 0)

        return m


class LSUInterface:
    def __init__(self) -> None:
        # Misaligned exception detected in X stage
        self.dport         = Interface(addr_width=32, data_width=32, granularity=8, features=['err'], name='dport')
        self.x_addr        = Signal(32)  # input
        self.x_data_w      = Signal(32)  # input
        self.x_store       = Signal()    # input
        self.x_load        = Signal()    # input
        self.x_byte_sel    = Signal(4)   # input
        self.x_enable      = Signal()    # input
        self.m_stall       = Signal()    # input
        self.m_load_data   = Signal(32)  # output
        self.m_busy        = Signal()    # output
        self.m_load_error  = Signal()    # output
        self.m_store_error = Signal()    # output
        self.m_badaddr     = Signal(32)  # output


class BasicLSU(LSUInterface, Elaboratable):
    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        with m.FSM():
            with m.State('IDLE'):
                m.d.sync += [
                    self.m_load_error.eq(0),
                    self.m_store_error.eq(0)
                ]
                with m.If((self.x_load | self.x_store) & self.x_enable & ~self.m_stall):
                    m.d.sync += [
                        self.dport.adr.eq(self.x_addr),
                        self.dport.dat_w.eq(self.x_data_w),
                        self.dport.sel.eq(self.x_byte_sel),
                        self.dport.we.eq(self.x_store),
                        self.dport.cyc.eq(1),
                        self.dport.stb.eq(1)
                    ]
                    m.next = 'BUSY'
            with m.State('BUSY'):
                m.d.comb += self.m_busy.eq(1)

                with m.If(self.dport.err):
                    m.d.sync += [
                        self.m_load_error.eq(~self.dport.we),
                        self.m_store_error.eq(self.dport.we),
                        self.m_badaddr.eq(self.dport.adr)
                    ]
                with m.If(self.dport.ack | self.dport.err):
                    m.d.sync += [
                        self.m_load_data.eq(self.dport.dat_r),
                        self.dport.we.eq(0),
                        self.dport.cyc.eq(0),
                        self.dport.stb.eq(0)
                    ]
                    m.next = 'IDLE'

        return m


class CachedLSU(LSUInterface, Elaboratable):
    def __init__(self, **cache_kwargs: int) -> None:
        super().__init__()

        self.dport        = Interface(addr_width=32, data_width=32, granularity=8, features=['err', 'cti', 'bte'], name='dport')
        self.cache_kwargs = cache_kwargs
        self.start_addr   = cache_kwargs['start_addr']
        self.end_addr     = cache_kwargs['end_addr']
        self.nwords       = cache_kwargs['nwords']
        # IO
        self.x_fence_i    = Signal()    # input
        self.x_fence      = Signal()    # input
        self.x_busy       = Signal()    # input
        self.m_addr       = Signal(32)  # input
        self.m_load       = Signal()    # input
        self.m_store      = Signal()    # input

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        wbuffer_layout = [
            ("addr", 32),
            ("data", 32),
            ("sel",  4)
        ]

        wbuffer_din  = Record(wbuffer_layout)
        wbuffer_dout = Record(wbuffer_layout)

        dcache  = m.submodules.dcache  = Cache(enable_write=True, **self.cache_kwargs)
        arbiter = m.submodules.arbiter = Arbiter(addr_width=32, data_width=32, granularity=8, features=['err', 'cti', 'bte'])
        wbuffer = m.submodules.wbuffer = SyncFIFOBuffered(width=len(wbuffer_din), depth=self.nwords)

        wbuffer_port = arbiter.add_port(priority=0)
        cache_port   = arbiter.add_port(priority=1)

        x_use_cache = Signal()
        m_use_cache = Signal()
        m_data_w    = Signal(32)
        m_byte_sel  = Signal(4)

        bits_range = log2_int(self.end_addr - self.start_addr, need_pow2=False)
        m.d.comb += x_use_cache.eq((self.x_addr[bits_range:] == (self.start_addr >> bits_range)))

        with m.If(~self.m_stall):
            m.d.sync += [
                m_use_cache.eq(x_use_cache),
                m_data_w.eq(self.x_data_w),
                m_byte_sel.eq(self.x_byte_sel)
            ]
        m.d.comb += arbiter.bus.connect(self.dport)

        # --------------------------------------------------
        # write buffer IO
        m.d.comb += [
            # input
            wbuffer.w_data.eq(wbuffer_din),
            wbuffer.w_en.eq(self.x_store & ~self.m_stall & self.x_enable),  # x_use_cache &
            wbuffer_din.addr.eq(self.x_addr),
            wbuffer_din.data.eq(self.x_data_w),
            wbuffer_din.sel.eq(self.x_byte_sel),
            # output
            wbuffer_dout.eq(wbuffer.r_data),
        ]

        # drive the arbiter port
        with m.FSM():
            with m.State('IDLE'):
                with m.If(wbuffer.r_rdy):
                    m.d.sync += [
                        wbuffer_port.cyc.eq(1),
                        wbuffer_port.stb.eq(1),
                        wbuffer_port.we.eq(1),
                        wbuffer_port.adr.eq(wbuffer_dout.addr),
                        wbuffer_port.dat_w.eq(wbuffer_dout.data),
                        wbuffer_port.sel.eq(wbuffer_dout.sel)
                    ]
                    m.next = 'BUSY'
            with m.State('BUSY'):
                with m.If(wbuffer_port.ack | wbuffer_port.err):
                    m.d.comb += wbuffer.r_en.eq(1)
                    m.d.sync += wbuffer_port.stb.eq(0)

                    with m.If(wbuffer.level == 1):  # Buffer is empty (next clock, ofc)
                        m.d.sync += [
                            wbuffer_port.cyc.eq(0),
                            wbuffer_port.we.eq(0)
                        ]
                        m.next = 'IDLE'
                    with m.Else():
                        m.next = 'WAIT'
            with m.State('WAIT'):
                m.d.sync += [
                    wbuffer_port.stb.eq(1),
                    wbuffer_port.adr.eq(wbuffer_dout.addr),
                    wbuffer_port.dat_w.eq(wbuffer_dout.data),
                    wbuffer_port.sel.eq(wbuffer_dout.sel)
                ]
                m.next = 'BUSY'

        m.d.comb += [
            wbuffer_port.cti.eq(CycleType.CLASSIC),
            wbuffer_port.bte.eq(0)
        ]

        # --------------------------------------------------
        # connect IO: cache
        m.d.comb += [
            dcache.s1_address.eq(self.x_addr),
            dcache.s1_flush.eq(0),              # TODO: connect
            dcache.s2_address.eq(self.m_addr),
            dcache.s2_valid.eq(m_use_cache & self.m_load),    # address in range, and load. Ignore stores
            dcache.s2_stall.eq(0),
            dcache.s2_wdata.eq(m_data_w),
            dcache.s2_sel.eq(m_byte_sel),
            dcache.s2_we.eq(self.m_store)
        ]

        # connect cache to arbiter
        m.d.comb += [
            cache_port.adr.eq(dcache.bus_addr),
            cache_port.dat_w.eq(0),
            cache_port.sel.eq(0),
            cache_port.we.eq(0),
            cache_port.cyc.eq(dcache.bus_valid),
            cache_port.stb.eq(dcache.bus_valid),
            cache_port.cti.eq(Mux(dcache.bus_last, CycleType.END_OF_BURST, CycleType.INCR_BURST)),
            cache_port.bte.eq(log2_int(self.nwords) - 1),
            dcache.bus_data.eq(cache_port.dat_r),
            dcache.bus_ack.eq(cache_port.ack),
            dcache.bus_err.eq(cache_port.err)
        ]

        # --------------------------------------------------
        # extra logic
        with m.If(self.x_fence_i | self.x_fence):
            m.d.comb += self.x_busy.eq(wbuffer.r_rdy)
        with m.Elif(x_use_cache):
            m.d.comb += self.x_busy.eq(self.x_store & ~wbuffer.w_rdy)

        with m.If(m_use_cache & self.m_load):
            m.d.comb += [
                self.m_busy.eq(dcache.s2_miss),
                self.m_load_data.eq(dcache.s2_rdata)
            ]

        # --------------------------------------------------
        # exceptions
        with m.If(self.dport.cyc & self.dport.err):
            m.d.sync += [
                self.m_load_error.eq(~self.dport.we),
                self.m_store_error.eq(self.dport.we),
                self.m_badaddr.eq(self.dport.adr)
            ]
        with m.Else():
            m.d.sync += [
                self.m_load_error.eq(0),
                self.m_store_error.eq(0)
            ]

        return m
