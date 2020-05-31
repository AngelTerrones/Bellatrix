from nmigen import Cat
from nmigen import Signal
from nmigen import Module
from nmigen import Memory
from nmigen import Record
from nmigen import Elaboratable
from nmigen.utils import log2_int
from nmigen.build import Platform


class BranchPredictor(Elaboratable):
    def __init__(self, predictor_size: int) -> None:
        # ----------------------------------------------------------------------
        self.predictor_size   = predictor_size

        self.f_pc               = Signal(32)  # input
        self.f_stall            = Signal()    # input
        self.f2_pc              = Signal(32)  # input
        self.f_prediction       = Signal()    # output
        self.f_prediction_state = Signal(2)   # output
        self.f_prediction_pc    = Signal(32)  # output
        self.m_prediction_state = Signal(2)   # input
        self.m_take_jmp_branch  = Signal()    # input
        self.m_pc               = Signal(32)  # input
        self.m_target_pc        = Signal(32)  # input
        self.m_update           = Signal()    # input

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        if self.predictor_size == 0 or (self.predictor_size & (self.predictor_size - 1)):
            raise ValueError(f'size must be a power of 2: {self.predictor_size}')

        _bits_index = log2_int(self.predictor_size)
        _bits_tag   = 32 - _bits_index
        _btb_width  = 1 + 32 + _bits_tag  # valid + data + tag
        _btb_depth  = 1 << _bits_index

        _btb_layout = [
            ('target', 32),
            ('tag', _bits_tag),
            ('valid', 1)
        ]

        _pc_layout = [
            ('index', _bits_index),
            ('tag', _bits_tag)
        ]

        btb    = Memory(width=_btb_width, depth=_btb_depth)
        btb_rp = btb.read_port(transparent=False)
        btb_wp = btb.write_port()

        bht = Memory(width=2, depth=_btb_depth)
        bht_rp = bht.read_port(transparent=False)
        bht_wp = bht.write_port()

        m.submodules += btb_rp, btb_wp
        m.submodules += bht_rp, bht_wp

        btb_r       = Record(_btb_layout)
        f_pc        = Record(_pc_layout)
        f2_pc       = Record(_pc_layout)
        m_pc        = Record(_pc_layout)
        hit         = Signal()
        pstate_next = Signal(2)

        m.d.comb += [
            btb_rp.addr.eq(f_pc.index),
            btb_rp.en.eq(~self.f_stall),
            bht_rp.addr.eq(f_pc.index),
            bht_rp.en.eq(~self.f_stall),
            btb_r.eq(btb_rp.data),
            #
            f_pc.eq(self.f_pc),
            f2_pc.eq(self.f2_pc),
            hit.eq(btb_r.valid & (btb_r.tag == f2_pc.tag))
        ]
        m.d.comb += [
            self.f_prediction.eq(hit & bht_rp.data[1]),
            self.f_prediction_state.eq(bht_rp.data),
            self.f_prediction_pc.eq(btb_r.target)
        ]

        # update the predictor
        m.d.comb += [
            btb_wp.addr.eq(m_pc.index),
            btb_wp.data.eq(Cat(self.m_target_pc, m_pc.tag, 1)),
            btb_wp.en.eq(self.m_update),

            bht_wp.addr.eq(m_pc.index),
            bht_wp.data.eq(pstate_next),
            bht_wp.en.eq(self.m_update),

            m_pc.eq(self.m_pc)
        ]
        with m.Switch(Cat(self.m_prediction_state, self.m_take_jmp_branch)):
            with m.Case(0b000, 0b001):
                m.d.comb += pstate_next.eq(0b00)
            with m.Case(0b010, 0b100):
                m.d.comb += pstate_next.eq(0b01)
            with m.Case(0b011, 0b101):
                m.d.comb += pstate_next.eq(0b10)
            with m.Case(0b110, 0b111):
                m.d.comb += pstate_next.eq(0b11)

        return m
