from nmigen import Cat
from nmigen import Signal
from nmigen import Module
from nmigen import Elaboratable
from nmigen.build import Platform
from bellatrix.gateware.core.isa import Funct7
from bellatrix.gateware.core.isa import Funct3
from bellatrix.gateware.core.isa import Funct12
from bellatrix.gateware.core.isa import Opcode
from bellatrix.gateware.core.isa import PrivMode
from functools import reduce
from operator import or_
from enum import IntEnum


class Type(IntEnum):
    R = 0
    I = 1  # noqa
    S = 2
    B = 3
    U = 4
    J = 5


class DecoderUnit(Elaboratable):
    def __init__(self, enable_rv32m: bool) -> None:
        self.enable_rv32m = enable_rv32m

        self.instruction     = Signal(32)
        self.instruction2    = Signal(32)
        self.funct3          = Signal(Funct3)
        self.gpr_rs1         = Signal(5)
        self.gpr_rs1_use     = Signal()
        self.gpr_rs2         = Signal(5)
        self.gpr_rs2_use     = Signal()
        self.gpr_rd          = Signal(5)
        self.gpr_we          = Signal()
        self.immediate       = Signal(32)
        self.lui             = Signal()
        self.aiupc           = Signal()
        self.jump            = Signal()
        self.branch          = Signal()
        self.load            = Signal()
        self.store           = Signal()
        self.aritmetic       = Signal()
        self.substract       = Signal()
        self.logic           = Signal()
        self.shift           = Signal()
        self.shift_direction = Signal()
        self.shit_signed     = Signal()
        self.compare         = Signal()
        self.csr             = Signal()
        self.csr_we          = Signal()
        self.needed_in_m     = Signal()
        self.needed_in_w     = Signal()
        self.ecall           = Signal()
        self.ebreak          = Signal()
        self.mret            = Signal()
        self.fence_i         = Signal()
        self.fence           = Signal()
        self.multiply        = Signal()
        self.divide          = Signal()
        self.illegal         = Signal()
        self.privmode        = Signal(PrivMode)

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        opcode       = Signal(Opcode)
        funct3       = Signal(Funct3)
        funct7       = Signal(Funct7)
        funct12      = Signal(Funct12)
        iimm12       = Signal((12, True))
        simm12       = Signal((12, True))
        bimm12       = Signal((13, True))
        uimm20       = Signal(20)
        jimm20       = Signal((21, True))
        itype        = Signal(Type)
        instruction  = self.instruction
        instruction2 = self.instruction2

        with m.Switch(opcode):
            with m.Case(Opcode.LUI):
                m.d.comb += itype.eq(Type.U)
            with m.Case(Opcode.AUIPC):
                m.d.comb += itype.eq(Type.U)
            with m.Case(Opcode.JAL):
                m.d.comb += itype.eq(Type.J)
            with m.Case(Opcode.JALR):
                m.d.comb += itype.eq(Type.I)
            with m.Case(Opcode.BRANCH):
                m.d.comb += itype.eq(Type.B)
            with m.Case(Opcode.LOAD):
                m.d.comb += itype.eq(Type.I)
            with m.Case(Opcode.STORE):
                m.d.comb += itype.eq(Type.S)
            with m.Case(Opcode.OP_IMM):
                m.d.comb += itype.eq(Type.I)
            with m.Case(Opcode.OP):
                m.d.comb += itype.eq(Type.R)
            with m.Case(Opcode.FENCE):
                m.d.comb += itype.eq(Type.I)
            with m.Case(Opcode.SYSTEM):
                m.d.comb += itype.eq(Type.I)

        with m.Switch(itype):
            with m.Case(Type.I):
                m.d.comb += self.immediate.eq(iimm12)
            with m.Case(Type.S):
                m.d.comb += self.immediate.eq(simm12)
            with m.Case(Type.B):
                m.d.comb += self.immediate.eq(bimm12)
            with m.Case(Type.U):
                m.d.comb += self.immediate.eq(uimm20 << 12)
            with m.Case(Type.J):
                m.d.comb += self.immediate.eq(jimm20)

        m.d.comb += [
            opcode.eq(instruction[:7]),
            funct3.eq(instruction[12:15]),
            funct7.eq(instruction[25:32]),
            funct12.eq(instruction[20:32]),
            iimm12.eq(instruction[20:32]),
            simm12.eq(Cat(instruction[7:12], instruction[25:32])),
            bimm12.eq(Cat(0, instruction[8:12], instruction[25:31], instruction[7],
                      instruction[31])),
            uimm20.eq(instruction[12:32]),
            jimm20.eq(Cat(0, instruction[21:31], instruction[20], instruction[12:20],
                      instruction[31]))
        ]

        m.d.comb += [
            self.gpr_rs1.eq(instruction2[15:20]),
            self.gpr_rs1_use.eq(reduce(or_, [itype == tmp for tmp in (Type.R, Type.I, Type.S, Type.B)])),
            self.gpr_rs2.eq(instruction2[20:25]),
            self.gpr_rs2_use.eq(reduce(or_, [itype == tmp for tmp in (Type.R, Type.S, Type.B)])),
            self.gpr_rd.eq(instruction2[7:12]),
            self.gpr_we.eq(reduce(or_, [itype == tmp for tmp in (Type.R, Type.I, Type.U, Type.J)])),
            self.funct3.eq(funct3)
        ]

        m.d.comb += [
            self.needed_in_m.eq(self.compare | self.shift | self.divide),
            self.needed_in_w.eq(self.csr | self.load),
        ]

        # ----------------------------------------------------------------------
        # Fields = list of (Opcode, F3, F7, F12)
        def match(fields):
            def check(op, f3=None, f7=None, f12=None):
                op_match  = opcode == op
                f3_match  = funct3 == f3 if f3 is not None else 1
                f7_match  = funct7 == f7 if f7 is not None else 1
                f12_match = funct12 == f12 if f12 is not None else 1
                return op_match & f3_match & f7_match & f12_match

            return reduce(or_, [check(*instr) for instr in fields])
        # ----------------------------------------------------------------------

        m.d.comb += [
            self.lui.eq(opcode == Opcode.LUI),
            self.aiupc.eq(opcode == Opcode.AUIPC),
            self.jump.eq(match([
                (Opcode.JAL, None, None, None),
                (Opcode.JALR, 0,   None, None)
            ])),
            self.branch.eq(match([
                (Opcode.BRANCH, Funct3.BEQ,  None, None),
                (Opcode.BRANCH, Funct3.BNE,  None, None),
                (Opcode.BRANCH, Funct3.BLT,  None, None),
                (Opcode.BRANCH, Funct3.BGE,  None, None),
                (Opcode.BRANCH, Funct3.BLTU, None, None),
                (Opcode.BRANCH, Funct3.BGEU, None, None)
            ])),
            self.load.eq(match([
                (Opcode.LOAD, Funct3.B,  None, None),
                (Opcode.LOAD, Funct3.H,  None, None),
                (Opcode.LOAD, Funct3.W,  None, None),
                (Opcode.LOAD, Funct3.BU, None, None),
                (Opcode.LOAD, Funct3.HU, None, None)
            ])),
            self.store.eq(match([
                (Opcode.STORE, Funct3.B, None, None),
                (Opcode.STORE, Funct3.H, None, None),
                (Opcode.STORE, Funct3.W, None, None)
            ])),
            self.aritmetic.eq(match([
                (Opcode.OP_IMM, Funct3.ADD, None, None),
                (Opcode.OP,     Funct3.ADD, Funct7.ADD, None),
                (Opcode.OP,     Funct3.ADD, Funct7.SUB, None)
            ])),
            self.logic.eq(match([
                (Opcode.OP_IMM, Funct3.XOR, None, None),
                (Opcode.OP_IMM, Funct3.OR,  None, None),
                (Opcode.OP_IMM, Funct3.AND, None, None),
                (Opcode.OP,     Funct3.XOR, 0,    None),
                (Opcode.OP,     Funct3.OR,  0,    None),
                (Opcode.OP,     Funct3.AND, 0,    None)
            ])),
            self.compare.eq(match([
                (Opcode.OP_IMM, Funct3.SLT,  None, None),
                (Opcode.OP_IMM, Funct3.SLTU, None, None),
                (Opcode.OP,     Funct3.SLT,  0,    None),
                (Opcode.OP,     Funct3.SLTU, 0,    None)
            ])),
            self.shift.eq(match([
                (Opcode.OP_IMM, Funct3.SLL, 0,          None),
                (Opcode.OP_IMM, Funct3.SR,  Funct7.SRL, None),
                (Opcode.OP_IMM, Funct3.SR,  Funct7.SRA, None),
                (Opcode.OP,     Funct3.SLL, 0,          None),
                (Opcode.OP,     Funct3.SR,  Funct7.SRL, None),
                (Opcode.OP,     Funct3.SR,  Funct7.SRA, None)
            ])),
            self.csr.eq(match([
                (Opcode.SYSTEM, Funct3.CSRRW,  None, None),
                (Opcode.SYSTEM, Funct3.CSRRS,  None, None),
                (Opcode.SYSTEM, Funct3.CSRRC,  None, None),
                (Opcode.SYSTEM, Funct3.CSRRWI, None, None),
                (Opcode.SYSTEM, Funct3.CSRRSI, None, None),
                (Opcode.SYSTEM, Funct3.CSRRCI, None, None),
            ])),
            self.ecall.eq(match([
                (Opcode.SYSTEM, Funct3.PRIV, None, Funct12.ECALL)
            ])),
            self.ebreak.eq(match([
                (Opcode.SYSTEM, Funct3.PRIV, None, Funct12.EBREAK)
            ])),
            self.mret.eq((self.privmode == PrivMode.Machine) & match([
                (Opcode.SYSTEM, Funct3.PRIV, None, Funct12.MRET)
            ])),
            self.fence_i.eq(match([
                (Opcode.FENCE, Funct3.FENCEI, None, None)
            ])),
            self.fence.eq(match([
                (Opcode.FENCE, Funct3.FENCE, None, None)
            ])),
            self.substract.eq(match([
                (Opcode.OP, Funct3.ADD, Funct7.SUB, None)
            ])),
            self.shift_direction.eq(funct3 == Funct3.SR),
            self.shit_signed.eq(funct7 == Funct7.SRA),
            self.csr_we.eq(~funct3[1] | self.gpr_rs1.any()),
        ]

        if (self.enable_rv32m):
            m.d.comb += [
                self.multiply.eq(match([
                    (Opcode.OP, Funct3.MUL, Funct7.MULDIV, None),
                    (Opcode.OP, Funct3.MULH, Funct7.MULDIV, None),
                    (Opcode.OP, Funct3.MULHU, Funct7.MULDIV, None),
                    (Opcode.OP, Funct3.MULHSU, Funct7.MULDIV, None)
                ])),
                self.divide.eq(match([
                    (Opcode.OP, Funct3.DIV, Funct7.MULDIV, None),
                    (Opcode.OP, Funct3.DIVU, Funct7.MULDIV, None),
                    (Opcode.OP, Funct3.REM, Funct7.MULDIV, None),
                    (Opcode.OP, Funct3.REMU, Funct7.MULDIV, None)
                ]))
            ]

        m.d.comb += self.illegal.eq(
            ~reduce(or_, [
                self.lui, self.aiupc, self.jump, self.branch, self.load, self.store,
                self.aritmetic, self.logic, self.shift, self.compare, self.csr,
                self.ecall, self.ebreak, self.mret, self.fence_i, self.fence, self.multiply,
                self.divide
            ])
        )

        return m
