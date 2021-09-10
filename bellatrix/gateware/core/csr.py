from nmigen import Module
from nmigen import Record
from nmigen import Signal
from nmigen import Elaboratable
from nmigen.build import Platform
from bellatrix.gateware.core.isa import CSRAccess
from bellatrix.gateware.core.isa import PrivMode
from bellatrix.gateware.core.isa import CSRIndex
from bellatrix.gateware.core.isa import basic_rw_layout
from bellatrix.gateware.core.isa import basic_ro_layout
from bellatrix.gateware.core.isa import misa_layout
from bellatrix.gateware.core.isa import mstatus_layout
from bellatrix.gateware.core.isa import mtvec_layout
from bellatrix.gateware.core.isa import mepc_layout
from bellatrix.gateware.core.isa import mip_layout
from bellatrix.gateware.core.isa import mie_layout
from bellatrix.gateware.core.isa import mcause_layout
from bellatrix.gateware.core.isa import dcsr_layout
from bellatrix.gateware.core.isa import tdata1_layout
from typing import List, Tuple, Dict

# layout for CSRs:
# (name, shape/size, access type)
Layout = List[Tuple[str, int, CSRAccess]]

reg_map = {
    CSRIndex.MVENDORID:  basic_ro_layout,
    CSRIndex.MARCHID:    basic_ro_layout,
    CSRIndex.MIMPID:     basic_ro_layout,
    CSRIndex.MHARTID:    basic_ro_layout,
    CSRIndex.MSTATUS:    mstatus_layout,
    CSRIndex.MISA:       misa_layout,
    CSRIndex.MEDELEG:    basic_rw_layout,
    CSRIndex.MIDELEG:    basic_rw_layout,
    CSRIndex.MIE:        mie_layout,
    CSRIndex.MTVEC:      mtvec_layout,
    CSRIndex.MCOUNTEREN: basic_rw_layout,
    CSRIndex.MSCRATCH:   basic_rw_layout,
    CSRIndex.MEPC:       mepc_layout,
    CSRIndex.MCAUSE:     mcause_layout,
    CSRIndex.MTVAL:      basic_rw_layout,
    CSRIndex.MIP:        mip_layout,
    CSRIndex.MCYCLE:     basic_rw_layout,
    CSRIndex.MINSTRET:   basic_rw_layout,
    CSRIndex.MCYCLEH:    basic_rw_layout,
    CSRIndex.MINSTRETH:  basic_rw_layout,
    CSRIndex.CYCLE:      basic_rw_layout,
    CSRIndex.INSTRET:    basic_rw_layout,
    CSRIndex.CYCLEH:     basic_rw_layout,
    CSRIndex.INSTRETH:   basic_rw_layout,
    CSRIndex.DCSR:       dcsr_layout,
    CSRIndex.DPC:        basic_rw_layout,
    CSRIndex.TSELECT:    basic_rw_layout,
    CSRIndex.TDATA1:     tdata1_layout,
    CSRIndex.TDATA2:     basic_rw_layout,
}

csr_port_layout = [
    ('addr',  12),  # Address
    ('dat_w', 32),  # Write data (in)
    ('valid',  1),  # Start operation: enable signal
    ('we',     1),  # Write enable
    ('dat_r', 32),  # Read data (out)
    ('done',   1)   # End of operation.
]


class _CSR(Record):
    def __init__(self, name: str, layout: Layout) -> None:
        temp = [
            ('read',   layout),  # read port (out)
            ('write',  layout),  # write port (in)
            ('update', 1)        # write -> read. Is a Write Enable.
        ]
        super().__init__(temp, name=name)


class AutoCSR():
    """Extract all CSR from the module in a recursive way."""
    def get_csrs(self):
        for v in vars(self).values():
            if isinstance(v, _CSR):
                yield v
            elif hasattr(v, "get_csrs"):
                yield from v.get_csrs()


