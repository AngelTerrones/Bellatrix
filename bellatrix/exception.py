from nmigen import Cat
from nmigen import Module
from nmigen import Signal
from nmigen import Elaboratable
from nmigen.lib.coding import PriorityEncoder
from .csr import CSR
from .isa import CSRIndex
from .isa import ExceptionCause
from .isa import misa_layout, mstatus_layout, mie_layout, mtvec_layout
from .isa import mepc_layout, mcause_layout, mip_layout, basic_layout
from .isa import PrivMode


class ExceptionCSR:
    def __init__(self, extra_csr=False):
        if extra_csr:
            self.misa      = CSR(CSRIndex.MISA, 'misa', misa_layout)
            self.mhartid   = CSR(CSRIndex.MHARTID, 'mhartid', basic_layout)
            self.mimpid    = CSR(CSRIndex.MIMPID, 'mimpid', basic_layout)
            self.marchid   = CSR(CSRIndex.MARCHID, 'marchid', basic_layout)
            self.mvendorid = CSR(CSRIndex.MVENDORID, 'mvendorid', basic_layout)
            self.minstret  = CSR(CSRIndex.MINSTRET, 'minstret', basic_layout)
            self.mcycle    = CSR(CSRIndex.MCYCLE, 'mcycle', basic_layout)
            self.minstreth = CSR(CSRIndex.MINSTRETH, 'minstreth', basic_layout)
            self.mcycleh   = CSR(CSRIndex.MCYCLEH, 'mcycleh', basic_layout)
        self.mstatus   = CSR(CSRIndex.MSTATUS, 'mstatus', mstatus_layout)
        self.mie       = CSR(CSRIndex.MIE, 'mie', mie_layout)
        self.mtvec     = CSR(CSRIndex.MTVEC, 'mtvec', mtvec_layout)
        self.mscratch  = CSR(CSRIndex.MSCRATCH, 'mscratch', basic_layout)
        self.mepc      = CSR(CSRIndex.MEPC, 'mepc', mepc_layout)
        self.mcause    = CSR(CSRIndex.MCAUSE, 'mcause', mcause_layout)
        self.mtval     = CSR(CSRIndex.MTVAL, 'mtval', basic_layout)
        self.mip       = CSR(CSRIndex.MIP, 'mip', mip_layout)

        self.csr_list = [
            self.mstatus, self.mie, self.mtvec, self.mscratch,
            self.mepc, self.mcause, self.mtval, self.mip
        ]
        if extra_csr:
            self.csr_list += [self.misa, self.mhartid, self.mimpid, self.marchid, self.mvendorid]
            self.csr_list += [self.minstret, self.mcycle, self.minstreth, self.mcycleh]


