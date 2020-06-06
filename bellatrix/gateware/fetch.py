from nmigen import Mux
from nmigen import Module
from nmigen import Signal
from nmigen import Elaboratable
from nmigen.utils import log2_int
from nmigen.build import Platform
from nmigen_soc.wishbone.bus import CycleType
from nmigen_soc.wishbone.bus import Interface
from bellatrix.gateware.cache import Cache
from bellatrix.gateware.wishbone import Arbiter


class FetchUnitInterface:
    def __init__(self) -> None:
        self.iport         = Interface(addr_width=32, data_width=32, granularity=32, features=['err'], name='iport')
        self.f_pc          = Signal(32)  # input
        self.f_kill        = Signal()    # input
        self.f_busy        = Signal()    # output
        self.f2_pc         = Signal(32)  # output
        self.f_instruction = Signal(32, reset=0x00000013)  # output
        self.f_bus_error   = Signal()    # output
        self.d_stall       = Signal()    # input


class BasicFetchUnit(FetchUnitInterface, Elaboratable):
    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        with m.FSM():
            with m.State('IDLE'):
                with m.If(self.f_kill | ~self.d_stall):
                    m.d.sync += self.f_instruction.eq(0x00000013)
                with m.If(~(self.d_stall | self.f_kill)):
                    m.d.sync += [
                        self.f2_pc.eq(self.f_pc),
                        self.iport.adr.eq(self.f_pc),
                        self.iport.cyc.eq(1),
                        self.iport.stb.eq(1),

                        self.f_bus_error.eq(0)
                    ]
                    m.next = 'BUSY'
            with m.State('BUSY'):
                m.d.comb += self.f_busy.eq(1)
                with m.If(self.iport.ack | self.iport.err | self.f_kill):
                    m.d.sync += [
                        self.iport.cyc.eq(0),
                        self.iport.stb.eq(0),
                        self.f_instruction.eq(self.iport.dat_r),

                        self.f_bus_error.eq(self.iport.err)
                    ]
                    m.next = 'IDLE'
                with m.If(self.f_kill):
                    m.d.sync += self.f_instruction.eq(0x00000013)

        return m


class CachedFetchUnit(FetchUnitInterface, Elaboratable):
    def __init__(self, **cache_kwargs: int) -> None:
        super().__init__()

        self.iport        = Interface(addr_width=32, data_width=32, granularity=32, features=['err', 'bte', 'cti'], name='iport')
        self.cache_kwargs = cache_kwargs
        self.start_addr   = cache_kwargs['start_addr']
        self.end_addr     = cache_kwargs['end_addr']
        self.nwords       = cache_kwargs['nwords']
        # IO
        self.flush        = Signal()

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        arbiter = m.submodules.arbiter = Arbiter(addr_width=32, data_width=32, granularity=32, features=['err', 'cti', 'bte'])
        icache  = m.submodules.icache  = Cache(enable_write=False, **self.cache_kwargs)

        cache_port = arbiter.add_port(priority=0)
        bare_port  = arbiter.add_port(priority=1)

        f1_use_cache = Signal()
        f2_use_cache = Signal()

        bits_range = log2_int(self.end_addr - self.start_addr, need_pow2=False)
        m.d.comb += f1_use_cache.eq((self.f_pc[bits_range:] == (self.start_addr >> bits_range)))

        with m.If(self.f_kill | ~(self.d_stall | self.f_busy)):
            m.d.sync += self.f2_pc.eq(self.f_pc)

        with m.If(self.f_kill):
            m.d.sync += f2_use_cache.eq(0)
        with m.Elif(~(self.d_stall | self.f_busy)):
            m.d.sync += f2_use_cache.eq(f1_use_cache)

        m.d.comb += arbiter.bus.connect(self.iport)

        # connect IO: cache
        m.d.comb += [
            icache.s1_address.eq(self.f_pc),
            icache.s1_flush.eq(self.flush),
            icache.s2_address.eq(self.f2_pc),
            icache.s2_valid.eq(f2_use_cache),
            icache.s2_stall.eq(self.d_stall),
            icache.s2_kill.eq(self.f_kill)
        ]

        # connect cache to arbiter
        m.d.comb += [
            cache_port.adr.eq(icache.bus_addr),
            cache_port.dat_w.eq(0),
            cache_port.sel.eq(0),
            cache_port.we.eq(0),
            cache_port.cyc.eq(icache.bus_valid),
            cache_port.stb.eq(icache.bus_valid),
            cache_port.cti.eq(Mux(icache.bus_last, CycleType.END_OF_BURST, CycleType.INCR_BURST)),
            cache_port.bte.eq(log2_int(self.nwords) - 1),
            icache.bus_data.eq(cache_port.dat_r),
            icache.bus_ack.eq(cache_port.ack),
            icache.bus_err.eq(cache_port.err)
        ]

        # drive the bare bus IO
        rdata = Signal(32, reset=0x00000013)

        with m.FSM():
            with m.State('IDLE'):
                with m.If(~(self.d_stall | f1_use_cache | self.f_kill)):
                    m.d.sync += [
                        bare_port.adr.eq(self.f_pc),
                        bare_port.cyc.eq(1),
                        bare_port.stb.eq(1)
                    ]
                    m.next = 'BUSY'
            with m.State('BUSY'):
                with m.If(bare_port.ack | bare_port.err | self.f_kill):
                    m.d.sync += [
                        bare_port.cyc.eq(0),
                        bare_port.stb.eq(0),
                        rdata.eq(bare_port.dat_r)
                    ]
                    m.next = 'IDLE'
                with m.If(self.f_kill):
                    m.d.sync += rdata.eq(0x00000013)

        # in case of error, make the instruction a NOP
        with m.If(self.f_kill | self.f_bus_error):
            m.d.comb += [
                self.f_instruction.eq(0x00000013),  # NOP
                self.f_busy.eq(0)
            ]
        with m.Elif(f2_use_cache):
            m.d.comb += [
                self.f_instruction.eq(icache.s2_rdata),
                self.f_busy.eq(icache.s2_miss)
            ]
        with m.Else():
            m.d.comb += [
                self.f_instruction.eq(rdata),
                self.f_busy.eq(bare_port.cyc)
            ]

        # excepcion
        with m.If(self.iport.cyc & self.iport.err):
            m.d.sync += self.f_bus_error.eq(1)
        with m.Elif(~self.d_stall):
            m.d.sync += self.f_bus_error.eq(0)

        return m
