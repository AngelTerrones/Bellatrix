from nmigen import Const
from nmigen import Module
from nmigen import Record
from nmigen import Signal
from nmigen import Elaboratable
from .isa import CSRAccess


class CSR:
    """ Container for the CSR """
    def __init__(self, addr, name, layout):
        self.addr = addr
        self.name = name
        mask      = 0
        offset    = 0
        fields    = list()

        # layout for CSRs:
        # (name, shape/size, access type)
        for _name, _shape, _access in layout:
            if not isinstance(_shape, int):
                raise TypeError('Shape must be a flat int: {}'.format(_shape))

            fields.append((_name, _shape))
            if _access in [CSRAccess.WLRL, CSRAccess.WARL]:
                _mask = (1 << _shape) - 1
                mask = mask | (_mask << offset)
            offset = offset + _shape

        self.mask = Const(mask)  # using the same mask for read and write operations
        # IO
        self.read  = Record(fields, name=self.name)
        self.write = Record(fields, name=self.name)
        self.we    = Signal()


class CSRFile(Elaboratable):
    def __init__(self):
        self.width        = 32
        self.addr_w       = 12
        self._csr_map     = dict()
        self._read_ports  = []
        self._write_ports = []
        self.invalid      = Signal()

    def add_csr_from_list(self, csr_list):
        for csr in csr_list:
            if not isinstance(csr, CSR):
                raise TypeError("Item {} is not a CSR".format(csr))
            if csr.addr in self._csr_map:
                raise ValueError("CSR address 0x{:x} is already in use.".format(csr.addr))
            self._csr_map[csr.addr] = csr

    def create_read_port(self):
        layout = [
            ('addr', self.addr_w),
            ('data', self.width)
        ]
        port = Record(layout)
        self._read_ports.append(port)
        return port

    def create_write_port(self):
        layout = [
            ('addr', self.addr_w),
            ('en',   1),
            ('data', self.width)
        ]
        port = Record(layout)
        self._write_ports.append(port)
        return port

    def elaborate(self, platform):
        m = Module()

        invalid_r = Signal()
        invalid_w = Signal()

        # do the read
        m.d.comb += invalid_r.eq(0)
        for rport in self._read_ports:
            with m.Switch(rport.addr):
                for addr, csr in self._csr_map.items():
                    with m.Case(addr):
                        m.d.comb += rport.data.eq(csr.read & csr.mask)
                with m.Default():
                    m.d.comb += invalid_r.eq(1)

        # do the write
        m.d.comb += invalid_r.eq(0)
        for wport in self._write_ports:
            with m.Switch(wport.addr):
                for addr, csr in self._csr_map.items():
                    with m.Case(addr):
                        m.d.comb += [
                            csr.we.eq(wport.en),
                            csr.write.eq(wport.data & csr.mask)
                        ]
                with m.Default():
                    m.d.comb += invalid_r.eq(1)

        m.d.comb += self.invalid.eq(invalid_r | invalid_w)
        return m
