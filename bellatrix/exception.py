from nmigen import Module
from nmigen import Signal
from nmigen import Elaboratable
from nmigen.lib.coding import PriorityEncoder
from .csr import CSR
from .isa import CSRIndex
from .isa import ExceptionCause
from .isa import misa_layout, mstatus_layout, mie_layout, mtvec_layout
from .isa import mepc_layout, mcause_layout, mip_layout, basic_layout


class ExceptionCSR:
    def __init__(self, extra_csr=False):
        if extra_csr:
            self.misa      = CSR(CSRIndex.MISA, 'misa', misa_layout)
            self.mhartid   = CSR(CSRIndex.MHARTID, 'mhartid', basic_layout)
            self.mimpid    = CSR(CSRIndex.MIMPID, 'mimpid', basic_layout)
            self.marchid   = CSR(CSRIndex.MARCHID, 'marchid', basic_layout)
            self.mvendorid = CSR(CSRIndex.MVENDORID, 'mvendorid', basic_layout)
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


class ExceptionUnit(Elaboratable):
    def __init__(self, configuration):
        self.configuration = configuration
        self.csr = ExceptionCSR(configuration.getOption('isa', 'enable_extra_csr'))

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

    def elaborate(self, platform):
        m = Module()

        # constants (at least, the important ones)
        if self.configuration.getOption('isa', 'enable_extra_csr'):
            misa = 0x1 << 30 | (1 << (ord('i') - ord('a')))  # 32-bits processor. RV32IM
            if self.configuration.getOption('isa', 'enable_rv32m'):
                misa |= 1 << (ord('m') - ord('a'))  # RV32M

            m.d.sync += [
                self.csr.misa.read.eq(misa),
                self.csr.mhartid.read.eq(0),   # ID 0 FOREVER. TODO: make this read only
                self.csr.mimpid.read.eq(0),    # No implemented = 0
                self.csr.marchid.read.eq(0),   # No implemented = 0
                self.csr.mvendorid.read.eq(0)  # No implemented = 0
            ]
        m.d.sync += self.csr.mstatus.read.mpp.eq(0b11)  # Only machine mode

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

        m.d.sync += [
            self.csr.mip.read.msip.eq(self.software_interrupt),
            self.csr.mip.read.mtip.eq(self.timer_interrupt),
            self.csr.mip.read.meip.eq(self.external_interrupt)
        ]

        # generate the exception/trap/interrupt signal to kill the pipeline
        m.d.comb += self.m_exception.eq(~traps.n | (~interrupts.n & self.csr.mstatus.read.mie & ~self.m_store))

        # default behavior for all registers.
        for reg in self.csr.csr_list:
            with m.If(reg.we):
                m.d.sync += reg.read.eq(reg.write)

        # behavior for exception handling
        with m.If(self.m_valid):
            with m.If(self.m_exception):
                # Register the exception and move one priviledge mode down.
                # No other priviledge mode, so stay in 'machine' mode
                m.d.sync += [
                    self.csr.mepc.read.base.eq(self.m_pc[2:]),
                    self.csr.mstatus.read.mpie.eq(self.csr.mstatus.read.mie),
                    self.csr.mstatus.read.mie.eq(0)
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
                # No other priviledge mode, so nothing more to do
                m.d.sync += self.csr.mstatus.read.mie.eq(self.csr.mstatus.read.mpie)

        return m
