from amaranth import Module
from amaranth import Record
from amaranth import Array
from amaranth import Elaboratable
from amaranth.hdl.rec import DIR_FANOUT
from amaranth.lib.coding import PriorityEncoder
from amaranth.build import Platform
from amaranth_soc.wishbone.bus import Interface
from typing import Dict


class Arbiter(Elaboratable):
    def __init__(self, addr_width, data_width, granularity=None, features=frozenset()) -> None:
        self.bus = Interface(addr_width=addr_width,
                             data_width=data_width,
                             granularity=granularity,
                             features=features,
                             name='arbiter_bus'
                             )
        self._ports: Dict[int, Record] = dict()

        self.addr_w      = addr_width
        self.data_w      = data_width
        self.granularity = granularity
        self.features    = features

    def add_port(self, priority: int) -> Record:
        # check if the priority is a number
        if not isinstance(priority, int) or priority < 0:
            raise TypeError('Priority must be a positive integer: {}'.format(priority))
        # check for duplicates
        if priority in self._ports:
            raise ValueError('Duplicated priority: {}'.format(priority))

        port = self._ports[priority] = Interface(addr_width=self.addr_w,
                                                 data_width=self.data_w,
                                                 granularity=self.granularity,
                                                 features=self.features,
                                                 name=f'arbiter_m{priority}'
                                                 )
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

        for name, size, direction in self.bus.layout:
            if direction is DIR_FANOUT:
                m.d.comb += getattr(self.bus, name).eq(getattr(bselected, name))
            else:
                m.d.comb += getattr(bselected, name).eq(getattr(self.bus, name))

        return m
