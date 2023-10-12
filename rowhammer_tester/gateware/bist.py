from migen import *

from migen.genlib.coding import Decoder as OneHotDecoder

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus, CSR
from litex.soc.integration.doc import AutoDoc, ModuleDoc

from litedram.frontend.dma import LiteDRAMDMAReader, LiteDRAMDMAWriter


class PatternMemory(Module):
    """
    Memory for storing access pattern

    It consists of two separate memories: `data` and `addr`, each of `mem_depth`,
    but with different word widths. BIST modules read corresponding pairs (`data`,
    `addr`) during operation. BISTWriter writes `data` to the given `addr`,
    BISTReader reads `addr` and compares the data read to `data` from the pattern.
    """
    def __init__(self, data_width, mem_depth, addr_width=32, pattern_init=None):
        addr_init, data_init = None, None
        if pattern_init is not None:
            addr_init, data_init = zip(*pattern_init)

        self.data = Memory(data_width, mem_depth, init=data_init)
        self.addr = Memory(addr_width, mem_depth, init=addr_init)
        self.specials += self.data, self.addr


class AddressSelector(Module):
    # Selects addresses given two mask as done in:
    # https://github.com/google/hammer-kit/blob/40f3988cac39e20ed0294d20bc886e17376ef47b/hammer.c#L270
    def __init__(self, nbits):
        self.address        = Signal(nbits)     # part of address used for selection
        self.selected       = Signal()          # 1 if selection_mask matches
        self.divisor_mask   = Signal(nbits)     # modulo division using provided mask
        self.selection_mask = Signal(2**nbits)  # used to select addresses after division

        decoder = OneHotDecoder(len(self.selection_mask))
        self.submodules += decoder
        assert len(decoder.i) == len(self.divisor_mask)
        assert len(decoder.o) == len(self.selection_mask)

        self.sync += [
            decoder.i.eq(self.address & self.divisor_mask),
            self.selected.eq((self.selection_mask & decoder.o) != 0),
        ]


class RowDataInverter(Module, AutoCSR):
    """
    Inverts data for given range of row bits

    Specify small range, e.g. rowbits=5, keep in mind that
    AddressSelector has to construct one-hot encoded signal
    with width of 2**rowbits with 1 bit per row, so it quickly
    becomes huge.
    """
    def __init__(self, addr, data_in, data_out, rowbits, row_shift):
        nrows = 2**rowbits
        assert rowbits <= 6, \
            'High rowbits={} leads to {}-bit selection_mask, this is most likely not desired.'.format(rowbits, nrows) \
            + ' See:\n{}'.format(self.__doc__)

        self.submodules.selector = selector = AddressSelector(nbits=rowbits)

        self.comb += [
            selector.address.eq(addr[row_shift:row_shift + rowbits]),
        ]
        self.sync += [
            If(selector.selected,
                data_out.eq(~data_in)
            ).Else(
                data_out.eq(data_in)
            )
        ]

    def add_csrs(self):
        self._divisor_mask = CSRStorage(len(self.selector.divisor_mask),
            description="Divisor mask for selecting rows for which pattern data gets inverted")
        self._selection_mask = CSRStorage(len(self.selector.selection_mask),
            description="Selection mask for selecting rows for which pattern data gets inverted")

        self.comb += [
            self.selector.divisor_mask.eq(self._divisor_mask.storage),
            self.selector.selection_mask.eq(self._selection_mask.storage),
        ]


