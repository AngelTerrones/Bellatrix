from nmigen import Signal
from nmigen import Module
from nmigen import Elaboratable
from .isa import Funct3


class LogicUnit(Elaboratable):
    def __init__(self):
        # inputs
        self.op   = Signal(3)
        self.dat1 = Signal(32)
        self.dat2 = Signal(32)
        # outputs
        self.result = Signal(32)

    def elaborate(self, platform):
        m = Module()

        with m.Switch(self.op):
            with m.Case(Funct3.XOR):
                m.d.comb += self.result.eq(self.dat1 ^ self.dat2)
            with m.Case(Funct3.OR):
                m.d.comb += self.result.eq(self.dat1 | self.dat2)
            with m.Case(Funct3.AND):
                m.d.comb += self.result.eq(self.dat1 & self.dat2)
            with m.Default():
                m.d.comb += self.result.eq(0)

        return m
