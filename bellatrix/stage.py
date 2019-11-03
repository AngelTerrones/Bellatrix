from nmigen import Module
from nmigen import Record
from nmigen import Signal
from nmigen import Elaboratable
from nmigen.hdl.rec import DIR_FANIN
from nmigen.hdl.rec import DIR_FANOUT
from functools import reduce
from operator import or_


class _Endpoint(Record):
    def __init__(self, layout, direction):
        if direction not in (DIR_FANIN, DIR_FANOUT):
            raise ValueError('Invalid direction for the endpoint. Valid values: {}'.format((DIR_FANIN, DIR_FANOUT)))

        # check for reserved keywords. I will add these signals later
        for item in layout:
            if item[0] in ('valid', 'stall'):
                raise ValueError('{} cannot be used as a signal in the endpoint layout.')

        full_layout = [
            ('valid', 1, direction),
            ('stall', 1, DIR_FANOUT if direction is DIR_FANIN else DIR_FANIN)
        ]

        for item in layout:
            full_layout.append((*item, direction))

        super().__init__(full_layout, src_loc_at=2)


class Stage(Elaboratable):
    def __init__(self, ep_a_layout, ep_b_layout):
        self.kill  = Signal()
        self.stall = Signal()
        self.valid = Signal()

        if ep_a_layout is None and ep_b_layout is None:
            raise ValueError("Empty endpoint layout. Abort")
        if ep_a_layout is not None:
            self.endpoint_a = _Endpoint(ep_a_layout, DIR_FANIN)
        if ep_b_layout is not None:
            self.endpoint_b = _Endpoint(ep_b_layout, DIR_FANOUT)

        self._kill_sources  = list()
        self._stall_sources = list()

    def add_kill_source(self, source):
        self._kill_sources.append(source)

    def add_stall_source(self, source):
        self._stall_sources.append(source)

    def elaborate(self, platform):
        m = Module()

        # receive the valid signal from the previous stage
        # give the stall signal to the previous stage
        if hasattr(self, 'endpoint_a'):
            m.d.comb += [
                self.valid.eq(self.endpoint_a.valid),
                self.endpoint_a.stall.eq(self.stall)
            ]

        # Add the 'stall' signal from next stage to the list of stall sources to this stage
        # Generate the local 'kill' signal, and give it to the next stage. No conditions.
        # Generate the 'valid' signal
        if hasattr(self, 'endpoint_b'):
            with m.If(self.kill):
                m.d.sync += self.endpoint_b.valid.eq(0)
            with m.Elif(~self.stall):
                m.d.sync += self.endpoint_b.valid.eq(self.valid)
            with m.Elif(~self.endpoint_b.stall):
                m.d.sync += self.endpoint_b.valid.eq(0)

            m.d.comb += self.kill.eq(reduce(or_, self._kill_sources, 0))
            self.add_stall_source(self.endpoint_b.stall)

        m.d.comb += self.stall.eq(reduce(or_, self._stall_sources, 0))

        return m