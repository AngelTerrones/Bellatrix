from nmigen import Mux
from nmigen import Module
from nmigen import Signal
from nmigen import Elaboratable
from nmigen.utils import log2_int
from nmigen.build import Platform
from nmigen_soc.wishbone.bus import CycleType
from nmigen_soc.wishbone.bus import Interface
from bellatrix.gateware.core.cache import Cache


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
        self.f_prediction  = Signal()


class BasicFetchUnit(FetchUnitInterface, Elaboratable):
    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        with m.FSM():
            with m.State('IDLE'):
                with m.If(self.f_kill | ~self.d_stall):
                    # If D is not stalled, return a nop the next cycle
                    # because I don't have a valid instruction
                    m.d.sync += self.f_instruction.eq(0x00000013)
                with m.If(~(self.d_stall | self.f_kill | self.f_prediction)):  # !d_stall & !f_kill
                    m.d.sync += [
                        self.f2_pc.eq(self.f_pc),
                        self.iport.adr.eq(self.f_pc),
                        self.iport.cyc.eq(1),
                        self.iport.stb.eq(1),

                        self.f_bus_error.eq(0),
                        self.f_busy.eq(1)
                    ]
                    m.next = 'BUSY'
            with m.State('BUSY'):
                with m.If(self.iport.ack | self.iport.err | self.f_kill):
                    m.d.sync += [
                        self.iport.cyc.eq(0),
                        self.iport.stb.eq(0),
                        self.f_instruction.eq(self.iport.dat_r),

                        self.f_bus_error.eq(self.iport.err),
                        self.f_busy.eq(0)
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

        f2_valid = Signal()
        f2_pc    = Signal(32)  # to reduce the timing

        icache  = m.submodules.icache  = Cache(enable_write=False, **self.cache_kwargs)

        # pipeline
        with m.If(self.f_kill | ~(self.d_stall | self.f_busy)):  # !d_stall & !f_busy
            m.d.sync += [
                self.f2_pc.eq(self.f_pc),
                f2_pc.eq(self.f_pc)
            ]

        with m.If(self.f_kill):
            m.d.sync += f2_valid.eq(0)
        with m.Elif(~(self.d_stall | self.f_busy)):  # !d_stall & !f_busy
            m.d.sync += f2_valid.eq(~self.f_prediction)

        # connect IO: cache
        m.d.comb += [
            icache.s1_address.eq(self.f_pc),
            icache.s1_flush.eq(self.flush),
            icache.s2_address.eq(self.f2_pc),
            icache.s2_address2.eq(f2_pc),
            icache.s2_valid.eq(f2_valid),
            icache.s2_stall.eq(self.d_stall),
            icache.s2_kill.eq(self.f_kill)
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
            self.iport.bte.eq(log2_int(self.nwords) - 1),
            icache.bus_data.eq(self.iport.dat_r),
            icache.bus_ack.eq(self.iport.ack),
            icache.bus_err.eq(self.iport.err)
        ]

        # in case of error, make the instruction a NOP
        with m.If(self.f_kill | self.f_bus_error):
            m.d.comb += self.f_instruction.eq(0x00000013),  # NOP
        with m.Elif(f2_valid):
            m.d.comb += [
                self.f_instruction.eq(icache.s2_rdata),
                self.f_busy.eq(icache.s2_miss)
            ]

        # excepcion
        with m.If(self.iport.cyc & self.iport.err):
            m.d.sync += self.f_bus_error.eq(1)
        with m.Elif(~self.d_stall):
            # No stall -> reset error
            m.d.sync += self.f_bus_error.eq(0)

        return m
