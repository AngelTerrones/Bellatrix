from nmigen import Signal
from nmigen import Module
from nmigen import Elaboratable
from nmigen.build import Platform
from bellatrix.isa import Funct3


class LogicUnit(Elaboratable):
    def __init__(self) -> None:
        self.op     = Signal(Funct3)  # Input
        self.dat1   = Signal(32)  # Input
        self.dat2   = Signal(32)  # Input
        self.result = Signal(32)  # Output

    def elaborate(self, platform: Platform) -> Module:
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