class BISTModule(Module):
    """
    Provides access to RAM to store access pattern: `mem_addr` and `mem_data`.
    The pattern address space can be limited using the `data_mask`.

    For example, having `mem_adr` filled with `[ 0x04, 0x02, 0x03, ... ]`
    and `mem_data` filled with `[ 0xff, 0xaa, 0x55, ... ]` and setting
    `data_mask = 0b01`, the pattern [(address, data), ...] written will be:
    `[(0x04, 0xff), (0x02, 0xaa), (0x04, 0xff), ...]` (wraps due to masking).

    DRAM memory range that is being accessed can be configured using `mem_mask`.

    To use this module, make sure that `ready` is 1, then write the desired
    number of transfers to `count`. Writing to the `start` CSR will initialize
    the operation. When the operation is ongoing `ready` will be 0.
    """
    def __init__(self, pattern_mem):
        self.start  = Signal()
        self.ready  = Signal()
        self.modulo = Signal()
        self.count  = Signal(32)
        self.done   = Signal(32)

        self.mem_mask = Signal(32)
        self.data_mask = Signal(max=pattern_mem.data.depth)
        self.data_div = Signal(max=pattern_mem.data.depth)

        self.data_port = pattern_mem.data.get_port(mode=READ_FIRST)
        self.addr_port = pattern_mem.addr.get_port(mode=READ_FIRST)
        self.specials += self.data_port, self.addr_port

    def add_csrs(self):
        self._start = CSR()
        self._start.description = 'Write to the register starts the transfer (if ready=1)'
        self._ready = CSRStatus(description='Indicates that the transfer is not ongoing')
        self._modulo = CSRStorage(description='When set use modulo to calculate DMA transfers address'
            ' rather than bit masking')
        self._count = CSRStorage(size=len(self.count), description='Desired number of DMA transfers')
        self._done = CSRStatus(size=len(self.done), description='Number of completed DMA transfers')
        self._mem_mask = CSRStorage(
            size        = len(self.mem_mask),
            description = 'DRAM address mask for DMA transfers'
        )
        self._data_mask = CSRStorage(
            size        = len(self.data_mask),
            description = 'Pattern memory address mask'
        )
        self._data_div = CSRStorage(
            size        = len(self.data_mask),
            description = 'Pattern memory address divisior-1'
        )

        self.comb += [
            self.start.eq(self._start.re),
            self._ready.status.eq(self.ready),
            self.modulo.eq(self._modulo.storage),
            self.count.eq(self._count.storage),
            self._done.status.eq(self.done),
            self.mem_mask.eq(self._mem_mask.storage),
            self.data_mask.eq(self._data_mask.storage),
            self.data_div.eq(self._data_div.storage),
        ]


class Writer(BISTModule, AutoCSR, AutoDoc):
    def __init__(self, dram_port, pattern_mem, *, rowbits, row_shift):
        super().__init__(pattern_mem)

        self.doc = ModuleDoc("""
DMA DRAM writer.

Allows to fill DRAM with a predefined pattern using DMA.

Pattern
-------

{common}
        """.format(common=BISTModule.__doc__))

        dma = LiteDRAMDMAWriter(dram_port, fifo_depth=4, fifo_buffered=True)
        self.submodules.dma = dma

        cmd_counter = Signal(32)
        mem_addr    = Signal.like(self.data_mask)
        self.dram_addr = dram_addr = Signal.like(dma.sink.address)

        wait_counter = Signal(max=3)

        self.comb += [
            self.done.eq(cmd_counter),
            # pattern
            self.data_port.adr.eq(mem_addr),
            self.addr_port.adr.eq(mem_addr),
            # DMA
            dma.sink.address.eq(dram_addr),
        ]

        # DMA data may be inverted using AddressSelector
        self.submodules.inverter = RowDataInverter(
            addr      = dram_addr,
            data_in   = self.data_port.dat_r,
            data_out  = dma.sink.data,
            rowbits   = rowbits,
            row_shift = row_shift,
        )

        self.submodules.fsm = fsm = FSM()
        fsm.act("READY",
            self.ready.eq(1),
            If(self.start,
                NextValue(cmd_counter, 0),
                NextValue(mem_addr, 0),
                NextState("COMPUTE_MEM_ADDR"),
            )
        )
        fsm.act("COMPUTE_MEM_ADDR",
            If(~self.modulo,
                NextValue(mem_addr, cmd_counter[:len(self.data_mask)] & self.data_mask),
            ),
            If(cmd_counter >= self.count,
                NextState("READY")
            ).Else(
                NextState("WAIT_FOR_DRAM_ADDR"),
            )
        )
        fsm.act("WAIT_FOR_DRAM_ADDR",
            NextState("COMPUTE_DRAM_ADDR"),
        )
        fsm.act("COMPUTE_DRAM_ADDR",
            NextValue(wait_counter, 0),
            NextValue(dram_addr, self.addr_port.dat_r +
                (cmd_counter & self.mem_mask)),
            NextState("INVERT_COMPUTE"),
        )
        fsm.act("INVERT_COMPUTE",
            If(wait_counter == 2,
                NextState("SEND")
            ),
            NextValue(wait_counter, wait_counter + 1),
        )
        fsm.act("SEND",
            dma.sink.valid.eq(1),
            If(dma.sink.ready,
                NextValue(cmd_counter, cmd_counter + 1),
                If(self.modulo & (mem_addr == self.data_div),
                    NextValue(mem_addr, 0),
                ).Elif(self.modulo,
                    NextValue(mem_addr, mem_addr + 1),
                ),
                NextState("COMPUTE_MEM_ADDR")
            )
        )

    def add_csrs(self):
        super().add_csrs()
        self.inverter.add_csrs()
        self._last_address = CSRStatus(size=32, description='Number of completed DMA transfers')
        self.sync += [
            If(self.dma.sink.valid & self.dma.sink.ready,
                self._last_address.status.eq(self.dram_addr)
            ),
        ]


