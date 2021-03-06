from enum import Enum
from enum import IntEnum

"""
Unpriviledge ISA RV32IM v2.1
Priviledge Arquitecture v1.11
"""


class Opcode(IntEnum):
    LUI    = 0b0110111
    AUIPC  = 0b0010111
    JAL    = 0b1101111
    JALR   = 0b1100111
    BRANCH = 0b1100011
    LOAD   = 0b0000011
    STORE  = 0b0100011
    OP_IMM = 0b0010011
    OP     = 0b0110011
    FENCE  = 0b0001111
    SYSTEM = 0b1110011


class Funct3(IntEnum):
    BEQ  = B  = ADD  = FENCE  = PRIV   = MUL    = 0b000
    BNE  = H  = SLL  = FENCEI = CSRRW  = MULH   = 0b001
    _0   = W  = SLT  = _1     = CSRRS  = MULHSU = 0b010
    _2   = _3 = SLTU = _4     = CSRRC  = MULHU  = 0b011
    BLT  = BU = XOR  = _5     = _6     = DIV    = 0b100
    BGE  = HU = SR   = _7     = CSRRWI = DIVU   = 0b101
    BLTU = _8 = OR   = _9     = CSRRSI = REM    = 0b110
    BGEU = _a = AND  = _b     = CSRRCI = REMU   = 0b111


class Funct7(IntEnum):
    SRL = ADD = 0b0000000
    SRA = SUB = 0b0100000
    MULDIV    = 0b0000001


class Funct12(IntEnum):
    ECALL  = 0b000000000000
    EBREAK = 0b000000000001
    URET   = 0b000000000010
    SRET   = 0b000100000010
    MRET   = 0b001100000010


class CSRIndex(IntEnum):
    MVENDORID  = 0xF11
    MARCHID    = 0xF12
    MIMPID     = 0xF13
    MHARTID    = 0xF14
    MSTATUS    = 0x300
    MISA       = 0x301
    MEDELEG    = 0x302
    MIDELEG    = 0x303
    MIE        = 0x304
    MTVEC      = 0x305
    MCOUNTEREN = 0x306
    MSCRATCH   = 0x340
    MEPC       = 0x341
    MCAUSE     = 0x342
    MTVAL      = 0x343
    MIP        = 0x344
    # performance counters
    MCYCLE     = 0xB00
    MINSTRET   = 0xB02
    MCYCLEH    = 0xB80
    MINSTRETH  = 0xB82
    CYCLE      = 0xC00
    INSTRET    = 0xC02
    CYCLEH     = 0xC80
    INSTRETH   = 0xC82
    # debug
    DCSR       = 0x7B0
    DPC        = 0x7B1
    # trigger
    TSELECT    = 0x7A0
    TDATA1     = 0x7A1
    TDATA2     = 0x7A2


class ExceptionCause(IntEnum):
    MAX_NUM                     = 16
    # Exceptions
    E_INST_ADDR_MISALIGNED      = 0
    E_INST_ACCESS_FAULT         = 1
    E_ILLEGAL_INST              = 2
    E_BREAKPOINT                = 3
    E_LOAD_ADDR_MISALIGNED      = 4
    E_LOAD_ACCESS_FAULT         = 5
    E_STORE_AMO_ADDR_MISALIGNED = 6
    E_STORE_AMO_ACCESS_FAULT    = 7
    E_ECALL_FROM_U              = 8
    E_ECALL_FROM_S              = 9
    E_ECALL_FROM_M              = 11
    E_INST_PAGE_FAULT           = 12
    E_LOAD_PAGE_FAULT           = 13
    E_STORE_AMO_PAGE_FAULT      = 15
    # interrupts
    I_U_SOFTWARE                = 0
    I_S_SOFTWARE                = 1
    I_M_SOFTWARE                = 3
    I_U_TIMER                   = 4
    I_S_TIMER                   = 5
    I_M_TIMER                   = 7
    I_U_EXTERNAL                = 8
    I_S_EXTERNAL                = 9
    I_M_EXTERNAL                = 11


class PrivMode(IntEnum):
    User       = 0
    Supervisor = 1
    Machine    = 3


# Behavior for field within the CSRs
# WPRI: Write Preserve Values, Reads Ignore Values
# WLRL: Write/Read Only Legal Values
# WARL: Write Any Values, Reads Legal Values
CSRAccess = Enum('CSRAccess', ['WPRI', 'WLRL', 'WARL'])

# layouts for CSR
basic_layout = [
    ('data', 32, CSRAccess.WARL)
]

misa_layout = [
    ('extensions', 26, CSRAccess.WARL),  # Extensions implemented
    ('wlrl0',       4, CSRAccess.WLRL),
    ('mxl',         2, CSRAccess.WARL)   # Native base integer ISA
]

