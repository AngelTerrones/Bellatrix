from nmigen import Module
from nmigen import Signal
from nmigen import Elaboratable
from .isa import Funct3


class CompareUnit(Elaboratable):
    def __init__(self):
        self.op       = Signal(3)
        self.zero     = Signal()
        self.negative = Signal()
        self.overflow = Signal()
        self.carry    = Signal()
        self.cmp_ok   = Signal()

    def elaborate(self, platform):
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
            with m.Default():
                m.d.comb += self.cmp_ok.eq(0)

        return m
