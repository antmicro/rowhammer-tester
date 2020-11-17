from migen import *

from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus
from litedram.frontend.dma import LiteDRAMDMAReader

# FIXME: add add_csr() function just like litedram dma does
# FIXME: reset signal
class Reader(Module, AutoCSR):
    def __init__(self, dram_port):
        self.reset     = CSRStorage()
        self.start     = CSRStorage()
        self.count     = CSRStorage(size=32)

        # 'generator' mask used by address and pattern tables
        self.gen_mask  = CSRStorage(size=32)
        self.mem_mask  = CSRStorage(size=32)

        self.done      = CSRStatus(size=32)
        self.ready     = CSRStatus()

        # FIXME: Support other configurations
        assert dram_port.data_width == 128
        dma = LiteDRAMDMAReader(dram_port)
        self.submodules += dma

        # FIXME: Merge w[0,1,2,3] into one memory
        self.memory_w0  = Memory(32, 1024)
        self.memory_w1  = Memory(32, 1024)
        self.memory_w2  = Memory(32, 1024)
        self.memory_w3  = Memory(32, 1024)
        self.memory_adr = Memory(32, 1024) # FIXME: it's really an offset
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


        # ----------------- Address FSM -----------------
        # Address source
        counter_adr = Signal(32)

        self.comb += [
            adr_port.adr.eq(counter_adr & self.gen_mask.storage),
            dma.sink.address.eq((counter_adr & self.mem_mask.storage) + adr_port.dat_r),
        ]

        # Using temporary state 'WAIT' to obtain address offset from memory
        fsm_adr = FSM(reset_state="IDLE")
        self.submodules += fsm_adr
        fsm_adr.act("IDLE",
            If(self.start.storage,
                NextValue(counter_adr, 0),
                NextState("WAIT"),
            )
        )
        fsm_adr.act("WAIT",
            If(counter_adr >= self.count.storage,
                NextState("DONE")
            ).Else(
                NextState("WR_ADR")
            )
        )
        fsm_adr.act("WR_ADR",
            dma.sink.valid.eq(1),
            If(dma.sink.ready,
                NextValue(counter_adr, counter_adr + 1),
                NextState("WAIT")
            )
        )
        fsm_adr.act("DONE",
            If(self.reset.storage,
                NextState("IDLE")
            )
        )

        # ------------- Pattern FSM ----------------
        counter_gen = Signal(32)
        self.comb += [
            w0_port.adr.eq(counter_gen & self.gen_mask.storage),
            w1_port.adr.eq(counter_gen & self.gen_mask.storage),
            w2_port.adr.eq(counter_gen & self.gen_mask.storage),
            w3_port.adr.eq(counter_gen & self.gen_mask.storage),
        ]

        pattern = Signal(32 * 4)
        self.comb += pattern.eq(Cat( \
            w0_port.dat_r, \
            w1_port.dat_r, \
            w2_port.dat_r, \
            w3_port.dat_r \
        )),

        # Unmatched memory offsets
        from litex.soc.interconnect import stream
        err_fifo = stream.SyncFIFO([('data', 32)], 16, False)
        self.submodules += err_fifo

        self.err_rd = CSRStatus(size=32)
        self.comb += [
            self.err_rd.status.eq(err_fifo.source.data),
            err_fifo.source.ready.eq(self.err_rd.we),
        ]
        self.err_rdy = CSRStatus()
        self.comb += self.err_rdy.status.eq(err_fifo.source.valid)

        self.skipfifo = CSRStorage()

        # Progress register
        self.comb += self.done.status.eq(counter_gen)

        fsm_pattern = FSM(reset_state="IDLE")
        self.submodules += fsm_pattern
        fsm_pattern.act("IDLE",
            If(self.start.storage,
                NextValue(counter_gen, 0),
                NextState("WAIT"),
            )
        )
        fsm_pattern.act("WAIT",
            If(counter_gen >= self.count.storage,
                NextState("DONE")
            ).Else(
                NextState("RD_DATA")
            )
        )
        fsm_pattern.act("RD_DATA",
            dma.source.ready.eq(1),
            If(dma.source.valid,
                NextValue(counter_gen, counter_gen + 1),
                If(dma.source.data != pattern,
                    NextValue(err_fifo.sink.data, counter_gen),
                    If(self.skipfifo.storage,
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
            err_fifo.sink.valid.eq(1),
            If(self.reset.storage,
                NextState("IDLE")
            ).Elif(err_fifo.sink.ready,
                NextState("WAIT")
            )
        )
        fsm_pattern.act("DONE",
            self.ready.status.eq(1),
            If(self.reset.storage,
                NextState("IDLE"))
        )
