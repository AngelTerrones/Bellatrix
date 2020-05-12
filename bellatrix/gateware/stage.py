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

Layout = List[Tuple[str, int]]


class _Endpoint(Record):
    def __init__(self, layout: Layout, direction: Direction, name: str) -> None:
        if direction not in (DIR_FANIN, DIR_FANOUT):
            raise ValueError('Invalid direction for the endpoint. Valid values: {}'.format((DIR_FANIN, DIR_FANOUT)))

        # check for reserved keywords. I will add these signals later
        for item in layout:
            if item[0] in ('valid', 'stall'):
                raise ValueError('{} cannot be used as a signal in the endpoint layout.')

        full_layout = [
            ('is_instruction', 1, direction),
            ('valid', 1, direction),
            ('stall', 1, DIR_FANOUT if direction is DIR_FANIN else DIR_FANIN)
        ]
        # add signals to the final layout
        for item in layout:
            full_layout.append(item + (direction,))  # generate new layout, adding direction to each pin

        super().__init__(full_layout, name=name)


class Stage(Elaboratable):
    def __init__(self, name: str, ep_a_layout: Optional[Layout], ep_b_layout: Optional[Layout]) -> None:
        self.kill           = Signal(name=name + '_kill')  # output
        self.stall          = Signal(name=name + '_stall')  # output
        self.valid          = Signal(name=name + '_valid')  # output
        self.is_instruction = Signal(name=name + '_is_instruction')  # output

        if ep_a_layout is None and ep_b_layout is None:
            raise ValueError("Empty endpoint layout. Abort")
        if ep_a_layout is not None:
            self.endpoint_a = _Endpoint(ep_a_layout, DIR_FANIN, name=name + '_a')
        if ep_b_layout is not None:
            self.endpoint_b = _Endpoint(ep_b_layout, DIR_FANOUT, name=name + '_b')

        self._kill_sources: List[Signal]  = []
        self._stall_sources: List[Signal] = []

    def add_kill_source(self, source: Signal) -> None:
        self._kill_sources.append(source)

    def add_stall_source(self, source: Signal) -> None:
        self._stall_sources.append(source)

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        # receive the valid signal from the previous stage
        # give the stall signal to the previous stage
        if hasattr(self, 'endpoint_a'):
            m.d.comb += [
                self.is_instruction.eq(self.endpoint_a.is_instruction | self.endpoint_a.valid),
                self.valid.eq(self.endpoint_a.valid),
                self.endpoint_a.stall.eq(self.stall)
            ]

        # Add the 'stall' signal from the next stage to the list of stall sources to this stage
        # Generate the local 'kill' signal.
        # Generate the 'stall' (registered) signal
        # 'is_instruction' indicates if the stage was a valid instruction once.
        if hasattr(self, 'endpoint_b'):
            with m.If(self.kill):
                m.d.sync += [
                    self.endpoint_b.valid.eq(0),
                    self.endpoint_b.is_instruction.eq(self.is_instruction)
                ]
            with m.Elif(~self.stall):
                m.d.sync += [
                    self.endpoint_b.valid.eq(self.valid),
                    self.endpoint_b.is_instruction.eq(self.is_instruction)
                ]
            with m.Elif(~self.endpoint_b.stall):
                m.d.sync += [
                    self.endpoint_b.valid.eq(0),
                    self.endpoint_b.is_instruction.eq(0)
                ]

            m.d.comb += self.kill.eq(reduce(or_, self._kill_sources, 0))
            self.add_stall_source(self.endpoint_b.stall)

        m.d.comb += self.stall.eq(reduce(or_, self._stall_sources, 0))

        return m
