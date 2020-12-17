from migen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus, CSR
from litex.soc.integration.doc import AutoDoc, ModuleDoc

from litedram.frontend.dma import LiteDRAMDMAReader, LiteDRAMDMAWriter


class PatternMemory(Module):
    def __init__(self, data_width, mem_depth, addr_width=32):
        self.data = Memory(data_width, mem_depth)
        self.addr = Memory(addr_width, mem_depth)
        self.specials += self.data, self.addr


class BISTModule(Module):
    """
Provides RAM to store access pattern: `mem_addr` and `mem_data`.
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
        self.start = Signal()
        self.ready = Signal()
        self.count = Signal(32)
        self.done  = Signal(32)

        self.mem_mask = Signal(32)
        self.data_mask = Signal(32)

        self.data_port = pattern_mem.data.get_port()
        self.addr_port = pattern_mem.addr.get_port()
        self.specials += self.data_port, self.addr_port

    def add_csrs(self):
        self._start = CSR()
        self._start.description = 'Write to the register starts the transfer (if ready=1)'
        self._ready = CSRStatus(description='Indicates that the transfer is not ongoing')
        self._count = CSRStorage(size=len(self.count), description='Desired number of DMA transfers')
        self._done = CSRStatus(size=len(self.done), description='Number of completed DMA transfers')
        self._mem_mask = CSRStorage(
            size        = len(self.mem_mask),
            description = 'DRAM address mask for DMA transfers'
        )
        self._data_mask = CSRStorage(
            size        = len(self.mem_mask),
            description = 'Pattern memory address mask'
        )

        self.comb += [
            self.start.eq(self._start.re),
            self._ready.status.eq(self.ready),
            self.count.eq(self._count.storage),
            self._done.status.eq(self.done),
            self.mem_mask.eq(self._mem_mask.storage),
            self.data_mask.eq(self._data_mask.storage),
        ]


class Writer(BISTModule, AutoCSR, AutoDoc):
    def __init__(self, dram_port, pattern_mem):
        super().__init__(pattern_mem)

        self.doc = ModuleDoc("""
DMA DRAM writer.

Allows to fill DRAM with a predefined pattern using DMA.

Pattern
-------

{common}
        """.format(common=BISTModule.__doc__))

        # FIXME: Increase fifo depth
        dma = LiteDRAMDMAWriter(dram_port, fifo_depth=1)
        self.submodules += dma

        cmd_counter = Signal(32)

        self.comb += [
            self.done.eq(cmd_counter),
            # pattern
            self.data_port.adr.eq(cmd_counter & self.data_mask),
            self.addr_port.adr.eq(cmd_counter & self.data_mask),
            # DMA
            dma.sink.address.eq(self.addr_port.dat_r + (cmd_counter & self.mem_mask)),
            dma.sink.data.eq(self.data_port.dat_r),
        ]

        self.submodules.fsm = fsm = FSM()
        fsm.act("READY",
            self.ready.eq(1),
            If(self.start,
                NextValue(cmd_counter, 0),
                NextState("WAIT"),
            )
        )
        fsm.act("WAIT",  # TODO: we could pipeline the access
            If(cmd_counter >= self.count,
                NextState("READY")
            ).Else(
                NextState("RUN")
            )
        )
        fsm.act("RUN",
            dma.sink.valid.eq(1),
            If(dma.sink.ready,
                NextValue(cmd_counter, cmd_counter + 1),
                NextState("WAIT")
            )
        )


class Reader(BISTModule, AutoCSR, AutoDoc):
    def __init__(self, dram_port, pattern_mem):
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

The final nubmer of errors can be read from `error_count`.
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

        # FIXME: Increase fifo depth
        dma = LiteDRAMDMAReader(dram_port)
        self.submodules += dma

        # ----------------- Address FSM -----------------
        counter_addr = Signal(32)

        self.comb += [
            self.addr_port.adr.eq(counter_addr & self.data_mask),
            dma.sink.address.eq(self.addr_port.dat_r + (counter_addr & self.mem_mask)),
        ]

        # Using temporary state 'WAIT' to obtain address offset from memory
        self.submodules.fsm_addr = fsm_addr = FSM()
        fsm_addr.act("READY",
            If(self.start,
                NextValue(counter_addr, 0),
                NextState("WAIT"),
            )
        )
        fsm_addr.act("WAIT",  # TODO: we could pipeline the access
            If(counter_addr >= self.count,
                NextState("READY")
            ).Else(
                NextState("WR_ADDR")
            )
        )
        fsm_addr.act("WR_ADDR",
            dma.sink.valid.eq(1),
            If(dma.sink.ready,
                NextValue(counter_addr, counter_addr + 1),
                NextState("WAIT")
            )
        )

        # ------------- Pattern FSM ----------------
        counter_gen = Signal(32)

        # Unmatched memory offsets
        error_fifo = stream.SyncFIFO(error_desc, depth=2, buffered=False)
        self.submodules += error_fifo

        self.comb += [
            self.data_port.adr.eq(counter_gen & self.data_mask),
            self.error.offset.eq(error_fifo.source.offset),
            self.error.data.eq(error_fifo.source.data),
            self.error.expected.eq(error_fifo.source.expected),
            self.error.valid.eq(error_fifo.source.valid),
            error_fifo.source.ready.eq(self.error.ready | self.skip_fifo),
            self.done.eq(counter_gen),
        ]

        self.submodules.fsm_pattern = fsm_pattern = FSM()
        fsm_pattern.act("READY",
            self.ready.eq(1),
            If(self.start,
                NextValue(counter_gen, 0),
                NextValue(self.error_count, 0),
                NextState("WAIT"),
            )
        )
        fsm_pattern.act("WAIT",  # TODO: we could pipeline the access
            If(counter_gen >= self.count,
                NextState("READY")
            ).Else(
                NextState("RD_DATA")
            )
        )
        fsm_pattern.act("RD_DATA",
            dma.source.ready.eq(1),
            If(dma.source.valid,
                NextValue(counter_gen, counter_gen + 1),
                If(dma.source.data != self.data_port.dat_r,
                    NextValue(self.error_count, self.error_count + 1),
                    NextValue(error_fifo.sink.offset, counter_gen),
                    NextValue(error_fifo.sink.data, dma.source.data),
                    NextValue(error_fifo.sink.expected, self.data_port.dat_r),
                    If(self.skip_fifo,
                        NextState("WAIT")
                    ).Else(
                        NextState("WR_ERR")
                    )
                ).Else(
                    NextState("WAIT")
                )
            )
        )
        fsm_pattern.act("WR_ERR",
            error_fifo.sink.valid.eq(1),
            If(error_fifo.sink.ready | self.skip_fifo,
                NextState("WAIT")
            )
        )

    def add_csrs(self):
        super().add_csrs()

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
