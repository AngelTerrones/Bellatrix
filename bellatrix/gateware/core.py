from nmigen import Mux
from nmigen import Cat
from nmigen import Signal
from nmigen import Module
from nmigen import Memory
from nmigen import Elaboratable
from nmigen.build import Platform
from nmigen_soc.wishbone.bus import Interface
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
        if self.dcache_enable:
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
        csr       = cpu.submodules.csr       = CSRFile()
        exception = cpu.submodules.exception = ExceptionUnit(csr, **self.exception_unit_kw)
        data_sel  = cpu.submodules.data_sel  = DataFormat()
        if self.icache_enable:
            fetch = cpu.submodules.fetch = CachedFetchUnit(**self.icache_kwargs)
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
        # Address Stage
        a_pc = Signal(32)
        # reset value
        a.endpoint_b.pc.reset = self.reset_address
        # select the next pc
        with cpu.If(exception.m_exception):
            cpu.d.comb += a_pc.eq(exception.mtvec.read)  # exception
        with cpu.Elif(m.endpoint_a.mret):
            cpu.d.comb += a_pc.eq(exception.mepc.read)  # mret
        # ****************************************
        if self.predictor_enable:
            with cpu.Elif(m.endpoint_a.prediction & ~m_take_jb):
                cpu.d.comb += a_pc.eq(m.endpoint_a.pc + 4)  # branch not taken
            with cpu.Elif(~m.endpoint_a.prediction & m_take_jb):
                cpu.d.comb += a_pc.eq(m.endpoint_a.jb_target)  # branck taken
            with cpu.Elif(predictor.f_prediction):
                cpu.d.comb += a_pc.eq(predictor.f_prediction_pc + 4)  # prediction
        else:
            with cpu.Elif(m_take_jb):
                cpu.d.comb += a_pc.eq(m.endpoint_a.jb_target)  # jmp/branch
        # ****************************************
        with cpu.Elif(x.endpoint_a.fence_i):
            cpu.d.comb += a_pc.eq(x.endpoint_a.pc + 4)  # fence_i.
        with cpu.Else():
            cpu.d.comb += a_pc.eq(f.endpoint_a.pc + 4)

        a.add_kill_source(m_kill_jb)
        a.add_kill_source(x.endpoint_a.fence_i & ~x.stall)
        a.add_kill_source(exception.m_exception)
        a.add_kill_source(m.endpoint_a.mret)
        # ----------------------------------------------------------------------
        # Fetch Stage
        cpu.d.comb += fetch.iport.connect(self.iport)
        cpu.d.comb += [
            fetch.f_pc.eq(f.endpoint_a.pc),
            fetch.f_kill.eq(f.kill),
            fetch.d_stall.eq(d.stall)
        ]
        if self.predictor_enable:
            with cpu.If(predictor.f_prediction & f.valid):
                cpu.d.comb += fetch.f_pc.eq(predictor.f_prediction_pc)
            with cpu.Else():
                cpu.d.comb += fetch.f_pc.eq(f.endpoint_a.pc)

        if self.icache_enable:
            flush_icache = x.endpoint_a.fence_i
            cpu.d.comb += fetch.flush.eq(flush_icache)

        f.add_stall_source(fetch.f_busy)
        f.add_kill_source(m_kill_jb)
        f.add_kill_source(x.endpoint_a.fence_i & ~x.stall)
        f.add_kill_source(exception.m_exception)
        f.add_kill_source(m.endpoint_a.mret)
        # ----------------------------------------------------------------------
        # Decode Stage
        cpu.d.comb += [
            decoder.instruction.eq(d.endpoint_a.instruction),
            decoder.instruction2.eq(d.endpoint_a.instruction2),
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
                    gprf_rp1.addr.eq(fetch.f_instruction[15:20]),
                    gprf_rp2.addr.eq(fetch.f_instruction[20:25])
                ]

        cpu.d.comb += [
            gprf_wp.addr.eq(w.endpoint_a.gpr_rd),
            gprf_wp.data.eq(w_result),
            gprf_wp.en.eq(w.endpoint_a.gpr_we)
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
            fwd_x_rs1.eq((decoder.gpr_rs1 == x.endpoint_a.gpr_rd) & decoder.gpr_rs1.any() & x.endpoint_a.gpr_we),
            fwd_m_rs1.eq((decoder.gpr_rs1 == m.endpoint_a.gpr_rd) & decoder.gpr_rs1.any() & m.endpoint_a.gpr_we),
            fwd_w_rs1.eq((decoder.gpr_rs1 == w.endpoint_a.gpr_rd) & decoder.gpr_rs1.any() & w.endpoint_a.gpr_we),

            fwd_x_rs2.eq((decoder.gpr_rs2 == x.endpoint_a.gpr_rd) & decoder.gpr_rs2.any() & x.endpoint_a.gpr_we),
            fwd_m_rs2.eq((decoder.gpr_rs2 == m.endpoint_a.gpr_rd) & decoder.gpr_rs2.any() & m.endpoint_a.gpr_we),
            fwd_w_rs2.eq((decoder.gpr_rs2 == w.endpoint_a.gpr_rd) & decoder.gpr_rs2.any() & w.endpoint_a.gpr_we),
        ]

        bubble_x = (x.endpoint_a.needed_in_m | x.endpoint_a.needed_in_w)
        bubble_m = m.endpoint_a.needed_in_w
        d.add_stall_source(((fwd_x_rs1 & decoder.gpr_rs1_use) | (fwd_x_rs2 & decoder.gpr_rs2_use)) & bubble_x)
        d.add_stall_source(((fwd_m_rs1 & decoder.gpr_rs1_use) | (fwd_m_rs2 & decoder.gpr_rs2_use)) & bubble_m)
        d.add_kill_source(m_kill_jb)
        d.add_kill_source(x.endpoint_a.fence_i & ~x.stall)
        d.add_kill_source(exception.m_exception)
        d.add_kill_source(m.endpoint_a.mret)
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
            logic.dat1.eq(x.endpoint_a.src_data1b),
            logic.dat2.eq(x.endpoint_a.src_data2b)
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
        x_ls_addr = Signal(32)
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
            lsu.x_enable.eq(~data_sel.x_misaligned & ~x.kill)
        ]
        if self.trigger_enable:
            cpu.d.comb += lsu.x_enable.eq(~trigger.trap & ~data_sel.x_misaligned & ~x.kill)

        # ebreak logic
        x_ebreak = x.endpoint_a.ebreak
        if self.trigger_enable:
            x_ebreak = x_ebreak | trigger.trap

        # stall/kill sources
        if self.dcache_enable:
            cpu.d.comb += [
                lsu.x_fence.eq(x.endpoint_a.fence),
                lsu.x_fence_i.eq(x.endpoint_a.fence_i)  # x.valid
            ]
            # the first stall is for the first cycle of the new store
            # the second stall is for the data stored in the write buffer: we have to wait
            x.add_stall_source((x.endpoint_a.fence_i | x.endpoint_a.fence) & m.endpoint_a.store)  # x.xalid/m.valid
            x.add_stall_source(lsu.x_busy)
        if self.enable_rv32m:
            x.add_stall_source(x.endpoint_a.multiplier & ~multiplier.ready)
        x.add_kill_source(m_kill_jb)
        x.add_kill_source(exception.m_exception)
        x.add_kill_source(m.endpoint_a.mret)
        # ----------------------------------------------------------------------
        # Memory/CSR Stage
        csr_wdata = Signal(32)

        cpu.d.comb += [
            compare.op.eq(m.endpoint_a.funct3),
            compare.zero.eq(m.endpoint_a.zero),
            compare.zero2.eq(m.endpoint_a.zero2),
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
        cpu.d.comb += lsu.m_stall.eq(m.stall)

        if self.dcache_enable:
            cpu.d.comb += [
                lsu.m_addr.eq(m.endpoint_a.ls_addr),
                lsu.m_load.eq(m.endpoint_a.load),
                lsu.m_store.eq(m.endpoint_a.store)
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
            csr.port.valid.eq(m.endpoint_a.csr),
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
            exception.m_load_store_badaddr.eq(lsu.m_badaddr),  # TODO use m.endpoint_a.ls_addr
            exception.m_store.eq(m.endpoint_a.store),
            exception.m_valid.eq(m.valid)
        ]
        if self.enable_rv32m:
            m.add_stall_source(divider.busy)
        m.add_stall_source(lsu.m_busy)
        m.add_stall_source(m.endpoint_a.csr & ~csr.port.ok)
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
                multiplier.valid.eq(x.endpoint_a.multiplier)
            ]
            cpu.d.comb += [
                divider.op.eq(x.endpoint_a.funct3),
                divider.dat1.eq(x.endpoint_a.src_data1),
                divider.dat2.eq(x.endpoint_a.src_data2),
                divider.stall.eq(x.stall),
                divider.start.eq(x.endpoint_a.divider)
            ]
        # ----------------------------------------------------------------------
        # Optional unit: branch predictor
        if self.predictor_enable:
            cpu.d.comb += [
                predictor.f_pc.eq(f.endpoint_a.pc),
                predictor.f_stall.eq(f.stall),
                predictor.f2_pc.eq(fetch.f2_pc),
                predictor.m_prediction_state.eq(m.endpoint_a.prediction_state),
                predictor.m_take_jmp_branch.eq(m_take_jb),
                predictor.m_pc.eq(m.endpoint_a.pc),
                predictor.m_target_pc.eq(m.endpoint_a.jb_target),
                predictor.m_update.eq(m.endpoint_a.branch)
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
        # A -> F
        with cpu.If(~a.stall | f.kill):
            cpu.d.sync += a.endpoint_b.pc.eq(a_pc)

        # F -> D
        f.endpoint_b.instruction.reset = 0x00000013
        f.endpoint_b.instruction2.reset = 0x00000013
        with cpu.If(f.kill):
            cpu.d.sync += [
                f.endpoint_b.instruction.eq(0x00000013),
                f.endpoint_b.instruction2.eq(0x00000013),
                f.endpoint_b.fetch_error.eq(0)
            ]
        with cpu.Elif(~f.stall):
            cpu.d.sync += [
                f.endpoint_b.pc.eq(fetch.f2_pc),
                f.endpoint_b.instruction.eq(fetch.f_instruction),
                f.endpoint_b.instruction2.eq(fetch.f_instruction),
                f.endpoint_b.fetch_error.eq(fetch.f_bus_error)
            ]
            if self.predictor_enable:
                cpu.d.sync += [
                    f.endpoint_b.prediction.eq(predictor.f_prediction),
                    f.endpoint_b.prediction_state.eq(predictor.f_prediction_state)
                ]
        with cpu.Elif(~d.stall):
            cpu.d.sync += [
                f.endpoint_b.instruction.eq(0x00000013),
                f.endpoint_b.instruction2.eq(0x00000013),
                f.endpoint_b.fetch_error.eq(0)
            ]

        # D -> X
        with cpu.If(d.kill):
            cpu.d.sync += [
                d.endpoint_b.gpr_we.eq(0),
                d.endpoint_b.jump.eq(0),
                d.endpoint_b.branch.eq(0),
                d.endpoint_b.load.eq(0),
                d.endpoint_b.store.eq(0),
                d.endpoint_b.csr.eq(0),
                d.endpoint_b.fence_i.eq(0),
                d.endpoint_b.fence.eq(0),
                d.endpoint_b.multiplier.eq(0),
                d.endpoint_b.divider.eq(0),
                d.endpoint_b.csr_we.eq(0),
                d.endpoint_b.fetch_error.eq(0),
                d.endpoint_b.ecall.eq(0),
                d.endpoint_b.ebreak.eq(0),
                d.endpoint_b.mret.eq(0),
                d.endpoint_b.illegal.eq(0),
                d.endpoint_b.prediction.eq(0),
                d.endpoint_b.needed_in_m.eq(0),
                d.endpoint_b.needed_in_w.eq(0)
            ]
        with cpu.Elif(~d.stall):
            cpu.d.sync += [
                d.endpoint_b.pc.eq(d.endpoint_a.pc),
                d.endpoint_b.instruction.eq(d.endpoint_a.instruction),
                d.endpoint_b.gpr_rd.eq(decoder.gpr_rd),
                d.endpoint_b.gpr_we.eq(decoder.gpr_we),
                d.endpoint_b.src_data1.eq(rs1_data),
                d.endpoint_b.src_data2.eq(rs2_data),
                d.endpoint_b.src_data1b.eq(rs1_data),
                d.endpoint_b.src_data2b.eq(rs2_data),
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
                d.endpoint_b.shift_sign.eq(decoder.shit_signed),
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
        with cpu.Elif(~x.stall):
            cpu.d.sync += [
                d.endpoint_b.needed_in_m.eq(0),
                d.endpoint_b.needed_in_w.eq(0),
                d.endpoint_b.gpr_we.eq(0),
                d.endpoint_b.load.eq(0),
                d.endpoint_b.store.eq(0),
                d.endpoint_b.fence_i.eq(0),
                d.endpoint_b.fence.eq(0),
            ]

        # X -> M
        with cpu.If(x.kill):
            cpu.d.sync += [
                x.endpoint_b.gpr_we.eq(0),
                x.endpoint_b.needed_in_w.eq(0),
                x.endpoint_b.compare.eq(0),
                x.endpoint_b.shifter.eq(0),
                x.endpoint_b.jump.eq(0),
                x.endpoint_b.branch.eq(0),
                x.endpoint_b.load.eq(0),
                x.endpoint_b.store.eq(0),
                x.endpoint_b.csr.eq(0),
                x.endpoint_b.divider.eq(0),
                x.endpoint_b.fetch_error.eq(0),
                x.endpoint_b.ecall.eq(0),
                x.endpoint_b.ebreak.eq(0),
                x.endpoint_b.mret.eq(0),
                x.endpoint_b.illegal.eq(0),
                x.endpoint_b.ls_misalign.eq(0),
                x.endpoint_b.prediction.eq(0),
                x.endpoint_b.needed_in_w.eq(0)
            ]
        with cpu.Elif(~x.stall):
            cpu.d.sync += [
                x.endpoint_b.pc.eq(x.endpoint_a.pc),
                x.endpoint_b.instruction.eq(x.endpoint_a.instruction),
                x.endpoint_b.gpr_rd.eq(x.endpoint_a.gpr_rd),
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
                x.endpoint_b.zero2.eq(adder.result == 0),
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
        with cpu.Elif(~m.stall):
            cpu.d.sync += [
                x.endpoint_b.needed_in_w.eq(0),
                x.endpoint_b.gpr_we.eq(0),
                x.endpoint_b.load.eq(0),
                x.endpoint_b.store.eq(0),
            ]

        # M -> W
        with cpu.If(m.kill):
            cpu.d.sync += m.endpoint_b.gpr_we.eq(0)
        with cpu.Elif(~m.stall):
            cpu.d.sync += [
                m.endpoint_b.pc.eq(m.endpoint_a.pc),
                m.endpoint_b.gpr_rd.eq(m.endpoint_a.gpr_rd),
                m.endpoint_b.gpr_we.eq(m.endpoint_a.gpr_we),
                m.endpoint_b.result.eq(m_result),
                m.endpoint_b.ld_result.eq(data_sel.m_load_data),
                m.endpoint_b.csr_result.eq(csr.port.dat_r),
                m.endpoint_b.load.eq(m.endpoint_a.load),
                m.endpoint_b.csr.eq(m.endpoint_a.csr)
            ]

        return cpu
