from nmigen import Cat
from nmigen import Module
from nmigen import Signal
from nmigen import Elaboratable
from nmigen.build import Platform


class AdderUnit(Elaboratable):
    def __init__(self) -> None:
        self.sub      = Signal()    # input
        self.dat1     = Signal(32)  # input
        self.dat2     = Signal(32)  # input
        self.result   = Signal(32)  # output
        self.carry    = Signal()    # output
        self.overflow = Signal()    # output

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        # From: http://teaching.idallen.com/cst8214/08w/notes/overflow.txt
        with m.If(self.sub):
            m.d.comb += [
                Cat(self.result, self.carry).eq(self.dat1 - self.dat2),
                self.overflow.eq((self.dat1[-1] != self.dat2[-1]) & (self.dat2[-1] == self.result[-1]))
            ]
        with m.Else():
            m.d.comb += [
                Cat(self.result, self.carry).eq(self.dat1 + self.dat2),
                self.overflow.eq((self.dat1[-1] == self.dat2[-1]) & (self.dat2[-1] != self.result[-1]))
            ]

        return m
