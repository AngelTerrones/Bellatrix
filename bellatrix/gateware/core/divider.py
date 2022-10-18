from amaranth import Mux
from amaranth import Module
from amaranth import Signal
from amaranth import Elaboratable
from amaranth.build import Platform
from bellatrix.gateware.core.isa import Funct3


class Divider(Elaboratable):
    def __init__(self) -> None:
        self.op     = Signal(Funct3)   # input
        self.dat1   = Signal(32)  # input
        self.dat2   = Signal(32)  # input
        self.stall  = Signal()    # input
        self.start  = Signal()    # input
        self.result = Signal(32)  # output
        self.busy   = Signal()    # output

    def elaborate(self, platform: Platform) -> Module:
        m             = Module()

        is_div        = Signal()
        is_div_q      = Signal()
        is_divu       = Signal()
        is_divu_q     = Signal()
        is_rem        = Signal()
        dividend      = Signal(32)
        divisor       = Signal(63)
        quotient      = Signal(32)
        quotient_mask = Signal(32)
        start         = Signal()
        outsign       = Signal()

        m.d.comb += [
            is_div.eq(self.op == Funct3.DIV),
            is_divu.eq(self.op == Funct3.DIVU),
            is_rem.eq(self.op == Funct3.REM)
        ]

        m.d.comb += start.eq(self.start & ~self.busy)

        with m.If(start):
            m.d.sync += [
                dividend.eq(Mux((is_div | is_rem) & self.dat1[-1], -self.dat1, self.dat1)),
                divisor.eq(Mux((is_div | is_rem) & self.dat2[-1], -self.dat2, self.dat2) << 31),
                outsign.eq((is_div & (self.dat1[-1] ^ self.dat2[-1]) & (self.dat2 != 0)) | (is_rem & self.dat1[-1])),
                quotient.eq(0),
                quotient_mask.eq(1 << 31),
                self.busy.eq(1),

                is_div_q.eq(is_div),
                is_divu_q.eq(is_divu)
            ]
        with m.Elif(quotient_mask == 0 & self.busy):
            m.d.sync += [
                self.busy.eq(0),
                is_div_q.eq(0),
                is_divu_q.eq(0)
            ]

            with m.If(is_div_q | is_divu_q):
                m.d.sync += self.result.eq(Mux(outsign, -quotient, quotient))
            with m.Else():
                m.d.sync += self.result.eq(Mux(outsign, -dividend, dividend))
        with m.Else():
            with m.If(divisor <= dividend):
                m.d.sync += [
                    dividend.eq(dividend - divisor),
                    quotient.eq(quotient | quotient_mask)
                ]
            m.d.sync += [
                divisor.eq(divisor >> 1),
                quotient_mask.eq(quotient_mask >> 1)
            ]

        return m
