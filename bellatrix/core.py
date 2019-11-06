from nmigen import Mux
from nmigen import Signal
from nmigen import Module
from nmigen import Record
from nmigen import Memory
from nmigen import Elaboratable
from .csr import CSRFile
from .stage import Stage
from .adder import AdderUnit
from .logic import LogicUnit
from .compare import CompareUnit
from .shifter import ShifterUnit
from .fetch import BasicFetchUnit
from .fetch import CachedFetchUnit
from .lsu import BasicLSU
from .lsu import DataFormat
from .lsu import CachedLSU
from .layout import _af_layout
from .layout import _fd_layout
from .layout import _dx_layout
from .layout import _xm_layout
from .layout import _mw_layout
from .exception import ExceptionUnit
from .wishbone import wishbone_layout
from .decoder import DecoderUnit
from .multiplier import Multiplier
from .divider import Divider
from .predictor import BranchPredictor
from .configuration import configuration as cfg


class Bellatrix(Elaboratable):
    def __init__(self, configuration):
        if not isinstance(configuration, cfg.Configuration):
            raise TypeError('Invalid data type for configuration. Must be a "Configuration" type')

        self.configuration      = configuration
        self.iport              = Record(wishbone_layout)
        self.dport              = Record(wishbone_layout)
        self.external_interrupt = Signal()
        self.timer_interrupt    = Signal()
        self.software_interrupt = Signal()

    def elaborate(self, platform):
        cpu = Module()
        # ----------------------------------------------------------------------
        # create the pipeline stages
        a = cpu.submodules.a = Stage(None,       _af_layout)
        f = cpu.submodules.f = Stage(_af_layout, _fd_layout)
        d = cpu.submodules.d = Stage(_fd_layout, _dx_layout)
        x = cpu.submodules.x = Stage(_dx_layout, _xm_layout)
        m = cpu.submodules.m = Stage(_xm_layout, _mw_layout)
        w = cpu.submodules.w = Stage(_mw_layout, None)
        # ----------------------------------------------------------------------
        # connect the stages
        cpu.d.comb += [
            a.endpoint_b.connect(f.endpoint_a),
            f.endpoint_b.connect(d.endpoint_a),
            d.endpoint_b.connect(x.endpoint_a),
            x.endpoint_b.connect(m.endpoint_a),
            m.endpoint_b.connect(w.endpoint_a)
        ]
        # ----------------------------------------------------------------------
        # units
        adder     = cpu.submodules.adder     = AdderUnit()
        logic     = cpu.submodules.logic     = LogicUnit()
        shifter   = cpu.submodules.shifter   = ShifterUnit()
        compare   = cpu.submodules.compare   = CompareUnit()
        decoder   = cpu.submodules.decoder   = DecoderUnit(self.configuration)
        exception = cpu.submodules.exception = ExceptionUnit(self.configuration)
        data_sel  = cpu.submodules.data_sel  = DataFormat()
        csr       = cpu.submodules.csr       = CSRFile()
        if (self.configuration.getOption('icache',  'enable')):
            fetch = cpu.submodules.fetch = CachedFetchUnit(self.configuration)
        else:
            fetch = cpu.submodules.fetch = BasicFetchUnit()
        if (self.configuration.getOption('dcache',  'enable')):
            lsu = cpu.submodules.lsu = CachedLSU(self.configuration)
        else:
            lsu = cpu.submodules.lsu = BasicLSU()
        if self.configuration.getOption('isa', 'enable_rv32m'):
            multiplier = cpu.submodules.multiplier = Multiplier()
            divider    = cpu.submodules.divider    = Divider()
        if self.configuration.getOption('predictor', 'enable_predictor'):
            predictor = cpu.submodules.predictor = BranchPredictor(self.configuration)
        # ----------------------------------------------------------------------
        # register file (GPR)
        gprf     = Memory(width=32, depth=32)
        gprf_rp1 = gprf.read_port()
        gprf_rp2 = gprf.read_port()
        gprf_wp  = gprf.write_port()
        cpu.submodules += gprf_rp1, gprf_rp2, gprf_wp
        # ----------------------------------------------------------------------
        # CSR
        csr.add_csr_from_list(exception.csr.csr_list)
        csr_rp = csr.create_read_port()
        csr_wp = csr.create_write_port()
        # ----------------------------------------------------------------------
        # forward declaration of signals
        fwd_x_rs1 = Signal()
        fwd_m_rs1 = Signal()
        fwd_w_rs1 = Signal()
        fwd_x_rs2 = Signal()
        fwd_m_rs2 = Signal()
        fwd_w_rs2 = Signal()
        x_result  = Signal(32)
        m_result  = Signal(32)
        w_result  = Signal(32)
        m_kill_bj = Signal()
        # ----------------------------------------------------------------------
        # Address Stage
        a_next_pc    = Signal(32)
        a_next_pc_q  = Signal(32)
        a_next_pc_fu = Signal(32)
        latched_pc   = Signal()

        # set the reset value.
        # to (RA -4) because the value to feed the fetch unit is the next pc:
        a.endpoint_b.pc.reset = self.configuration.getOption('reset', 'reset_address') - 4

        # select next pc
        with cpu.If(exception.m_exception & m.valid):
            cpu.d.comb += a_next_pc.eq(exception.csr.mtvec.read)  # exception
        with cpu.Elif(m.endpoint_a.mret & m.valid):
            cpu.d.comb += a_next_pc.eq(exception.csr.mepc.read)  # mret

        if (self.configuration.getOption('predictor', 'enable_predictor')):
            with cpu.Elif((m.endpoint_a.prediction & m.endpoint_a.branch) & ~m.endpoint_a.take_jmp_branch & m.valid):
                cpu.d.comb += a_next_pc.eq(m.endpoint_a.pc + 4)  # branch not taken
            with cpu.Elif(~(m.endpoint_a.prediction & m.endpoint_a.branch) & m.endpoint_a.take_jmp_branch & m.valid):
                cpu.d.comb += a_next_pc.eq(m.endpoint_a.jmp_branch_target)  # branck taken
            with cpu.Elif(predictor.f_prediction):
                cpu.d.comb += a_next_pc.eq(predictor.f_prediction_pc)  # prediction
        else:
            with cpu.Elif(m.endpoint_a.take_jmp_branch & m.valid):
                cpu.d.comb += a_next_pc.eq(m.endpoint_a.jmp_branch_target)  # jmp/branch

        with cpu.Elif(x.endpoint_a.fence_i & x.valid):
            cpu.d.comb += a_next_pc.eq(x.endpoint_a.pc + 4)  # fence_i.
        with cpu.Else():
            cpu.d.comb += a_next_pc.eq(f.endpoint_a.pc + 4)

        with cpu.If(f.stall):
            with cpu.If(f.kill & ~latched_pc):
                cpu.d.sync += [
                    a_next_pc_q.eq(a_next_pc),
                    latched_pc.eq(1)
                ]
        with cpu.Else():
            cpu.d.sync += latched_pc.eq(0)

        with cpu.If(latched_pc):
            cpu.d.comb += a_next_pc_fu.eq(a_next_pc_q)
        with cpu.Else():
            cpu.d.comb += a_next_pc_fu.eq(a_next_pc)

        cpu.d.comb += [
            fetch.a_pc.eq(a_next_pc_fu),
            fetch.a_stall.eq(a.stall),
            fetch.a_valid.eq(a.valid),
        ]

        cpu.d.comb += a.valid.eq(1)  # the stage is always valid
        # ----------------------------------------------------------------------
        # Fetch Stage
        cpu.d.comb += fetch.iport.connect(self.iport)  # connect the wishbone port

        cpu.d.comb += [
            fetch.f_stall.eq(f.stall),
            fetch.f_valid.eq(f.valid)
        ]

        f_kill_r = Signal()

        with cpu.If(f.stall):
            with cpu.If(f_kill_r == 0):
                cpu.d.sync += f_kill_r.eq(f.kill)
        with cpu.Else():
            cpu.d.sync += f_kill_r.eq(0)

        if (self.configuration.getOption('icache',  'enable')):
            cpu.d.comb += [
                fetch.flush.eq(x.endpoint_a.fence_i & x.valid & ~x.stall),
                fetch.f_pc.eq(f.endpoint_a.pc)
            ]

        f.add_kill_source(f_kill_r)
        f.add_stall_source(fetch.f_busy)
        f.add_kill_source(exception.m_exception & m.valid)
        f.add_kill_source(m.endpoint_a.mret & m.valid)
        f.add_kill_source(m_kill_bj)
        f.add_kill_source(x.endpoint_a.fence_i & x.valid & ~x.stall)
        # ----------------------------------------------------------------------
        # Decode Stage
        cpu.d.comb += decoder.instruction.eq(d.endpoint_a.instruction)

        with cpu.If(~d.stall):
            cpu.d.comb += [
                gprf_rp1.addr.eq(fetch.f_instruction[15:20]),
                gprf_rp2.addr.eq(fetch.f_instruction[20:25])
            ]
        with cpu.Else():
            cpu.d.comb += [
                gprf_rp1.addr.eq(decoder.gpr_rs1),
                gprf_rp2.addr.eq(decoder.gpr_rs2)
            ]

        cpu.d.comb += [
            gprf_wp.addr.eq(w.endpoint_a.gpr_rd),
            gprf_wp.data.eq(w_result),
            gprf_wp.en.eq(w.endpoint_a.gpr_we & w.valid)
        ]

        rs1_data = Signal(32)
        rs2_data = Signal(32)

        # select data for RS1
        with cpu.If(decoder.aiupc):
            cpu.d.comb += rs1_data.eq(d.endpoint_a.pc)
        with cpu.Elif((decoder.gpr_rs1 == 0) | decoder.lui):
            cpu.d.comb += rs1_data.eq(0)
        with cpu.Elif(fwd_x_rs1 & x.valid):
            cpu.d.comb += rs1_data.eq(x_result)
        with cpu.Elif(fwd_m_rs1 & m.valid):
            cpu.d.comb += rs1_data.eq(m_result)
        with cpu.Elif(fwd_w_rs1 & w.valid):
            cpu.d.comb += rs1_data.eq(w_result)
        with cpu.Else():
            cpu.d.comb += rs1_data.eq(gprf_rp1.data)

        # select data for RS2
        with cpu.If(decoder.csr):
            cpu.d.comb += rs2_data.eq(0)
        with cpu.Elif(~decoder.gpr_rs2_use):
            cpu.d.comb += rs2_data.eq(decoder.immediate)
        with cpu.Elif(decoder.gpr_rs2 == 0):
            cpu.d.comb += rs2_data.eq(0)
        with cpu.Elif(fwd_x_rs2 & x.valid):
            cpu.d.comb += rs2_data.eq(x_result)
        with cpu.Elif(fwd_m_rs2 & m.valid):
            cpu.d.comb += rs2_data.eq(m_result)
        with cpu.Elif(fwd_w_rs2 & w.valid):
            cpu.d.comb += rs2_data.eq(w_result)
        with cpu.Else():
            cpu.d.comb += rs2_data.eq(gprf_rp2.data)

        # Check if the forwarding is needed
        cpu.d.comb += [
            fwd_x_rs1.eq((decoder.gpr_rs1 == x.endpoint_a.gpr_rd) & (decoder.gpr_rs1 != 0) & x.endpoint_a.gpr_we),
            fwd_m_rs1.eq((decoder.gpr_rs1 == m.endpoint_a.gpr_rd) & (decoder.gpr_rs1 != 0) & m.endpoint_a.gpr_we),
            fwd_w_rs1.eq((decoder.gpr_rs1 == w.endpoint_a.gpr_rd) & (decoder.gpr_rs1 != 0) & w.endpoint_a.gpr_we),

            fwd_x_rs2.eq((decoder.gpr_rs2 == x.endpoint_a.gpr_rd) & (decoder.gpr_rs2 != 0) & x.endpoint_a.gpr_we),
            fwd_m_rs2.eq((decoder.gpr_rs2 == m.endpoint_a.gpr_rd) & (decoder.gpr_rs2 != 0) & m.endpoint_a.gpr_we),
            fwd_w_rs2.eq((decoder.gpr_rs2 == w.endpoint_a.gpr_rd) & (decoder.gpr_rs2 != 0) & w.endpoint_a.gpr_we),
        ]

        d.add_stall_source(((fwd_x_rs1 & decoder.gpr_rs1_use) | (fwd_x_rs2 & decoder.gpr_rs2_use)) & ~x.endpoint_a.needed_in_x & x.valid)
        d.add_stall_source(((fwd_m_rs1 & decoder.gpr_rs1_use) | (fwd_m_rs2 & decoder.gpr_rs2_use)) & ~m.endpoint_a.needed_in_m & m.valid)
        d.add_kill_source(exception.m_exception & m.valid)
        d.add_kill_source(m.endpoint_a.mret & m.valid)
        d.add_kill_source(m_kill_bj)
        d.add_kill_source(x.endpoint_a.fence_i & x.valid & ~x.stall)
        # ----------------------------------------------------------------------
        # Execute Stage
        x_branch_target   = Signal(32)
        x_take_jmp_branch = Signal()

        cpu.d.comb += [
            x_branch_target.eq(x.endpoint_a.pc + x.endpoint_a.immediate),
            x_take_jmp_branch.eq(x.endpoint_a.jump | (x.endpoint_a.branch & compare.cmp_ok))
        ]

        cpu.d.comb += [
            adder.dat1.eq(x.endpoint_a.src_data1),
            adder.dat2.eq(Mux(x.endpoint_a.store, x.endpoint_a.immediate, x.endpoint_a.src_data2)),
            adder.sub.eq((x.endpoint_a.arithmetic & x.endpoint_a.add_sub) | x.endpoint_a.compare | x.endpoint_a.branch)
        ]

        cpu.d.comb += [
            logic.op.eq(x.endpoint_a.funct3),
            logic.dat1.eq(x.endpoint_a.src_data1),
            logic.dat2.eq(x.endpoint_a.src_data2)
        ]

        cpu.d.comb += [
            shifter.direction.eq(x.endpoint_a.shift_dir),
            shifter.sign_ext.eq(x.endpoint_a.shift_sign),
            shifter.dat.eq(x.endpoint_a.src_data1),
            shifter.shamt.eq(x.endpoint_a.src_data2),
            shifter.stall.eq(x.stall)
        ]

        cpu.d.comb += [
            compare.op.eq(x.endpoint_a.funct3),
            compare.zero.eq(adder.result == 0),
            compare.negative.eq(adder.result[-1]),
            compare.overflow.eq(adder.overflow),
            compare.carry.eq(adder.carry)
        ]

        # select result
        with cpu.If(x.endpoint_a.logic):
            cpu.d.comb += x_result.eq(logic.result)
        with cpu.Elif(x.endpoint_a.jump):
            cpu.d.comb += x_result.eq(x.endpoint_a.pc + 4)
        if (self.configuration.getOption('isa', 'enable_rv32m')):
            with cpu.Elif(x.endpoint_a.multiplier):
                cpu.d.comb += x_result.eq(multiplier.result)
        with cpu.Else():
            cpu.d.comb += x_result.eq(adder.result)

        # load/store unit
        cpu.d.comb += [
            data_sel.x_funct3.eq(x.endpoint_a.funct3),
            data_sel.x_offset.eq(adder.result[:2]),
            data_sel.x_store_data.eq(x.endpoint_a.src_data2),
        ]

        cpu.d.comb += [
            lsu.x_addr.eq(adder.result),
            lsu.x_data_w.eq(data_sel.x_data_w),
            lsu.x_store.eq(x.endpoint_a.store),
            lsu.x_load.eq(x.endpoint_a.load),
            lsu.x_byte_sel.eq(data_sel.x_byte_sel),
            lsu.x_valid.eq(x.valid & ~data_sel.x_misaligned),
            lsu.x_stall.eq(x.stall)
        ]
        if (self.configuration.getOption('dcache', 'enable')):
            cpu.d.comb += lsu.x_fence_i.eq(x.valid & x.endpoint_a.fence_i)
            x.add_stall_source(x.valid & x.endpoint_a.fence_i & m.valid & m.endpoint_a.store)
        if (self.configuration.getOption('isa', 'enable_rv32m')):
            x.add_stall_source(x.valid & x.endpoint_a.multiplier & ~multiplier.ready)
        if (self.configuration.getOption('dcache', 'enable')):
            x.add_stall_source(x.valid & lsu.x_busy)
        x.add_kill_source(exception.m_exception & m.valid)
        x.add_kill_source(m.endpoint_a.mret & m.valid)
        x.add_kill_source(m_kill_bj)
        # ----------------------------------------------------------------------
        # Memory (and CSR) Stage
        csr_wdata = Signal(32)

        # jump/branch
        if (self.configuration.getOption('predictor', 'enable_predictor')):
            cpu.d.comb += m_kill_bj.eq(((m.endpoint_a.prediction & m.endpoint_a.branch) ^ m.endpoint_a.take_jmp_branch) & m.valid)
        else:
            cpu.d.comb += m_kill_bj.eq(m.endpoint_a.take_jmp_branch & m.valid)

        cpu.d.comb += lsu.dport.connect(self.dport)  # connect the wishbone port

        # select result
        with cpu.If(m.endpoint_a.shifter):
            cpu.d.comb += m_result.eq(shifter.result)
        with cpu.Elif(m.endpoint_a.compare):
            cpu.d.comb += m_result.eq(m.endpoint_a.compare_result)
        if (self.configuration.getOption('isa', 'enable_rv32m')):
            with cpu.Elif(m.endpoint_a.divider):
                cpu.d.comb += m_result.eq(divider.result)
        with cpu.Else():
            cpu.d.comb += m_result.eq(m.endpoint_a.result)

        cpu.d.comb += [
            data_sel.m_data_r.eq(lsu.m_load_data),
            data_sel.m_funct3.eq(m.endpoint_a.funct3),
            data_sel.m_offset.eq(m.endpoint_a.result)
        ]

        cpu.d.comb += [
            lsu.m_valid.eq(m.valid),
            lsu.m_stall.eq(m.stall)
        ]
        if (self.configuration.getOption('dcache', 'enable')):
            cpu.d.comb += [
                lsu.m_addr.eq(m.endpoint_a.result),
                lsu.m_load.eq(m.endpoint_a.load),
                lsu.m_store.eq(m.endpoint_a.store)
            ]

        csr_src0 = Signal(32)
        csr_src = Signal(32)

        cpu.d.comb += [
            csr_src0.eq(Mux(m.endpoint_a.funct3[2], m.endpoint_a.instruction[15:20], m.endpoint_a.result)),
            csr_src.eq(Mux(m.endpoint_a.funct3[:2] == 0b11, ~csr_src0, csr_src0))
        ]

        with cpu.If(m.endpoint_a.funct3[:2] == 0b01):  # write
            cpu.d.comb += csr_wdata.eq(csr_src)
        with cpu.Elif(m.endpoint_a.funct3[:2] == 0b10):  # set
            cpu.d.comb += csr_wdata.eq(csr_rp.data | csr_src)
        with cpu.Else():  # clear
            cpu.d.comb += csr_wdata.eq(csr_rp.data & csr_src)

        # csr
        cpu.d.comb += [
            csr_rp.addr.eq(m.endpoint_a.csr_addr),
            csr_wp.addr.eq(m.endpoint_a.csr_addr),
            csr_wp.en.eq(m.endpoint_a.csr_we & m.valid),
            csr_wp.data.eq(csr_wdata)
        ]

        # exception unit
        cpu.d.comb += [
            exception.external_interrupt.eq(self.external_interrupt),
            exception.software_interrupt.eq(self.software_interrupt),
            exception.timer_interrupt.eq(self.timer_interrupt),
            exception.m_fetch_misalign.eq(m.endpoint_a.take_jmp_branch & (m.endpoint_a.jmp_branch_target[:2] != 0)),
            exception.m_fetch_error.eq(m.endpoint_a.fetch_error),
            exception.m_illegal.eq(m.endpoint_a.illegal | (m.endpoint_a.csr & csr.invalid)),
            exception.m_load_misalign.eq(m.endpoint_a.ls_misalign & m.endpoint_a.load),
            exception.m_load_error.eq(lsu.m_load_error),
            exception.m_store_misalign.eq(m.endpoint_a.ls_misalign & m.endpoint_a.store),
            exception.m_store_error.eq(lsu.m_store_error),
            exception.m_ecall.eq(m.endpoint_a.ecall),
            exception.m_ebreak.eq(m.endpoint_a.ebreak),
            exception.m_mret.eq(m.endpoint_a.mret),
            exception.m_pc.eq(m.endpoint_a.pc),
            exception.m_instruction.eq(m.endpoint_a.instruction),
            exception.m_fetch_badaddr.eq(m.endpoint_a.fetch_badaddr),
            exception.m_pc_misalign.eq(m.endpoint_a.jmp_branch_target),
            exception.m_ls_misalign.eq(m.endpoint_a.result),
            exception.m_load_store_badaddr.eq(lsu.m_badaddr),
            exception.m_store.eq(m.endpoint_a.store),
            exception.m_valid.eq(m.valid),
            exception.m_stall.eq(m.stall)
        ]

        m.add_stall_source(m.valid & lsu.m_busy)
        if (self.configuration.getOption('isa', 'enable_rv32m')):
            m.add_stall_source(divider.busy)
        m.add_kill_source(exception.m_exception & m.valid)
        # ----------------------------------------------------------------------
        # Write-back stage
        with cpu.If(w.endpoint_a.load):
            cpu.d.comb += w_result.eq(w.endpoint_a.ld_result)
        with cpu.Elif(w.endpoint_a.csr):
            cpu.d.comb += w_result.eq(w.endpoint_a.csr_result)
        with cpu.Else():
            cpu.d.comb += w_result.eq(w.endpoint_a.result)

        # ----------------------------------------------------------------------
        # Optional units: Multiplier/Divider
        if (self.configuration.getOption('isa', 'enable_rv32m')):
            cpu.d.comb += [
                multiplier.op.eq(x.endpoint_a.funct3),
                multiplier.dat1.eq(x.endpoint_a.src_data1),
                multiplier.dat2.eq(x.endpoint_a.src_data2),
                multiplier.valid.eq(x.endpoint_a.multiplier & x.valid)
            ]
            cpu.d.comb += [
                divider.op.eq(x.endpoint_a.funct3),
                divider.dat1.eq(x.endpoint_a.src_data1),
                divider.dat2.eq(x.endpoint_a.src_data2),
                divider.stall.eq(x.stall),
                divider.start.eq(x.endpoint_a.divider)
            ]
        # ----------------------------------------------------------------------
        # Optional units: branch predictor
        if (self.configuration.getOption('predictor', 'enable_predictor')):
            cpu.d.comb += [
                predictor.a_pc.eq(a_next_pc_fu),
                predictor.a_stall.eq(a.stall),
                predictor.f_pc.eq(f.endpoint_a.pc),
                predictor.m_prediction_state.eq(m.endpoint_a.prediction_state),
                predictor.m_take_jmp_branch.eq(m.endpoint_a.take_jmp_branch & m.valid),
                predictor.m_pc.eq(m.endpoint_a.pc),
                predictor.m_target_pc.eq(m.endpoint_a.jmp_branch_target),
                predictor.m_update.eq(m.endpoint_a.branch & m.valid)
            ]
        # ----------------------------------------------------------------------
        # Pipeline registers

        # A -> F
        with cpu.If(~a.stall):
            cpu.d.sync += a.endpoint_b.pc.eq(a_next_pc_fu)

        # F -> D
        with cpu.If(~f.stall):
            cpu.d.sync += [
                f.endpoint_b.pc.eq(f.endpoint_a.pc),
                f.endpoint_b.instruction.eq(fetch.f_instruction),
                f.endpoint_b.fetch_error.eq(fetch.f_bus_error),
                f.endpoint_b.fetch_badaddr.eq(fetch.f_badaddr)
            ]
            if (self.configuration.getOption('predictor', 'enable_predictor')):
                cpu.d.sync += [
                    f.endpoint_b.prediction.eq(predictor.f_prediction),
                    f.endpoint_b.prediction_state.eq(predictor.f_prediction_state)
                ]

        # D -> X
        with cpu.If(~d.stall):
            cpu.d.sync += [
                d.endpoint_b.pc.eq(d.endpoint_a.pc),
                d.endpoint_b.instruction.eq(d.endpoint_a.instruction),
                d.endpoint_b.gpr_rd.eq(decoder.gpr_rd),
                d.endpoint_b.gpr_we.eq(decoder.gpr_we),
                d.endpoint_b.src_data1.eq(rs1_data),
                d.endpoint_b.src_data2.eq(rs2_data),
                d.endpoint_b.immediate.eq(decoder.immediate),
                d.endpoint_b.funct3.eq(decoder.funct3),
                d.endpoint_b.gpr_rs1_use.eq(decoder.gpr_rs1_use),
                d.endpoint_b.needed_in_x.eq(decoder.needed_in_x),
                d.endpoint_b.needed_in_m.eq(decoder.needed_in_m),
                d.endpoint_b.arithmetic.eq(decoder.aritmetic),
                d.endpoint_b.logic.eq(decoder.logic),
                d.endpoint_b.shifter.eq(decoder.shift),
                d.endpoint_b.jump.eq(decoder.jump),
                d.endpoint_b.branch.eq(decoder.branch),
                d.endpoint_b.compare.eq(decoder.compare),
                d.endpoint_b.load.eq(decoder.load),
                d.endpoint_b.store.eq(decoder.store),
                d.endpoint_b.csr.eq(decoder.csr),
                d.endpoint_b.add_sub.eq(decoder.substract),
                d.endpoint_b.shift_dir.eq(decoder.shift_direction),
                d.endpoint_b.shift_sign.eq(decoder.shit_signed),
                d.endpoint_b.csr_addr.eq(decoder.immediate),
                d.endpoint_b.csr_we.eq(decoder.csr_we),
                d.endpoint_b.fetch_error.eq(d.endpoint_a.fetch_error),
                d.endpoint_b.fetch_badaddr.eq(d.endpoint_a.fetch_badaddr),
                d.endpoint_b.ecall.eq(decoder.ecall),
                d.endpoint_b.ebreak.eq(decoder.ebreak),
                d.endpoint_b.mret.eq(decoder.mret),
                d.endpoint_b.illegal.eq(decoder.illegal),
                d.endpoint_b.fence_i.eq(decoder.fence_i),
                d.endpoint_b.multiplier.eq(decoder.multiply),
                d.endpoint_b.divider.eq(decoder.divide),
                d.endpoint_b.prediction.eq(d.endpoint_a.prediction),
                d.endpoint_b.prediction_state.eq(d.endpoint_a.prediction_state)
            ]

        # X -> M
        with cpu.If(~x.stall):
            cpu.d.sync += [
                x.endpoint_b.pc.eq(x.endpoint_a.pc),
                x.endpoint_b.instruction.eq(x.endpoint_a.instruction),
                x.endpoint_b.gpr_rd.eq(x.endpoint_a.gpr_rd),
                x.endpoint_b.gpr_we.eq(x.endpoint_a.gpr_we),
                x.endpoint_b.needed_in_m.eq(x.endpoint_a.needed_in_m | x.endpoint_a.needed_in_x),
                x.endpoint_b.funct3.eq(x.endpoint_a.funct3),
                x.endpoint_b.shifter.eq(x.endpoint_a.shifter),
                x.endpoint_b.compare.eq(x.endpoint_a.compare),
                x.endpoint_b.branch.eq(x.endpoint_a.branch),
                x.endpoint_b.load.eq(x.endpoint_a.load),
                x.endpoint_b.store.eq(x.endpoint_a.store),
                x.endpoint_b.csr.eq(x.endpoint_a.csr),
                x.endpoint_b.csr_addr.eq(x.endpoint_a.csr_addr),
                x.endpoint_b.csr_we.eq(x.endpoint_a.csr_we),
                x.endpoint_b.result.eq(x_result),
                x.endpoint_b.compare_result.eq(compare.cmp_ok),
                x.endpoint_b.compare_result.eq(compare.cmp_ok),
                x.endpoint_b.jmp_branch_target.eq(Mux(x.endpoint_a.jump & x.endpoint_a.gpr_rs1_use, adder.result[1:] << 1,  x_branch_target)),
                x.endpoint_b.take_jmp_branch.eq(x_take_jmp_branch),
                x.endpoint_b.fetch_error.eq(x.endpoint_a.fetch_error),
                x.endpoint_b.fetch_badaddr.eq(x.endpoint_a.fetch_badaddr),
                x.endpoint_b.ecall.eq(x.endpoint_a.ecall),
                x.endpoint_b.ebreak.eq(x.endpoint_a.ebreak),
                x.endpoint_b.mret.eq(x.endpoint_a.mret),
                x.endpoint_b.illegal.eq(x.endpoint_a.illegal),
                x.endpoint_b.ls_misalign.eq(data_sel.x_misaligned),
                x.endpoint_b.divider.eq(x.endpoint_a.divider),
                x.endpoint_b.prediction.eq(x.endpoint_a.prediction),
                x.endpoint_b.prediction_state.eq(x.endpoint_a.prediction_state),
            ]

        # M -> W
        with cpu.If(~m.stall):
            cpu.d.sync += [
                m.endpoint_b.pc.eq(m.endpoint_a.pc),
                m.endpoint_b.gpr_rd.eq(m.endpoint_a.gpr_rd),
                m.endpoint_b.gpr_we.eq(m.endpoint_a.gpr_we),
                m.endpoint_b.result.eq(m_result),
                m.endpoint_b.ld_result.eq(data_sel.m_load_data),
                m.endpoint_b.csr_result.eq(csr_rp.data),
                m.endpoint_b.load.eq(m.endpoint_a.load),
                m.endpoint_b.csr.eq(m.endpoint_a.csr)
            ]

        return cpu
