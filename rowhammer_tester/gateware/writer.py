from migen import *

from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus
from litedram.frontend.dma import LiteDRAMDMAWriter


class Writer(Module, AutoCSR):
    """DRAM DMA memory writer

    This module allows to fill the DRAM with a given pattern.

    DRAM memory range can be configured using `mem_base` and `mem_mask` CSRs.
    The number of DMA transfers is configured using the `count` CSR.

    The access pattern is stored in `mem_data` and `mem_adr`.
    The pattern address space can be limited using the `data_mask` CSR.

    For example, having `mem_adr` filled with `[ 0x04, 0x02, 0x03, ... ]`
    and `mem_data` filled with `[ 0xff, 0xaa, 0x55, ... ]` and setting
    `data_mask = 0b01`, the pattern (address, data) written will be:
    `[(0x04, 0xff), (0x02, 0xaa), (0x04, 0xff), ...]`
    """
    def __init__(self, dram_port, mem_depth):
        self.reset     = CSRStorage(description='Reset the module')
        self.start     = CSRStorage(description='Initialize the transfer')
        self.done      = CSRStatus(description='Indicates that the transfer has finished')

        self.count     = CSRStorage(size=(32*1), description='Desired number of transfers')

        # TODO: remove mem_base as mem_adr should be enough?
        self.mem_base  = CSRStorage(size=32, description='DRAM memory address offset')
        self.mem_mask  = CSRStorage(size=32, description='DRAM memory address mask')
        self.data_mask = CSRStorage(size=32, description='Pattern memories address mask')

        # FIXME: Increase fifo depth
        dma = LiteDRAMDMAWriter(dram_port, fifo_depth=1)
        self.submodules += dma

        self.mem_data = Memory(dram_port.data_width, mem_depth)
        self.mem_adr  = Memory(32, mem_depth)
        self.specials += self.mem_data, self.mem_adr

        self.autocsr_exclude = ('mem_data', 'mem_adr')

        data_port = self.mem_data.get_port()
        adr_port  = self.mem_adr.get_port()
        self.specials += data_port, adr_port

        cmd_counter = Signal(32)

        self.comb += [
            data_port.adr.eq(cmd_counter & self.data_mask.storage),
            adr_port.adr.eq(cmd_counter & self.data_mask.storage),
        ]

        self.comb += [
            dma.sink.address.eq(self.mem_base.storage +
                                adr_port.dat_r + (cmd_counter & self.mem_mask.storage)),
            dma.sink.data.eq(data_port.dat_r),
        ]

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm
        fsm.act("IDLE",
            If(self.start.storage,
                NextValue(cmd_counter, 0),
                NextState("WAIT"),
            )
        )
        fsm.act("WAIT",
            If(cmd_counter >= self.count.storage,
                NextState("DONE")
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
        fsm.act("DONE",
            self.done.status.eq(1),
            If(self.reset.storage,
                NextState("IDLE"))
        )
