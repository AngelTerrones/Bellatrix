from nmigen import Mux
from nmigen import Cat
from nmigen import Signal
from nmigen import Module
from nmigen import Memory
from nmigen import Elaboratable
from nmigen.build import Platform
from nmigen_soc.wishbone.bus import Interface
from bellatrix.gateware.core.csr import CSRFile
from bellatrix.gateware.core.stage import Stage
from bellatrix.gateware.core.adder import AdderUnit
from bellatrix.gateware.core.logic import LogicUnit
from bellatrix.gateware.core.compare import CompareUnit
from bellatrix.gateware.core.shifter import ShifterUnit
from bellatrix.gateware.core.frontend import Frontend
from bellatrix.gateware.core.lsu import BasicLSU
from bellatrix.gateware.core.lsu import DataFormat
from bellatrix.gateware.core.layout import _fd_layout
from bellatrix.gateware.core.layout import _dx_layout
from bellatrix.gateware.core.layout import _xm_layout
from bellatrix.gateware.core.layout import _mw_layout
from bellatrix.gateware.core.exception import ExceptionUnit
from bellatrix.gateware.core.decoder import DecoderUnit
from bellatrix.gateware.core.multiplier import Multiplier
from bellatrix.gateware.core.divider import Divider
from bellatrix.gateware.debug.trigger import TriggerModule
from typing import List


