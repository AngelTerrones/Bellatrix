from nmigen import Mux
from nmigen import Const
from nmigen import Array
from nmigen import Module
from nmigen import Record
from nmigen import Signal
from nmigen import Memory
from nmigen import Elaboratable
from nmigen.lib.coding import Encoder
from nmigen.utils import log2_int


class Cache(Elaboratable):
    def __init__(self, nlines, nwords, nways, start_addr=0, end_addr=2**32, enable_write=True):
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
        offset_bits       = log2_int(nwords)
        line_bits         = log2_int(nlines)
        addr_bits         = log2_int(end_addr - start_addr, need_pow2=False)
        tag_bits          = addr_bits - line_bits - offset_bits - 2  # -2 because word line.
        extra_bits        = 32 - tag_bits - line_bits - offset_bits - 2

        pc_layout = [
            ('byte',   2),
            ('offset', offset_bits),
            ('line',   line_bits),
            ('tag',    tag_bits)
        ]
        if (extra_bits != 0):
            pc_layout.append(('unused', extra_bits))

        self.s1_address = Record(pc_layout)
        self.s1_flush   = Signal()
        self.s1_valid   = Signal()
        self.s1_stall   = Signal()
        self.s2_address = Record(pc_layout)
        self.s2_evict   = Signal()
        self.s2_valid   = Signal()
        self.s2_miss    = Signal()
        self.s2_rdata   = Signal(32)
        self.s2_re      = Signal()
        if enable_write:
            self.s2_wdata = Signal(32)
            self.s2_sel   = Signal(4)
            self.s2_we    = Signal()

        self.bus_addr  = Record(pc_layout)
        self.bus_valid = Signal()
        self.bus_last  = Signal()
        self.bus_data  = Signal(32)
        self.bus_ack   = Signal()
        self.bus_err   = Signal()

    def elaborate(self, platform):
        m = Module()

        way_layout = [
            ('data',     32 * self.nwords),
            ('tag',      self.s1_address.tag.shape()),
            ('valid',    1),
            ('sel_lru',  1)
        ]
        if self.enable_write:
            way_layout.append(('sel_we',   1))

        ways     = Array(Record(way_layout) for _way in range(self.nways))
        fill_cnt = Signal.like(self.s1_address.offset)
        # set the LRU
        if self.nways == 1:
            lru = Const(0)  # self.nlines
        else:
            lru = Signal(self.nlines)
            with m.If(self.bus_valid & self.bus_ack & self.bus_last):  # err ^ ack == 1
                _lru = lru.bit_select(self.s2_address.line, 1)
                m.d.sync += lru.bit_select(self.s2_address.line, 1).eq(~_lru)

        # hit/miss
        way_hit = m.submodules.way_hit = Encoder(self.nways)
        for idx, way in enumerate(ways):
            m.d.comb += way_hit.i[idx].eq((way.tag == self.s2_address.tag) & way.valid)

        m.d.comb += self.s2_miss.eq(way_hit.n)
        if self.enable_write:
            m.d.comb += ways[way_hit.o].sel_we.eq(self.s2_we & self.s2_valid)

        # read data
        m.d.comb += self.s2_rdata.eq(ways[way_hit.o].data.word_select(self.s2_address.offset, 32))

        with m.FSM():
            with m.State('READ'):
                with m.If(self.s2_re & self.s2_miss & self.s2_valid):
                    m.d.sync += [
                        self.bus_addr.eq(self.s2_address),  # WARNING extra_bits
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
                with m.If(~self.bus_valid | self.s1_flush):
                    # in case of flush, abort ongoing refill.
                    m.next = 'READ'
                    m.d.sync += self.bus_valid.eq(0)

        # mark the way to use (replace)
        m.d.comb += ways[lru.bit_select(self.s2_address.line, 1)].sel_lru.eq(self.bus_valid)

        # generate for N ways
        for way in ways:
            # create the memory structures for valid, tag and data.
            valid = Signal(self.nlines)

            tag_m  = Memory(width=len(way.tag), depth=self.nlines)
            tag_rp = tag_m.read_port()
            tag_wp = tag_m.write_port()
            m.submodules += tag_rp, tag_wp

            data_m  = Memory(width=len(way.data), depth=self.nlines)
            data_rp = data_m.read_port()
            data_wp = data_m.write_port(granularity=32)
            m.submodules += data_rp, data_wp
            if self.enable_write:
                data_cpu_wp = data_m.write_port(granularity=8)
                m.submodules += data_cpu_wp

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
                data_wp.addr.eq(self.bus_addr.line),
                data_wp.data.eq(self.bus_data << (32 * self.bus_addr.offset)),
                data_wp.en.bit_select(self.bus_addr.offset, 1).eq(way.sel_lru & self.bus_ack),

                way.data.eq(data_rp.data),
                way.tag.eq(tag_rp.data),
                way.valid.eq(valid.bit_select(self.s2_address.line, 1))
            ]

            # update cache
            if self.enable_write:
                m.d.comb += [
                    data_cpu_wp.addr.eq(self.s2_address.line),
                    data_cpu_wp.data.eq(self.s2_wdata << (32 * self.s2_address.offset)),
                    # data_cpu_wp.en.bit_select(self.s2_address.offset, 1).eq(way.sel_we)
                    data_cpu_wp.en.eq(Mux(way.sel_we & ~self.s2_miss, self.s2_sel << (4 * self.s2_address.offset), 0))
                ]

        return m
