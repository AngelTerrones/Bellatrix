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


CSRAccess = Enum('CSRAccess', ['RO', 'RW'])

# layouts for CSR
basic_rw_layout = [
    ('data', 32, CSRAccess.RW)
]

basic_ro_layout = [
    ('data', 32, CSRAccess.RO)
]

misa_layout = [
    ('extensions', 26, CSRAccess.RO),  # Extensions implemented
    ('wlrl0',       4, CSRAccess.RO),
    ('mxl',         2, CSRAccess.RO)   # Native base integer ISA
]

mstatus_layout = [
    ('uie',   1, CSRAccess.RO),  # User Interrupt Enable
    ('sie',   1, CSRAccess.RO),  # Supervisor Interrupt Enable
    ('wpri0', 1, CSRAccess.RO),
    ('mie',   1, CSRAccess.RW),  # Machine Interrupt Enable
    ('upie',  1, CSRAccess.RO),  # User Previous Interrupt Enable
    ('spie',  1, CSRAccess.RO),  # Supervisor Previous Interrupt Enable
    ('wpri1', 1, CSRAccess.RO),
    ('mpie',  1, CSRAccess.RW),  # Machine Previous Interrupt Enable
    ('spp',   1, CSRAccess.RO),  # Supervisor Previous Privilege
    ('wpri2', 2, CSRAccess.RO),
    ('mpp',   2, CSRAccess.RW),  # Machine Previous Privilege
    ('fs',    2, CSRAccess.RO),  # FPU Status
    ('xs',    2, CSRAccess.RO),  # user-mode eXtensions Status
    ('mprv',  1, CSRAccess.RO),  # Modify PRiVilege
    ('sum',   1, CSRAccess.RO),  # Supervisor User Memory access
    ('mxr',   1, CSRAccess.RO),  # Make eXecutable Readable
    ('tvm',   1, CSRAccess.RO),  # Trap Virtual Memory
    ('tw',    1, CSRAccess.RO),  # Timeout Wait
    ('tsr',   1, CSRAccess.RO),  # Trap SRET
    ('wpri3', 8, CSRAccess.RO),
    ('sd',    1, CSRAccess.RO)   # State Dirty
]

mtvec_layout = [
    ('mode',  2, CSRAccess.RW),  # 0: Direct. 1: Vectored. >=2: Reserved
    ('base', 30, CSRAccess.RW)
]

mepc_layout = [
    ('zero',   2, CSRAccess.RO),
    ('base',  30, CSRAccess.RW)
]

mip_layout = [
    ('usip',   1, CSRAccess.RW),
    ('ssip',   1, CSRAccess.RW),
    ('wpri0',  1, CSRAccess.RO),
    ('msip',   1, CSRAccess.RO),
    ('utip',   1, CSRAccess.RW),
    ('stip',   1, CSRAccess.RW),
    ('wpri1',  1, CSRAccess.RO),
    ('mtip',   1, CSRAccess.RO),
    ('ueip',   1, CSRAccess.RW),
    ('seip',   1, CSRAccess.RW),
    ('wpri2',  1, CSRAccess.RO),
    ('meip',   1, CSRAccess.RO),
    ('wpri3', 20, CSRAccess.RO)
]

mie_layout = [
    ('usie',   1, CSRAccess.RO),
    ('ssie',   1, CSRAccess.RO),
    ('wpri0',  1, CSRAccess.RO),
    ('msie',   1, CSRAccess.RW),
    ('utie',   1, CSRAccess.RO),
    ('stie',   1, CSRAccess.RO),
    ('wpri1',  1, CSRAccess.RO),
    ('mtie',   1, CSRAccess.RW),
    ('ueie',   1, CSRAccess.RO),
    ('seie',   1, CSRAccess.RO),
    ('wpri2',  1, CSRAccess.RO),
    ('meie',   1, CSRAccess.RW),
    ('wpri3', 20, CSRAccess.RO)
]

mcause_layout = [
    ('ecode',     31, CSRAccess.RW),
    ('interrupt',  1, CSRAccess.RW)
]

mcycle_layout = [
    ('mcyclel', 32, CSRAccess.RW),
    ('mcycleh', 32, CSRAccess.RW)
]

minstret_layout = [
    ('minstretl', 32, CSRAccess.RW),
    ('minstreth', 32, CSRAccess.RW)
]

dcsr_layout = [
    ('prv',        2, CSRAccess.RW),  # Privilege level before Debug Mode was entered
    ('step',       1, CSRAccess.RW),  # Execute a single instruction and re-enter Debug Mode
    ('nmip',       1, CSRAccess.RO),  # A non-maskable interrupt is pending
    ('mprven',     1, CSRAccess.RW),  # Use mstatus.mprv in Debug Mode
    ('zero0',      1, CSRAccess.RO),
    ('cause',      3, CSRAccess.RO),  # Why Debug Mode was entered
    ('stoptime',   1, CSRAccess.RW),  # Stop timer increment during Debug Mode
    ('stopcount',  1, CSRAccess.RW),  # Stop counter increment during Debug Mode
    ('stepie',     1, CSRAccess.RW),  # Enable interrupts during single stepping
    ('ebreaku',    1, CSRAccess.RW),  # EBREAKs in U-mode enter Debug Mode
    ('ebreaks',    1, CSRAccess.RW),  # EBREAKs in S-mode enter Debug Mode
    ('zero1',      1, CSRAccess.RO),
    ('ebreakm',    1, CSRAccess.RW),  # EBREAKs in M-mode enter Debug Mode
    ('zero2',     12, CSRAccess.RO),
    ('xdebugver',  4, CSRAccess.RO)   # External Debug specification version
]

tdata1_layout = [
    ('data',   27, CSRAccess.RW),
    ('dmode',   1, CSRAccess.RW),
    ('type',    4, CSRAccess.RW)
]
