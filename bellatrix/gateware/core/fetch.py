from nmigen import Mux
from nmigen import Module
from nmigen import Signal
from nmigen import Elaboratable
from nmigen.utils import log2_int
from nmigen.build import Platform
from nmigen_soc.wishbone.bus import CycleType
from nmigen_soc.wishbone.bus import Interface
from bellatrix.gateware.core.cache import Cache


class BasicFetchUnit(Elaboratable):
    def __init__(self) -> None:
        self.iport          = Interface(addr_width=32, data_width=32, granularity=32, features=['err'], name='iport')
        self.f1_pc          = Signal(32)  # input
        self.f1_start       = Signal()    # input
        self.f2_kill        = Signal()    # input
        self.f2_busy        = Signal()    # output
        self.f2_instruction = Signal(32, reset=0x00000013)  # output
        self.f2_bus_error   = Signal()    # output

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        with m.FSM():
            with m.State('IDLE'):
                with m.If(self.f1_start):
                    m.d.sync += [
                        self.iport.adr.eq(self.f1_pc),
                        self.iport.cyc.eq(1),
                        self.iport.stb.eq(1),
                        self.f2_bus_error.eq(0),
                        self.f2_busy.eq(1)
                    ]
                    m.next = 'BUSY'
            with m.State('BUSY'):
                with m.If(self.iport.ack | self.iport.err | self.f2_kill):
                    m.d.sync += [
                        self.iport.cyc.eq(0),
                        self.iport.stb.eq(0),
                        self.f2_bus_error.eq(self.iport.err),
                        self.f2_busy.eq(0)
                    ]
                    m.next = 'IDLE'

                m.d.sync += self.f2_instruction.eq(0x00000013)  # default: NOP
                with m.If(self.iport.ack):
                    m.d.sync += self.f2_instruction.eq(self.iport.dat_r)

        return m


class CachedFetchUnit(Elaboratable):
    def __init__(self, **cache_kwargs: int) -> None:
        super().__init__()
        self.iport        = Interface(addr_width=32, data_width=32, granularity=32, features=['err', 'bte', 'cti'], name='iport')
        self.cache_kwargs = cache_kwargs
        self.start_addr   = cache_kwargs['start_addr']
        self.end_addr     = cache_kwargs['end_addr']
        self.nwords       = cache_kwargs['nwords']
        # IO
        self.f1_pc          = Signal(32)  # (in) PC for first state
        self.f2_pc          = Signal(32)  # (in) PC for second stage
        self.f2_valid       = Signal()    # (in) Data access is valid
        self.f2_stall       = Signal()    # (in) Pipeline is busy
        self.f2_kill        = Signal()    # (in) Kill all pending operations
        self.f2_flush       = Signal()    # (in) Nuke the cache
        self.f2_busy        = Signal()    # (out) The access is pending
        self.f2_instruction = Signal(32, reset=0x00000013)  # (out) Instruction, ofc
        self.f2_bus_error   = Signal()    # (out) Bus error

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        # TODO: Missing handling uncached regions...
        icache = m.submodules.icache  = Cache(**self.cache_kwargs)

        # connect IO: cache
        m.d.comb += [
            icache.s1_address.eq(self.f1_pc),
            icache.s1_flush.eq(self.f2_flush),
            icache.s2_address.eq(self.f2_pc),
            icache.s2_valid.eq(self.f2_valid),
            icache.s2_stall.eq(self.f2_stall),
            icache.s2_kill.eq(self.f2_kill)
        ]
        # connect cache to instruction port
        m.d.comb += [
            self.iport.adr.eq(icache.bus_addr),
            self.iport.dat_w.eq(0),
            self.iport.sel.eq(0),
            self.iport.we.eq(0),
            self.iport.cyc.eq(icache.bus_valid),
            self.iport.stb.eq(icache.bus_valid),
            self.iport.cti.eq(Mux(icache.bus_last, CycleType.END_OF_BURST, CycleType.INCR_BURST)),
            self.iport.bte.eq(log2_int(self.nwords) - 1),  # (2^(N+1))-beat wrap busrt. View page 70 of WB spec
            icache.bus_data.eq(self.iport.dat_r),
            icache.bus_ack.eq(self.iport.ack),
            icache.bus_err.eq(self.iport.err)
        ]
        m.d.comb += [
            self.f2_instruction.eq(icache.s2_rdata),
            self.f2_busy.eq(icache.s2_miss)
        ]
        # log bus error
        with m.If(self.iport.cyc & self.iport.err):
            m.d.sync += self.f2_bus_error.eq(1)
        with m.Elif(~self.f2_stall):
            # No stall -> reset error
            m.d.sync += self.f2_bus_error.eq(0)

        return m
