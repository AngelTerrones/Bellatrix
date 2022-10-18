from amaranth import Mux
from amaranth import Cat
from amaranth import Repl
from amaranth import Signal
from amaranth import Module
from amaranth import Elaboratable
from amaranth.build import Platform


class ShifterUnit(Elaboratable):
    def __init__(self) -> None:
        self.direction = Signal()    # Input
        self.sign_ext  = Signal()    # Input
        self.shamt     = Signal(5)   # Input
        self.dat       = Signal(32)  # Input
        self.stall     = Signal()    # Input
        self.result    = Signal(32)  # Output

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        sign_fill   = Signal()
        operand     = Signal(32)
        r_direction = Signal()
        r_result    = Signal(32)

        shdata      = Signal(64)  # temp data

        # pre-invert the value, if needed
        # Direction:  1 = right. 0 = left.
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