class ExceptionUnit(Elaboratable):
    def __init__(self, configuration):
        self.usermode  = configuration.getOption('isa', 'enable_user_mode')
        self.extra_csr = configuration.getOption('isa', 'enable_extra_csr')
        self.rv32m     = configuration.getOption('isa', 'enable_rv32m')

        self.csr = ExceptionCSR(self.extra_csr)

        self.external_interrupt   = Signal()
        self.software_interrupt   = Signal()
        self.timer_interrupt      = Signal()
        self.m_fetch_misalign     = Signal()
        self.m_fetch_error        = Signal()
        self.m_illegal            = Signal()
        self.m_load_misalign      = Signal()
        self.m_load_error         = Signal()
        self.m_store_misalign     = Signal()
        self.m_store_error        = Signal()
        self.m_ecall              = Signal()
        self.m_ebreak             = Signal()
        self.m_mret               = Signal()
        self.m_pc                 = Signal(32)
        self.m_instruction        = Signal(32)
        self.m_fetch_badaddr      = Signal(32)
        self.m_pc_misalign        = Signal(32)
        self.m_ls_misalign        = Signal(32)
        self.m_load_store_badaddr = Signal(32)
        self.m_store              = Signal()
        self.m_valid              = Signal()
        self.m_stall              = Signal()
        self.m_exception          = Signal()
        if self.usermode:
            self.m_privmode = Signal(2)
        if self.extra_csr:
            self.w_retire = Signal()

    def elaborate(self, platform):
        m = Module()

        # Read/write behavior for all registers.
        for reg in self.csr.csr_list:
            with m.If(reg.we):
                m.d.sync += reg.read.eq(reg.write)

        # constants (at least, the important ones)
        if self.extra_csr:
            misa = 0x1 << 30 | (1 << (ord('i') - ord('a')))  # 32-bits processor. RV32IM
            if self.rv32m:
                misa |= 1 << (ord('m') - ord('a'))  # RV32M
            if self.usermode:
                misa |= 1 << (ord('u') - ord('a'))  # User mode enabled

            m.d.sync += [
                self.csr.misa.read.eq(misa),
                self.csr.mhartid.read.eq(0),   # ID 0 FOREVER. TODO: make this read only
                self.csr.mimpid.read.eq(0),    # No implemented = 0
                self.csr.marchid.read.eq(0),   # No implemented = 0
                self.csr.mvendorid.read.eq(0)  # No implemented = 0
            ]

        traps = m.submodules.traps = PriorityEncoder(16)
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

        interrupts = m.submodules.interrupts = PriorityEncoder(16)
        m.d.comb += [
            interrupts.i[ExceptionCause.I_M_SOFTWARE].eq(self.csr.mip.read.msip & self.csr.mie.read.msie),
            interrupts.i[ExceptionCause.I_M_TIMER].eq(self.csr.mip.read.mtip & self.csr.mie.read.mtie),
            interrupts.i[ExceptionCause.I_M_EXTERNAL].eq(self.csr.mip.read.meip & self.csr.mie.read.meie),
        ]

        # generate the exception/trap/interrupt signal to kill the pipeline
        m.d.comb += self.m_exception.eq(~traps.n | (~interrupts.n & self.csr.mstatus.read.mie & ~self.m_store))

        # --------------------------------------------------------------------------------
        # overwrite values from the RW circuit
        # --------------------------------------------------------------------------------
        m.d.sync += [
            self.csr.mip.read.msip.eq(self.software_interrupt),
            self.csr.mip.read.mtip.eq(self.timer_interrupt),
            self.csr.mip.read.meip.eq(self.external_interrupt)
        ]

        if self.usermode:
            privmode       = Signal(2)
            privmode.reset = PrivMode.Machine  # default mode is User
            self.csr.mstatus.read.mpp.reset = PrivMode.User

            m.d.comb += self.m_privmode.eq(privmode)
            with m.If(self.csr.mstatus.write.mpp != PrivMode.User):
                # In case of writting an invalid priviledge mode, force a valid one
                # For this case, anything different to the User mode is forced to Machine mode.
                m.d.sync += self.csr.mstatus.read.mpp.eq(PrivMode.Machine)
        else:
            self.csr.mstatus.read.mpp.reset = PrivMode.Machine
            m.d.sync += self.csr.mstatus.read.mpp.eq(PrivMode.Machine)  # Only machine mode

        # Constant fields in MSTATUS
        # Disable because S-mode is not supported
        m.d.sync += [
            self.csr.mstatus.read.sie.eq(0),
            self.csr.mstatus.read.spie.eq(0),
            self.csr.mstatus.read.spp.eq(0),
            self.csr.mstatus.read.mxr.eq(0),
            self.csr.mstatus.read.sum.eq(0),
            self.csr.mstatus.read.tvm.eq(0),
            self.csr.mstatus.read.tsr.eq(0),
            self.csr.mstatus.read.fs.eq(0),
            self.csr.mstatus.read.xs.eq(0),
            self.csr.mstatus.read.sd.eq(0)
        ]

        # behavior for exception handling
        with m.If(self.m_valid):
            with m.If(self.m_exception):
                # Register the exception and move one priviledge mode down.
                m.d.sync += [
                    self.csr.mepc.read.base.eq(self.m_pc[2:]),
                    self.csr.mstatus.read.mpie.eq(self.csr.mstatus.read.mie),
                    self.csr.mstatus.read.mie.eq(0)
                ]
                if self.usermode:
                    # If user mode is enabled, we have to go move one priviledge mode down
                    m.d.sync += [
                        privmode.eq(PrivMode.Machine),
                        self.csr.mstatus.read.mpp.eq(privmode)
                    ]
                # store cause/mtval
                with m.If(~traps.n):
                    m.d.sync += [
                        self.csr.mcause.read.ecode.eq(traps.o),
                        self.csr.mcause.read.interrupt.eq(0)
                    ]
                    with m.Switch(traps.o):
                        with m.Case(ExceptionCause.E_INST_ADDR_MISALIGNED):
                            m.d.sync += self.csr.mtval.read.eq(self.m_pc_misalign)
                        with m.Case(ExceptionCause.E_INST_ACCESS_FAULT):
                            m.d.sync += self.csr.mtval.read.eq(self.m_fetch_badaddr)
                        with m.Case(ExceptionCause.E_ILLEGAL_INST):
                            m.d.sync += self.csr.mtval.read.eq(self.m_instruction)
                        with m.Case(ExceptionCause.E_BREAKPOINT):
                            m.d.sync += self.csr.mtval.read.eq(self.m_pc)
                        with m.Case(ExceptionCause.E_LOAD_ADDR_MISALIGNED, ExceptionCause.E_STORE_AMO_ADDR_MISALIGNED):
                            m.d.sync += self.csr.mtval.read.eq(self.m_ls_misalign)
                        with m.Case(ExceptionCause.E_LOAD_ACCESS_FAULT, ExceptionCause.E_STORE_AMO_ACCESS_FAULT):
                            m.d.sync += self.csr.mtval.read.eq(self.m_load_store_badaddr)
                        with m.Default():
                            m.d.sync += self.csr.mtval.read.eq(0)

                with m.Else():
                    m.d.sync += [
                        self.csr.mcause.read.ecode.eq(interrupts.o),
                        self.csr.mcause.read.interrupt.eq(1)
                    ]
            with m.Elif(self.m_mret):
                # restore old mie
                # Restore priviledge mode
                m.d.sync += self.csr.mstatus.read.mie.eq(self.csr.mstatus.read.mpie)
                if self.usermode:
                    m.d.sync += [
                        privmode.eq(self.csr.mstatus.read.mpp),
                        self.csr.mstatus.read.mpp.eq(PrivMode.User)
                    ]

        # counters
        if self.extra_csr:
            mcycle   = Signal(64)
            minstret = Signal(64)

            m.d.sync += [
                self.csr.mcycle.read.eq(mcycle[:32]),
                self.csr.mcycleh.read.eq(mcycle[32:64]),
                #
                self.csr.minstret.read.eq(minstret[:32]),
                self.csr.minstreth.read.eq(minstret[32:64])
            ]
            m.d.comb += mcycle.eq(Cat(self.csr.mcycle.read, self.csr.mcycleh.read) + 1)
            with m.If(self.w_retire):
                m.d.comb += minstret.eq(Cat(self.csr.minstret.read, self.csr.minstreth.read) + 1)
            with m.Else():
                m.d.comb += minstret.eq(Cat(self.csr.minstret.read, self.csr.minstreth.read))

        return m
