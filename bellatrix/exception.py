from nmigen import Cat
from nmigen import Module
from nmigen import Signal
from nmigen import Elaboratable
from nmigen.lib.coding import PriorityEncoder
from nmigen.build import Platform
from bellatrix.csr import CSR
from bellatrix.csr import AutoCSR
from bellatrix.isa import CSRIndex
from bellatrix.isa import ExceptionCause
from bellatrix.isa import misa_layout, mstatus_layout, mie_layout, mtvec_layout
from bellatrix.isa import mepc_layout, mcause_layout, mip_layout, basic_layout
from bellatrix.isa import PrivMode


class ExceptionUnit(Elaboratable, AutoCSR):
    def __init__(self,
                 enable_rv32m: bool,
                 enable_extra_csr: bool,
                 enable_user_mode: bool
                 ) -> None:
        # ----------------------------------------------------------------------
        self.enable_user_mode = enable_user_mode
        self.enable_extra_csr = enable_extra_csr
        self.enable_rv32m     = enable_rv32m
        # ----------------------------------------------------------------------
        if enable_extra_csr:
            self.misa      = CSR(CSRIndex.MISA, 'misa', misa_layout)
            self.mhartid   = CSR(CSRIndex.MHARTID, 'mhartid', basic_layout)
            self.mimpid    = CSR(CSRIndex.MIMPID, 'mimpid', basic_layout)
            self.marchid   = CSR(CSRIndex.MARCHID, 'marchid', basic_layout)
            self.mvendorid = CSR(CSRIndex.MVENDORID, 'mvendorid', basic_layout)
            self.minstret  = CSR(CSRIndex.MINSTRET, 'minstret', basic_layout)
            self.mcycle    = CSR(CSRIndex.MCYCLE, 'mcycle', basic_layout)
            self.minstreth = CSR(CSRIndex.MINSTRETH, 'minstreth', basic_layout)
            self.mcycleh   = CSR(CSRIndex.MCYCLEH, 'mcycleh', basic_layout)
            if enable_user_mode:
                self.instret  = CSR(CSRIndex.INSTRET, 'instret', basic_layout)
                self.cycle    = CSR(CSRIndex.CYCLE, 'cycle', basic_layout)
                self.instreth = CSR(CSRIndex.INSTRETH, 'instreth', basic_layout)
                self.cycleh   = CSR(CSRIndex.CYCLEH, 'cycleh', basic_layout)
        self.mstatus   = CSR(CSRIndex.MSTATUS, 'mstatus', mstatus_layout)
        self.mie       = CSR(CSRIndex.MIE, 'mie', mie_layout)
        self.mtvec     = CSR(CSRIndex.MTVEC, 'mtvec', mtvec_layout)
        self.mscratch  = CSR(CSRIndex.MSCRATCH, 'mscratch', basic_layout)
        self.mepc      = CSR(CSRIndex.MEPC, 'mepc', mepc_layout)
        self.mcause    = CSR(CSRIndex.MCAUSE, 'mcause', mcause_layout)
        self.mtval     = CSR(CSRIndex.MTVAL, 'mtval', basic_layout)
        self.mip       = CSR(CSRIndex.MIP, 'mip', mip_layout)
        # ----------------------------------------------------------------------
        self.external_interrupt   = Signal()    # input
        self.software_interrupt   = Signal()    # input
        self.timer_interrupt      = Signal()    # input
        self.m_fetch_misalign     = Signal()    # input
        self.m_fetch_error        = Signal()    # input
        self.m_illegal            = Signal()    # input
        self.m_load_misalign      = Signal()    # input
        self.m_load_error         = Signal()    # input
        self.m_store_misalign     = Signal()    # input
        self.m_store_error        = Signal()    # input
        self.m_ecall              = Signal()    # input
        self.m_ebreak             = Signal()    # input
        self.m_mret               = Signal()    # input
        self.m_pc                 = Signal(32)  # input
        self.m_instruction        = Signal(32)  # input
        self.m_fetch_badaddr      = Signal(32)  # input
        self.m_pc_misalign        = Signal(32)  # input
        self.m_ls_misalign        = Signal(32)  # input
        self.m_load_store_badaddr = Signal(32)  # input
        self.m_store              = Signal()    # input
        self.m_valid              = Signal()    # input
        self.m_exception          = Signal()    # output
        self.m_privmode           = Signal(PrivMode)   # output
        if self.enable_extra_csr:
            self.w_retire = Signal()

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        privmode = Signal(PrivMode)
        privmode.reset = PrivMode.Machine  # default mode is Machine

        m.d.comb += self.m_privmode.eq(privmode)

        # Read/write behavior for all registers
        for reg in self.get_csrs():
            with m.If(reg.we):
                m.d.sync += reg.read.eq(reg.write)

        # constants (at least, the important ones)
        if self.enable_extra_csr:
            misa = 0x1 << 30 | (1 << (ord('i') - ord('a')))  # 32-bits processor. RV32I
            if self.enable_rv32m:
                misa |= 1 << (ord('m') - ord('a'))  # RV32M
            if self.enable_user_mode:
                misa |= 1 << (ord('u') - ord('a'))  # User mode enabled

            m.d.sync += [
                self.misa.read.eq(misa),
                self.mhartid.read.eq(0),   # ID 0 FOREVER.
                self.mimpid.read.eq(0),    # No implemented = 0
                self.marchid.read.eq(0),   # No implemented = 0
                self.mvendorid.read.eq(0)  # No implemented = 0
            ]

        traps = m.submodules.traps = PriorityEncoder(ExceptionCause.MAX_NUM)
        m.d.comb += [
            traps.i[ExceptionCause.E_INST_ADDR_MISALIGNED].eq(self.m_fetch_misalign),
            traps.i[ExceptionCause.E_INST_ACCESS_FAULT].eq(self.m_fetch_error),
            traps.i[ExceptionCause.E_ILLEGAL_INST].eq(self.m_illegal),
            traps.i[ExceptionCause.E_BREAKPOINT].eq(self.m_ebreak),
            traps.i[ExceptionCause.E_LOAD_ADDR_MISALIGNED].eq(self.m_load_misalign),
            traps.i[ExceptionCause.E_LOAD_ACCESS_FAULT].eq(self.m_load_error),
            traps.i[ExceptionCause.E_STORE_AMO_ADDR_MISALIGNED].eq(self.m_store_misalign),
            traps.i[ExceptionCause.E_STORE_AMO_ACCESS_FAULT].eq(self.m_store_error),
            traps.i[ExceptionCause.E_ECALL_FROM_M].eq(self.m_ecall)
        ]

        interrupts = m.submodules.interrupts = PriorityEncoder(ExceptionCause.MAX_NUM)
        m.d.comb += [
            interrupts.i[ExceptionCause.I_M_SOFTWARE].eq(self.mip.read.msip & self.mie.read.msie),
            interrupts.i[ExceptionCause.I_M_TIMER].eq(self.mip.read.mtip & self.mie.read.mtie),
            interrupts.i[ExceptionCause.I_M_EXTERNAL].eq(self.mip.read.meip & self.mie.read.meie),
        ]

        # generate the exception/trap/interrupt signal to kill the pipeline
        # interrupts are globally enable for less priviledge mode than Machine
        m.d.comb += self.m_exception.eq(~traps.n | (~interrupts.n & (self.mstatus.read.mie | (privmode != PrivMode.Machine)) & ~self.m_store))

        # --------------------------------------------------------------------------------
        # overwrite values from the RW circuit
        # --------------------------------------------------------------------------------
        m.d.sync += [
            self.mip.read.msip.eq(self.software_interrupt),
            self.mip.read.mtip.eq(self.timer_interrupt),
            self.mip.read.meip.eq(self.external_interrupt)
        ]

        if self.enable_user_mode:
            self.mstatus.read.mpp.reset = PrivMode.User
            with m.If(self.mstatus.write.mpp != PrivMode.User):
                # In case of writting an invalid priviledge mode, force a valid one
                # For this case, anything different to the User mode is forced to Machine mode.
                m.d.sync += self.mstatus.read.mpp.eq(PrivMode.Machine)
        else:
            self.mstatus.read.mpp.reset = PrivMode.Machine
            m.d.sync += self.mstatus.read.mpp.eq(PrivMode.Machine)  # Only machine mode

        # Constant fields in MSTATUS
        # Disable because S-mode and User-level interrupts
        # are not supported.
        m.d.sync += [
            self.mstatus.read.uie.eq(0),
            self.mstatus.read.upie.eq(0),
            self.mstatus.read.sie.eq(0),
            self.mstatus.read.spie.eq(0),
            self.mstatus.read.spp.eq(0),
            self.mstatus.read.mxr.eq(0),
            self.mstatus.read.sum.eq(0),
            self.mstatus.read.tvm.eq(0),
            self.mstatus.read.tsr.eq(0),
            self.mstatus.read.fs.eq(0),
            self.mstatus.read.xs.eq(0),
            self.mstatus.read.sd.eq(0)
        ]
        # MIP and MIE
        m.d.sync += [
            self.mip.read.usip.eq(0),
            self.mip.read.ssip.eq(0),
            self.mip.read.utip.eq(0),
            self.mip.read.stip.eq(0),
            self.mip.read.ueip.eq(0),
            self.mip.read.seip.eq(0),
            self.mie.read.usie.eq(0),
            self.mie.read.ssie.eq(0),
            self.mie.read.utie.eq(0),
            self.mie.read.stie.eq(0),
            self.mie.read.ueie.eq(0),
            self.mie.read.seie.eq(0)
        ]

        # behavior for exception handling
        with m.If(self.m_valid):
            with m.If(self.m_exception):
                # Register the exception and move one priviledge mode down.
                m.d.sync += [
                    self.mepc.read.base.eq(self.m_pc[2:]),
                    self.mstatus.read.mpie.eq(self.mstatus.read.mie),
                    self.mstatus.read.mie.eq(0),

                    # Change priviledge mode
                    privmode.eq(PrivMode.Machine),
                    self.mstatus.read.mpp.eq(privmode)
                ]
                # store cause/mtval
                with m.If(~traps.n):
                    m.d.sync += [
                        self.mcause.read.ecode.eq(traps.o),
                        self.mcause.read.interrupt.eq(0)
                    ]
                    with m.Switch(traps.o):
                        with m.Case(ExceptionCause.E_INST_ADDR_MISALIGNED):
                            m.d.sync += self.mtval.read.eq(self.m_pc_misalign)
                        with m.Case(ExceptionCause.E_INST_ACCESS_FAULT):
                            m.d.sync += self.mtval.read.eq(self.m_fetch_badaddr)
                        with m.Case(ExceptionCause.E_ILLEGAL_INST):
                            m.d.sync += self.mtval.read.eq(self.m_instruction)
                        with m.Case(ExceptionCause.E_BREAKPOINT):
                            m.d.sync += self.mtval.read.eq(self.m_pc)
                        with m.Case(ExceptionCause.E_LOAD_ADDR_MISALIGNED, ExceptionCause.E_STORE_AMO_ADDR_MISALIGNED):
                            m.d.sync += self.mtval.read.eq(self.m_ls_misalign)
                        with m.Case(ExceptionCause.E_LOAD_ACCESS_FAULT, ExceptionCause.E_STORE_AMO_ACCESS_FAULT):
                            m.d.sync += self.mtval.read.eq(self.m_load_store_badaddr)
                        with m.Default():
                            m.d.sync += self.mtval.read.eq(0)

                with m.Else():
                    m.d.sync += [
                        self.mcause.read.ecode.eq(interrupts.o),
                        self.mcause.read.interrupt.eq(1)
                    ]
            with m.Elif(self.m_mret):
                # restore old mie
                # Restore priviledge mode
                m.d.sync += [
                    self.mstatus.read.mie.eq(self.mstatus.read.mpie),
                    privmode.eq(self.mstatus.read.mpp),
                ]
                if self.enable_user_mode:
                    m.d.sync += self.mstatus.read.mpp.eq(PrivMode.User)

        # counters
        if self.enable_extra_csr:
            mcycle   = Signal(64)
            minstret = Signal(64)

            m.d.sync += [
                self.mcycle.read.eq(mcycle[:32]),
                self.mcycleh.read.eq(mcycle[32:64]),
                #
                self.minstret.read.eq(minstret[:32]),
                self.minstreth.read.eq(minstret[32:64])
            ]

            m.d.comb += mcycle.eq(Cat(self.mcycle.read, self.mcycleh.read) + 1)
            with m.If(self.w_retire):
                m.d.comb += minstret.eq(Cat(self.minstret.read, self.minstreth.read) + 1)
            with m.Else():
                m.d.comb += minstret.eq(Cat(self.minstret.read, self.minstreth.read))

            # shadow versions of MCYCLE and MINSTRET
            if self.enable_user_mode:
                m.d.sync += [
                    self.cycle.read.eq(mcycle[:32]),
                    self.cycleh.read.eq(mcycle[32:64]),
                    #
                    self.instret.read.eq(minstret[:32]),
                    self.instreth.read.eq(minstret[32:64])
                ]

        return m
