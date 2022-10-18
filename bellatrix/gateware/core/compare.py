from amaranth import Module
from amaranth import Signal
from amaranth import Elaboratable
from amaranth.build import Platform
from bellatrix.gateware.core.isa import Funct3


class CompareUnit(Elaboratable):
    def __init__(self) -> None:
        self.op       = Signal(Funct3)  # Input
        self.zero     = Signal()   # Input
        self.negative = Signal()   # Input
        self.overflow = Signal()   # Input
        self.carry    = Signal()   # Input
        self.cmp_ok   = Signal()   # Output

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        with m.Switch(self.op):
            with m.Case(Funct3.BEQ):
                m.d.comb += self.cmp_ok.eq(self.zero)
            with m.Case(Funct3.BNE):
                m.d.comb += self.cmp_ok.eq(~self.zero)
            with m.Case(Funct3.BLT, Funct3.SLT):
                m.d.comb += self.cmp_ok.eq(~self.zero & (self.negative != self.overflow))
            with m.Case(Funct3.BLTU, Funct3.SLTU):
                m.d.comb += self.cmp_ok.eq(~self.zero & self.carry)
            with m.Case(Funct3.BGE):
                m.d.comb += self.cmp_ok.eq(self.negative == self.overflow)
            with m.Case(Funct3.BGEU):
                m.d.comb += self.cmp_ok.eq(~self.carry)

        return m
