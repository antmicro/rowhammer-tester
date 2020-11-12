from enum import IntEnum, unique
from functools import reduce
from operator import or_

from migen import *
from migen.genlib.coding import Decoder as OneHotDecoder

from litex.soc.interconnect.csr import CSR, CSRStatus, CSRStorage, CSRField, AutoCSR
from litex.soc.integration.doc import AutoDoc, ModuleDoc

@unique
class OpCode(IntEnum):
    NOOP = 0b000
    LOOP = 0b111
    # (ras, cas, we)
    ACT  = 0b100
    PRE  = 0b101
    REF  = 0b110
    ZQC  = 0b001
    READ = 0b010

    @classmethod
    def table(cls):
        div = '+------+-------+\n'
        t = ''
        t += div
        t += '+ Op   + Value +\n'
        t += div.replace('-', '=')
        for op_code in cls:
            t += '+ {:4} | 0b{:03b} +\n'.format(op_code.name, op_code.value)
            t += div
        t = t.rstrip()
        return t

class Decoder(Module):
    __doc__ = """
    **Instruction decoder**

    All instructions are 32-bit. The format of most instructions is the same,
    except for the LOOP instruction, which has a constant TIMESLICE of 0.

    **NOTE:** LOOP instruction will *jump* COUNT times, meaning that the "code"
    inside the loop will effectively be executed COUNT+1 times.

    Op codes:

{op_codes}

    Instruction format::

              LSB                       MSB
        dfi:  OP_CODE | TIMESLICE | ADDRESS
        noop: OP_CODE | TIMESLICE_NOOP
        loop: OP_CODE | COUNT     | JUMP

    Where ADDRESS depends on the DFI command and is one of::

        LSB              MSB
        RANK | BANK | COLUMN
        RANK | BANK | ROW
    """.format(op_codes=OpCode.table())

    # TODO: Load widths from .proto file
    INSTRUCTION    = 32
    OP_CODE        = 3
    TIMESLICE      = 8
    ADDRESS        = 21
    TIMESLICE_NOOP = TIMESLICE + ADDRESS
    LOOP_COUNT     = 20
    LOOP_JUMP      = 9

    def __init__(self, instruction, *, rankbits, bankbits, rowbits, colbits):
        assert len(instruction) == self.INSTRUCTION
        assert self.OP_CODE + self.TIMESLICE_NOOP == self.INSTRUCTION
        assert self.OP_CODE + self.TIMESLICE + self.ADDRESS == self.INSTRUCTION
        assert self.OP_CODE + self.LOOP_COUNT + self.LOOP_JUMP == self.INSTRUCTION
        assert rankbits + bankbits + max(rowbits, colbits) <= self.ADDRESS

        self.op_code = Signal(self.OP_CODE)
        # DFI-mappable instructions
        self.timeslice   = Signal(self.TIMESLICE_NOOP)
        self.address     = Signal(self.ADDRESS)  # TODO: NOOP could resuse it as timeslice
        self.cas         = Signal()
        self.ras         = Signal()
        self.we          = Signal()
        self.dfi_bank    = Signal(bankbits)
        self.dfi_address = Signal(max(rowbits, colbits))
        # Loop instruction
        self.loop_count = Signal(self.LOOP_COUNT)  # max 32K loops
        self.loop_jump  = Signal(self.LOOP_JUMP)  # max jump by 16K instructions

        tail = instruction[self.OP_CODE:]
        self.comb += [
            self.op_code.eq(instruction[:self.OP_CODE]),
            If(self.op_code == OpCode.NOOP,
                self.timeslice.eq(tail[:self.TIMESLICE_NOOP]),
            ).Else(
                self.timeslice.eq(tail[:self.TIMESLICE]),
            ),
            self.address.eq(tail[self.TIMESLICE:]),
            self.loop_count.eq(tail[:self.LOOP_COUNT]),
            self.loop_jump.eq(tail[self.LOOP_COUNT:]),
            self.cas.eq(self.op_code[1]),
            self.ras.eq(self.op_code[2]),
            self.we.eq(self.op_code[0]),
            self.dfi_bank.eq(self.address[rankbits:rankbits+bankbits]),
            self.dfi_address.eq(self.address[rankbits+bankbits:]),
        ]

        if rankbits:
            self.dfi_rank = Signal(rankbits)
            self.comb += self.dfi_bank.eq(self.address[:rankbits]),

