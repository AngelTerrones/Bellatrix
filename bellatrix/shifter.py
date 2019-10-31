from nmigen import Mux
from nmigen import Cat
from nmigen import Repl
from nmigen import Signal
from nmigen import Module
from nmigen import Elaboratable


class ShifterUnit(Elaboratable):
    def __init__(self):
        # inputs
        self.direction = Signal()   # 1: right. 0: left
        self.sign_ext  = Signal()
        self.shamt     = Signal(5)
        self.dat       = Signal(32)
        self.stall     = Signal()
        # outputs
        self.result = Signal(32)

    def elaborate(self, platform):
        m = Module()

        sign_fill   = Signal()
        operand     = Signal(32)
        r_direction = Signal()
        r_result    = Signal(32)

        shdata      = Signal(64)  # temp data

        # pre-invert the value, if needed
        m.d.comb += [
            operand.eq(Mux(self.direction, self.dat, self.dat[::-1])),
            sign_fill.eq(Mux(self.direction & self.sign_ext, self.dat[-1], 0)),

            shdata.eq(Cat(operand, Repl(sign_fill, 32)))
        ]

        with m.If(~self.stall):
            m.d.sync += [
                r_direction.eq(self.direction),
                r_result.eq(shdata >> self.shamt)
            ]

        m.d.comb += self.result.eq(Mux(r_direction, r_result, r_result[::-1]))
        return m
