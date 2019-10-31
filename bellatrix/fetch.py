from nmigen import Mux
from nmigen import Module
from nmigen import Record
from nmigen import Signal
from nmigen import Elaboratable
from nmigen.utils import log2_int
from .wishbone import Arbiter
from .wishbone import CycleType
from .wishbone import wishbone_layout
from .cache import Cache


class FetchUnitInterface:
    def __init__(self):
        self.iport = Record(wishbone_layout)
        # from address stage
        self.a_pc   = Signal(32)
        # control signals
        self.a_stall = Signal()  # needed because the unit uses the pc@address stage
        self.a_valid = Signal()  # needed because the unit uses the pc@address stage
        self.f_stall = Signal()
        self.f_valid = Signal()
        self.f_busy  = Signal()
        # to decode stage
        self.f_instruction = Signal(32)
        self.f_bus_error   = Signal()
        self.f_badaddr     = Signal(32)


class BasicFetchUnit(FetchUnitInterface, Elaboratable):
    def elaborate(self, platform):
        m = Module()

        rdata = Signal.like(self.iport.dat_r)

        # handle transaction logic
        with m.If(self.iport.cyc):
            with m.If(self.iport.ack | self.iport.err | ~self.f_valid):
                m.d.sync += [
                    self.iport.cyc.eq(0),
                    self.iport.stb.eq(0),
                    rdata.eq(self.iport.dat_r)
                ]
        with m.Elif(self.a_valid & ~self.a_stall):  # start transaction
            m.d.sync += [
                self.iport.addr.eq(self.a_pc),
                self.iport.cyc.eq(1),
                self.iport.stb.eq(1)
            ]
        m.d.comb += [
            self.iport.dat_w.eq(0),
            self.iport.sel.eq(0),
            self.iport.we.eq(0),
            self.iport.cti.eq(CycleType.CLASSIC),
            self.iport.bte.eq(0)
        ]

        # in case of error, make the instruction a NOP
        with m.If(self.f_bus_error):
            m.d.comb += self.f_instruction.eq(0x00000013)  # NOP
        with m.Else():
            m.d.comb += self.f_instruction.eq(rdata)

        # excepcion
        with m.If(self.iport.cyc & self.iport.err):
            m.d.sync += [
                self.f_bus_error.eq(1),
                self.f_badaddr.eq(self.iport.addr)
            ]
        with m.Elif(~self.f_stall):  # in case of error, but the pipe is stalled, do not lose the error
            m.d.sync += self.f_bus_error.eq(0)

        # busy flag
        m.d.comb += self.f_busy.eq(self.iport.cyc)

        return m


class CachedFetchUnit(FetchUnitInterface, Elaboratable):
    def __init__(self, configuration):
        super().__init__()

        self.f_pc  = Signal(32)
        self.flush = Signal()

        self.nlines     = configuration.getOption('icache', 'nlines')
        self.nwords     = configuration.getOption('icache', 'nwords')
        self.nways      = configuration.getOption('icache', 'nways')
        self.start_addr = configuration.getOption('icache', 'start_addr')
        self.end_addr   = configuration.getOption('icache', 'end_addr')

    def elaborate(self, platform):
        m = Module()

        icache  = m.submodules.icache  = Cache(nlines=self.nlines, nwords=self.nwords, nways=self.nways,
                                               start_addr=self.start_addr, end_addr=self.end_addr,
                                               enable_write=False)
        arbiter = m.submodules.arbiter = Arbiter()

        cache_port = arbiter.add_port(priority=0)
        bare_port  = arbiter.add_port(priority=1)

        a_use_cache = Signal()
        f_use_cache = Signal()

        bits_range = log2_int(self.end_addr - self.start_addr, need_pow2=False)
        m.d.comb += a_use_cache.eq((self.a_pc[bits_range:] == (self.start_addr >> bits_range)))

        with m.If(~self.a_stall):
            m.d.sync += f_use_cache.eq(a_use_cache)
        m.d.comb += arbiter.bus.connect(self.iport)

        # connect IO: cache
        m.d.comb += [
            icache.s1_address.eq(self.a_pc),
            icache.s1_flush.eq(self.flush),
            icache.s1_valid.eq(self.a_valid & a_use_cache),
            icache.s1_stall.eq(self.a_stall),
            icache.s2_address.eq(self.f_pc),
            icache.s2_evict.eq(0),
            icache.s2_valid.eq(self.f_valid & f_use_cache),
            icache.s2_re.eq(1)
        ]

        # connect cache to arbiter
        m.d.comb += [
            cache_port.addr.eq(icache.bus_addr),
            cache_port.dat_w.eq(0),
            cache_port.sel.eq(0),
            cache_port.we.eq(0),
            cache_port.cyc.eq(icache.bus_valid),
            cache_port.stb.eq(icache.bus_valid),
            cache_port.cti.eq(Mux(icache.bus_last, CycleType.END, CycleType.INCREMENT)),
            cache_port.bte.eq(log2_int(self.nwords) - 1),
            icache.bus_data.eq(cache_port.dat_r),
            icache.bus_ack.eq(cache_port.ack),
            icache.bus_err.eq(cache_port.err)
        ]

        # drive the bare bus IO
        rdata = Signal.like(bare_port.dat_r)
        with m.If(bare_port.cyc):
            with m.If(bare_port.ack | bare_port.err | ~self.f_valid):
                m.d.sync += [
                    bare_port.cyc.eq(0),
                    bare_port.stb.eq(0),
                    rdata.eq(bare_port.dat_r)
                ]
        with m.Elif(self.a_valid & ~self.a_stall & ~a_use_cache):
            m.d.sync += [
                bare_port.addr.eq(self.a_pc),
                bare_port.cyc.eq(1),
                bare_port.stb.eq(1)
            ]
        m.d.comb += [
            bare_port.dat_w.eq(0),
            bare_port.sel.eq(0),
            bare_port.we.eq(0),
            bare_port.cti.eq(CycleType.CLASSIC),
            bare_port.bte.eq(0)
        ]

        # in case of error, make the instruction a NOP
        with m.If(f_use_cache):
            m.d.comb += [
                self.f_instruction.eq(icache.s2_rdata),
                self.f_busy.eq(icache.s2_miss)
            ]
        with m.Elif(self.f_bus_error):
            m.d.comb += [
                self.f_instruction.eq(0x00000013),  # NOP
                self.f_busy.eq(0)
            ]
        with m.Else():
            m.d.comb += [
                self.f_instruction.eq(rdata),
                self.f_busy.eq(bare_port.cyc)
            ]

        # excepcion
        with m.If(self.iport.cyc & self.iport.err):
            m.d.sync += [
                self.f_bus_error.eq(1),
                self.f_badaddr.eq(self.iport.addr)
            ]
        with m.Elif(~self.f_stall):  # in case of error, but the pipe is stalled, do not lose the error
            m.d.sync += self.f_bus_error.eq(0)

        return m
