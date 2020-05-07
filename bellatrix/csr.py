from nmigen import Const
from nmigen import Module
from nmigen import Record
from nmigen import Signal
from nmigen import Elaboratable
from nmigen.build import Platform
from .isa import CSRAccess
from .isa import PrivMode
from typing import List, Tuple, Dict


# layout for CSRs:
# (name, shape/size, access type)
Layout = List[Tuple[str, int, CSRAccess]]


class CSR:
    """ Container for the CSR """
    def __init__(self,
                 addr: int,      # CSR's address
                 name: str,      # CSR's name
                 layout: Layout  # CSR's layout
                 ) -> None:
        mask      = 0
        offset    = 0
        fields    = list()

        for _name, _shape, _access in layout:
            if not isinstance(_shape, int):
                raise TypeError('Shape must be a flat int: {}'.format(_shape))

            fields.append((_name, _shape))
            if _access in [CSRAccess.WLRL, CSRAccess.WARL]:
                _mask = (1 << _shape) - 1
                mask = mask | (_mask << offset)
            offset = offset + _shape

        self.addr = addr
        self.name = name
        self.mask = Const(mask)  # using the same mask for read and write operations
        # IO
        self.read  = Record(fields, name=self.name + '_r')
        self.write = Record(fields, name=self.name + '_w')
        self.we    = Signal()


class AutoCSR():
    def get_csrs(self):
        for v in vars(self).values():
            if isinstance(v, CSR):
                yield v
            elif hasattr(v, "get_csrs"):
                yield from v.get_csrs()


class CSRFile(Elaboratable):
    def __init__(self) -> None:
        self.width                    = 32
        self.addr_w                   = 12
        self._ports: List[Record]     = []
        self._csr_map: Dict[int, CSR] = dict()
        # IO
        self.privmode                 = Signal(PrivMode)  # output
        self.invalid                  = Signal()   # input

    def add_csr_from_list(self, csr_list: List[CSR]) -> None:
        for csr in csr_list:
            if not isinstance(csr, CSR):
                raise TypeError("Item {} is not a CSR".format(csr))
            if csr.addr in self._csr_map:
                raise ValueError("CSR address 0x{:x} is already in use.".format(csr.addr))
            self._csr_map[csr.addr] = csr

    def create_port(self) -> Record:
        layout = [
            ('addr',   self.addr_w),
            ('data_r', self.width),
            ('data_w', self.width),
            ('en',     1)
        ]
        port = Record(layout)
        self._ports.append(port)
        return port

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        invalid_undef = Signal()  # The register is not defined
        invalid_ro    = Signal()  # The register is read-only.
        invalid_priv  = Signal()  # The priviledge mode is incorrect.

        # ----------------------------------------------------------------------
        # access
        for idx, port in enumerate(self._ports):
            if idx == 0:
                # The first write port is for pipeline use, and is the only one that
                # can generate exceptions
                # Other write ports do not generate exceptions: for debug use, for example.

                # Priv mode must be greater or equal to the priv mode of the register.
                m.d.comb += [
                    invalid_ro.eq(port.addr[10:12] == 0b11),
                    invalid_priv.eq(port.addr[8:10] > self.privmode)
                ]

                with m.Switch(port.addr):
                    for addr, csr in self._csr_map.items():
                        with m.Case(addr):
                            m.d.comb += [
                                csr.we.eq(port.en & ~(invalid_ro | invalid_priv)),
                                port.data_r.eq(csr.read & csr.mask),
                                csr.write.eq(port.data_w & csr.mask)
                            ]
                    with m.Default():
                        m.d.comb += invalid_undef.eq(1)

                m.d.comb += self.invalid.eq(invalid_undef | (invalid_ro & port.en) | invalid_priv)
            else:
                with m.Switch(port.addr):
                    for addr, csr in self._csr_map.items():
                        with m.Case(addr):
                            m.d.comb += [
                                csr.we.eq(port.en),
                                port.data_r.eq(csr.read & csr.mask),
                                csr.write.eq(port.data_w & csr.mask)
                            ]

        return m
