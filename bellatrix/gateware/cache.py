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


class ICache(Elaboratable):
    def __init__(self,
                 nlines: int,           # number of lines
                 nwords: int,           # number of words x line x way
                 nways: int,            # number of ways
                 start_addr: int = 0,   # start of cacheable region
                 end_addr: int = 2**32  # end of cacheable region
                 ) -> None:
        # enable write -> data cache
        if nlines == 0 or (nlines & (nlines - 1)):
            raise ValueError(f'nlines must be a power of 2: {nlines}')
        if nwords not in (4, 8, 16):
            raise ValueError(f'nwords must be 4, 8 or 16: {nwords}')
        if nways not in (1, 2):
            raise ValueError(f'nways must be 1 or 2: {nways}')

        self.nlines       = nlines
        self.nwords       = nwords
        self.nways        = nways
        self.start_addr   = start_addr
        self.end_addr     = end_addr
        offset_bits       = log2_int(nwords)
        line_bits         = log2_int(nlines)
        addr_bits         = log2_int(end_addr - start_addr, need_pow2=False)
        tag_bits          = addr_bits - line_bits - offset_bits - 2
        extra_bits        = 32 - tag_bits - line_bits - offset_bits - 2

        self.pc_layout = [
            ('byte',   2),
            ('offset', offset_bits),
            ('line',   line_bits),
            ('tag',    tag_bits)
        ]
        if extra_bits != 0:
            self.pc_layout.append(('unused', extra_bits))

        # -------------------------------------------------------------------------
        # IO
        self.s1_address = Record(self.pc_layout)
        self.s1_flush   = Signal()

        self.s2_address = Record(self.pc_layout)
        self.s2_valid   = Signal()
        self.s2_stall   = Signal()
        self.s2_kill    = Signal()
        self.s2_miss    = Signal()
        self.s2_rdata   = Signal(32)

        self.bus_addr  = Record(self.pc_layout)
        self.bus_valid = Signal()
        self.bus_last  = Signal()
        self.bus_data  = Signal(32)
        self.bus_ack   = Signal()
        self.bus_err   = Signal()

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        miss = Signal()

        way_layout = [
            ('data',      32 * self.nwords),
            ('tag',       self.s1_address.tag.shape()),
            ('valid',     1),
            ('sel_lru',   1)
        ]

        ways     = Array(Record(way_layout, name='way_idx{}'.format(_way)) for _way in range(self.nways))
        fill_cnt = Signal.like(self.s1_address.offset)

        # Check hit/miss
        way_hit = m.submodules.way_hit = Encoder(self.nways)
        for idx, way in enumerate(ways):
            m.d.comb += way_hit.i[idx].eq((way.tag == self.s2_address.tag) & way.valid)

        m.d.comb += self.s2_miss.eq(way_hit.n)
        m.d.comb += miss.eq(self.s2_miss & self.s2_valid)

        # set the LRU
        if self.nways == 1:
            lru = Const(0)
        else:
            # LRU es un vector de N bits, cada uno indicado el set a reemplazar
            # como NWAY es máximo 2, cada LRU es de un bit
            lru         = Signal(self.nlines)
            _lru        = lru.bit_select(self.s2_address.line, 1)
            write_ended = self.bus_valid & self.bus_ack & self.bus_last  # err ^ ack = = 1
            access_hit  = ~miss & (way_hit.o == _lru)
            with m.If(write_ended | access_hit):
                m.d.sync += _lru.eq(~_lru)

        # read data from the cache
        m.d.comb += self.s2_rdata.eq(ways[way_hit.o].data.word_select(self.s2_address.offset, 32))

        tag_addr = Signal.like(self.s2_address.line)
        tag_data = Signal.like(self.s2_address.tag)
        with m.FSM():
            with m.State('READ'):
                with m.If(miss & ~self.s2_kill):
                    m.d.sync += [
                        tag_addr.eq(self.s2_address.line),
                        tag_data.eq(self.s2_address.tag),
                        self.bus_addr.eq(self.s2_address),
                        self.bus_valid.eq(1),
                        fill_cnt.eq(self.s2_address.offset - 1)
                    ]
                    m.next = 'REFILL'
            with m.State('REFILL'):
                m.d.comb += self.bus_last.eq(fill_cnt == self.bus_addr.offset)

                with m.If(self.bus_ack):
                    m.d.sync += self.bus_addr.offset.eq(self.bus_addr.offset + 1)
                with m.If((self.bus_ack & self.bus_last) | self.bus_err | self.s1_flush | self.s2_kill):
                    m.d.sync += self.bus_valid.eq(0)
                with m.If(~self.bus_valid):
                    m.d.sync += self.bus_valid.eq(0)
                    m.next = 'READ'

        # # mark the selected way for replacement (refill)
        m.d.comb += ways[lru.bit_select(self.s2_address.line, 1)].sel_lru.eq(self.bus_valid)

        # generate for N ways
        for way in ways:
            # create the memory structures for valid, tag and data.
            valid = Signal(self.nlines)  # Valid bits

            tag_m    = Memory(width=len(way.tag), depth=self.nlines)  # tag memory
            tag_rp   = tag_m.read_port()
            tag_wp   = tag_m.write_port()
            m.submodules += tag_rp, tag_wp

            data_m  = Memory(width=len(way.data), depth=self.nlines)  # data memory
            data_rp = data_m.read_port()
            data_wp = data_m.write_port(granularity=32)  # implica que solo puedo escribir palabras de 32 bits.
            m.submodules += data_rp, data_wp

            # handle valid
            with m.If(self.s1_flush):  # flush
                m.d.sync += valid.eq(0)
            with m.Elif(way.sel_lru):  # refill incomplete
                m.d.sync += valid.bit_select(self.bus_addr.line, 1).eq(self.bus_last & self.bus_ack)

            read_addr = Signal.like(self.s1_address.line)

            with m.FSM():
                with m.State('IDLE'):
                    with m.If(self.s2_stall):
                        m.d.comb += read_addr.eq(self.s2_address.line)
                    with m.Else():
                        m.d.comb += read_addr.eq(self.s1_address.line)

                    with m.If(self.s2_kill):
                        m.next = 'KILLED'
                    with m.Elif(miss):
                        m.next = 'REFILL'
                with m.State('REFILL'):
                    m.d.comb += read_addr.eq(self.s2_address.line)

                    with m.If(self.s2_kill):
                        m.next = 'IDLE'
                    with m.Elif(~self.bus_valid):
                        m.d.comb += read_addr.eq(self.s1_address.line)
                        m.next = 'IDLE'
                with m.State('KILLED'):
                    m.d.comb += read_addr.eq(self.s1_address.line)
                    m.next = 'IDLE'

            m.d.comb += [
                tag_rp.addr.eq(read_addr),

                tag_wp.addr.eq(tag_addr),
                tag_wp.data.eq(tag_data),
                tag_wp.en.eq(way.sel_lru & self.bus_ack & self.bus_last),

                data_rp.addr.eq(read_addr),

                way.data.eq(data_rp.data),
                way.tag.eq(tag_rp.data),
                way.valid.eq(valid.bit_select(self.s2_address.line, 1))
            ]
            m.d.comb += [
                data_wp.addr.eq(self.bus_addr.line),
                data_wp.data.eq(Repl(self.bus_data, self.nwords)),
                data_wp.en.bit_select(self.bus_addr.offset, 1).eq(way.sel_lru & self.bus_ack),
            ]

        return m


class DCache(Elaboratable):
    pass