class Encoder:
    """Helper for writing payloads"""
    def __init__(self, bankbits, nranks=1):
        self.nranks = nranks
        self.bankbits = bankbits

    def __call__(self, op_code, **kwargs):
        if op_code == OpCode.LOOP:
            parts = [
                (Decoder.OP_CODE,    op_code),
                (Decoder.LOOP_COUNT, kwargs['count']),
                (Decoder.LOOP_JUMP,  kwargs['jump']),
            ]
        elif op_code == OpCode.NOOP:
            parts = [
                (Decoder.OP_CODE,        op_code),
                (Decoder.TIMESLICE_NOOP, kwargs['timeslice']),
            ]
        else:
            parts = [
                (Decoder.OP_CODE,   op_code),
                (Decoder.TIMESLICE, kwargs['timeslice']),
                (Decoder.ADDRESS,   kwargs.get('address', 0)),
            ]
        instr = 0
        n = 0
        for width, val in parts:
            mask = 2**width - 1
            instr |= (val & mask) << n
            n += width
        return instr

    def address(self, *, rank=None, bank=0, row=None, col=None):
        assert not (row is not None and col is not None)
        if row is not None:
            rowcol = row
        elif col is not None:
            rowcol = col
        else:
            rowcol = 0
        address = bank & (2**self.bankbits - 1)
        address |= (rowcol) << self.bankbits
        if self.nranks > 1:
            address <<= log2_int(self.nranks)
            address |= rank
        return address

@ResetInserter()
class Scratchpad(Module):
    """
    Scratchpad memory filled with data from subsequent READ commands
    """
    def __init__(self, mem, dfi):
        assert mem.width == len(dfi.p0.rddata) * len(dfi.phases)

        self.counter  = Signal(max=mem.depth - 1)
        self.overflow = Signal()

        wr_port = mem.get_port(write_capable=True)
        self.specials += wr_port

        self.sync += [  # use sync for easier timing as we don't need comb here
            wr_port.adr.eq(self.counter),
            wr_port.dat_w.eq(Cat(*[p.rddata for p in dfi.phases])),
            wr_port.we.eq(reduce(or_, [p.rddata_valid for p in dfi.phases])),
        ]

        self.sync += [
            If(wr_port.we,
                If(self.counter == mem.depth - 1,
                    self.overflow.eq(1),
                    self.counter.eq(0),
                ).Else(
                    self.counter.eq(self.counter + 1)
                )
            )
        ]

class DFIExecutor(Module):
    def __init__(self, dfi, decoder, rank_decoder):
        self.phase = Signal(max=len(dfi.phases) - 1)
        self.exec  = Signal()

        nranks = len(dfi.p0.cs_n)

        for i, phase in enumerate(dfi.phases):
            self.comb += [
                # constant signals
                phase.cke.eq(Replicate(1, nranks)),
                phase.odt.eq(Replicate(1, nranks)),  # FIXME: needs to be dynamically driven for multi-rank systems
                phase.reset_n.eq(Replicate(1, nranks)),
                # send the command on current phase
                If((self.phase == i) & self.exec,  # selected
                    phase.cas_n.eq(~decoder.cas),
                    phase.ras_n.eq(~decoder.ras),
                    phase.we_n .eq(~decoder.we),
                    phase.address.eq(decoder.dfi_address),
                    phase.bank.eq(decoder.dfi_bank),
                    phase.rddata_en.eq(decoder.op_code == OpCode.READ),
                    # chip select
                    If(decoder.op_code == OpCode.NOOP,
                        phase.cs_n.eq(Replicate(1, nranks)),
                    ).Elif(decoder.op_code == OpCode.REF,  # select all ranks on refresh
                        phase.cs_n.eq(0),
                    ).Else(
                        phase.cs_n.eq(~rank_decoder.o),
                    ),
                ).Else(  # inactive
                    phase.cs_n.eq(Replicate(1, nranks)),
                    phase.cas_n.eq(1),
                    phase.ras_n.eq(1),
                    phase.we_n.eq(1),
                )
            ]

