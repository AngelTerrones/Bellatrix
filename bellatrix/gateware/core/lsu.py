from amaranth import Cat
from amaranth import Mux
from amaranth import Repl
from amaranth import Module
from amaranth import Record
from amaranth import Signal
from amaranth import Elaboratable
from amaranth.utils import log2_int
from amaranth.build import Platform
from amaranth.lib.fifo import SyncFIFOBuffered
from amaranth_soc.wishbone.bus import CycleType
from amaranth_soc.wishbone.bus import Interface
from bellatrix.gateware.core.isa import Funct3
from bellatrix.gateware.core.cache import Cache
from bellatrix.gateware.core.wishbone import Arbiter


class DataFormat(Elaboratable):
    def __init__(self) -> None:
        self.x_funct3     = Signal(Funct3)   # input
        self.x_offset     = Signal(2)        # input
        self.x_store_data = Signal(32)       # input  (raw data to store)
        self.x_byte_sel   = Signal(4)        # output
        self.x_data_w     = Signal(32)       # output (formatted data to bus)
        self.x_misaligned = Signal()         # output
        self.m_offset     = Signal(2)        # input
        self.m_data_r     = Signal(32)       # input  (raw data from load)
        self.m_funct3     = Signal(Funct3)   # input
        self.m_load_data  = Signal(32)       # output (formatted data to pipeline)

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
                with m.If((self.x_load | self.x_store) & self.x_enable):
                    m.d.sync += [
                        self.dport.adr.eq(self.x_addr),
                        self.dport.dat_w.eq(self.x_data_w),
                        self.dport.sel.eq(self.x_byte_sel),
                        self.dport.we.eq(self.x_store),
                        self.dport.cyc.eq(1),
                        self.dport.stb.eq(1),
                        self.m_busy.eq(1)
                    ]
                    m.next = 'BUSY'
            with m.State('BUSY'):
                m.d.sync += [
                    self.m_load_error.eq(~self.dport.we & self.dport.err),
                    self.m_store_error.eq(self.dport.we & self.dport.err),
                    self.m_badaddr.eq(self.dport.adr)
                ]
                with m.If(self.dport.ack | self.dport.err):
                    m.d.sync += [
                        self.m_load_data.eq(self.dport.dat_r),
                        self.dport.we.eq(0),
                        self.dport.cyc.eq(0),
                        self.dport.stb.eq(0),
                        self.m_busy.eq(0)
                    ]
                    m.next = 'IDLE'

        return m
