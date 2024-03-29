from amaranth import Mux
from amaranth import Signal
from amaranth import Module
from amaranth import Memory
from amaranth import Elaboratable
from amaranth.build import Platform
from amaranth_soc.wishbone.bus import Interface
from typing import List
from bellatrix.gateware.csr import CSRFile
from bellatrix.gateware.stage import Stage
from bellatrix.gateware.adder import AdderUnit
from bellatrix.gateware.logic import LogicUnit
from bellatrix.gateware.compare import CompareUnit
from bellatrix.gateware.shifter import ShifterUnit
from bellatrix.gateware.fetch import BasicFetchUnit
from bellatrix.gateware.fetch import CachedFetchUnit
from bellatrix.gateware.lsu import BasicLSU
from bellatrix.gateware.lsu import DataFormat
from bellatrix.gateware.lsu import CachedLSU
from bellatrix.gateware.layout import _af_layout
from bellatrix.gateware.layout import _fd_layout
from bellatrix.gateware.layout import _dx_layout
from bellatrix.gateware.layout import _xm_layout
from bellatrix.gateware.layout import _mw_layout
from bellatrix.gateware.exception import ExceptionUnit
from bellatrix.gateware.decoder import DecoderUnit
from bellatrix.gateware.multiplier import Multiplier
from bellatrix.gateware.divider import Divider
from bellatrix.gateware.predictor import BranchPredictor
from bellatrix.gateware.debug.trigger import TriggerModule


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
                 # Data cache
                 dcache_enable: bool = False,
                 dcache_nlines: int = 128,
                 dcache_nwords: int = 8,
                 dcache_nways: int = 1,
                 dcache_start: int = 0x8000_0000,
                 dcache_end: int = 0xffff_ffff,
                 # trigger module
                 trigger_enable: bool = False,
                 trigger_ntriggers: int = 4
                 ) -> None:
        # ----------------------------------------------------------------------
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
        self.dcache_enable     = dcache_enable
        self.dcache_nlines     = dcache_nlines
        self.dcache_nwords     = dcache_nwords
        self.dcache_nways      = dcache_nways
        self.dcache_start      = dcache_start
        self.dcache_end        = dcache_end
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
        self.dcache_kwargs = dict(nlines=self.dcache_nlines,
                                  nwords=self.dcache_nwords,
                                  nways=self.dcache_nways,
                                  start_addr=self.dcache_start,
                                  end_addr=self.dcache_end)
        # ----------------------------------------------------------------------
        i_features = ['err']
        if self.icache_enable:
            i_features.extend(['cti', 'bte'])
        d_features = ['err']
        if self.icache_enable:
            d_features.extend(['cti', 'bte'])
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
        a = cpu.submodules.a = Stage('A', None,       _af_layout)
        f = cpu.submodules.f = Stage('F', _af_layout, _fd_layout)
        d = cpu.submodules.d = Stage('D', _fd_layout, _dx_layout)
        x = cpu.submodules.x = Stage('X', _dx_layout, _xm_layout)
        m = cpu.submodules.m = Stage('M', _xm_layout, _mw_layout)
        w = cpu.submodules.w = Stage('W', _mw_layout, None)
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
        decoder   = cpu.submodules.decoder   = DecoderUnit(self.enable_rv32m)
        exception = cpu.submodules.exception = ExceptionUnit(**self.exception_unit_kw)
        data_sel  = cpu.submodules.data_sel  = DataFormat()
        csr       = cpu.submodules.csr       = CSRFile()
        if self.icache_enable:
            fetch = cpu.submodules.fetch = CachedFetchUnit(**self.icache_kwargs)
            # connect the data port to the "internal snoop bus"
            # TODO need to change the name...
            cpu.d.comb += [
                fetch.dcache_snoop.addr.eq(self.dport.adr),
                fetch.dcache_snoop.we.eq(self.dport.we),
                fetch.dcache_snoop.valid.eq(self.dport.cyc),
                fetch.dcache_snoop.ack.eq(self.dport.ack)
            ]
        else:
            fetch = cpu.submodules.fetch = BasicFetchUnit()
        if self.dcache_enable:
            lsu = cpu.submodules.lsu = CachedLSU(**self.dcache_kwargs)
        else:
            lsu = cpu.submodules.lsu = BasicLSU()
        if self.enable_rv32m:
            multiplier = cpu.submodules.multiplier = Multiplier()
            divider    = cpu.submodules.divider    = Divider()
        if self.predictor_enable:
            predictor = cpu.submodules.predictor = BranchPredictor(self.predictor_size)
        if self.trigger_enable:
            trigger = cpu.submodules.trigger = TriggerModule(privmode=exception.m_privmode,
                                                             ntriggers=self.trigger_ntriggers,
                                                             enable_user_mode=self.enable_user_mode)
        # ----------------------------------------------------------------------
        # register file (GPR)
        gprf     = Memory(width=32, depth=32)
        gprf_rp1 = gprf.read_port()
        gprf_rp2 = gprf.read_port()
        gprf_wp  = gprf.write_port()
        cpu.submodules += gprf_rp1, gprf_rp2, gprf_wp
        # ----------------------------------------------------------------------
        # CSR
        csr.add_csr_from_list(exception.get_csrs())
        if self.trigger_enable:
            csr.add_csr_from_list(trigger.get_csrs())
        csr_port = csr.create_port()
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
        a.endpoint_b.pc.reset = self.reset_address - 4

        # select next pc
        with cpu.If(exception.m_exception & m.valid):
            cpu.d.comb += a_next_pc.eq(exception.mtvec.read)  # exception
        with cpu.Elif(m.endpoint_a.mret & m.valid):
            cpu.d.comb += a_next_pc.eq(exception.mepc.read)  # mret

        if self.predictor_enable:
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

        # If the pipeline requires a flush and the fetch unit is busy
        # latch the kill signal, so the other stages does not wait for
        # a free FU
        f_kill_r = Signal()

        with cpu.If(f.stall):
            with cpu.If(f_kill_r == 0):
                cpu.d.sync += f_kill_r.eq(f.kill)
        with cpu.Else():
            cpu.d.sync += f_kill_r.eq(0)

        if self.icache_enable:
            cpu.d.comb += fetch.f_pc.eq(f.endpoint_a.pc)
            # TODO: create a (custom) CSR so we can flush the cache in software (?)
            # fetch.flush.eq(x.endpoint_a.fence_i & x.valid & ~x.stall),

        f.add_kill_source(f_kill_r)
        f.add_stall_source(fetch.f_busy)
        f.add_kill_source(exception.m_exception & m.valid)
        f.add_kill_source(m.endpoint_a.mret & m.valid)
        f.add_kill_source(m_kill_bj)
        f.add_kill_source(x.endpoint_a.fence_i & x.valid & ~x.stall)
        # ----------------------------------------------------------------------
        # Decode Stage
        cpu.d.comb += [
            decoder.instruction.eq(d.endpoint_a.instruction),
            decoder.privmode.eq(exception.m_privmode)
        ]

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

        d.add_stall_source(((fwd_x_rs1 & decoder.gpr_rs1_use) | (fwd_x_rs2 & decoder.gpr_rs2_use)) & ~x.endpoint_a.needed_in_x & x.valid & d.valid)
        d.add_stall_source(((fwd_m_rs1 & decoder.gpr_rs1_use) | (fwd_m_rs2 & decoder.gpr_rs2_use)) & ~m.endpoint_a.needed_in_m & m.valid & d.valid)
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
        if self.enable_rv32m:
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

        x_valid = x.valid
        if self.trigger_enable:
            x_valid = x.valid & ~trigger.trap

        cpu.d.comb += [
            lsu.x_addr.eq(adder.result),
            lsu.x_data_w.eq(data_sel.x_data_w),
            lsu.x_store.eq(x.endpoint_a.store),
            lsu.x_load.eq(x.endpoint_a.load),
            lsu.x_byte_sel.eq(data_sel.x_byte_sel),
            lsu.x_valid.eq(x_valid & ~data_sel.x_misaligned),
            lsu.x_stall.eq(x.stall)
        ]
        if self.dcache_enable:
            cpu.d.comb += [
                lsu.x_fence.eq(x.valid & x.endpoint_a.fence),
                lsu.x_fence_i.eq(x.valid & x.endpoint_a.fence_i)
            ]
            # the first stall is for the first cycle of the new store
            # the second stall is for the data stored in the write buffer: we have to wait
            x.add_stall_source(x.valid & (x.endpoint_a.fence_i | x.endpoint_a.fence) & m.valid & m.endpoint_a.store)
            x.add_stall_source(x.valid & lsu.x_busy)
        if self.enable_rv32m:
            x.add_stall_source(x.valid & x.endpoint_a.multiplier & ~multiplier.ready)

        # ebreak logic
        x_ebreak = x.endpoint_a.ebreak
        if self.trigger_enable:
            x_ebreak = x_ebreak | trigger.trap

        x.add_kill_source(exception.m_exception & m.valid)
        x.add_kill_source(m.endpoint_a.mret & m.valid)
        x.add_kill_source(m_kill_bj)
        # ----------------------------------------------------------------------
        # Memory (and CSR) Stage
        csr_wdata = Signal(32)

        # jump/branch
        if self.predictor_enable:
            cpu.d.comb += m_kill_bj.eq(((m.endpoint_a.prediction & m.endpoint_a.branch) ^ m.endpoint_a.take_jmp_branch) & m.valid)
        else:
            cpu.d.comb += m_kill_bj.eq(m.endpoint_a.take_jmp_branch & m.valid)

        cpu.d.comb += lsu.dport.connect(self.dport)  # connect the wishbone port

        # select result
        with cpu.If(m.endpoint_a.shifter):
            cpu.d.comb += m_result.eq(shifter.result)
        with cpu.Elif(m.endpoint_a.compare):
            cpu.d.comb += m_result.eq(m.endpoint_a.compare_result)
        if self.enable_rv32m:
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
        if self.dcache_enable:
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
            cpu.d.comb += csr_wdata.eq(csr_port.data_r | csr_src)
        with cpu.Else():  # clear
            cpu.d.comb += csr_wdata.eq(csr_port.data_r & csr_src)

        # csr
        cpu.d.comb += [
            csr_port.addr.eq(m.endpoint_a.csr_addr),
            csr_port.en.eq(m.endpoint_a.csr_we & m.valid),
            csr_port.data_w.eq(csr_wdata)
        ]
        cpu.d.comb += csr.privmode.eq(exception.m_privmode)

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
            exception.m_valid.eq(m.valid)
        ]
        m.add_stall_source(m.valid & lsu.m_busy)
        if self.enable_rv32m:
            m.add_stall_source(divider.busy)
        m.add_kill_source(exception.m_exception & m.valid)
        # ----------------------------------------------------------------------
        # Write-back stage
        if self.enable_extra_csr:
            cpu.d.comb += exception.w_retire.eq(w.is_instruction)  # use the stage's signal

        with cpu.If(w.endpoint_a.load):
            cpu.d.comb += w_result.eq(w.endpoint_a.ld_result)
        with cpu.Elif(w.endpoint_a.csr):
            cpu.d.comb += w_result.eq(w.endpoint_a.csr_result)
        with cpu.Else():
            cpu.d.comb += w_result.eq(w.endpoint_a.result)

        # ----------------------------------------------------------------------
        # Optional units: Multiplier/Divider
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
                divider.start.eq(x.endpoint_a.divider)
            ]
        # ----------------------------------------------------------------------
        # Optional units: branch predictor
        if self.predictor_enable:
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
            if self.predictor_enable:
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
                d.endpoint_b.fence.eq(decoder.fence),
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
                x.endpoint_b.ebreak.eq(x_ebreak),
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
                m.endpoint_b.csr_result.eq(csr_port.data_r),
                m.endpoint_b.load.eq(m.endpoint_a.load),
                m.endpoint_b.csr.eq(m.endpoint_a.csr)
            ]

        return cpu
