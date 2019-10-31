from nmigen import Cat
from nmigen import Module
from nmigen import Signal
from nmigen import Elaboratable


class AdderUnit(Elaboratable):
    def __init__(self):
        # inputs
        self.sub  = Signal()
        self.dat1 = Signal(32)
        self.dat2 = Signal(32)
        # outputs
        self.result   = Signal(32)
        self.carry    = Signal()
        self.overflow = Signal()

    def elaborate(self, platform):
        m = Module()
        # http://teaching.idallen.com/cst8214/08w/notes/overflow.txt
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
