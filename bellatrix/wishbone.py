from nmigen import Signal
from nmigen import Module
from nmigen import Record
from nmigen import Array
from nmigen import Repl
from nmigen import Elaboratable
from nmigen.hdl.rec import DIR_FANIN
from nmigen.hdl.rec import DIR_FANOUT
from nmigen.lib.coding import PriorityEncoder
from nmigen.build import Platform
from typing import List, Tuple, Callable, Union
from operator import or_
from functools import reduce


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


class Wishbone(Record):
    def __init__(self, name=None) -> None:
        super().__init__(wishbone_layout, name=name)
        # resetless
        self.addr.reset_less  = True
        self.dat_w.reset_less = True
        self.sel.reset_less   = True
        self.we.reset_less    = True
        self.cti.reset_less   = True
        self.bte.reset_less   = True


class Arbiter(Elaboratable):
    def __init__(self,
                 masters: Union[List[Wishbone], Tuple[Wishbone, ...]],
                 slave: Wishbone
                 ) -> None:
        self.masters = masters
        self.slave   = slave

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        aports = Array(self.masters)
        bus_pe = m.submodules.bus_prio = PriorityEncoder(len(self.masters))

        with m.If(~self.slave.cyc):
            for idx, port in enumerate(self.masters):
                m.d.sync += bus_pe.i[idx].eq(port.cyc)

        bselected = aports[bus_pe.o]

        # connect selected master <-> slave signal
        for name, size, direction in wishbone_layout:
            if direction == DIR_FANOUT:
                m.d.comb += getattr(self.slave, name).eq(getattr(bselected, name))
            else:
                m.d.comb += getattr(bselected, name).eq(getattr(self.slave, name))

        return m


class Decoder(Elaboratable):
    def __init__(self,
                 master: Wishbone,
                 slaves: List[Tuple[Wishbone, Callable]],
                 register: bool = False
                 ) -> None:
        # TODO: define better way to define the region
        # Dictionary or tuple of values ?
        self.register = register
        self.master   = master
        self.slaves   = slaves

    def elaborate(self, platform: Platform) -> None:
        m = Module()

        ns = len(self.slaves)
        slave_sel   = Signal(ns)
        slave_sel_r = Signal(ns)

        # decode slave address
        for i, (bus, fun) in enumerate(self.slaves):
            m.d.comb += slave_sel[i].eq(fun(self.master.addr))

        # register the slave select signal
        if self.register:
            m.d.sync += slave_sel_r.eq(slave_sel)
        else:
            m.d.comb += slave_sel_r.eq(slave_sel)

        # connect master -> slave signals
        for slave in self.slaves:
            for name, size, direction in wishbone_layout:
                if direction == DIR_FANOUT and name != 'cyc':
                    m.d.comb += getattr(slave[0], name).eq(getattr(self.master, name))

        # mask the cyc signal using the slave select
        for i, slave in enumerate(self.slaves):
            m.d.comb += slave[0].cyc.eq(self.master.cyc & slave_sel_r[i])

        # connect slave -> master signals
        dat_masked = [Repl(slave_sel_r[i], 32) & self.slaves[i][0].dat_r for i in range(ns)]
        m.d.comb += [
            self.master.dat_r.eq(reduce(or_, dat_masked)),
            self.master.ack.eq(reduce(or_, [slave[0].ack for slave in self.slaves])),
            self.master.err.eq(reduce(or_, [slave[0].err for slave in self.slaves]))
        ]

        return m


class SharedInterconnect(Elaboratable):
    def __init__(self,
                 masters: List[Record],
                 slaves: List[Tuple[Wishbone, Callable]],
                 register: bool = False
                 ) -> None:
        self.register = register
        self.masters  = masters
        self.slaves   = slaves

    def elaborate(self, plaform: Platform) -> Module:
        m = Module()
        shared = Wishbone(name='shared_intercon')
        m.submodules.arbiter = Arbiter(masters=self.masters, slave=shared)
        m.submodules.decoder = Decoder(master=shared, slaves=self.slaves, register=self.register)

        return m


class Crossbar(Elaboratable):
    def __init__(self,
                 masters: List[Record],
                 slaves: List[Tuple[Wishbone, Callable]],
                 register: bool = False
                 ) -> None:
        self.register = register
        self.masters  = masters
        self.slaves   = slaves

    def elaborate(self, plaform: Platform) -> Module:
        m = Module()

        busses, matches = zip(*self.slaves)
        access = [[Wishbone(name='xbar_{}{}'.format(i, j)) for j in self.slaves] for i in self.masters]
        # decode master into access row
        for master, row in zip(self.masters, access):
            row2 = list(zip(row, matches))
            m.submodules += Decoder(master=master, slaves=row2, register=self.register)
        # arbitrate access column -> slave
        for column, bus in zip(zip(*access), busses):
            m.submodules += Arbiter(masters=column, slave=bus)

        return m
