from migen import *

from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus
from litedram.frontend.dma import LiteDRAMDMAWriter


class Writer(Module, AutoCSR):
    def __init__(self, dram_port):
        self.reset        = CSRStorage()
        self.start        = CSRStorage()
        self.done         = CSRStatus()

        self.count        = CSRStorage(size=(32*1))

        self.mem_base     = CSRStorage(size=32)
        self.mem_mask     = CSRStorage(size=32)
        self.data_mask    = CSRStorage(size=32) # patterns

        # FIXME: Increase fifo depth
        dma = LiteDRAMDMAWriter(dram_port, fifo_depth=1)
        self.submodules += dma

        self.memory_w0  = Memory(32, 1024)
        self.memory_w1  = Memory(32, 1024)
        self.memory_w2  = Memory(32, 1024)
        self.memory_w3  = Memory(32, 1024)
        self.memory_adr = Memory(32, 1024)
        self.specials += self.memory_w0, self.memory_w1, \
                         self.memory_w2, self.memory_w3, \
                         self.memory_adr

        self.autocsr_exclude = 'memory_w0', 'memory_w1', \
                               'memory_w2', 'memory_w3', \
                               'memory_adr'

        w0_port   = self.memory_w0.get_port()
        w1_port   = self.memory_w1.get_port()
        w2_port   = self.memory_w2.get_port()
        w3_port   = self.memory_w3.get_port()
        adr_port  = self.memory_adr.get_port()
        self.specials += w0_port, w1_port, w2_port, w3_port, adr_port

        cmd_counter = Signal(32)

        self.comb += [
            w0_port.adr.eq(cmd_counter & self.data_mask.storage),
            w1_port.adr.eq(cmd_counter & self.data_mask.storage),
            w2_port.adr.eq(cmd_counter & self.data_mask.storage),
            w3_port.adr.eq(cmd_counter & self.data_mask.storage),
            adr_port.adr.eq(cmd_counter & self.data_mask.storage),
        ]

        self.comb += [
            dma.sink.address.eq(self.mem_base.storage +
                                adr_port.dat_r + (cmd_counter & self.mem_mask.storage)),
            dma.sink.data.eq(Cat(w0_port.dat_r, w1_port.dat_r, w2_port.dat_r, w3_port.dat_r)),
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
