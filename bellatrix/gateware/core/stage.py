from nmigen import Module
from nmigen import Record
from nmigen import Signal
from nmigen import Elaboratable
from nmigen.hdl.rec import Direction
from nmigen.hdl.rec import DIR_FANIN
from nmigen.hdl.rec import DIR_FANOUT
from nmigen.build import Platform
from functools import reduce
from operator import or_
from typing import List, Tuple, Optional

Layout = List[Tuple[str, int, bool]]


class _Endpoint(Record):
    '''Define the input/output of a stage'''
    def __init__(self, layout: Layout, direction: Direction, name: str) -> None:
        if direction not in (DIR_FANIN, DIR_FANOUT):
            valid = (DIR_FANIN, DIR_FANOUT)
            raise ValueError(f'Invalid direction for the endpoint. Valid values: {valid}')

        # check for reserved keywords. I will add these signals later
        for item in layout:
            if item[0] in ('valid', 'stall'):
                raise ValueError(f'{item} cannot be used as a signal in the endpoint layout')

        full_layout = [
            ('retire', 1, direction),  # increment instruction counter. TODO check if needed in the end...
            ('valid',  1, direction),
            ('stall',  1, DIR_FANOUT if direction is DIR_FANIN else DIR_FANIN),  # this signal goes from right to left
        ]

        for item in layout:
            full_layout.append(item[:2] + (direction,))  # use only first 2 values in layout: (name, size)

        # create the signals
        super().__init__(full_layout, name=name)


class Stage(Elaboratable):
    def __init__(self, name: str, ep_a_layout: Optional[Layout], ep_b_layout: Optional[Layout]) -> None:
        self.kill   = Signal(name=name + '_kill')
        self.stall  = Signal(name=name + '_stall')
        self.valid  = Signal(name=name + '_valid')
        self.retire = Signal(name=name + '_retire')

        if ep_a_layout is None and ep_b_layout is None:
            raise ValueError("Both endpoints are empty")
        if ep_a_layout is not None:
            self.endpoint_a = _Endpoint(ep_a_layout, DIR_FANIN, name=f'{name}_a')
        if ep_b_layout is not None:
            self.endpoint_b = _Endpoint(ep_b_layout, DIR_FANOUT, name=f'{name}_b')

        self._kill_sources: List[Signal]  = []
        self._stall_sources: List[Signal] = []

    def add_kill_source(self, source: Signal) -> None:
        self._kill_sources.append(source)

    def add_stall_source(self, source: Signal) -> None:
        self._stall_sources.append(source)

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        if hasattr(self, 'endpoint_a'):
            m.d.comb += [
                self.retire.eq(self.endpoint_a.retire),
                self.valid.eq(self.endpoint_a.valid),
                self.endpoint_a.stall.eq(self.stall)
            ]
        else:
            m.d.comb += [
                self.valid.eq(1),
                self.retire.eq(1)
            ]

        if hasattr(self, 'endpoint_b'):
            self.add_stall_source(self.endpoint_b.stall)
            m.d.comb += self.kill.eq(reduce(or_, self._kill_sources, 0))

            with m.If(self.kill):
                m.d.sync += [
                    self.endpoint_b.valid.eq(0),
                    self.endpoint_b.retire.eq(self.retire)
                ]
            with m.Elif(~self.stall):
                m.d.sync += [
                    self.endpoint_b.valid.eq(self.valid),
                    self.endpoint_b.retire.eq(self.retire)
                ]
            with m.Elif(~self.endpoint_b.stall):
                m.d.sync += [
                    self.endpoint_b.valid.eq(0),
                    self.endpoint_b.retire.eq(0)
                ]

        m.d.comb += self.stall.eq(reduce(or_, self._stall_sources, 0))

        return m