class PayloadExecutor(Module, AutoCSR, AutoDoc):
    def __init__(self, mem_payload, mem_scratchpad, dfi, dfi_sel, *,
                 nranks, bankbits, rowbits, colbits, rdphase):
        self.description = ModuleDoc("""
        Executes the DRAM payload from memory

        {}
        """.format(Decoder.__doc__))

        self.start               = Signal()
        self.ready               = Signal()
        self.program_counter     = Signal(max=mem_payload.depth - 1)
        self.loop_counter        = Signal(Decoder.LOOP_COUNT)
        self.idle_counter        = Signal(Decoder.TIMESLICE_NOOP)

        # Scratchpad
        self.submodules.scratchpad = Scratchpad(mem_scratchpad, dfi)

        # Fetcher
        # simple async reads, later we would probably want 1 cycle prefetch?
        instruction = Signal(Decoder.INSTRUCTION)
        payload_port = mem_payload.get_port(write_capable=False, async_read=True)
        self.specials += payload_port
        self.comb += [
            payload_port.adr.eq(self.program_counter),
            instruction.eq(payload_port.dat_r),
        ]

        # Decoder
        rankbits = log2_int(nranks)
        self.submodules.decoder = decoder = Decoder(
            instruction, rankbits=rankbits, bankbits=bankbits, rowbits=rowbits, colbits=colbits)
        self.submodules.rank_decoder = OneHotDecoder(nranks)
        if rankbits:
            self.comb += self.rank_decoder.i.eq(self.decoder.dfi_rank)

        # Executor
        self.submodules.dfi_executor = DFIExecutor(dfi, self.decoder, self.rank_decoder)
        self.submodules.fsm = FSM()
        self.fsm.act("READY",
            self.ready.eq(1),
            self.scratchpad.reset.eq(self.start),
            If(self.start,
                NextState("RUN"),
                NextValue(self.program_counter, 0),
            )
        )
        self.fsm.act("RUN",
            dfi_sel.eq(1),
            # Always execute the whole program
            If(self.program_counter == mem_payload.depth - 1,
                NextState("READY")
            ),
            # Execute instruction
            If(decoder.op_code == OpCode.LOOP,
               # If a loop instruction with count=0 is found it will be a NOOP
               If(self.loop_counter != decoder.loop_count,
                   # Continue the loop
                   NextValue(self.program_counter, self.program_counter - decoder.loop_jump),
                   NextValue(self.loop_counter, self.loop_counter + 1),
               ).Else(
                   # Finish the loop
                   # Set loop_counter to 0 so that next loop instruction will start properly
                   NextValue(self.program_counter, self.program_counter + 1),
                   NextValue(self.loop_counter, 0),
               ),
            ).Else(
                # DFI instruction
                If(decoder.timeslice == 0,
                    NextValue(self.program_counter, self.program_counter + 1)
                ).Else(
                    # Wait in idle loop after sending the command
                    NextValue(self.idle_counter, decoder.timeslice - 1),
                    NextState("IDLE"),
                ),
                # Send DFI command
                self.dfi_executor.exec.eq(1),
                If(decoder.cas & ~decoder.ras & ~decoder.we,  # READ command
                    self.dfi_executor.phase.eq(rdphase),
                ).Else(
                    self.dfi_executor.phase.eq(0),
                )
            ),
        )
        self.fsm.act("IDLE",
            dfi_sel.eq(1),
            If(self.idle_counter == 0,
                NextState("RUN"),
                NextValue(self.program_counter, self.program_counter + 1),
            ).Else(
                NextValue(self.idle_counter, self.idle_counter - 1),
            )
        )

    def add_csrs(self):
        self._start = CSR()
        # CSR does not take a description parameter so we must set it manually
        self._start.description = "Writing to this register initializes payload execution"
        self._status = CSRStatus(fields=[
            CSRField("ready", description="Indicates that the executor is not running"),
            CSRField("overflow", description="Indicates the scratchpad memory address counter"
                     " has overflown due to the number of READ commands sent during execution"),
        ], description="Payload executor status register")
        self._read_count = CSRStatus(len(self.scratchpad.counter), description="Number of data"
                                     " from READ commands that is stored in the scratchpad memory")

        self.comb += [
            self.start.eq(self._start.re),
            self._status.fields.ready.eq(self.ready),
            self._status.fields.overflow.eq(self.scratchpad.overflow),
            self._read_count.status.eq(self.scratchpad.counter),
        ]
