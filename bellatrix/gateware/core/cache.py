from amaranth import Repl
from amaranth import Const
from amaranth import Array
from amaranth import Module
from amaranth import Record
from amaranth import Signal
from amaranth import Memory
from amaranth import Elaboratable
from amaranth.lib.coding import Encoder
from amaranth.utils import log2_int
from amaranth.build import Platform


class Cache(Elaboratable):
    def __init__(self,
                 nlines: int,               # number of lines
                 nwords: int,               # number of words x line x way
                 nways: int,                # number of ways
                 start_addr: int = 0,       # start of cacheable region
                 end_addr: int = 2**32      # end of cacheable region
                 ) -> None:
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
        self.mem_ptr_layout = [
            ('byte', 2),
            ('addr', offset_bits + line_bits)
        ]
        # Complete the 32-bits, or we get errors...
        if extra_bits != 0:
            self.pc_layout.append(('unused', extra_bits))

        # -------------------------------------------------------------------------
        # IO
        self.s1_address  = Record(self.pc_layout)  # (in) Stage 1 address
        self.s1_flush    = Signal()                # (in) Flush cache
        self.s2_address  = Record(self.pc_layout)  # (in) Stage 2 address
        self.s2_valid    = Signal()                # (in) Stage 2 valid
        self.s2_stall    = Signal()                # (in) Stage 2 stall
        self.s2_kill     = Signal()                # (in) Stage 2 kill
        self.s2_miss     = Signal()                # (out) Stage 2 cache miss
        self.s2_rdata    = Signal(32)              # (out) Stage 2 read data

        self.bus_addr  = Record(self.pc_layout)  # (out) bus addr
        self.bus_valid = Signal()                # (out) valid transaction
        self.bus_last  = Signal()                # (out) last access
        self.bus_data  = Signal(32)              # (in) read data from bus
        self.bus_ack   = Signal()                # (in) ack
        self.bus_err   = Signal()                # (in) bus error

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        miss      = Signal()
        miss_data = Signal(32)
        bus_addr  = Record(self.pc_layout)

        way_layout = [
            ('data',    32),
            ('tag',     self.s1_address.tag.shape()),
            ('valid',   1),
            ('sel_lru', 1)
        ]

        ways     = Array(Record(way_layout, name='way_idx{}'.format(idx)) for idx in range(self.nways))
        fill_cnt = Signal.like(self.s1_address.offset)  # counter for refill

        # Check hit/miss
        way_hit = m.submodules.way_hit = Encoder(self.nways)
        for idx, way in enumerate(ways):
            # XORing the tags to check is both are the same
            tag_eq = ~(way.tag ^ self.s2_address.tag).any()
            m.d.comb += way_hit.i[idx].eq(tag_eq & way.valid)

        m.d.comb += miss.eq(way_hit.n & self.s2_valid)

        # set the LRU
        if self.nways == 1:
            lru = Const(0)
        else:
            # LRU es un vector de N bits, cada uno indicado el set a reemplazar
            # como NWAY es máximo 2, cada LRU es de un bit
            lru         = Signal(self.nlines)
            write_ended = Signal()
            access_hit  = Signal()
            lru_bit     = lru.bit_select(self.s2_address.line, 1)
            m.d.comb += [
                write_ended.eq(self.bus_valid & self.bus_ack & self.bus_last),  # only if write is ok, ofc
                access_hit.eq(~way_hit.n & (way_hit.o == lru_bit) & self.s2_valid)
            ]
            with m.If(write_ended | access_hit):
                m.d.sync += lru_bit.eq(~lru_bit)

        # mark the selected way for replacement (during refill)
        if self.nways == 1:
            m.d.comb += ways[0].sel_lru.eq(self.bus_valid)
        else:
            m.d.comb += ways[lru.bit_select(self.s2_address.line, 1)].sel_lru.eq(self.bus_valid)

        # Read data from the cache.
        # Defaults to data from cache if the data is in it (hit).
        # Otherwise (miss), latch the first fetch from memory.
        with m.FSM(name='read'):
            with m.State('IDLE'):
                m.d.comb += self.s2_rdata.eq(ways[way_hit.o].data)
                with m.If(self.bus_valid & self.bus_ack):
                    # latch first access.
                    m.d.sync += miss_data.eq(self.bus_data),
                    m.next = 'LATCHED'
            with m.State('LATCHED'):
                m.d.comb += self.s2_rdata.eq(miss_data)
                with m.If(~(self.bus_valid | self.s2_stall)):
                    # no stalls and done with refill
                    m.next = 'IDLE'

        # refill the cache
        tag_addr = Signal.like(self.s2_address.line)
        tag_data = Signal.like(self.s2_address.tag)
        with m.FSM(name='refill'):
            with m.State('READ'):
                m.d.comb += self.s2_miss.eq(miss)
                with m.If(miss & ~self.s2_kill):
                    m.d.sync += [
                        tag_addr.eq(self.s2_address.line),
                        tag_data.eq(self.s2_address.tag),
                        self.bus_addr.eq(self.s2_address),
                        self.bus_valid.eq(1),
                        bus_addr.eq(self.s2_address),  # internal use for addressing the cache memory
                        fill_cnt.eq(self.s2_address.offset - 1)  # wrap around: from n to n-1
                    ]
                    m.next = 'REFILL'
            with m.State('REFILL'):
                m.d.comb += [
                    self.s2_miss.eq(1),  # hard miss
                    self.bus_last.eq(fill_cnt == self.bus_addr.offset)  # check if this is the last access to memory
                ]
                # For each ack, increase the offset field of the bus address.
                with m.If(self.bus_ack):
                    m.d.sync += self.bus_addr.offset.eq(self.bus_addr.offset + 1)
                # conditions to end the refill
                with m.If((self.bus_ack & self.bus_last) | self.bus_err | self.s1_flush | self.s2_kill):
                    m.d.sync += self.bus_valid.eq(0)
                    m.next = 'NOP'
            with m.State('NOP'):
                m.d.comb += self.s2_miss.eq(0)
                m.next = 'READ'

        # generate for N ways
        for way in ways:
            # create the memory structures for valid, tag and data.
            # Transparent = requires a EN(able) signal to read/write
            valid = Signal(self.nlines)  # Valid bits

            tag_m  = Memory(width=len(way.tag), depth=self.nlines)  # tag memory
            tag_rp = tag_m.read_port(transparent=False)
            tag_wp = tag_m.write_port()
            m.submodules += tag_rp, tag_wp

            data_m  = Memory(width=32, depth=self.nlines * self.nwords)  # data memory
            data_rp = data_m.read_port(transparent=False)
            data_wp = data_m.write_port(granularity=8)
            m.submodules += data_rp, data_wp

            # handle valid
            with m.If(self.s1_flush):
                m.d.sync += valid.eq(0)
            with m.Elif(way.sel_lru):
                m.d.sync += valid.bit_select(bus_addr.line, 1).eq(self.bus_last & self.bus_ack)  # end of refill.

            # casting
            rdata_ptr = Record(self.mem_ptr_layout)
            wdata_ptr = Record(self.mem_ptr_layout)

            m.d.comb += [
                rdata_ptr.eq(self.s1_address),
                wdata_ptr.eq(self.bus_addr),

                tag_rp.addr.eq(self.s1_address.line),
                tag_rp.en.eq(~self.s2_stall),
                tag_wp.addr.eq(tag_addr),
                tag_wp.data.eq(tag_data),
                tag_wp.en.eq(way.sel_lru & self.bus_ack & self.bus_last),

                data_rp.addr.eq(rdata_ptr.addr),
                data_rp.en.eq(~self.s2_stall),

                way.data.eq(data_rp.data),
                way.tag.eq(tag_rp.data),
                way.valid.eq(valid.bit_select(self.s2_address.line, 1)),
                data_wp.addr.eq(wdata_ptr.addr),
                data_wp.data.eq(self.bus_data),
                data_wp.en.eq(Repl(way.sel_lru & self.bus_ack, 4)),
            ]

        return m