class Bellatrix(Elaboratable):
    def __init__(self,
                 # Core
                 core_reset_address: int = 0x8000_0000,
                 # ISA
                 isa_enable_rv32m: bool = False,
                 isa_enable_extra_csr: bool = False,
                 isa_enable_user_mode: bool = False,
                 # Brach predictor
                 predictor_enable: bool = False,
                 predictor_size: int = 64,
                 # Instruction Cache
                 icache_enable: bool = False,
                 icache_nlines: int = 128,
                 icache_nwords: int = 8,
                 icache_nways: int = 1,
                 icache_start: int = 0x8000_0000,
                 icache_end: int = 0xffff_ffff,
                 # trigger module
                 trigger_enable: bool = False,
                 trigger_ntriggers: int = 4,
                 # eat extra arguments. Do nothing with it
                 **kwargs
                 ) -> None:
        # ----------------------------------------------------------------------
        if len(kwargs) != 0:
            print(f'Warning: Got unused kwargs: {kwargs.keys()}')

        self.reset_address     = core_reset_address
        self.enable_rv32m      = isa_enable_rv32m
        self.enable_extra_csr  = isa_enable_extra_csr
        self.enable_user_mode  = isa_enable_user_mode
        self.predictor_enable  = predictor_enable
        self.predictor_size    = predictor_size
        self.icache_enable     = icache_enable
        self.icache_nlines     = icache_nlines
        self.icache_nwords     = icache_nwords
        self.icache_nways      = icache_nways
        self.icache_start      = icache_start
        self.icache_end        = icache_end
        self.trigger_enable    = trigger_enable
        self.trigger_ntriggers = trigger_ntriggers
        # kwargs for units
        self.exception_unit_kw = dict(enable_rv32m=self.enable_rv32m,
                                      enable_extra_csr=self.enable_extra_csr,
                                      enable_user_mode=self.enable_user_mode,
                                      core_reset_address=self.reset_address)
        self.icache_kwargs = dict(nlines=self.icache_nlines,
                                  nwords=self.icache_nwords,
                                  nways=self.icache_nways,
                                  start_addr=self.icache_start,
                                  end_addr=self.icache_end)
        self.frontend_kwargs = dict(reset_address=self.reset_address,
                                    predictor_enable=self.predictor_enable,
                                    predictor_size=self.predictor_size,
                                    icache_enable=self.icache_enable,
                                    icache_kwargs=self.icache_kwargs)
        # ----------------------------------------------------------------------
        i_features = ['err']
        if self.icache_enable:
            i_features.extend(['cti', 'bte'])
        d_features = ['err']
        # IO
        self.iport              = Interface(addr_width=32, data_width=32, granularity=32, features=i_features, name='iport')
        self.dport              = Interface(addr_width=32, data_width=32, granularity=8,  features=d_features, name='dport')
        self.external_interrupt = Signal()  # input
        self.timer_interrupt    = Signal()  # input
        self.software_interrupt = Signal()  # input

    def port_list(self) -> List:
        iport = [getattr(self.iport, name) for name, _, _ in self.iport.layout]
        dport = [getattr(self.dport, name) for name, _, _ in self.dport.layout]
        return [
            *iport,  # instruction port
            *dport,  # data port
            self.external_interrupt,  # exceptions
            self.timer_interrupt,
            self.software_interrupt
        ]

    def elaborate(self, platform: Platform) -> Module:
        cpu = Module()
        # ----------------------------------------------------------------------
        # create the pipeline stages
        d = cpu.submodules.d = Stage('D', _fd_layout, _dx_layout)
        x = cpu.submodules.x = Stage('X', _dx_layout, _xm_layout)
        m = cpu.submodules.m = Stage('M', _xm_layout, _mw_layout)
        w = cpu.submodules.w = Stage('W', _mw_layout, None)
        # ----------------------------------------------------------------------
        # units
        adder     = cpu.submodules.adder     = AdderUnit()
        logic     = cpu.submodules.logic     = LogicUnit()
        shifter   = cpu.submodules.shifter   = ShifterUnit()
        compare   = cpu.submodules.compare   = CompareUnit()
        decoder   = cpu.submodules.decoder   = DecoderUnit(self.enable_rv32m)
        csr       = cpu.submodules.csr       = CSRFile()
        exception = cpu.submodules.exception = ExceptionUnit(csr, **self.exception_unit_kw)
        data_sel  = cpu.submodules.data_sel  = DataFormat()
        frontend  = cpu.submodules.frontend  = Frontend(**self.frontend_kwargs)
        lsu       = cpu.submodules.lsu = BasicLSU()
        if self.enable_rv32m:
            multiplier = cpu.submodules.multiplier = Multiplier()
            divider    = cpu.submodules.divider    = Divider()
        if self.trigger_enable:
            trigger = cpu.submodules.trigger = TriggerModule(privmode=exception.m_privmode,
                                                             ntriggers=self.trigger_ntriggers,
                                                             csrf=csr,
                                                             enable_user_mode=self.enable_user_mode)
        # ----------------------------------------------------------------------
        # register file (GPR)
        gprf     = Memory(width=32, depth=32)
        gprf_rp1 = gprf.read_port()
        gprf_rp2 = gprf.read_port()
        gprf_wp  = gprf.write_port()
        cpu.submodules += gprf_rp1, gprf_rp2, gprf_wp
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
        m_take_jb = Signal()
        m_kill_jb = Signal()
        # ----------------------------------------------------------------------
        # connect the stages
        cpu.d.comb += [
            frontend.endpoint.connect(d.endpoint_a),
            d.endpoint_b.connect(x.endpoint_a),
            x.endpoint_b.connect(m.endpoint_a),
            m.endpoint_b.connect(w.endpoint_a)
        ]
        # ----------------------------------------------------------------------
        # Frontend
        cpu.d.comb += frontend.iport.connect(self.iport)
        cpu.d.comb += [
            frontend.mtvec.eq(exception.mtvec.read),
            frontend.mepc.eq(exception.mepc.read),
            frontend.jb_pc.eq(m.endpoint_a.jb_target),
            frontend.fence_pc.eq(x.endpoint_a.pc + 4),
            frontend.exception.eq(exception.m_exception),
            frontend.mret.eq(m.endpoint_a.mret & m.valid),
            frontend.take_jb.eq(m_take_jb & m.valid),
            frontend.fence_i.eq(x.endpoint_a.fence_i & x.valid),
            frontend.kill.eq(d.kill),
        ]
        if self.predictor_enable:
            cpu.d.comb += [
                frontend.p_bad_predict_jump.eq(m.endpoint_a.prediction & ~m_take_jb & m.valid),
                frontend.p_bad_predict_nojump.eq(~m.endpoint_a.prediction & m_take_jb & m.valid),
                frontend.p_no_jump_next_pc.eq(m.endpoint_a.pc + 4),
                frontend.p_prediction_pc.eq(m.endpoint_a.pc),
                frontend.p_prediction_target.eq(m.endpoint_a.jb_target),
                frontend.p_prediction_state.eq(m.endpoint_a.prediction_state),
                frontend.p_predictor_update.eq(m.endpoint_a.branch &m.valid),
            ]
        if self.icache_enable:
            cpu.d.comb += frontend.p_flush.eq(0)

        # ----------------------------------------------------------------------
        # Decode Stage
        cpu.d.comb += [
            decoder.instruction.eq(d.endpoint_a.instruction),
            decoder.privmode.eq(exception.m_privmode)
        ]
        with cpu.Switch(d.stall):
            with cpu.Case(1):
                cpu.d.comb += [
                    gprf_rp1.addr.eq(decoder.gpr_rs1),
                    gprf_rp2.addr.eq(decoder.gpr_rs2)
                ]
            with cpu.Default():
                cpu.d.comb += [
                    gprf_rp1.addr.eq(frontend.fe_instruction[15:20]),
                    gprf_rp2.addr.eq(frontend.fe_instruction[20:25])
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
        with cpu.Elif(fwd_x_rs1):
            cpu.d.comb += rs1_data.eq(x_result)
        with cpu.Elif(fwd_m_rs1):
            cpu.d.comb += rs1_data.eq(m_result)
        with cpu.Elif(fwd_w_rs1):
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
        with cpu.Elif(fwd_x_rs2):
            cpu.d.comb += rs2_data.eq(x_result)
        with cpu.Elif(fwd_m_rs2):
            cpu.d.comb += rs2_data.eq(m_result)
        with cpu.Elif(fwd_w_rs2):
            cpu.d.comb += rs2_data.eq(w_result)
        with cpu.Else():
            cpu.d.comb += rs2_data.eq(gprf_rp2.data)

        d_jb_base_addr = Signal(32)
        with cpu.If(decoder.jump & decoder.gpr_rs1_use):  # JALR
            cpu.d.comb += d_jb_base_addr.eq(rs1_data)
        with cpu.Else():
            cpu.d.comb += d_jb_base_addr.eq(d.endpoint_a.pc)

        # forwarding
        cpu.d.comb += [
            fwd_x_rs1.eq((decoder.gpr_rs1 == x.endpoint_a.gpr_rd) & x.endpoint_a.gpr_rd_is_nzero & x.endpoint_a.gpr_we & x.valid),
            fwd_m_rs1.eq((decoder.gpr_rs1 == m.endpoint_a.gpr_rd) & m.endpoint_a.gpr_rd_is_nzero & m.endpoint_a.gpr_we & m.valid),
            fwd_w_rs1.eq((decoder.gpr_rs1 == w.endpoint_a.gpr_rd) & w.endpoint_a.gpr_rd_is_nzero & w.endpoint_a.gpr_we & w.valid),

            fwd_x_rs2.eq((decoder.gpr_rs2 == x.endpoint_a.gpr_rd) & x.endpoint_a.gpr_rd_is_nzero & x.endpoint_a.gpr_we & x.valid),
            fwd_m_rs2.eq((decoder.gpr_rs2 == m.endpoint_a.gpr_rd) & m.endpoint_a.gpr_rd_is_nzero & m.endpoint_a.gpr_we & m.valid),
            fwd_w_rs2.eq((decoder.gpr_rs2 == w.endpoint_a.gpr_rd) & w.endpoint_a.gpr_rd_is_nzero & w.endpoint_a.gpr_we & w.valid),
        ]

        bubble_x = (x.endpoint_a.needed_in_m | x.endpoint_a.needed_in_w)
        bubble_m = m.endpoint_a.needed_in_w
        d.add_stall_source(((fwd_x_rs1 & decoder.gpr_rs1_use) | (fwd_x_rs2 & decoder.gpr_rs2_use)) & bubble_x)
        d.add_stall_source(((fwd_m_rs1 & decoder.gpr_rs1_use) | (fwd_m_rs2 & decoder.gpr_rs2_use)) & bubble_m)
        d.add_kill_source(m_kill_jb & m.valid)
        d.add_kill_source(x.endpoint_a.fence_i & ~x.stall & x.valid)
        d.add_kill_source(exception.m_exception)
        d.add_kill_source(m.endpoint_a.mret & m.valid)
        # ----------------------------------------------------------------------
        # Execute Stage
        x_jb_target = Signal(32)

        cpu.d.comb += x_jb_target.eq((x.endpoint_a.jb_base_addr + x.endpoint_a.immediate) & 0xFFFFFFFE),
        cpu.d.comb += [
            adder.dat1.eq(x.endpoint_a.src_data1),
            adder.dat2.eq(x.endpoint_a.src_data2),
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
        # select output data
        with cpu.Switch(Cat(x.endpoint_a.logic, x.endpoint_a.jump)):
            with cpu.Case('01'):
                cpu.d.comb += x_result.eq(logic.result)
            with cpu.Case('10'):
                cpu.d.comb += x_result.eq(x.endpoint_a.pc + 4)
            with cpu.Default():
                cpu.d.comb += x_result.eq(adder.result)
        if self.enable_rv32m:
            with cpu.If(x.endpoint_a.multiplier):
                cpu.d.comb += x_result.eq(multiplier.result)

        # load/store unit
        x_ls_addr  = Signal(32)
        lsu_enable = ~data_sel.x_misaligned & ~x.kill & ~x.stall & x.valid
        cpu.d.comb += x_ls_addr.eq(x.endpoint_a.ls_base_addr + x.endpoint_a.immediate)

        cpu.d.comb += [
            data_sel.x_funct3.eq(x.endpoint_a.funct3),
            data_sel.x_offset.eq(x_ls_addr[:2]),
            data_sel.x_store_data.eq(x.endpoint_a.st_data),
        ]
        cpu.d.comb += [
            lsu.x_addr.eq(x_ls_addr),
            lsu.x_data_w.eq(data_sel.x_data_w),
            lsu.x_store.eq(x.endpoint_a.store),
            lsu.x_load.eq(x.endpoint_a.load),
            lsu.x_byte_sel.eq(data_sel.x_byte_sel),
            lsu.x_enable.eq(lsu_enable)
        ]
        if self.trigger_enable:
            cpu.d.comb += lsu.x_enable.eq(~trigger.trap & lsu_enable)

        # ebreak logic
        x_ebreak = x.endpoint_a.ebreak & x.valid
        if self.trigger_enable:
            x_ebreak = x_ebreak | trigger.trap

        # stall/kill sources
        if self.enable_rv32m:
            x.add_stall_source(x.endpoint_a.multiplier & ~multiplier.ready & x.valid)
        if self.trigger_enable:
            # wait for commits to the CSR if the instruction@X is a memory operation
            # csr.port.done is 1 only after a CSR operation.
            x.add_stall_source((x.endpoint_a.load | x.endpoint_a.store) & csr.port.we & csr.port.done & x.valid)
        x.add_kill_source(m_kill_jb & m.valid)
        x.add_kill_source(exception.m_exception)
        x.add_kill_source(m.endpoint_a.mret & m.valid)
        # ----------------------------------------------------------------------
        # Memory/CSR Stage
        csr_wdata = Signal(32)

        cpu.d.comb += [
            compare.op.eq(m.endpoint_a.funct3),
            compare.zero.eq(m.endpoint_a.zero),
            compare.negative.eq(m.endpoint_a.negative),
            compare.overflow.eq(m.endpoint_a.overflow),
            compare.carry.eq(m.endpoint_a.carry)
        ]

        # jump/branch
        cpu.d.comb += m_take_jb.eq(m.endpoint_a.jump | (m.endpoint_a.branch & compare.cmp_ok))
        if self.predictor_enable:
            cpu.d.comb += m_kill_jb.eq(m.endpoint_a.prediction ^ m_take_jb)
        else:
            cpu.d.comb += m_kill_jb.eq(m_take_jb)

        # select result
        with cpu.Switch(Cat(m.endpoint_a.shifter, m.endpoint_a.compare)):
            with cpu.Case('01'):
                cpu.d.comb += m_result.eq(shifter.result)
            with cpu.Case('10'):
                cpu.d.comb += m_result.eq(compare.cmp_ok)
            with cpu.Default():
                cpu.d.comb += m_result.eq(m.endpoint_a.result)
        if self.enable_rv32m:
            with cpu.If(m.endpoint_a.divider):
                cpu.d.comb += m_result.eq(divider.result)

        # LSU
        cpu.d.comb += lsu.dport.connect(self.dport)  # connect the wishbone port
        cpu.d.comb += [
            data_sel.m_data_r.eq(lsu.m_load_data),
            data_sel.m_funct3.eq(m.endpoint_a.funct3),
            data_sel.m_offset.eq(m.endpoint_a.ls_addr[:2])
        ]
        # csr
        csr_src0 = Signal(32)
        csr_src  = Signal(32)

        cpu.d.comb += [
            csr_src0.eq(Mux(m.endpoint_a.funct3[2], m.endpoint_a.instruction[15:20], m.endpoint_a.result)),
            csr_src.eq(Mux(m.endpoint_a.funct3[:2] == 0b11, ~csr_src0, csr_src0))
        ]

        with cpu.If(m.endpoint_a.funct3[:2] == 0b01):  # write
            cpu.d.comb += csr_wdata.eq(csr_src)
        with cpu.Elif(m.endpoint_a.funct3[:2] == 0b10):  # set
            cpu.d.comb += csr_wdata.eq(csr.port.dat_r | csr_src)
        with cpu.Else():  # clear
            cpu.d.comb += csr_wdata.eq(csr.port.dat_r & csr_src)

        cpu.d.comb += [
            csr.port.addr.eq(m.endpoint_a.csr_addr),
            csr.port.dat_w.eq(csr_wdata),
            csr.port.valid.eq(m.endpoint_a.csr & m.valid),
            csr.port.we.eq(m.endpoint_a.csr_we)
        ]
        cpu.d.comb += csr.privmode.eq(exception.m_privmode)

        # exception unit
        cpu.d.comb += [
            exception.external_interrupt.eq(self.external_interrupt),
            exception.software_interrupt.eq(self.software_interrupt),
            exception.timer_interrupt.eq(self.timer_interrupt),
            exception.m_fetch_misalign.eq(m_take_jb & m.endpoint_a.jb_target[1]),
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
            exception.m_fetch_badaddr.eq(m.endpoint_a.pc),
            exception.m_pc_misalign.eq(m.endpoint_a.jb_target),
            exception.m_ls_misalign.eq(m.endpoint_a.ls_addr),
            exception.m_load_store_badaddr.eq(lsu.m_badaddr),
            exception.m_store.eq(m.endpoint_a.store),
            exception.m_valid.eq(m.valid)
        ]
        if self.enable_rv32m:
            m.add_stall_source(divider.busy & m.valid)
        m.add_stall_source(lsu.m_busy)  # TODO check
        m.add_stall_source(m.endpoint_a.csr & ~csr.port.done & m.valid)
        m.add_kill_source(exception.m_exception)
        # ----------------------------------------------------------------------
        # Write Back Stage
        if self.enable_extra_csr:
            cpu.d.comb += exception.w_retire.eq(w.retire)  # use the stage's signal

        with cpu.Switch(Cat(w.endpoint_a.load, w.endpoint_a.csr)):
            with cpu.Case('01'):
                cpu.d.comb += w_result.eq(w.endpoint_a.ld_result)
            with cpu.Case('10'):
                cpu.d.comb += w_result.eq(w.endpoint_a.csr_result)
            with cpu.Default():
                cpu.d.comb += w_result.eq(w.endpoint_a.result)

        # ----------------------------------------------------------------------
        # Optional unit: Multiplier/Divider
        if self.enable_rv32m:
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
                divider.start.eq(x.endpoint_a.divider & x.valid)
            ]
        # ----------------------------------------------------------------------
        # Optional unit: trigger
        if self.trigger_enable:
            cpu.d.comb += [
                trigger.x_pc.eq(x.endpoint_a.pc),
                trigger.x_bus_addr.eq(lsu.x_addr),
                trigger.x_store.eq(lsu.x_store),
                trigger.x_load.eq(lsu.x_load),
                trigger.x_valid.eq(x.valid)
            ]
        # ----------------------------------------------------------------------
        # Pipeline registers
        # D -> X
        with cpu.If(~x.stall):
            cpu.d.sync += [
                d.endpoint_b.pc.eq(d.endpoint_a.pc),
                d.endpoint_b.instruction.eq(d.endpoint_a.instruction),
                d.endpoint_b.gpr_rd.eq(decoder.gpr_rd),
                d.endpoint_b.gpr_rd_is_nzero.eq(decoder.gpr_rd_is_nzero),
                d.endpoint_b.gpr_we.eq(decoder.gpr_we),
                d.endpoint_b.src_data1.eq(rs1_data),
                d.endpoint_b.src_data2.eq(rs2_data),
                d.endpoint_b.immediate.eq(decoder.immediate),
                d.endpoint_b.funct3.eq(decoder.funct3),
                d.endpoint_b.needed_in_m.eq(decoder.needed_in_m),
                d.endpoint_b.needed_in_w.eq(decoder.needed_in_w),
                d.endpoint_b.arithmetic.eq(decoder.aritmetic),
                d.endpoint_b.logic.eq(decoder.logic),
                d.endpoint_b.compare.eq(decoder.compare),
                d.endpoint_b.shifter.eq(decoder.shift),
                d.endpoint_b.jump.eq(decoder.jump),
                d.endpoint_b.branch.eq(decoder.branch),
                d.endpoint_b.load.eq(decoder.load),
                d.endpoint_b.store.eq(decoder.store),
                d.endpoint_b.csr.eq(decoder.csr),
                d.endpoint_b.fence_i.eq(decoder.fence_i),
                d.endpoint_b.fence.eq(decoder.fence),
                d.endpoint_b.multiplier.eq(decoder.multiply),
                d.endpoint_b.divider.eq(decoder.divide),
                d.endpoint_b.add_sub.eq(decoder.substract),
                d.endpoint_b.shift_dir.eq(decoder.shift_direction),
                d.endpoint_b.shift_sign.eq(decoder.shift_signed),
                d.endpoint_b.jb_base_addr.eq(d_jb_base_addr),
                d.endpoint_b.ls_base_addr.eq(rs1_data),
                d.endpoint_b.st_data.eq(rs2_data),
                d.endpoint_b.csr_addr.eq(decoder.immediate),
                d.endpoint_b.csr_we.eq(decoder.csr_we),
                d.endpoint_b.fetch_error.eq(d.endpoint_a.fetch_error),
                d.endpoint_b.ecall.eq(decoder.ecall),
                d.endpoint_b.ebreak.eq(decoder.ebreak),
                d.endpoint_b.mret.eq(decoder.mret),
                d.endpoint_b.illegal.eq(decoder.illegal),
                d.endpoint_b.prediction.eq(d.endpoint_a.prediction & decoder.branch),
                d.endpoint_b.prediction_state.eq(d.endpoint_a.prediction_state)
            ]

        # X -> M
        with cpu.If(~m.stall):
            cpu.d.sync += [
                x.endpoint_b.pc.eq(x.endpoint_a.pc),
                x.endpoint_b.instruction.eq(x.endpoint_a.instruction),
                x.endpoint_b.gpr_rd.eq(x.endpoint_a.gpr_rd),
                x.endpoint_b.gpr_rd_is_nzero.eq(x.endpoint_a.gpr_rd_is_nzero),
                x.endpoint_b.gpr_we.eq(x.endpoint_a.gpr_we),
                x.endpoint_b.needed_in_w.eq(x.endpoint_a.needed_in_w),
                x.endpoint_b.funct3.eq(x.endpoint_a.funct3),
                x.endpoint_b.compare.eq(x.endpoint_a.compare),
                x.endpoint_b.shifter.eq(x.endpoint_a.shifter),
                x.endpoint_b.jump.eq(x.endpoint_a.jump),
                x.endpoint_b.branch.eq(x.endpoint_a.branch),
                x.endpoint_b.load.eq(x.endpoint_a.load),
                x.endpoint_b.store.eq(x.endpoint_a.store),
                x.endpoint_b.csr.eq(x.endpoint_a.csr),
                x.endpoint_b.csr_addr.eq(x.endpoint_a.csr_addr),
                x.endpoint_b.csr_we.eq(x.endpoint_a.csr_we),
                x.endpoint_b.divider.eq(x.endpoint_a.divider),
                x.endpoint_b.result.eq(x_result),
                x.endpoint_b.ls_addr.eq(x_ls_addr),
                x.endpoint_b.zero.eq(adder.result == 0),
                x.endpoint_b.overflow.eq(adder.overflow),
                x.endpoint_b.negative.eq(adder.result[-1]),
                x.endpoint_b.carry.eq(adder.carry),
                x.endpoint_b.jb_target.eq(x_jb_target),
                x.endpoint_b.fetch_error.eq(x.endpoint_a.fetch_error),
                x.endpoint_b.ecall.eq(x.endpoint_a.ecall),
                x.endpoint_b.ebreak.eq(x_ebreak),
                x.endpoint_b.mret.eq(x.endpoint_a.mret),
                x.endpoint_b.illegal.eq(x.endpoint_a.illegal),
                x.endpoint_b.ls_misalign.eq(data_sel.x_misaligned),
                x.endpoint_b.prediction.eq(x.endpoint_a.prediction),
                x.endpoint_b.prediction_state.eq(x.endpoint_a.prediction_state),
            ]

        # M -> W
        cpu.d.sync += [
            m.endpoint_b.pc.eq(m.endpoint_a.pc),
            m.endpoint_b.gpr_rd.eq(m.endpoint_a.gpr_rd),
            m.endpoint_b.gpr_rd_is_nzero.eq(m.endpoint_a.gpr_rd_is_nzero),
            m.endpoint_b.gpr_we.eq(m.endpoint_a.gpr_we),
            m.endpoint_b.result.eq(m_result),
            m.endpoint_b.ld_result.eq(data_sel.m_load_data),
            m.endpoint_b.csr_result.eq(csr.port.dat_r),
            m.endpoint_b.load.eq(m.endpoint_a.load),
            m.endpoint_b.csr.eq(m.endpoint_a.csr)
        ]

        return cpu