class CSRFile(Elaboratable):
    def __init__(self, enable_debug: bool = False) -> None:
        # IO
        self.invalid  = Signal()          # output
        self.privmode = Signal(PrivMode)  # input
        self.port     = Record(csr_port_layout)
        if enable_debug:
            self.debug_port = Record(csr_port_layout)
        # data
        self._enable_debug = enable_debug
        self._ports: List[Record] = []
        self.registers: Dict[int, _CSR] = {}

    def add_register(self, name: str, addr: int) -> _CSR:
        if addr not in reg_map:
            raise ValueError(f'Unknown register at {addr:x}')
        if addr in self.registers:
            raise ValueError(f'Address {addr:x} already in the allocated list')

        layout = [f[:2] for f in reg_map[addr]]  # keep (name, size)
        self.registers[addr] = _CSR(name, layout)

        return self.registers[addr]

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        invalid_undef = Signal()  # The register is not defined
        invalid_ro    = Signal()  # The register is read-only.
        invalid_priv  = Signal()  # The priviledge mode is incorrect.
        delay         = Signal()  # the operation takes time...

        # ----------------------------------------------------------------------
        # normal port
        with m.If(self.port.valid & ~self.port.done):
            m.d.sync += [
                delay.eq(1),
                self.port.done.eq(delay),  # 2 cycle delay
                invalid_ro.eq((self.port.addr[10:12] == 0b11) & self.port.we),  # trying to write a RO register
                invalid_priv.eq(self.port.addr[8:10] > self.privmode)           # The register is from a higher priv mode
            ]
            # Do the read/write
            with m.Switch(self.port.addr):
                for addr, register in self.registers.items():
                    with m.Case(addr):
                        # read
                        m.d.sync += self.port.dat_r.eq(register.read)
                        # write
                        tmp = Record(register.write.layout)  # port.dat_w -> temp -> register
                        m.d.comb += tmp.eq(self.port.dat_w)
                        for name, _, mode in reg_map[addr]:
                            src = getattr(tmp, name)
                            dst = getattr(register.write, name)
                            if mode is CSRAccess.RW:
                                m.d.sync += dst.eq(src)
                        m.d.sync += register.update.eq(self.port.we & delay & ~self.invalid)  # this will be in sync with port.done
                with m.Default():
                    m.d.sync += invalid_undef.eq(1)  # the register does not exist.
        with m.Else():
            m.d.sync += [
                delay.eq(0),
                self.port.done.eq(0),
                invalid_ro.eq(0),
                invalid_priv.eq(0),
                invalid_undef.eq(0)
            ]

        m.d.comb += self.invalid.eq(invalid_undef | invalid_ro | invalid_priv)  # deny access?

        # ----------------------------------------------------------------------
        # debug port: no exceptions
        if self._enable_debug:
            with m.If(self.debug_port.valid & ~self.debug_port.done):
                m.d.sync += self.debug_port.done.eq(1)

                with m.Switch(self.debug_port.addr):
                    for addr, register in self.registers.items():
                        with m.Case(addr):
                            # read
                            m.d.sync += self.debug_port.dat_r.eq(register.read)
                            # write
                            tmp = Record(register.write.layout)  # debug_port.dat_w -> temp -> register
                            m.d.comb += tmp.eq(self.debug_port.dat_w)
                            for name, size, mode in reg_map[addr]:
                                src = getattr(tmp, name)
                                dst = getattr(register.write, name)
                                if mode is CSRAccess.RW:
                                    m.d.sync += dst.eq(src)
                                else:
                                    m.d.sync += dst.eq(0)
                            m.d.sync += register.update.eq(self.debug_port.we)
                    with m.Default():
                        m.d.sync += self.debug_port.dat_r.eq(0xdeadf00d)
            with m.Else():
                m.d.sync += self.debug_port.done.eq(0)

        # ----------------------------------------------------------------------
        # reset the update signal after an update
        for register in self.registers.values():
            with m.If(register.update):
                m.d.sync += register.update.eq(0)

        return m
