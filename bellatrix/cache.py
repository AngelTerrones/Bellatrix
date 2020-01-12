from nmigen import Mux
from nmigen import Cat
from nmigen import Repl
from nmigen import Const
from nmigen import Array
from nmigen import Module
from nmigen import Record
from nmigen import Signal
from nmigen import Memory
from nmigen import Elaboratable
from nmigen.lib.coding import Encoder
from nmigen.utils import log2_int
from nmigen.build import Platform
from nmigen.hdl.rec import DIR_FANIN


class SnoopPort(Record):
    def __init__(self, name=None) -> None:
        _layout = [
            ('addr', 32, DIR_FANIN),
            ('we',    1, DIR_FANIN),
            ('valid', 1, DIR_FANIN),
            ('ack',   1, DIR_FANIN),
        ]
        super().__init__(_layout, name=name)


class Cache(Elaboratable):
    def __init__(self,
                 nlines: int,  # number of lines
                 nwords: int,  # number of words x line x way
                 nways: int,  # number of ways
                 start_addr: int = 0,  # start of cacheable region
                 end_addr: int = 2**32,  # end of cacheable region
                 enable_write: bool = True  # enable writes to cache
                 ) -> None:
        # enable write -> data cache
        if nlines == 0 or (nlines & (nlines - 1)):
            raise ValueError(f'nlines must be a power of 2: {nlines}')
        if nwords not in (4, 8, 16):
            raise ValueError(f'nwords must be 4, 8 or 16: {nwords}')
        if nways not in (1, 2):
            raise ValueError(f'nways must be 1 or 2: {nways}')

        self.enable_write = enable_write
        self.nlines       = nlines
        self.nwords       = nwords
        self.nways        = nways
        self.start_addr   = start_addr
        self.end_addr     = end_addr
        offset_bits       = log2_int(nwords)
        line_bits         = log2_int(nlines)
        addr_bits         = log2_int(end_addr - start_addr, need_pow2=False)
        tag_bits          = addr_bits - line_bits - offset_bits - 2  # -2 because word line.
        extra_bits        = 32 - tag_bits - line_bits - offset_bits - 2

        self.pc_layout = [
            ('byte',   2),
            ('offset', offset_bits),
            ('line',   line_bits),
            ('tag',    tag_bits)
        ]
        if (extra_bits != 0):
            self.pc_layout.append(('unused', extra_bits))

        # -------------------------------------------------------------------------
        # IO
        self.s1_address = Record(self.pc_layout)
        self.s1_flush   = Signal()
        self.s1_valid   = Signal()
        self.s1_stall   = Signal()
        self.s1_access  = Signal()
        self.s2_address = Record(self.pc_layout)
        self.s2_evict   = Signal()
        self.s2_valid   = Signal()
        self.s2_stall   = Signal()
        self.s2_access  = Signal()
        self.s2_miss    = Signal()
        self.s2_rdata   = Signal(32)
        self.s2_re      = Signal()
        if enable_write:
            self.s2_wdata = Signal(32)
            self.s2_sel   = Signal(4)
            self.s2_we    = Signal()

        self.bus_addr  = Record(self.pc_layout)
        self.bus_valid = Signal()
        self.bus_last  = Signal()
        self.bus_data  = Signal(32)
        self.bus_ack   = Signal()
        self.bus_err   = Signal()

        self.access_cnt = Signal(40)
        self.miss_cnt   = Signal(40)
        # snoop bus
        self.snoop      = SnoopPort(name='cache_snoop')
        self.self_snoop = SnoopPort(name='self_snoop')

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        snoop_addr  = Record(self.pc_layout)
        snoop_valid = Signal()

        # -------------------------------------------------------------------------
        # Performance counter
        # TODO: connect to CSR's performance counter
        with m.If(~self.s1_stall & self.s1_valid & self.s1_access):
            m.d.sync += self.access_cnt.eq(self.access_cnt + 1)
        with m.If(self.s2_valid & self.s2_miss & ~self.bus_valid & self.s2_access):
            m.d.sync += self.miss_cnt.eq(self.miss_cnt + 1)
        # -------------------------------------------------------------------------

        way_layout = [
            ('data',      32 * self.nwords),
            ('tag',       self.s1_address.tag.shape()),
            ('valid',     1),
            ('sel_lru',   1),
            ('snoop_hit', 1)
        ]
        if self.enable_write:
            way_layout.append(('sel_we',   1))

        ways     = Array(Record(way_layout, name='way_idx{}'.format(_way)) for _way in range(self.nways))
        fill_cnt = Signal.like(self.s1_address.offset)

        # Check hit/miss
        way_hit = m.submodules.way_hit = Encoder(self.nways)
        for idx, way in enumerate(ways):
            m.d.comb += way_hit.i[idx].eq((way.tag == self.s2_address.tag) & way.valid)

        m.d.comb += self.s2_miss.eq(way_hit.n)
        if self.enable_write:
            # Asumiendo que hay un HIT, indicar que la vía que dió hit es en la cual se va a escribir
            m.d.comb += ways[way_hit.o].sel_we.eq(self.s2_we & self.s2_valid)

        # set the LRU
        if self.nways == 1:
            # One way: LRU is useless
            lru = Const(0)  # self.nlines
        else:
            # LRU es un vector de N bits, cada uno indicado el set a reemplazar
            # como NWAY es máximo 2, cada LRU es de un bit
            lru         = Signal(self.nlines)
            _lru        = lru.bit_select(self.s2_address.line, 1)
            write_ended = self.bus_valid & self.bus_ack & self.bus_last  # err ^ ack = = 1
            access_hit  = ~self.s2_miss & self.s2_valid & (way_hit.o == _lru)
            with m.If(write_ended | access_hit):
                m.d.sync += _lru.eq(~_lru)

        # read data from the cache
        m.d.comb += self.s2_rdata.eq(ways[way_hit.o].data.word_select(self.s2_address.offset, 32))

        # Snoop
        snoop_use_cache     = Signal()
        snoop_tag_match     = Signal()
        snoop_line_match    = Signal()
        snoop_cancel_refill = Signal()

        bits_range = log2_int(self.end_addr - self.start_addr, need_pow2=False)

        m.d.comb += [
            snoop_addr.eq(self.snoop.addr),  # aux

            snoop_valid.eq(self.snoop.we & self.snoop.valid & self.snoop.ack),
            snoop_use_cache.eq(snoop_addr[bits_range:] == (self.start_addr >> bits_range)),
            snoop_tag_match.eq(snoop_addr.tag == self.s2_address.tag),
            snoop_line_match.eq(snoop_addr.line == self.s2_address.line),
            snoop_cancel_refill.eq(snoop_use_cache & snoop_valid & snoop_line_match & snoop_tag_match),
        ]

        with m.FSM():
            with m.State('READ'):
                with m.If(self.s2_re & self.s2_miss & self.s2_valid):
                    m.d.sync += [
                        self.bus_addr.eq(self.s2_address),
                        self.bus_valid.eq(1),
                        fill_cnt.eq(self.s2_address.offset - 1)
                    ]
                    m.next = 'REFILL'
            with m.State('REFILL'):
                m.d.comb += self.bus_last.eq(fill_cnt == self.bus_addr.offset)
                with m.If(self.bus_ack):
                    m.d.sync += self.bus_addr.offset.eq(self.bus_addr.offset + 1)
                with m.If(self.bus_ack & self.bus_last | self.bus_err):
                    m.d.sync += self.bus_valid.eq(0)
                with m.If(~self.bus_valid | self.s1_flush | snoop_cancel_refill):
                    m.next = 'READ'
                    m.d.sync += self.bus_valid.eq(0)

        # mark the way to use (replace)
        m.d.comb += ways[lru.bit_select(self.s2_address.line, 1)].sel_lru.eq(self.bus_valid)

        # generate for N ways
        for way in ways:
            # create the memory structures for valid, tag and data.
            valid = Signal(self.nlines)  # Valid bits

            tag_m    = Memory(width=len(way.tag), depth=self.nlines)  # tag memory
            tag_rp   = tag_m.read_port()
            snoop_rp = tag_m.read_port()
            tag_wp   = tag_m.write_port()
            m.submodules += tag_rp, tag_wp, snoop_rp

            data_m  = Memory(width=len(way.data), depth=self.nlines)  # data memory
            data_rp = data_m.read_port()
            data_wp = data_m.write_port(granularity=32)  # implica que solo puedo escribir palabras de 32 bits.
            m.submodules += data_rp, data_wp

            # handle valid
            with m.If(self.s1_flush & self.s1_valid):  # flush
                m.d.sync += valid.eq(0)
            with m.Elif(way.sel_lru & self.bus_last & self.bus_ack):  # refill ok
                m.d.sync += valid.bit_select(self.bus_addr.line, 1).eq(1)
            with m.Elif(way.sel_lru & self.bus_err):  # refill error
                m.d.sync += valid.bit_select(self.bus_addr.line, 1).eq(0)
            with m.Elif(self.s2_evict & self.s2_valid & (way.tag == self.s2_address.tag)):  # evict
                m.d.sync += valid.bit_select(self.s2_address.line, 1).eq(0)

            # assignments
            m.d.comb += [
                tag_rp.addr.eq(Mux(self.s1_stall, self.s2_address.line, self.s1_address.line)),
                tag_wp.addr.eq(self.bus_addr.line),
                tag_wp.data.eq(self.bus_addr.tag),
                tag_wp.en.eq(way.sel_lru & self.bus_ack & self.bus_last),

                data_rp.addr.eq(Mux(self.s1_stall, self.s2_address.line, self.s1_address.line)),

                way.data.eq(data_rp.data),
                way.tag.eq(tag_rp.data),
                way.valid.eq(valid.bit_select(self.s2_address.line, 1))
            ]

            # update cache: CPU or Refill
            # El puerto de escritura se multiplexa debido a que la memoria solo puede tener un
            # puerto de escritura.
            if self.enable_write:
                update_addr = Signal(len(data_wp.addr))
                update_data = Signal(len(data_wp.data))
                update_we   = Signal(len(data_wp.en))
                aux_wdata   = Signal(32)

                with m.If(self.bus_valid):
                    m.d.comb += [
                        update_addr.eq(self.bus_addr.line),
                        update_data.eq(Repl(self.bus_data, self.nwords)),
                        update_we.bit_select(self.bus_addr.offset, 1).eq(way.sel_lru & self.bus_ack),
                    ]
                with m.Else():
                    m.d.comb += [
                        update_addr.eq(self.s2_address.line),
                        update_data.eq(Repl(aux_wdata, self.nwords)),
                        update_we.bit_select(self.s2_address.offset, 1).eq(way.sel_we & ~self.s2_miss)
                    ]
                m.d.comb += [
                    # Aux data: no tengo granularidad de byte en el puerto de escritura. Así que para el
                    # caso en el cual el CPU tiene que escribir, hay que construir el dato (wrord) a reemplazar
                    aux_wdata.eq(Cat(
                        Mux(self.s2_sel[0], self.s2_wdata.word_select(0, 8), self.s2_rdata.word_select(0, 8)),
                        Mux(self.s2_sel[1], self.s2_wdata.word_select(1, 8), self.s2_rdata.word_select(1, 8)),
                        Mux(self.s2_sel[2], self.s2_wdata.word_select(2, 8), self.s2_rdata.word_select(2, 8)),
                        Mux(self.s2_sel[3], self.s2_wdata.word_select(3, 8), self.s2_rdata.word_select(3, 8))
                    )),
                    #
                    data_wp.addr.eq(update_addr),
                    data_wp.data.eq(update_data),
                    data_wp.en.eq(update_we),
                ]
            else:
                m.d.comb += [
                    data_wp.addr.eq(self.bus_addr.line),
                    data_wp.data.eq(Repl(self.bus_data, self.nwords)),
                    data_wp.en.bit_select(self.bus_addr.offset, 1).eq(way.sel_lru & self.bus_ack),
                ]

            # snoop
            _match_snoop = Signal()
            self_match   = Signal()

            m.d.comb += [
                snoop_rp.addr.eq(snoop_addr.line),  # read tag memory
                _match_snoop.eq(snoop_rp.data == snoop_addr.tag),
                way.snoop_hit.eq(snoop_use_cache & snoop_valid & _match_snoop & valid.bit_select(snoop_addr.line, 1)),
            ]
            # check is the snoop match a write from this core
            m.d.comb += self_match.eq((self.self_snoop.addr == self.snoop.addr) & self.self_snoop.valid & self.self_snoop.we & self.self_snoop.ack)
            with m.If(way.snoop_hit):
                with m.If(~self_match):
                    m.d.sync += valid.bit_select(snoop_addr.line, 1).eq(0)

        return m
