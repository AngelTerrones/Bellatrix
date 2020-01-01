from nmigen import Cat
from nmigen import Repl
from nmigen import Mux
from nmigen import Module
from nmigen import Signal
from nmigen import Elaboratable
from nmigen import signed
from nmigen.build import Platform
from .isa import Funct3


class Multiplier(Elaboratable):
    def __init__(self) -> None:
        self.op     = Signal(3)   # input
        self.dat1   = Signal(32)  # input
        self.dat2   = Signal(32)  # input
        self.valid  = Signal()    # input
        self.result = Signal(32)  # output
        self.ready  = Signal()    # output

    def elaborate(self, platform: Platform) -> Module:
        m           = Module()

        a           = Signal(signed(33))
        b           = Signal(signed(33))
        result_ll   = Signal(32)
        result_lh   = Signal(33)
        result_hl   = Signal(33)
        result_hh   = Signal(33)
        result_3    = Signal(64)
        result_4    = Signal(64)
        active      = Signal(5)
        is_signed   = Signal()
        a_is_signed = Signal()
        b_is_signed = Signal()
        low         = Signal()

        m.d.sync += [
            is_signed.eq(a_is_signed ^ b_is_signed),
            active.eq(Cat(self.valid & (active == 0), active)),
            low.eq(self.op == Funct3.MUL)
        ]
        # ----------------------------------------------------------------------
        # fist state
        m.d.comb += [
            a_is_signed.eq(((self.op == Funct3.MULH) | (self.op == Funct3.MULHSU)) & self.dat1[-1]),
            b_is_signed.eq((self.op == Funct3.MULH) & self.dat2[-1])
        ]
        m.d.sync += [
            a.eq(Mux(a_is_signed, -Cat(self.dat1, 1), self.dat1)),
            b.eq(Mux(b_is_signed, -Cat(self.dat2, 1), self.dat2)),
        ]
        # ----------------------------------------------------------------------
        # second state
        m.d.sync += [
            result_ll.eq(a[0:16] * b[0:16]),
            result_lh.eq(a[0:16] * b[16:33]),
            result_hl.eq(a[16:33] * b[0:16]),
            result_hh.eq(a[16:33] * b[16:33])
        ]
        # ----------------------------------------------------------------------
        # third state
        m.d.sync += [
            result_3.eq(Cat(result_ll, result_hh) + Cat(Repl(0, 16), (result_lh + result_hl)))
        ]
        # ----------------------------------------------------------------------
        # fourth state
        m.d.sync += [
            result_4.eq(Mux(is_signed, -result_3, result_3)),
            self.result.eq(Mux(low, result_4[:32], result_4[32:64]))
        ]
        m.d.comb += self.ready.eq(active[-1])

        return m
