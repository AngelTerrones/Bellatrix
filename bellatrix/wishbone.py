from nmigen import Module
from nmigen import Record
from nmigen import Array
from nmigen import Elaboratable
from nmigen.hdl.rec import DIR_FANIN
from nmigen.hdl.rec import DIR_FANOUT
from nmigen.lib.coding import PriorityEncoder
from nmigen.build import Platform
from typing import Dict


class CycleType:
    CLASSIC   = 0
    CONSTANT  = 1
    INCREMENT = 2
    END       = 7


wishbone_layout = [
    ('addr',  32, DIR_FANOUT),
    ('dat_w', 32, DIR_FANOUT),
    ('sel',    4, DIR_FANOUT),
    ('we',     1, DIR_FANOUT),
    ('cyc',    1, DIR_FANOUT),
    ('stb',    1, DIR_FANOUT),
    ('cti',    3, DIR_FANOUT),
    ('bte',    2, DIR_FANOUT),
    ('dat_r', 32, DIR_FANIN),
    ('ack',    1, DIR_FANIN),
    ('err',    1, DIR_FANIN)
]


class Arbiter(Elaboratable):
    def __init__(self) -> None:
        self.bus = Record(wishbone_layout)
        self._ports: Dict[int, Record] = dict()

    def add_port(self, priority: int) -> Record:
        # check if the priority is a number
        if not isinstance(priority, int) or priority < 0:
            raise TypeError('Priority must be a positive integer: {}'.format(priority))
        # check for duplicates
        if priority in self._ports:
            raise ValueError('Duplicated priority: {}'.format(priority))

        port = self._ports[priority] = Record(wishbone_layout)
        return port

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        ports  = [port for prio, port in sorted(self._ports.items())]  # sort port for priority
        aports = Array(ports)
        bus_pe = m.submodules.bus_prio = PriorityEncoder(len(ports))

        with m.If(~self.bus.cyc):
            for idx, port in enumerate(ports):
                m.d.sync += bus_pe.i[idx].eq(port.cyc)

        bselected = aports[bus_pe.o]

        m.d.comb += [
            self.bus.addr.eq(bselected.addr),
            self.bus.dat_w.eq(bselected.dat_w),
            self.bus.sel.eq(bselected.sel),
            self.bus.we.eq(bselected.we),
            self.bus.cyc.eq(bselected.cyc),
            self.bus.stb.eq(bselected.stb),
            self.bus.cti.eq(bselected.cti),
            self.bus.bte.eq(bselected.bte),
            bselected.dat_r.eq(self.bus.dat_r),
            bselected.ack.eq(self.bus.ack),
            bselected.err.eq(self.bus.err)
        ]

        return m
