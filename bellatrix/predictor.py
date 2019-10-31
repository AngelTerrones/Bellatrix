from nmigen import Cat
from nmigen import Mux
from nmigen import Signal
from nmigen import Module
from nmigen import Memory
from nmigen import Record
from nmigen import Elaboratable
from nmigen.utils import log2_int


class BranchPredictor(Elaboratable):
    def __init__(self, configuration):
        self.configuration = configuration

        self.a_pc               = Signal(32)
        self.a_stall            = Signal()
        self.f_pc               = Signal(32)
        self.f_prediction       = Signal()
        self.f_prediction_state = Signal(2)
        self.f_prediction_pc    = Signal(32)
        self.m_prediction_state = Signal(2)
        self.m_take_jmp_branch  = Signal()
        self.m_pc               = Signal(32)
        self.m_target_pc        = Signal(32)
        self.m_update           = Signal()

    def elaborate(self, platform):
        m = Module()
        size = self.configuration.getOption('predictor', 'size')
        if size == 0 or (size & (size - 1)):
            raise ValueError(f'size must be a power of 2: {size}')

        _bits_index = log2_int(size)
        _bits_tag   = 32 - _bits_index
        _btb_width  = 32 + _bits_tag  # data + tag
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
        valid = Signal(_btb_depth)

        btb    = Memory(width=_btb_width, depth=_btb_depth)
        btb_rp = btb.read_port()
        btb_wp = btb.write_port()

        bht = Memory(width=2, depth=_btb_depth)
        bht_rp = bht.read_port()
        bht_wp = bht.write_port()

        m.submodules += btb_rp, btb_wp
        m.submodules += bht_rp, bht_wp

        btb_r       = Record(_btb_layout)
        a_pc        = Record(_pc_layout)
        f_pc        = Record(_pc_layout)
        m_pc        = Record(_pc_layout)
        hit         = Signal()
        pstate_next = Signal(2)
        bit_valid   = Signal()

        # prediction
        m.d.sync += bit_valid.eq(valid.bit_select(Mux(self.a_stall, f_pc.index, a_pc.index), 1))

        m.d.comb += [
            btb_rp.addr.eq(Mux(self.a_stall, f_pc.index, a_pc.index)),
            bht_rp.addr.eq(Mux(self.a_stall, f_pc.index, a_pc.index)),
            btb_r.eq(btb_rp.data),
            #
            a_pc.eq(self.a_pc),
            f_pc.eq(self.f_pc),
            hit.eq(btb_r.valid & (btb_r.tag == f_pc.tag)),
            #
            self.f_prediction.eq(hit & bht_rp.data[1]),
            self.f_prediction_state.eq(bht_rp.data),
            self.f_prediction_pc.eq(btb_r.target)
        ]

        # update
        m.d.comb += [
            valid.bit_select(m_pc.index, 1).eq(1),
            btb_wp.addr.eq(m_pc.index),
            btb_wp.data.eq(Cat(self.m_target_pc, m_pc.tag, 1)),
            btb_wp.en.eq(self.m_update),

            bht_wp.addr.eq(m_pc.index),
            bht_wp.data.eq(pstate_next),
            bht_wp.en.eq(self.m_update),

            m_pc.eq(self.m_pc),

            pstate_next.eq(0)
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