mstatus_layout = [
    ('uie',   1, CSRAccess.WARL),  # User Interrupt Enable
    ('sie',   1, CSRAccess.WARL),  # Supervisor Interrupt Enable
    ('wpri0', 1, CSRAccess.WPRI),
    ('mie',   1, CSRAccess.WARL),  # Machine Interrupt Enable
    ('upie',  1, CSRAccess.WARL),  # User Previous Interrupt Enable
    ('spie',  1, CSRAccess.WARL),  # Supervisor Previous Interrupt Enable
    ('wpri1', 1, CSRAccess.WPRI),
    ('mpie',  1, CSRAccess.WARL),  # Machine Previous Interrupt Enable
    ('spp',   1, CSRAccess.WARL),  # Supervisor Previous Privilege
    ('wpri2', 2, CSRAccess.WPRI),
    ('mpp',   2, CSRAccess.WARL),  # Machine Previous Privilege
    ('fs',    2, CSRAccess.WARL),  # FPU Status
    ('xs',    2, CSRAccess.WARL),  # user-mode eXtensions Status
    ('mprv',  1, CSRAccess.WARL),  # Modify PRiVilege
    ('sum',   1, CSRAccess.WARL),  # Supervisor User Memory access
    ('mxr',   1, CSRAccess.WARL),  # Make eXecutable Readable
    ('tvm',   1, CSRAccess.WARL),  # Trap Virtual Memory
    ('tw',    1, CSRAccess.WARL),  # Timeout Wait
    ('tsr',   1, CSRAccess.WARL),  # Trap SRET
    ('wpri3', 8, CSRAccess.WPRI),
    ('sd',    1, CSRAccess.WARL)   # State Dirty
]

mtvec_layout = [
    ('mode',  2, CSRAccess.WARL),  # 0: Direct. 1: Vectored. >=2: Reserved
    ('base', 30, CSRAccess.WARL)
]

mepc_layout = [
    ('zero',   2, CSRAccess.WPRI),
    ('base', 30, CSRAccess.WARL)
]

mip_layout = [
    ('usip',   1, CSRAccess.WARL),
    ('ssip',   1, CSRAccess.WARL),
    ('wpri0',  1, CSRAccess.WPRI),
    ('msip',   1, CSRAccess.WARL),
    ('utip',   1, CSRAccess.WARL),
    ('stip',   1, CSRAccess.WARL),
    ('wpri1',  1, CSRAccess.WPRI),
    ('mtip',   1, CSRAccess.WARL),
    ('ueip',   1, CSRAccess.WARL),
    ('seip',   1, CSRAccess.WARL),
    ('wpri2',  1, CSRAccess.WPRI),
    ('meip',   1, CSRAccess.WARL),
    ('wpri3', 20, CSRAccess.WPRI)
]

mie_layout = [
    ('usie',   1, CSRAccess.WARL),
    ('ssie',   1, CSRAccess.WARL),
    ('wpri0',  1, CSRAccess.WPRI),
    ('msie',   1, CSRAccess.WARL),
    ('utie',   1, CSRAccess.WARL),
    ('stie',   1, CSRAccess.WARL),
    ('wpri1',  1, CSRAccess.WPRI),
    ('mtie',   1, CSRAccess.WARL),
    ('ueie',   1, CSRAccess.WARL),
    ('seie',   1, CSRAccess.WARL),
    ('wpri2',  1, CSRAccess.WPRI),
    ('meie',   1, CSRAccess.WARL),
    ('wpri3', 20, CSRAccess.WPRI)
]

mcause_layout = [
    ('ecode',     31, CSRAccess.WARL),
    ('interrupt',  1, CSRAccess.WARL)
]

mcycle_layout = [
    ('mcyclel', 32, CSRAccess.WARL),
    ('mcycleh', 32, CSRAccess.WARL)
]

minstret_layout = [
    ('minstretl', 32, CSRAccess.WARL),
    ('minstreth', 32, CSRAccess.WARL)
]

dcsr_layout = [
    ('prv',        2, CSRAccess.WARL),  # Privilege level before Debug Mode was entered
    ('step',       1, CSRAccess.WARL),  # Execute a single instruction and re-enter Debug Mode
    ('nmip',       1, CSRAccess.WLRL),  # A non-maskable interrupt is pending
    ('mprven',     1, CSRAccess.WARL),  # Use mstatus.mprv in Debug Mode
    ('zero0',      1, CSRAccess.WPRI),
    ('cause',      3, CSRAccess.WLRL),  # Why Debug Mode was entered
    ('stoptime',   1, CSRAccess.WARL),  # Stop timer increment during Debug Mode
    ('stopcount',  1, CSRAccess.WARL),  # Stop counter increment during Debug Mode
    ('stepie',     1, CSRAccess.WARL),  # Enable interrupts during single stepping
    ('ebreaku',    1, CSRAccess.WARL),  # EBREAKs in U-mode enter Debug Mode
    ('ebreaks',    1, CSRAccess.WARL),  # EBREAKs in S-mode enter Debug Mode
    ('zero1',      1, CSRAccess.WPRI),
    ('ebreakm',    1, CSRAccess.WARL),  # EBREAKs in M-mode enter Debug Mode
    ('zero2',     12, CSRAccess.WPRI),
    ('xdebugver',  4, CSRAccess.WLRL)   # External Debug specification version
]

tdata1_layout = [
    ('data',   27, CSRAccess.WARL),
    ('dmode',   1, CSRAccess.WARL),
    ('type',    4, CSRAccess.WARL)
]
