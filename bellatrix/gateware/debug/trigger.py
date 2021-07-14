from nmigen import Signal
from nmigen import Module
from nmigen import Record
from nmigen import Elaboratable
from nmigen.build import Platform
from bellatrix.gateware.core.csr import CSRFile
from bellatrix.gateware.core.isa import CSRIndex
from bellatrix.gateware.core.isa import PrivMode
from operator import or_
from functools import reduce


class TriggerAction:
    RAISE = 0
    DEBUG = 1


class TriggerType:
    NOP         = 0
    LEGACY      = 1
    MATCH       = 2
    INSTR_COUNT = 3
    INTERRUPT   = 4
    EXCEPTION   = 5


mcontrol_layout = [
    ('load',    1),
    ('store',   1),
    ('execute', 1),
    ('u',       1),
    ('s',       1),
    ('zero0',   1),
    ('m',       1),
    ('match',   4),
    ('chain',   1),
    ('action',  4),
    ('size',    2),
    ('timing',  1),
    ('select',  1),
    ('hit',     1),
    ('maskmax', 6)
]


class TriggerModule(Elaboratable):
    def __init__(self,
                 privmode: Signal,
                 ntriggers: int,
                 csrf: CSRFile,
                 enable_user_mode: bool
                 ) -> None:
        # ----------------------------------------------------------------------
        self.ntriggers        = ntriggers
        self.enable_user_mode = enable_user_mode
        # create the registers
        self.tselect  = csrf.add_register('tselect', CSRIndex.TSELECT)
        self.tdata1   = csrf.add_register('tdata1',  CSRIndex.TDATA1)
        self.tdata2   = csrf.add_register('tdata2',  CSRIndex.TDATA2)
        # IO
        self.x_pc       = Signal(32)
        self.x_bus_addr = Signal(32)
        self.x_load     = Signal()
        self.x_store    = Signal()
        self.x_valid    = Signal()
        self.haltreq    = Signal()  # request halt to debug module
        self.trap       = Signal()  # generate exception (breakpoint)
        # priviledge mode
        self.privmode = privmode

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        # --------------------------------------------------------------------------------
        # Read/write behavior for all registers in this module
        for register in [self.tselect]:
            with m.If(register.update):
                m.d.sync += register.read.eq(register.write)

        triggers      = [Record.like(self.tdata1.read) for _ in range(self.ntriggers)]
        triggers_data = [Record.like(self.tdata2.read) for _ in range(self.ntriggers)]

        for t in triggers:
            m.d.comb += t.type.eq(TriggerType.MATCH)  # support only address/data match

        # handle writes to tselect
        with m.If(self.tselect.update):
            with m.If(self.tselect.write < self.ntriggers):  # no more than ntriggers
                m.d.sync += self.tselect.read.eq(self.tselect.write)

        # select the trigger
        with m.Switch(self.tselect.read):
            for idx, (trigger, trigger_data) in enumerate(zip(triggers, triggers_data)):
                with m.Case(idx):
                    m.d.comb += [
                        self.tdata1.read.eq(trigger),      # trigger visible @tdata1
                        self.tdata2.read.eq(trigger_data)  # data visible @tdata2
                    ]
                    # handle writes to tdata1
                    with m.If(self.tdata1.update):
                        mcontrol = Record([('i', mcontrol_layout), ('o', mcontrol_layout)])
                        m.d.comb += [
                            mcontrol.i.eq(self.tdata1.write.data),  # casting
                            mcontrol.o.execute.eq(mcontrol.i.execute),
                            mcontrol.o.store.eq(mcontrol.i.store),
                            mcontrol.o.load.eq(mcontrol.i.load),
                            mcontrol.o.m.eq(mcontrol.i.m),
                            mcontrol.o.u.eq(mcontrol.i.u),
                            mcontrol.o.action.eq(mcontrol.i.action)
                        ]
                        m.d.sync += [
                            trigger.dmode.eq(self.tdata1.write.dmode),
                            trigger.data.eq(mcontrol.o)
                        ]
                    # handle writes to tdata2
                    with m.If(self.tdata2.update):
                        m.d.sync += trigger_data.data.eq(self.tdata2.write)

        # trigger logic
        hit    = Signal()
        halt   = Signal()
        hit_v  = Signal(self.ntriggers)
        halt_v = Signal(self.ntriggers)

        for idx, (trigger, trigger_data) in enumerate(zip(triggers, triggers_data)):
            with m.Switch(trigger.type):
                with m.Case(TriggerType.MATCH):
                    match    = Signal()
                    mcontrol = Record(mcontrol_layout)
                    m.d.comb += mcontrol.eq(trigger)  # casting, lol

                    bus_match = ~(trigger_data ^ self.x_bus_addr).any()
                    pc_match  = ~(trigger_data ^ self.x_pc).any()
                    with m.If(mcontrol.execute):
                        m.d.comb += match.eq(self.x_valid & pc_match)
                    with m.Elif(mcontrol.store):
                        m.d.comb += match.eq(self.x_valid & self.x_store & bus_match)
                    with m.Elif(mcontrol.load):
                        m.d.comb += match.eq(self.x_valid & self.x_load & bus_match)

                    if self.enable_user_mode:
                        # check the current priv mode, and check the priv enable mode
                        priv_m = self.privmode == PrivMode.Machine
                        priv_u = self.privmode == PrivMode.User
                        hit_tmp = match & ((mcontrol.m & priv_m) | (mcontrol.u & priv_u))
                    else:
                        hit_tmp = match & mcontrol.m

                    m.d.comb += [
                        hit_v[idx].eq(hit_tmp),
                        halt_v[idx].eq(mcontrol.action)
                    ]

        # request signals: halt/exception
        m.d.comb += [
            hit.eq(reduce(or_, hit_v, 0)),
            halt.eq(reduce(or_, halt_v, 0))
        ]
        with m.If(hit):
            with m.If(halt):  # halt = mcontrol.action
                m.d.comb += self.haltreq.eq(self.tdata1.read.dmode)  # enter debug mode only if dmode = 1
            with m.Else():
                m.d.comb += self.trap.eq(1)  # generate exception

        return m