class Reader(BISTModule, AutoCSR, AutoDoc):
    def __init__(self, dram_port, pattern_mem, *, rowbits, row_shift):
        super().__init__(pattern_mem)

        self.doc = ModuleDoc("""
DMA DRAM reader.

Allows to check DRAM contents against a predefined pattern using DMA.

Pattern
-------

{common}

Reading errors
--------------

This module allows to check the locations of errors in the memory.
It scans the configured memory area and compares the values read to
the predefined pattern. If `skip_fifo` is 0, this module will stop
after each error encountered, so that it can be examined. Wait until
the `error_ready` CSR is 1. Then use the CSRs `error_offset`,
`error_data` and `error_expected` to examine the errors in the current
transfer. To continue reading, write 1 to `error_continue` CSR.
Setting `skip_fifo` to 1 will disable this behaviour entirely.

The final number of errors can be read from `error_count`.
NOTE: This value represents the number of erroneous *DMA transfers*.

The current progress can be read from the `done` CSR.
        """.format(common=BISTModule.__doc__))

        error_desc = [
            ('offset',   32),
            ('data',     dram_port.data_width),
            ('expected', dram_port.data_width),
        ]

        self.error_count  = Signal(32)
        self.skip_fifo    = Signal()
        self.error        = stream.Endpoint(error_desc)

        dma = LiteDRAMDMAReader(dram_port, fifo_depth=4, fifo_buffered=True)
        self.submodules += dma

        # pass addresses from address FSM (command producer) to pattern FSM (data consumer)
        address_fifo = stream.SyncFIFO([('address', len(dma.sink.address))], depth=4)
        self.submodules += address_fifo

        # ----------------- Address FSM -----------------
        counter_addr = Signal(32)
        mem_addr    = Signal.like(self.data_mask)
        dram_addr   = Signal.like(dma.sink.address)

        self.comb += [
            self.addr_port.adr.eq(mem_addr),
            address_fifo.sink.address.eq(dram_addr),
            dma.sink.address.eq(dram_addr),
        ]

        # Using temporary state 'WAIT' to obtain address offset from memory
        self.submodules.fsm_addr = fsm_addr = FSM()
        fsm_addr.act("READY",
            If(self.start,
                NextValue(counter_addr, 0),
                NextValue(mem_addr, 0),
                NextState("COMPUTE_MEM_ADDR"),
            ),
        )
        fsm_addr.act("COMPUTE_MEM_ADDR",
            If(~self.modulo,
                NextValue(mem_addr, counter_addr[:len(self.data_mask)] & self.data_mask),
            ),
            If(counter_addr >= self.count,
                NextState("READY"),
            ).Else(
                NextState("WAIT_FOR_DRAM_ADDR"),
            ),
        )
        fsm_addr.act("WAIT_FOR_DRAM_ADDR",
            NextState("COMPUTE_DRAM_ADDR"),
        )
        fsm_addr.act("COMPUTE_DRAM_ADDR",
            NextValue(dram_addr, self.addr_port.dat_r +
                (counter_addr & self.mem_mask)),
            NextState("PUSH_TO_FIFO"),
        )
        fsm_addr.act("PUSH_TO_FIFO",
            address_fifo.sink.valid.eq(1),
            If(address_fifo.sink.ready,
                NextState("PUSH_TO_DMA"),
            ),
        )
        fsm_addr.act("PUSH_TO_DMA",
            dma.sink.valid.eq(1),
            If(dma.sink.ready,
                NextValue(counter_addr, counter_addr + 1),
                If(self.modulo & (mem_addr == self.data_div),
                    NextValue(mem_addr, 0),
                ).Elif(self.modulo,
                    NextValue(mem_addr, mem_addr + 1),
                ),
                NextState("COMPUTE_MEM_ADDR")
            )
        )

        # ------------- Pattern FSM ----------------
        counter_gen = Signal(32)
        data_mem_addr = Signal.like(self.data_mask)
        wait_counter = Signal(max=3)

        # Unmatched memory offsets
        error_fifo = stream.SyncFIFO(error_desc, depth=2, buffered=True)
        self.submodules += error_fifo

        # DMA data may be inverted using AddressSelector
        data_expected = Signal.like(dma.source.data)
        self.submodules.inverter = RowDataInverter(
            addr      = address_fifo.source.address,
            data_in   = self.data_port.dat_r,
            data_out  = data_expected,
            rowbits   = rowbits,
            row_shift = row_shift,
        )

        self.submodules.fsm_pattern = fsm_pattern = FSM()
        fsm_pattern.act("READY",
            self.ready.eq(1),
            If(self.start,
                NextValue(counter_gen, 0),
                NextValue(data_mem_addr, 0),
                NextValue(self.error_count, 0),
                NextState("COMPUTE_MEM_ADDR"),
            )
        )
        fsm_pattern.act("COMPUTE_MEM_ADDR",
            If(~self.modulo,
                NextValue(data_mem_addr, counter_gen & self.data_mask),
            ),
            If(counter_gen >= self.count,
                NextState("READY")
            ).Else(
                NextState("WAIT_FOR_DRAM_ADDR"),
            )
        )
        fsm_pattern.act("WAIT_FOR_DRAM_ADDR",
            If(address_fifo.source.valid,
                NextValue(wait_counter, 0),
                NextState("INVERT_COMPUTE"),
            ),
        )
        fsm_pattern.act("INVERT_COMPUTE",
            If(wait_counter == 2,
                NextState("RD_DATA")
            ),
            NextValue(wait_counter, wait_counter + 1),
        )
        fsm_pattern.act("RD_DATA",
            If(dma.source.valid,
                # we must now change FSM state in single cycle
                dma.source.ready.eq(1),
                address_fifo.source.ready.eq(1),
                # count the command
                NextValue(counter_gen, counter_gen + 1),
                # next state depends on if there was an error
                If(dma.source.data != data_expected,
                    NextValue(self.error_count, self.error_count + 1),
                    NextValue(error_fifo.sink.offset, address_fifo.source.address),
                    NextValue(error_fifo.sink.data, dma.source.data),
                    NextValue(error_fifo.sink.expected, data_expected),
                    If(self.skip_fifo,
                        NextState("COMPUTE_MEM_ADDR")
                    ).Else(
                        NextState("WR_ERR")
                    )
                ).Else(
                    NextState("COMPUTE_MEM_ADDR")
                )
            )
        )
        fsm_pattern.act("WR_ERR",
            error_fifo.sink.valid.eq(1),
            If(error_fifo.sink.ready | self.skip_fifo,
                NextState("COMPUTE_MEM_ADDR")
            )
        )

        self.comb += [
            self.data_port.adr.eq(data_mem_addr),
            self.done.eq(counter_gen),
        ]

        error_reg = stream.Endpoint(error_desc)
        self.submodules.fsm_error = fsm_error = FSM()
        fsm_error.act("INVALID",
            If(error_fifo.source.valid,
                error_fifo.source.ready.eq(1),
                If(~self.skip_fifo,
                    NextValue(error_reg.offset, error_fifo.source.offset),
                    NextValue(error_reg.data, error_fifo.source.data),
                    NextValue(error_reg.expected, error_fifo.source.expected),
                    NextState("VALID"),
                )
            )
        )
        fsm_error.act("VALID",
            error_reg.valid.eq(1),
            If(error_reg.ready & error_fifo.source.valid,
                error_fifo.source.ready.eq(1),
                If(~self.skip_fifo,
                    NextValue(error_reg.offset, error_fifo.source.offset),
                    NextValue(error_reg.data, error_fifo.source.data),
                    NextValue(error_reg.expected, error_fifo.source.expected),
                ).Else(
                    NextState("INVALID"),
                )
            ).Elif(error_reg.ready,
                NextState("INVALID"),
            ),
        )

        self.comb += [
            self.error.offset.eq(error_reg.offset),
            self.error.data.eq(error_reg.data),
            self.error.expected.eq(error_reg.expected),
            self.error.valid.eq(error_reg.valid),
            error_reg.ready.eq(self.error.ready),
        ]


    def add_csrs(self):
        super().add_csrs()
        self.inverter.add_csrs()

        self._error_count    = CSRStatus(size=len(self.error_count), description='Number of errors detected')
        self._skip_fifo      = CSRStorage(description='Skip waiting for user to read the errors FIFO')
        self._error_offset   = CSRStatus(size=len(self.mem_mask), description='Current offset of the error')
        self._error_data     = CSRStatus(size=len(self.data_port.dat_r), description='Erroneous value read from DRAM memory')
        self._error_expected = CSRStatus(size=len(self.data_port.dat_r), description='Value expected to be read from DRAM memory')
        self._error_ready    = CSRStatus(description='Error detected and ready to read')
        self._error_continue = CSR()
        self._error_continue.description = 'Continue reading until the next error'

        self.comb += [
            self._error_count.status.eq(self.error_count),
            self.skip_fifo.eq(self._skip_fifo.storage),
            self._error_offset.status.eq(self.error.offset),
            self._error_data.status.eq(self.error.data),
            self._error_expected.status.eq(self.error.expected),
            self.error.ready.eq(self._error_continue.re),
            self._error_ready.status.eq(self.error.valid),
        ]
