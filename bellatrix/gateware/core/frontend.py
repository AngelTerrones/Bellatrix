from nmigen import Module
from nmigen import Signal
from nmigen import Elaboratable
from nmigen.build import Platform
from nmigen.hdl.rec import DIR_FANOUT
from bellatrix.gateware.core.fetch import BasicFetchUnit
from bellatrix.gateware.core.fetch import CachedFetchUnit
from bellatrix.gateware.core.predictor import BranchPredictor
from bellatrix.gateware.core.stage import _Endpoint
from bellatrix.gateware.core.layout import _fd_layout
from nmigen_soc.wishbone.bus import Interface


class Frontend(Elaboratable):
    def __init__(self, **frontend_kwargs) -> None:
        # ----------------------------------------------------------------------
        self.reset_address    = frontend_kwargs['reset_address']
        self.predictor_enable = frontend_kwargs['predictor_enable']
        self.predictor_size   = frontend_kwargs['predictor_size']
        self.icache_enable    = frontend_kwargs['icache_enable']
        self.icache_kwargs    = frontend_kwargs['icache_kwargs']
        i_features = ['err']
        if self.icache_enable:
            i_features.extend(['cti', 'bte'])
        # ----------------------------------------------------------------------
        self.iport          = Interface(addr_width=32, data_width=32, granularity=32, features=i_features, name='iport')
        self.endpoint       = _Endpoint(_fd_layout, DIR_FANOUT, name='fe')
        self.mtvec          = Signal(32)  # (in) next PC after exception
        self.mepc           = Signal(32)  # (in) next PC after MRET
        self.jb_pc          = Signal(32)  # (in) next PC after a jump or branch
        self.fence_pc       = Signal(32)  # (in) next PC after a fence_i
        self.exception      = Signal()    # (in) enter exception
        self.mret           = Signal()    # (in) return from exception
        self.take_jb        = Signal()    # (in) take jump
        self.fence_i        = Signal()    # (in) Fence.i instruction
        self.kill           = Signal()    # (in) Kill signal from the pipeline
        self.fe_instruction = Signal(32)  # (out) instruction from fetch. For the Reg file
        if self.predictor_enable:
            self.p_bad_predict_jump    = Signal()    # (in) Bad jump prediction
            self.p_bad_predict_nojump  = Signal()    # (in) Bad no-jump prediction
            self.p_no_jump_next_pc     = Signal(32)  # (in) next PC after a branch no taken
            self.p_prediction_pc       = Signal(32)  # (in) PC of the jump/branch instruction, from pipeline
            self.p_prediction_target   = Signal(32)  # (in) PC target of the jump/branch, from pipeline
            self.p_prediction_state    = Signal(2)   # (in) Prediction state from the pipeline
            self.p_predictor_update    = Signal()    # (in) Update tables in the predictor
        if self.icache_enable:
            self.p_flush = Signal()  # (in) clear cache

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        # ----------------------------------------------------------------------
        # Units
        if self.icache_enable:
            fetch = m.submodules.fetch = CachedFetchUnit(**self.icache_kwargs)
        else:
            fetch = m.submodules.fetch = BasicFetchUnit()
        if self.predictor_enable:
            predictor = m.submodules.predictor = BranchPredictor(self.predictor_size)

        # ----------------------------------------------------------------------
        # pipeline registers
        # Stage 0: Mux the new PC
        # Stage 1: New PC latched. Ready to start fetch
        # Stage 2: Doing the fetch, latching the instruction.
        f01_pc = Signal(32, reset=self.reset_address)  # from 0 -> 1
        f12_pc = Signal(32)                            # from 1 -> 2

        # ----------------------------------------------------------------------
        # F0 stage
        nxt_pc = Signal(32)

        # select the next pc
        # Priority is [m > x > f]
        with m.If(self.exception):
            m.d.comb += nxt_pc.eq(self.mtvec)
        with m.Elif(self.mret):
            m.d.comb += nxt_pc.eq(self.mepc)
        # ****************************************
        if self.predictor_enable:
            with m.Elif(self.p_bad_predict_jump):
                m.d.comb += nxt_pc.eq(self.p_no_jump_next_pc)  # branch not taken
            with m.Elif(self.p_bad_predict_nojump):
                m.d.comb += nxt_pc.eq(self.jb_pc)  # branck taken
        else:
            with m.Elif(self.take_jb):
                m.d.comb += nxt_pc.eq(self.jb_pc)  # jmp/branch
        # ****************************************
        with m.Elif(self.fence_i):
            m.d.comb += nxt_pc.eq(self.fence_pc)  # fence_i.
        # ****************************************
        if self.predictor_enable:
            with m.Elif(predictor.f_prediction):
                m.d.comb += nxt_pc.eq(predictor.f_prediction_pc)  # prediction
        # ****************************************
        with m.Else():
            m.d.comb += nxt_pc.eq(f01_pc + 4)  # next pc

        # --------------------------------------------- -------------------------
        # F1 stage
        frontend_stall = self.endpoint.stall | fetch.f2_busy
        f1_valid       = ~predictor.f_prediction if self.predictor_enable else 1
        fetch_start    = ~(self.endpoint.stall | self.kill | predictor.f_prediction) if self.predictor_enable else ~(self.endpoint.stall | self.kill)

        m.d.comb += fetch.iport.connect(self.iport)
        m.d.comb += [
            fetch.f1_pc.eq(f01_pc),
            fetch.f2_kill.eq(self.kill)
        ]
        if not self.icache_enable:
            m.d.comb += fetch.f1_start.eq(fetch_start)
        if self.predictor_enable:
            m.d.comb += [
                predictor.f_pc.eq(f01_pc),
                predictor.f_stall.eq(frontend_stall),
            ]

        # ----------------------------------------------------------------------
        # F2 stage
        valid_f2 = Signal()
        with m.If(self.kill):
            m.d.sync += valid_f2.eq(0)
        with m.Elif(~frontend_stall):
            m.d.sync += valid_f2.eq(f1_valid)

        m.d.comb += self.fe_instruction.eq(fetch.f2_instruction)
        if self.predictor_enable:
            m.d.comb += [
                    predictor.f2_pc.eq(f12_pc),
                    predictor.m_prediction_state.eq(self.p_prediction_state),
                    predictor.m_take_jmp_branch.eq(self.take_jb),
                    predictor.m_pc.eq(self.p_prediction_pc),
                    predictor.m_target_pc.eq(self.p_prediction_target),
                    predictor.m_update.eq(self.p_predictor_update)
                ]
        if self.icache_enable:
            m.d.comb += [
                fetch.f2_pc.eq(f12_pc),
                fetch.f2_valid.eq(valid_f2),
                fetch.f2_stall.eq(self.endpoint.stall),
                fetch.f2_flush.eq(self.p_flush | self.fence_i)
            ]

        # ----------------------------------------------------------------------
        # Pipeline logic
        with m.If(~frontend_stall | self.kill):
            m.d.sync += [
                f01_pc.eq(nxt_pc),
                f12_pc.eq(f01_pc)
            ]
        # F2 -> pipeline (out)
        with m.If(~self.endpoint.stall):
            m.d.sync += [
                self.endpoint.pc.eq(f12_pc),
                self.endpoint.instruction.eq(fetch.f2_instruction),
                self.endpoint.fetch_error.eq(fetch.f2_bus_error)
            ]
            if self.predictor_enable:
                m.d.sync += [
                    self.endpoint.prediction.eq(predictor.f_prediction),
                    self.endpoint.prediction_state.eq(predictor.f_prediction_state),
                ]

        valid_out = valid_f2 & ~fetch.f2_busy
        with m.If(self.kill):
            m.d.sync += [
                self.endpoint.valid.eq(0),
                self.endpoint.retire.eq(0)
            ]
        with m.Elif(~self.endpoint.stall):
            m.d.sync += [
                self.endpoint.valid.eq(valid_out),
                self.endpoint.retire.eq(valid_out)
            ]

        return m