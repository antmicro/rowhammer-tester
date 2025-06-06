import unittest
from collections import namedtuple
from random import randint

from litedram.dfii import DFIInjector
from litedram.phy import dfi
from litex.gen.sim import passive, run_simulation
from migen import Memory, Module, Signal
from migen.genlib.coding import Decoder as OneHotDecoder

from rowhammer_tester.gateware.payload_executor import (
    Decoder,
    DFIExecutor,
    DFISwitch,
    Encoder,
    OpCode,
    PayloadExecutor,
    Scratchpad,
)


class Hex:
    # Helper for constructing readable hex integers, e.g. 0x11111111
    def __init__(self, num, width):
        num %= 16
        self.string = f"{num:x}" * (width // 4)

    def __add__(self, other):
        new = Hex(0, 0)
        new.string = self.string + other.string
        return new

    def int(self):
        return int(f"0x{self.string}", 16)

    @staticmethod
    def error(int1, int2, width):
        return "\n{:{w}x}\n{:{w}x}".format(int1, int2, w=width)


DFI_COMMANDS = {
    OpCode.NOOP: dict(cas=0, ras=0, we=0),
    OpCode.ACT: dict(cas=0, ras=1, we=0),
    OpCode.READ: dict(cas=1, ras=0, we=0),
    OpCode.PRE: dict(cas=0, ras=1, we=1),
    OpCode.REF: dict(cas=1, ras=1, we=0),
    OpCode.ZQC: dict(cas=0, ras=0, we=1),
}

# Scratchpad -------------------------------------------------------------------


class TestScratchpad(unittest.TestCase):
    class DUT(Module):
        def __init__(self):
            self.mem = Memory(128, 8)
            self.read_port = self.mem.get_port()
            self.specials += self.mem, self.read_port
            self.dfi = dfi.Interface(
                addressbits=14, bankbits=3, nranks=1, databits=2 * 16, nphases=4
            )
            self.submodules.scratchpad = Scratchpad(self.mem, self.dfi)

        def receive_read(self, offset=0):
            hexdata = reversed([Hex(offset + i, 32) for i, _ in enumerate(self.dfi.phases)])
            for phase, data in zip(self.dfi.phases, hexdata):
                yield phase.rddata.eq(data.int())
                yield phase.rddata_valid.eq(1)
            yield
            for phase in self.dfi.phases:
                yield phase.rddata_valid.eq(0)
            yield

        def mem_read(self, adr):
            yield self.read_port.adr.eq(adr)
            yield
            yield
            return (yield self.read_port.dat_r)

    def test_counter(self):
        def generator(dut):
            n = 4
            for _ in range(n):
                yield from dut.receive_read()
            yield

            self.assertEqual((yield dut.scratchpad.counter), n)

        dut = self.DUT()
        run_simulation(dut, generator(dut))

    def test_overflow(self):
        def generator(dut):
            for _ in range(7):
                yield from dut.receive_read()
            yield

            self.assertEqual((yield dut.scratchpad.overflow), 0)

            yield from dut.receive_read()
            yield
            self.assertEqual((yield dut.scratchpad.overflow), 1)

        dut = self.DUT()
        run_simulation(dut, generator(dut))

    def test_correct_data(self):
        def generator(dut):
            for i in range(3):
                yield from dut.receive_read(i + 1)
            yield

            expected = [
                (Hex(1, 32) + Hex(2, 32) + Hex(3, 32) + Hex(4, 32)).int(),
                (Hex(2, 32) + Hex(3, 32) + Hex(4, 32) + Hex(5, 32)).int(),
                (Hex(3, 32) + Hex(4, 32) + Hex(5, 32) + Hex(6, 32)).int(),
            ]

            for i, e in enumerate(expected):
                memdata = yield from dut.mem_read(i)
                self.assertEqual(memdata, e, msg=Hex.error(memdata, e, 32))

        dut = self.DUT()
        run_simulation(dut, generator(dut))


# Decoder ----------------------------------------------------------------------


class TestDecoder(unittest.TestCase):
    class DUT(Module):
        def __init__(self):
            self.instruction = Signal(32)
            self.submodules.decoder = Decoder(
                self.instruction, rankbits=0, bankbits=3, rowbits=14, colbits=10
            )

    def test_op_code(self):
        def generator(dut):
            encoder = Encoder(bankbits=3)

            for op in OpCode:
                kwargs = {
                    OpCode.LOOP: dict(count=1, jump=1),
                    OpCode.NOOP: dict(timeslice=1),
                }.get(op, dict(timeslice=1, address=0))  # others
                yield dut.instruction.eq(encoder(op, **kwargs)[0])
                yield
                self.assertEqual((yield dut.decoder.op_code), op)

        dut = self.DUT()
        run_simulation(dut, generator(dut))

    def test_loop(self):
        def generator(dut):
            encoder = Encoder(bankbits=3)

            yield dut.instruction.eq(encoder(OpCode.LOOP, count=3, jump=9)[0])
            yield
            self.assertEqual((yield dut.decoder.loop_count), 3)
            self.assertEqual((yield dut.decoder.loop_jump), 9)

            count_max = 2**Decoder.LOOP_COUNT - 1
            yield dut.instruction.eq(encoder(OpCode.LOOP, count=count_max, jump=9)[0])
            yield
            self.assertEqual((yield dut.decoder.loop_count), count_max)
            self.assertEqual((yield dut.decoder.loop_jump), 9)

            jump_max = 2**Decoder.LOOP_JUMP - 1
            yield dut.instruction.eq(encoder(OpCode.LOOP, count=3, jump=jump_max)[0])
            yield
            self.assertEqual((yield dut.decoder.loop_count), 3)
            self.assertEqual((yield dut.decoder.loop_jump), jump_max)

        dut = self.DUT()
        run_simulation(dut, generator(dut))

    def test_noop_timeslice(self):
        def generator(dut):
            encoder = Encoder(bankbits=3)

            timeslice_max = 2**Decoder.TIMESLICE_NOOP - 1
            yield dut.instruction.eq(encoder(OpCode.NOOP, timeslice=timeslice_max)[0])
            yield
            self.assertEqual((yield dut.decoder.timeslice), timeslice_max)

        dut = self.DUT()
        run_simulation(dut, generator(dut))

    def test_dfi_timeslice(self):
        def generator(dut):
            encoder = Encoder(bankbits=3)

            timeslice_max = 2**Decoder.TIMESLICE - 1
            yield dut.instruction.eq(encoder(OpCode.ACT, timeslice=timeslice_max, address=0)[0])
            yield
            self.assertEqual((yield dut.decoder.timeslice), timeslice_max)

        dut = self.DUT()
        run_simulation(dut, generator(dut))

    def test_dfi_address(self):
        def generator(dut):
            encoder = Encoder(bankbits=3)
            bank, row, col = (2**3 - 1, 2**14 - 1, 2**10 - 1)

            yield dut.instruction.eq(
                encoder(OpCode.ACT, timeslice=3, address=encoder.address(bank=bank, row=row))[0]
            )
            yield
            self.assertEqual((yield dut.decoder.timeslice), 3)
            self.assertEqual((yield dut.decoder.dfi_bank), bank)
            self.assertEqual((yield dut.decoder.dfi_address), row)

            yield dut.instruction.eq(
                encoder(OpCode.READ, timeslice=4, address=encoder.address(bank=bank, col=col))[0]
            )
            yield
            self.assertEqual((yield dut.decoder.timeslice), 4)
            self.assertEqual((yield dut.decoder.dfi_bank), bank)
            self.assertEqual((yield dut.decoder.dfi_address), col)

        dut = self.DUT()
        run_simulation(dut, generator(dut))

    def test_dfi_command(self):
        def generator(dut):
            encoder = Encoder(bankbits=3)

            for op, desc in DFI_COMMANDS.items():
                kwargs = dict()
                if op != OpCode.NOOP:
                    kwargs["address"] = 11
                yield dut.instruction.eq(encoder(op, timeslice=5, **kwargs)[0])
                yield
                self.assertEqual((yield dut.decoder.timeslice), 5)
                self.assertEqual((yield dut.decoder.cas), desc["cas"])
                self.assertEqual((yield dut.decoder.ras), desc["ras"])
                self.assertEqual((yield dut.decoder.we), desc["we"])

        dut = self.DUT()
        run_simulation(dut, generator(dut))


# DFIExecutor ------------------------------------------------------------------


class TestDFIExecutor(unittest.TestCase):
    class DUT(TestDecoder.DUT):
        def __init__(self):
            super().__init__()
            self.dfi = dfi.Interface(
                addressbits=14, bankbits=3, nranks=1, databits=2 * 16, nphases=4
            )
            self.submodules.rank_decoder = OneHotDecoder(1)
            self.submodules.executor = DFIExecutor(self.dfi, self.decoder, self.rank_decoder)

    def test_inactive(self):
        def generator(dut):
            encoder = Encoder(bankbits=3)
            yield dut.executor.exec.eq(0)
            yield dut.instruction.eq(encoder(OpCode.NOOP, timeslice=1)[0])
            yield

            for phase in dut.dfi.phases:
                self.assertEqual((yield phase.cke), 1)
                self.assertEqual((yield phase.odt), 1)
                self.assertEqual((yield phase.reset_n), 1)
                self.assertEqual((yield phase.cs_n), 1)
                self.assertEqual((yield phase.cas_n), 1)
                self.assertEqual((yield phase.ras_n), 1)
                self.assertEqual((yield phase.we_n), 1)

            yield dut.instruction.eq(encoder(OpCode.ACT, timeslice=1, address=2)[0])
            yield

            # still inactive because exec=0
            for phase in dut.dfi.phases:
                self.assertEqual((yield phase.cke), 1)
                self.assertEqual((yield phase.odt), 1)
                self.assertEqual((yield phase.reset_n), 1)
                self.assertEqual((yield phase.cs_n), 1)
                self.assertEqual((yield phase.cas_n), 1)
                self.assertEqual((yield phase.ras_n), 1)
                self.assertEqual((yield phase.we_n), 1)

        dut = self.DUT()
        run_simulation(dut, generator(dut))

    def test_on_phase(self):
        def generator(dut):
            encoder = Encoder(bankbits=3)
            yield dut.instruction.eq(encoder(OpCode.ACT, timeslice=1, address=2)[0])
            yield dut.executor.phase.eq(0)
            yield dut.executor.exec.eq(1)
            yield
            yield dut.executor.exec.eq(0)
            yield

            for i, phase in enumerate(dut.dfi.phases):
                if i == 0:  # phase enabled
                    self.assertEqual((yield phase.cke), 1)
                    self.assertEqual((yield phase.odt), 1)
                    self.assertEqual((yield phase.reset_n), 1)
                    self.assertEqual((yield phase.cs_n), 0)
                    self.assertEqual((yield phase.cas_n), 1)
                    self.assertEqual((yield phase.ras_n), 0)
                    self.assertEqual((yield phase.we_n), 1)
                else:  # phase disabled
                    self.assertEqual((yield phase.cke), 1)
                    self.assertEqual((yield phase.odt), 1)
                    self.assertEqual((yield phase.reset_n), 1)
                    self.assertEqual((yield phase.cs_n), 1)
                    self.assertEqual((yield phase.cas_n), 1)
                    self.assertEqual((yield phase.ras_n), 1)
                    self.assertEqual((yield phase.we_n), 1)

        dut = self.DUT()
        run_simulation(dut, generator(dut))


# PayloadExecutor --------------------------------------------------------------


# Stores DFI command info
class DFICmd(namedtuple("Cmd", ["cas", "ras", "we"])):
    @property
    def op_code(self):
        for op, desc in DFI_COMMANDS.items():
            if tuple(self) == (desc["cas"], desc["ras"], desc["we"]):
                return op
        assert False


# Information about DFI command seen on the bus
HistoryEntry = namedtuple("HistoryEntry", ["time", "phase", "cmd"])


class PayloadExecutorDUT(Module):
    def __init__(
        self,
        payload,
        data_width=128,
        scratchpad_depth=8,
        payload_depth=32,
        instruction_width=32,
        bankbits=3,
        rowbits=14,
        colbits=10,
        nranks=1,
        dfi_databits=2 * 16,
        nphases=4,
        rdphase=2,
        with_refresh=True,
        refresh_delay=3,
    ):
        # store to be able to extract from dut later
        self.params = locals()
        self.payload = payload

        assert len(payload) <= payload_depth, f"{len(payload)} vs {payload_depth}"
        self.mem_scratchpad = Memory(data_width, scratchpad_depth)
        self.mem_payload = Memory(instruction_width, payload_depth, init=payload)
        self.specials += self.mem_scratchpad, self.mem_payload

        dfi_params = dict(
            addressbits=max(rowbits, colbits),
            bankbits=bankbits,
            nranks=nranks,
            databits=dfi_databits,
            nphases=nphases,
        )
        self.refresher_reset = Signal()
        self.submodules.dfii = DFIInjector(**dfi_params)
        self.submodules.dfi_switch = DFISwitch(
            with_refresh=with_refresh, dfii=self.dfii, refresher_reset=self.refresher_reset
        )

        self.submodules.payload_executor = PayloadExecutor(
            self.mem_payload,
            self.mem_scratchpad,
            self.dfi_switch,
            nranks=nranks,
            bankbits=bankbits,
            rowbits=rowbits,
            colbits=colbits,
            rdphase=2,
        )

        self.dfi_history: list[HistoryEntry] = []
        self.runtime_cycles = 0  # time when memory controller is disconnected
        self.execution_cycles = 0  # time when actually executing the payload

    def get_generators(self):
        return [self.dfi_monitor(), self.cycles_counter(), self.refresher()]

    @passive
    def dfi_monitor(self, dfi=None):
        if dfi is None:
            dfi = self.dfii.ext_dfi
        time = 0
        while True:
            for i, phase in enumerate(dfi.phases):
                cas = 1 - (yield phase.cas_n)
                ras = 1 - (yield phase.ras_n)
                we = 1 - (yield phase.we_n)
                entry = None
                for _, desc in DFI_COMMANDS.items():
                    if (cas, ras, we) == (desc["cas"], desc["ras"], desc["we"]):
                        cmd = DFICmd(cas=cas, ras=ras, we=we)
                        entry = HistoryEntry(time=time, phase=i, cmd=cmd)
                assert entry is not None, f"Unknown DFI command: cas={cas}, ras={ras}, we={we}"
                if entry.cmd.op_code != OpCode.NOOP:  # omit NOOPs
                    self.dfi_history.append(entry)
            yield
            time += 1

    @passive
    def cycles_counter(self):
        self.execution_cycles = 0
        self.runtime_cycles = 0
        while not (yield self.payload_executor.start):
            yield
        yield
        while not (yield self.payload_executor.ready):
            yield
            self.runtime_cycles += 1
            if (yield self.payload_executor.executing):
                self.execution_cycles += 1

    @passive
    def refresher(self):
        if not self.params["with_refresh"]:
            return

        counter = 0
        while True:
            if (yield self.refresher_reset):
                counter = 0
                yield
            else:
                if counter == self.params["refresh_delay"]:
                    counter = 0
                    yield self.dfii.slave.phases[0].cs_n.eq(0)
                    yield self.dfii.slave.phases[0].cas_n.eq(0)
                    yield self.dfii.slave.phases[0].ras_n.eq(0)
                    yield self.dfii.slave.phases[0].we_n.eq(1)
                    yield
                    yield self.dfii.slave.phases[0].cs_n.eq(1)
                    yield self.dfii.slave.phases[0].cas_n.eq(1)
                    yield self.dfii.slave.phases[0].ras_n.eq(1)
                    yield self.dfii.slave.phases[0].we_n.eq(1)
                else:
                    counter += 1
                    yield


class PayloadExecutorDDR5DUT(Module):
    def __init__(
        self,
        payload,
        data_width=128,
        scratchpad_depth=8,
        payload_depth=32,
        instruction_width=32,
        bankbits=5,
        rowbits=18,
        colbits=10,
        nranks=1,
        dfi_databits=2 * 16,
        nphases=4,
        rdphase=2,
        with_refresh=True,
        refresh_delay=3,
    ):
        # store to be able to extract from dut later
        self.params = locals()
        self.payload = payload

        assert len(payload) <= payload_depth, f"{len(payload)} vs {payload_depth}"
        self.mem_scratchpad = Memory(data_width, scratchpad_depth)
        self.mem_payload = Memory(instruction_width, payload_depth, init=payload)
        self.specials += self.mem_scratchpad, self.mem_payload

        dfi_params = dict(
            addressbits=max(rowbits, colbits),
            bankbits=8,
            nranks=nranks,
            databits=dfi_databits,
            nphases=nphases,
            memtype="DDR5",
            with_sub_channels=True,
            strobes=4,
        )
        self.refresher_reset = Signal()
        self.submodules.dfii = DFIInjector(**dfi_params)
        self.submodules.dfi_switch = DFISwitch(
            with_refresh=with_refresh,
            dfii=self.dfii,
            refresher_reset=self.refresher_reset,
            memtype="DDR5",
        )

        self.submodules.payload_executor = PayloadExecutor(
            self.mem_payload,
            self.mem_scratchpad,
            self.dfi_switch,
            nranks=nranks,
            bankbits=bankbits,
            rowbits=rowbits,
            colbits=colbits,
            rdphase=2,
        )

        self.dfi_history: list[HistoryEntry] = []
        self.runtime_cycles = 0  # time when memory controller is disconnected
        self.execution_cycles = 0  # time when actually executing the payload

    def get_generators(self):
        return [self.dfi_monitor(), self.cycles_counter(), self.refresher()]

    @passive
    def dfi_monitor(self, dfi=None):
        if dfi is None:
            dfi = self.dfii.ext_dfi
        time = 0
        while True:
            for i, phase in enumerate(dfi.phases):
                cas = 1 - (yield phase.cas_n)
                ras = 1 - (yield phase.ras_n)
                we = 1 - (yield phase.we_n)
                entry = None
                for _op, desc in DFI_COMMANDS.items():
                    if (cas, ras, we) == (desc["cas"], desc["ras"], desc["we"]):
                        cmd = DFICmd(cas=cas, ras=ras, we=we)
                        entry = HistoryEntry(time=time, phase=i, cmd=cmd)
                assert entry is not None, f"Unknown DFI command: cas={cas}, ras={ras}, we={we}"
                if entry.cmd.op_code != OpCode.NOOP:  # omit NOOPs
                    self.dfi_history.append(entry)
            yield
            time += 1

    @passive
    def cycles_counter(self):
        self.execution_cycles = 0
        self.runtime_cycles = 0
        while not (yield self.payload_executor.start):
            yield
        yield
        while not (yield self.payload_executor.ready):
            yield
            self.runtime_cycles += 1
            if (yield self.payload_executor.executing):
                self.execution_cycles += 1

    @passive
    def refresher(self):
        if not self.params["with_refresh"]:
            return

        counter = 0
        while True:
            if (yield self.refresher_reset):
                counter = 0
                yield
            else:
                if counter == self.params["refresh_delay"]:
                    counter = 0
                    yield self.dfii.slave.phases[0].cs_n.eq(0)
                    yield self.dfii.slave.phases[0].cas_n.eq(0)
                    yield self.dfii.slave.phases[0].ras_n.eq(0)
                    yield self.dfii.slave.phases[0].we_n.eq(1)
                    yield
                    yield self.dfii.slave.phases[0].cs_n.eq(1)
                    yield self.dfii.slave.phases[0].cas_n.eq(1)
                    yield self.dfii.slave.phases[0].ras_n.eq(1)
                    yield self.dfii.slave.phases[0].we_n.eq(1)
                else:
                    counter += 1
                    yield


class TestPayloadExecutor(unittest.TestCase):
    def run_payload(self, dut, **kwargs):
        def generator(dut):
            yield dut.payload_executor.start.eq(1)
            yield
            yield dut.payload_executor.start.eq(0)
            yield

            while not (yield dut.payload_executor.ready):
                yield

        run_simulation(dut, [generator(dut), *dut.get_generators()], **kwargs)

    def assert_history(self, history, op_codes):
        history_ops = [entry.cmd.op_code for entry in history]
        self.assertEqual(history_ops, op_codes)

    def test_timeslice_0_noop_legal(self):
        # Check that encoding NOOP with timeslice=0 is legal (STOP instruction)
        Encoder(bankbits=3)(OpCode.NOOP, timeslice=0)

    def test_timeslice_0_other_illegal(self):
        # Check that encoding DFI instructions with timeslice=0 is results in an error
        with self.assertRaises(AssertionError):
            Encoder(bankbits=3)(OpCode.ACT, timeslice=0)

    def test_payload_simple(self):
        # Check that DFI instructions in a simple payload are sent in correct order
        encoder = Encoder(bankbits=3)
        payload = (
            encoder(OpCode.ACT, timeslice=10, address=encoder.address(bank=1, row=100))
            + encoder(OpCode.READ, timeslice=3, address=encoder.address(bank=1, col=13))
            + encoder(OpCode.PRE, timeslice=10, address=encoder.address(bank=1))
            + encoder(OpCode.REF, timeslice=15)
        )

        dut = PayloadExecutorDUT(payload)
        self.run_payload(dut)

        # compare DFI history to what payload should yield
        op_codes = [OpCode.ACT, OpCode.READ, OpCode.PRE, OpCode.REF]
        self.assert_history(dut.dfi_history, op_codes)

    def test_payload_loop(self):
        # Check that LOOP is executed correctly
        encoder = Encoder(bankbits=3)
        payload = (
            encoder(OpCode.ACT, timeslice=10, address=encoder.address(bank=0, row=100))
            + encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=200))
            + encoder(OpCode.LOOP, count=8 - 1, jump=1)  # to READ col=200
            + encoder(OpCode.PRE, timeslice=30, address=encoder.address(bank=0))
            + encoder(OpCode.REF, timeslice=30)
            + encoder(OpCode.REF, timeslice=30)
            + encoder(OpCode.LOOP, count=5 - 1, jump=2)  # to first REF
        )

        dut = PayloadExecutorDUT(payload)
        self.run_payload(dut)

        op_codes = [OpCode.ACT] + 8 * [OpCode.READ] + [OpCode.PRE] + 5 * 2 * [OpCode.REF]
        self.assert_history(dut.dfi_history, op_codes)

    def test_stop(self):
        # Check that STOP terminates execution
        encoder = Encoder(bankbits=3)
        payload = (
            encoder(OpCode.ACT, timeslice=10, address=encoder.address(bank=1, row=100))
            + encoder(OpCode.READ, timeslice=10, address=encoder.address(bank=1, col=13))
            + encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=1, col=20))
            + encoder(OpCode.NOOP, timeslice=0)  # STOP instruction
            + encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=1, col=20))
            + encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=1, col=20))
            + encoder(OpCode.PRE, timeslice=10, address=encoder.address(bank=1))
        )

        dut = PayloadExecutorDUT(payload)
        self.run_payload(dut)

        op_codes = [OpCode.ACT] + 2 * [OpCode.READ]
        self.assert_history(dut.dfi_history, op_codes)

    def test_execution_cycles_with_stop(self):
        # Check that execution time is correct with STOP instruction
        encoder = Encoder(bankbits=3)
        payload = (
            encoder(OpCode.ACT, timeslice=1, address=encoder.address(bank=1, row=100))
            + encoder(OpCode.READ, timeslice=1, address=encoder.address(bank=1, col=20))
            + encoder(OpCode.PRE, timeslice=1, address=encoder.address(bank=1))
            + encoder(OpCode.NOOP, timeslice=0)  # STOP, takes 1 cycle
            + encoder(OpCode.ACT, timeslice=10, address=encoder.address(bank=1, row=100))
        )

        dut = PayloadExecutorDUT(payload)
        self.run_payload(dut)

        op_codes = [OpCode.ACT, OpCode.READ, OpCode.PRE]
        self.assert_history(dut.dfi_history, op_codes)
        self.assertEqual(dut.execution_cycles, 4 + dut.payload_executor.PIPELINE_DELAY)

    def test_execution_cycles_default_stop(self):
        # Check execution time with no explicit STOP,
        # but rest of memory is filled with zeros (=STOP)
        encoder = Encoder(bankbits=3)
        payload = (
            encoder(OpCode.ACT, timeslice=1, address=encoder.address(bank=1, row=100))
            + encoder(OpCode.READ, timeslice=1, address=encoder.address(bank=1, col=20))
            + encoder(OpCode.PRE, timeslice=1, address=encoder.address(bank=1))
        )

        dut = PayloadExecutorDUT(payload)
        self.run_payload(dut)

        op_codes = [OpCode.ACT, OpCode.READ, OpCode.PRE]
        self.assert_history(dut.dfi_history, op_codes)
        self.assertEqual(dut.execution_cycles, 4 + dut.payload_executor.PIPELINE_DELAY)

    def test_execution_cycles_no_stop(self):
        # Check execution time when there is no STOP instruction (rest of memory filled with NOOPs)
        encoder = Encoder(bankbits=3)
        payload = (
            encoder(OpCode.ACT, timeslice=1, address=encoder.address(bank=1, row=100))
            + encoder(OpCode.READ, timeslice=1, address=encoder.address(bank=1, col=20))
            + encoder(OpCode.PRE, timeslice=1, address=encoder.address(bank=1))
        )

        depth = 16
        payload += [encoder(OpCode.NOOP, timeslice=1)[0]] * (depth - len(payload))
        dut = PayloadExecutorDUT(payload, payload_depth=depth)
        self.run_payload(dut)

        op_codes = [OpCode.ACT, OpCode.READ, OpCode.PRE]
        self.assert_history(dut.dfi_history, op_codes)
        self.assertEqual(dut.execution_cycles, dut.payload_executor.PIPELINE_DELAY + depth)

    def test_execution_cycles_longer(self):
        # Check execution time with timeslices longer than 1
        encoder = Encoder(bankbits=3)
        payload = [
            encoder.Instruction(OpCode.ACT, timeslice=7, address=encoder.address(bank=1, row=100)),
            encoder.Instruction(OpCode.READ, timeslice=3, address=encoder.address(bank=1, col=20)),
            encoder.Instruction(OpCode.PRE, timeslice=5, address=encoder.address(bank=1)),
            encoder.Instruction(OpCode.REF, timeslice=10),
            encoder.Instruction(OpCode.NOOP, timeslice=0),  # STOP
        ]

        dut = PayloadExecutorDUT(encoder(payload))
        self.run_payload(dut)

        op_codes = [OpCode.ACT, OpCode.READ, OpCode.PRE, OpCode.REF]
        self.assert_history(dut.dfi_history, op_codes)
        self.assertEqual(
            dut.execution_cycles,
            dut.payload_executor.PIPELINE_DELAY + sum(max(1, i.timeslice) for i in payload),
        )

    def test_execution_refresh_delay(self):
        # Check that payload execution is started after refresh command
        encoder = Encoder(bankbits=3)
        payload = [
            encoder.Instruction(OpCode.ACT, timeslice=9, address=encoder.address(bank=1, row=100)),
            encoder.Instruction(OpCode.PRE, timeslice=10, address=encoder.address(bank=1)),
            encoder.Instruction(OpCode.NOOP, timeslice=0),  # STOP
        ]
        switch_latency = 1
        for refresh_delay in [0, 2, 4, 11]:
            with self.subTest(refresh_delay=refresh_delay):
                dut = PayloadExecutorDUT(encoder(payload), refresh_delay=refresh_delay)
                self.run_payload(dut)

                op_codes = [OpCode.ACT, OpCode.PRE]
                self.assert_history(dut.dfi_history, op_codes)
                self.assertEqual(dut.execution_cycles, 20 + dut.payload_executor.PIPELINE_DELAY)
                self.assertEqual(
                    dut.runtime_cycles,
                    20
                    + dut.payload_executor.PIPELINE_DELAY
                    + max(1, refresh_delay)
                    + switch_latency,
                )

    def test_refresh_counter(self):
        def generator(dut):
            # wait for some refresh commands to be issued by MC
            for _ in range(45):
                yield

            # start execution, this should wait for the next refresh, then latch refresh count
            yield dut.payload_executor.start.eq(1)
            yield
            yield dut.payload_executor.start.eq(0)
            yield

            while not (yield dut.payload_executor.ready):
                yield

            # read refresh count CSR twice
            at_transition = yield from dut.dfi_switch._refresh_count.read()
            yield from dut.dfi_switch._refresh_update.write(1)
            yield
            forced = yield from dut.dfi_switch._refresh_count.read()
            yield

            # refreshes during waiting time, +1 between start.eq(1) and actual transition
            self.assertEqual(at_transition, 4 + 1)
            self.assertEqual(forced, at_transition + 3)  # for payload

        encoder = Encoder(bankbits=3)
        payload = [
            encoder.Instruction(OpCode.NOOP, timeslice=2),
            encoder.Instruction(OpCode.REF, timeslice=8),
            encoder.Instruction(OpCode.REF, timeslice=8),
            encoder.Instruction(OpCode.REF, timeslice=8),
            encoder.Instruction(OpCode.NOOP, timeslice=0),  # STOP
        ]

        dut = PayloadExecutorDUT(encoder(payload), refresh_delay=10 - 1)
        dut.dfi_switch.add_csrs()
        run_simulation(dut, [generator(dut), *dut.get_generators()])

    def test_refresh_counter_64_bit(self):
        def generator(dut):
            # Subtract some value from 2^32
            value = 31
            yield dut.dfi_switch.refresh_counter.counter.eq(2**32 - value)
            # wait for `value` refreshes and land in the middle of the refresh period(10)
            for _ in range(value * 10 + 5):
                yield

            # start execution, this should wait for the next refresh, then latch refresh count
            yield dut.payload_executor.start.eq(1)
            yield
            yield dut.payload_executor.start.eq(0)
            yield

            while not (yield dut.payload_executor.ready):
                yield

            # read refresh count CSR twice
            at_transition = yield from dut.dfi_switch._refresh_count.read()
            yield from dut.dfi_switch._refresh_update.write(1)
            yield
            forced = yield from dut.dfi_switch._refresh_count.read()
            yield

            # refreshes during waiting time, +1 between start.eq(1) and actual transition
            self.assertEqual(at_transition, 2**32 + 1)
            self.assertEqual(forced, at_transition + 3)  # for payload

        encoder = Encoder(bankbits=3)
        payload = [
            encoder.Instruction(OpCode.NOOP, timeslice=2),
            encoder.Instruction(OpCode.REF, timeslice=8),
            encoder.Instruction(OpCode.REF, timeslice=8),
            encoder.Instruction(OpCode.REF, timeslice=8),
            encoder.Instruction(OpCode.NOOP, timeslice=0),  # STOP
        ]

        dut = PayloadExecutorDUT(encoder(payload), refresh_delay=9)
        dut.dfi_switch.add_csrs()
        run_simulation(dut, [generator(dut), *dut.get_generators()])

    def test_switch_at_refresh(self):
        def generator(dut, switch_at):
            yield from dut.dfi_switch._at_refresh.write(switch_at)
            self.assertEqual((yield dut.dfi_switch.refresh_counter.counter), 0)

            # start execution, this should wait for the next refresh, then latch refresh count
            yield dut.payload_executor.start.eq(1)
            yield
            yield dut.payload_executor.start.eq(0)
            yield

            while not (yield dut.payload_executor.ready):
                yield

            # +1 for payload
            self.assertEqual((yield dut.dfi_switch.refresh_counter.counter), switch_at + 1)

        encoder = Encoder(bankbits=3)
        payload = [
            encoder.Instruction(OpCode.NOOP, timeslice=10),
            encoder.Instruction(OpCode.REF, timeslice=8),
            encoder.Instruction(OpCode.NOOP, timeslice=10),
            encoder.Instruction(OpCode.NOOP, timeslice=0),  # STOP
        ]

        for switch_at in [5, 7, 10]:
            with self.subTest(switch_at=switch_at):
                dut = PayloadExecutorDUT(encoder(payload), refresh_delay=10 - 1)
                dut.dfi_switch.add_csrs()
                run_simulation(dut, [generator(dut, switch_at), *dut.get_generators()])

    def test_switch_at_refresh_64_bit(self):
        def generator(dut, switch_at):
            yield from dut.dfi_switch._at_refresh.write(switch_at)
            # Assert that write to _at_refresh doesn't affect refresh_counter
            self.assertEqual((yield dut.dfi_switch.refresh_counter.counter), 0)
            # Set refresh_counter to 2**32 minus a small value to
            # check that counter goes over 32 bits.
            # Starting from 2*32 - 31 speeds up simulation
            yield dut.dfi_switch.refresh_counter.counter.eq(2**32 - 31)

            # start execution, this should wait for the next refresh, then latch refresh count
            yield dut.payload_executor.start.eq(1)
            yield
            yield dut.payload_executor.start.eq(0)
            yield

            while not (yield dut.payload_executor.ready):
                yield

            # +1 for payload
            self.assertEqual((yield dut.dfi_switch.refresh_counter.counter), switch_at + 1)

        encoder = Encoder(bankbits=3)
        payload = [
            encoder.Instruction(OpCode.NOOP, timeslice=10),
            encoder.Instruction(OpCode.REF, timeslice=8),
            encoder.Instruction(OpCode.NOOP, timeslice=10),
            encoder.Instruction(OpCode.NOOP, timeslice=0),  # STOP
        ]

        for switch_at in [2**32 + 1]:
            with self.subTest(switch_at=switch_at):
                dut = PayloadExecutorDUT(encoder(payload), refresh_delay=3)
                dut.dfi_switch.add_csrs()
                run_simulation(dut, [generator(dut, switch_at), *dut.get_generators()])


class TestPayloadExecutorDDR5(unittest.TestCase):
    def run_payload(self, dut, **kwargs):
        def generator(dut):
            yield dut.dfii._control.fields.mode_2n.eq(0)
            yield dut.dfii._control.fields.reset_n.eq(1)
            yield dut.payload_executor.start.eq(1)
            yield
            yield dut.payload_executor.start.eq(0)
            yield

            while not (yield dut.payload_executor.ready):
                yield

        run_simulation(dut, [generator(dut), *dut.get_generators()], **kwargs)

    def assert_history(self, history, op_codes):
        history_ops = [entry.cmd.op_code for entry in history]
        self.assertEqual(history_ops, op_codes)

    def test_timeslice_0_noop_legal(self):
        # Check that encoding NOOP with timeslice=0 is legal (STOP instruction)
        Encoder(bankbits=5)(OpCode.NOOP, timeslice=0)

    def test_timeslice_0_other_illegal(self):
        # Check that encoding DFI instructions with timeslice=0 is results in an error
        with self.assertRaises(AssertionError):
            Encoder(bankbits=5)(OpCode.ACT, timeslice=0)

    def test_payload_simple(self):
        # Check that DFI instuctions in a simple payload are sent in correct order
        encoder = Encoder(bankbits=5)
        payload = (
            encoder(OpCode.ACT, timeslice=10, address=encoder.address(bank=1, row=100))
            + encoder(OpCode.READ, timeslice=3, address=encoder.address(bank=1, col=13))
            + encoder(OpCode.PRE, timeslice=10, address=encoder.address(bank=1))
            + encoder(OpCode.REF, timeslice=15)
        )

        dut = PayloadExecutorDDR5DUT(payload)
        self.run_payload(dut)

        # compare DFI history to what payload should yield
        op_codes = [OpCode.ACT, OpCode.READ, OpCode.PRE, OpCode.REF]
        self.assert_history(dut.dfi_history, op_codes)

    def test_payload_loop(self):
        # Check that LOOP is executed correctly
        encoder = Encoder(bankbits=5)
        payload = (
            encoder(OpCode.ACT, timeslice=10, address=encoder.address(bank=0, row=100))
            + encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=200))
            + encoder(OpCode.LOOP, count=8 - 1, jump=1)  # to READ col=200
            + encoder(OpCode.PRE, timeslice=30, address=encoder.address(bank=0))
            + encoder(OpCode.REF, timeslice=30)
            + encoder(OpCode.REF, timeslice=30)
            + encoder(OpCode.LOOP, count=5 - 1, jump=2)  # to first REF
        )

        dut = PayloadExecutorDDR5DUT(payload)
        self.run_payload(dut)

        op_codes = [OpCode.ACT] + 8 * [OpCode.READ] + [OpCode.PRE] + 5 * 2 * [OpCode.REF]
        self.assert_history(dut.dfi_history, op_codes)

    def test_stop(self):
        # Check that STOP terminates execution
        encoder = Encoder(bankbits=5)
        payload = (
            encoder(OpCode.ACT, timeslice=10, address=encoder.address(bank=1, row=100))
            + encoder(OpCode.READ, timeslice=10, address=encoder.address(bank=1, col=13))
            + encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=1, col=20))
            + encoder(OpCode.NOOP, timeslice=0)  # STOP instruction
            + encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=1, col=20))
            + encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=1, col=20))
            + encoder(OpCode.PRE, timeslice=10, address=encoder.address(bank=1))
        )

        dut = PayloadExecutorDDR5DUT(payload)
        self.run_payload(dut)

        op_codes = [OpCode.ACT] + 2 * [OpCode.READ]
        self.assert_history(dut.dfi_history, op_codes)

    def test_execution_cycles_with_stop(self):
        # Check that execution time is correct with STOP instruction
        encoder = Encoder(bankbits=5)
        payload = (
            encoder(OpCode.ACT, timeslice=1, address=encoder.address(bank=1, row=100))
            + encoder(OpCode.READ, timeslice=1, address=encoder.address(bank=1, col=20))
            + encoder(OpCode.PRE, timeslice=1, address=encoder.address(bank=1))
            + encoder(OpCode.NOOP, timeslice=0)  # STOP, takes 1 cycle
            + encoder(OpCode.ACT, timeslice=10, address=encoder.address(bank=1, row=100))
        )

        dut = PayloadExecutorDDR5DUT(payload)
        self.run_payload(dut)

        op_codes = [OpCode.ACT, OpCode.READ, OpCode.PRE]
        self.assert_history(dut.dfi_history, op_codes)
        self.assertEqual(dut.execution_cycles, 4 + dut.payload_executor.PIPELINE_DELAY)

    def test_execution_cycles_default_stop(self):
        # Check execution time with no explicit STOP,
        # but rest of memory is filled with zeros (=STOP)
        encoder = Encoder(bankbits=5)
        payload = (
            encoder(OpCode.ACT, timeslice=1, address=encoder.address(bank=1, row=100))
            + encoder(OpCode.READ, timeslice=1, address=encoder.address(bank=1, col=20))
            + encoder(OpCode.PRE, timeslice=1, address=encoder.address(bank=1))
        )

        dut = PayloadExecutorDDR5DUT(payload)
        self.run_payload(dut)

        op_codes = [OpCode.ACT, OpCode.READ, OpCode.PRE]
        self.assert_history(dut.dfi_history, op_codes)
        self.assertEqual(dut.execution_cycles, 4 + dut.payload_executor.PIPELINE_DELAY)

    def test_execution_cycles_no_stop(self):
        # Check execution time when there is no STOP instruction (rest of memory filled with NOOPs)
        encoder = Encoder(bankbits=5)
        payload = (
            encoder(OpCode.ACT, timeslice=1, address=encoder.address(bank=1, row=100))
            + encoder(OpCode.READ, timeslice=1, address=encoder.address(bank=1, col=20))
            + encoder(OpCode.PRE, timeslice=1, address=encoder.address(bank=1))
        )

        depth = 16
        payload += [encoder(OpCode.NOOP, timeslice=1)[0]] * (depth - len(payload))
        dut = PayloadExecutorDDR5DUT(payload, payload_depth=depth)
        self.run_payload(dut)

        op_codes = [OpCode.ACT, OpCode.READ, OpCode.PRE]
        self.assert_history(dut.dfi_history, op_codes)
        self.assertEqual(dut.execution_cycles, depth + dut.payload_executor.PIPELINE_DELAY)

    def test_execution_cycles_longer(self):
        # Check execution time with timeslices longer than 1
        encoder = Encoder(bankbits=5)
        payload = [
            encoder.Instruction(OpCode.ACT, timeslice=7, address=encoder.address(bank=1, row=100)),
            encoder.Instruction(OpCode.READ, timeslice=3, address=encoder.address(bank=1, col=20)),
            encoder.Instruction(OpCode.PRE, timeslice=5, address=encoder.address(bank=1)),
            encoder.Instruction(OpCode.REF, timeslice=10),
            encoder.Instruction(OpCode.NOOP, timeslice=0),  # STOP
        ]

        dut = PayloadExecutorDDR5DUT(encoder(payload))
        self.run_payload(dut)

        op_codes = [OpCode.ACT, OpCode.READ, OpCode.PRE, OpCode.REF]
        self.assert_history(dut.dfi_history, op_codes)
        self.assertEqual(
            dut.execution_cycles,
            sum(max(1, i.timeslice) for i in payload) + dut.payload_executor.PIPELINE_DELAY,
        )

    def test_execution_cycles_longer_loop(self):
        # Check execution time with timeslices longer than 1 and a loop
        encoder = Encoder(bankbits=5)
        payload = [
            encoder.Instruction(OpCode.ACT, timeslice=7, address=encoder.address(bank=1, row=100)),
            encoder.Instruction(OpCode.READ, timeslice=3, address=encoder.address(bank=1, col=20)),
            encoder.Instruction(OpCode.PRE, timeslice=5, address=encoder.address(bank=1)),
            encoder.Instruction(OpCode.LOOP, count=5, jump=2),  # to READ col=20
            encoder.Instruction(OpCode.REF, timeslice=10),
            encoder.Instruction(OpCode.NOOP, timeslice=0),  # STOP
        ]

        dut = PayloadExecutorDDR5DUT(encoder(payload))
        self.run_payload(dut)

        # Last loop won't have pipeline_delay, compensate by subtracting in time_total
        time_loop = 3 + 5 + 1 + dut.payload_executor.PIPELINE_DELAY
        time_total = 7 + 6 * time_loop + 10 - dut.payload_executor.PIPELINE_DELAY + 1

        op_codes = [OpCode.ACT] + 6 * [OpCode.READ, OpCode.PRE] + [OpCode.REF]
        self.assert_history(dut.dfi_history, op_codes)
        self.assertEqual(dut.execution_cycles, time_total + dut.payload_executor.PIPELINE_DELAY)

    def test_execution_cycles_longer_dual_loop(self):
        # Check execution time with timeslices longer than 1 and two loops (not nested)
        encoder = Encoder(bankbits=5)
        payload = [
            encoder.Instruction(OpCode.ACT, timeslice=7, address=encoder.address(bank=1, row=100)),
            encoder.Instruction(OpCode.READ, timeslice=3, address=encoder.address(bank=1, col=20)),
            encoder.Instruction(OpCode.PRE, timeslice=5, address=encoder.address(bank=1)),
            encoder.Instruction(OpCode.LOOP, count=6 - 1, jump=2),  # to READ col=20
            encoder.Instruction(OpCode.REF, timeslice=10),
            encoder.Instruction(OpCode.LOOP, count=4 - 1, jump=1),  # to REF timeslice = 10
            encoder.Instruction(OpCode.NOOP, timeslice=0),  # STOP
        ]

        dut = PayloadExecutorDDR5DUT(encoder(payload))
        self.run_payload(dut)

        # Last loop won't have pipeline_delay, compensate by subtracting in time_total
        time_loop1 = 3 + 5 + 1 + dut.payload_executor.PIPELINE_DELAY
        time_loop2 = 10 + 1 + dut.payload_executor.PIPELINE_DELAY
        time_total = (
            7
            + 6 * time_loop1
            - dut.payload_executor.PIPELINE_DELAY
            + 4 * time_loop2
            - dut.payload_executor.PIPELINE_DELAY
            + 1
        )

        op_codes = [OpCode.ACT] + 6 * [OpCode.READ, OpCode.PRE] + 4 * [OpCode.REF]
        self.assert_history(dut.dfi_history, op_codes)
        self.assertEqual(dut.execution_cycles, time_total + dut.payload_executor.PIPELINE_DELAY)

    def test_execution_cycles_loop_end(self):
        # Check execution time when loop is located at the end of the payload
        encoder = Encoder(bankbits=5)
        payload = (
            encoder(OpCode.ACT, timeslice=1, address=encoder.address(bank=1, row=100))
            + encoder(OpCode.READ, timeslice=1, address=encoder.address(bank=1, col=20))
            + encoder(OpCode.PRE, timeslice=1, address=encoder.address(bank=1))
        )

        depth = 16
        payload += [encoder(OpCode.NOOP, timeslice=1)[0]] * (depth - len(payload) - 2)
        payload += [encoder(OpCode.ACT, timeslice=7, address=encoder.address(bank=1, row=100))[0]]
        payload += [encoder(OpCode.LOOP, count=10 - 1, jump=2)[0]]
        dut = PayloadExecutorDDR5DUT(payload, payload_depth=depth)
        self.run_payload(dut)

        # Loops will be shorter by 1 pipeline_delay, compensate by subtracting it in time_total
        loop_time = 1 + 7 + 1 + dut.payload_executor.PIPELINE_DELAY
        time_total = depth - 3 + 10 * loop_time - dut.payload_executor.PIPELINE_DELAY

        op_codes = [OpCode.ACT, OpCode.READ, OpCode.PRE] + [OpCode.ACT] * 10
        self.assert_history(dut.dfi_history, op_codes)
        self.assertEqual(dut.execution_cycles, time_total + dut.payload_executor.PIPELINE_DELAY)

    def test_execution_cycles_no_stop_longer(self):
        # Check execution time when there is no STOP instruction (rest of memory filled with NOOPs)
        # This test has NOOPs timeslice set to 3
        encoder = Encoder(bankbits=5)
        payload = (
            encoder(OpCode.ACT, timeslice=1, address=encoder.address(bank=1, row=100))
            + encoder(OpCode.READ, timeslice=1, address=encoder.address(bank=1, col=20))
            + encoder(OpCode.PRE, timeslice=1, address=encoder.address(bank=1))
        )

        depth = 16
        payload += [encoder(OpCode.NOOP, timeslice=3)[0]] * (depth - len(payload))
        dut = PayloadExecutorDDR5DUT(payload, payload_depth=depth)
        self.run_payload(dut)

        op_codes = [OpCode.ACT, OpCode.READ, OpCode.PRE]
        self.assert_history(dut.dfi_history, op_codes)
        self.assertEqual(
            # We need to subtract 2 since last timeslice is not executed
            # because executor terminates on last instruction
            dut.execution_cycles,
            3 + (depth - 3) * 3 - 2 + dut.payload_executor.PIPELINE_DELAY,
        )

    def test_execution_cycles_loop_all_positions(self):
        # Check execution time with loop in all memory positions of 16-word deep memory
        # Doesn't include loop in pos=0 since that position is not legal for a loop instruction
        encoder = Encoder(bankbits=5)
        depth = 16

        for loop_position in range(1, depth):
            with self.subTest(loop_position=loop_position):
                payload = [encoder.I(OpCode.NOOP, timeslice=3)] * (depth)
                payload[loop_position - 1] = encoder.I(
                    OpCode.ACT, timeslice=2, address=encoder.address(bank=1, row=100)
                )
                payload[loop_position] = encoder.I(OpCode.LOOP, count=7 - 1, jump=1)

                dut = PayloadExecutorDDR5DUT(encoder(payload), payload_depth=depth)
                self.run_payload(dut)

                op_codes = [OpCode.ACT] * 7

                self.assert_history(dut.dfi_history, op_codes)
                if loop_position != depth - 1:
                    self.assertEqual(
                        # We need to subtract 2 since last timeslice is not executed
                        # because executor terminates on last instruction
                        dut.execution_cycles,
                        (depth - 2) * 3
                        + 6 * (2 + 1 + dut.payload_executor.PIPELINE_DELAY)
                        + (2 + 1)
                        - 2
                        + dut.payload_executor.PIPELINE_DELAY,
                    )
                else:
                    self.assertEqual(
                        dut.execution_cycles,
                        (depth - 2) * 3
                        + 6 * (2 + 1 + dut.payload_executor.PIPELINE_DELAY)
                        + (2 + 1)
                        + dut.payload_executor.PIPELINE_DELAY,
                    )

    def test_execution_refresh_delay(self):
        # Check that payload execution is started after refresh command
        encoder = Encoder(bankbits=5)
        payload = [
            encoder.Instruction(OpCode.ACT, timeslice=9, address=encoder.address(bank=1, row=100)),
            encoder.Instruction(OpCode.PRE, timeslice=10, address=encoder.address(bank=1)),
            encoder.Instruction(OpCode.NOOP, timeslice=0),  # STOP
        ]
        switch_latency = 1
        for refresh_delay in [0, 2, 4, 11]:
            with self.subTest(refresh_delay=refresh_delay):
                dut = PayloadExecutorDDR5DUT(encoder(payload), refresh_delay=refresh_delay)
                self.run_payload(dut)

                op_codes = [OpCode.ACT, OpCode.PRE]
                self.assert_history(dut.dfi_history, op_codes)
                self.assertEqual(dut.execution_cycles, 20 + dut.payload_executor.PIPELINE_DELAY)
                self.assertEqual(
                    dut.runtime_cycles,
                    20
                    + dut.payload_executor.PIPELINE_DELAY
                    + max(1, refresh_delay)
                    + switch_latency,
                )

    def test_refresh_counter(self):
        def generator(dut):
            # wait for some refresh commands to be issued by MC
            for _ in range(45):
                yield

            # start execution, this should wait for the next refresh, then latch refresh count
            yield dut.payload_executor.start.eq(1)
            yield
            yield dut.payload_executor.start.eq(0)
            yield

            while not (yield dut.payload_executor.ready):
                yield

            # read refresh count CSR twice
            at_transition = yield from dut.dfi_switch._refresh_count.read()
            yield from dut.dfi_switch._refresh_update.write(1)
            yield
            forced = yield from dut.dfi_switch._refresh_count.read()
            yield

            # refreshes during waiting time, +1 between start.eq(1) and actual transition
            self.assertEqual(at_transition, 4 + 1)
            self.assertEqual(forced, at_transition + 3)  # for payload

        encoder = Encoder(bankbits=5)
        payload = [
            encoder.Instruction(OpCode.NOOP, timeslice=2),
            encoder.Instruction(OpCode.REF, timeslice=8),
            encoder.Instruction(OpCode.REF, timeslice=8),
            encoder.Instruction(OpCode.REF, timeslice=8),
            encoder.Instruction(OpCode.NOOP, timeslice=0),  # STOP
        ]

        dut = PayloadExecutorDDR5DUT(encoder(payload), refresh_delay=10 - 1)
        dut.dfi_switch.add_csrs()
        run_simulation(dut, [generator(dut), *dut.get_generators()])

    def test_switch_at_refresh(self):
        def generator(dut, switch_at):
            yield from dut.dfi_switch._at_refresh.write(switch_at)
            self.assertEqual((yield dut.dfi_switch.refresh_counter.counter), 0)

            # start execution, this should wait for the next refresh, then latch refresh count
            yield dut.payload_executor.start.eq(1)
            yield
            yield dut.payload_executor.start.eq(0)
            yield

            while not (yield dut.payload_executor.ready):
                yield

            # +1 for payload
            self.assertEqual((yield dut.dfi_switch.refresh_counter.counter), switch_at + 1)

        encoder = Encoder(bankbits=5)
        payload = [
            encoder.Instruction(OpCode.NOOP, timeslice=10),
            encoder.Instruction(OpCode.REF, timeslice=8),
            encoder.Instruction(OpCode.NOOP, timeslice=10),
            encoder.Instruction(OpCode.NOOP, timeslice=0),  # STOP
        ]

        for switch_at in [5, 7, 10]:
            with self.subTest(switch_at=switch_at):
                dut = PayloadExecutorDDR5DUT(encoder(payload), refresh_delay=10 - 1)
                dut.dfi_switch.add_csrs()
                run_simulation(dut, [generator(dut, switch_at), *dut.get_generators()])

    def test_large_timeslice_ddr5(self):
        # Check that a instruction with timeslice > 31 is broken down into
        # the default instruction with max timeslice and fulfills the remaining
        # delay with NOOPs
        encoder = Encoder(bankbits=5)

        for ref_timeslice in [31, 32, 63, 64, randint(65, 129)]:
            with self.subTest():
                payload = [
                    encoder.Instruction(OpCode.NOOP, timeslice=10),
                    encoder.Instruction(OpCode.REF, timeslice=ref_timeslice),
                    encoder.Instruction(OpCode.NOOP, timeslice=0),  # STOP
                ]
                dut = PayloadExecutorDDR5DUT(encoder(payload))
                self.run_payload(dut)

                self.assert_history(dut.dfi_history, [OpCode.REF])
                self.assertEqual(
                    dut.execution_cycles,
                    sum(max(1, i.timeslice) for i in payload) + dut.payload_executor.PIPELINE_DELAY,
                )

    def test_payload_exec_snapshot(self):
        def generator(dut, expected_cycle_count):
            # start execution, this should wait for the next refresh, then latch the start and stop
            # cycle of the payload executor
            yield dut.payload_executor.start.eq(1)
            yield
            yield dut.payload_executor.start.eq(0)
            yield

            while not (yield dut.payload_executor.ready):
                yield

            start_cycle = yield dut.payload_executor.exec_start
            stop_cycle = yield dut.payload_executor.exec_stop
            yield

            self.assertNotEqual(start_cycle, 0)
            self.assertNotEqual(stop_cycle, 0)
            exec_cycles = stop_cycle - start_cycle
            self.assertEqual(exec_cycles, expected_cycle_count)

        encoder = Encoder(bankbits=5)
        payload = [
            encoder.Instruction(OpCode.ACT, timeslice=7, address=encoder.address(bank=1, row=100)),
            encoder.Instruction(OpCode.READ, timeslice=3, address=encoder.address(bank=1, col=20)),
            encoder.Instruction(OpCode.PRE, timeslice=5, address=encoder.address(bank=1)),
            encoder.Instruction(OpCode.REF, timeslice=10),
            encoder.Instruction(OpCode.NOOP, timeslice=0),  # STOP
        ]

        dut = PayloadExecutorDDR5DUT(encoder(payload))
        run_simulation(
            dut,
            [
                generator(
                    dut,
                    sum(max(1, i.timeslice) for i in payload) + dut.payload_executor.PIPELINE_DELAY,
                ),
                *dut.get_generators(),
            ],
        )
        self.assert_history(dut.dfi_history, [OpCode.ACT, OpCode.READ, OpCode.PRE, OpCode.REF])

    def test_instruction_fetch(self):
        def run_payload(dut, payload):
            def generator(dut, payload):
                yield dut.dfii._control.fields.mode_2n.eq(0)
                yield dut.dfii._control.fields.reset_n.eq(1)
                yield dut.payload_executor.start.eq(1)
                yield
                yield dut.payload_executor.start.eq(0)
                yield

                for instr in payload:
                    while (yield dut.payload_executor.stall):
                        yield
                    while (yield dut.payload_executor.bubble):
                        yield

                    self.assertEqual(instr, (yield dut.payload_executor.instruction))

                    yield

                while not (yield dut.payload_executor.ready):
                    yield

            run_simulation(dut, [generator(dut, payload), *dut.get_generators()])

        encoder = Encoder(bankbits=5)
        payload = (
            encoder(OpCode.ACT, timeslice=10, address=encoder.address(bank=1, row=100))
            + encoder(OpCode.READ, timeslice=3, address=encoder.address(bank=1, col=13))
            + encoder(OpCode.PRE, timeslice=10, address=encoder.address(bank=1))
            + encoder(OpCode.REF, timeslice=15)
        )

        dut = PayloadExecutorDDR5DUT(payload)
        run_payload(dut, payload)

        # compare DFI history to what payload should yield
        op_codes = [OpCode.ACT, OpCode.READ, OpCode.PRE, OpCode.REF]
        self.assert_history(dut.dfi_history, op_codes)

    def test_multiple_runs(self):
        def run_payload(dut):
            def generator(dut):
                yield dut.dfii._control.fields.mode_2n.eq(0)
                yield dut.dfii._control.fields.reset_n.eq(1)
                yield dut.payload_executor.start.eq(1)
                yield
                yield dut.payload_executor.start.eq(0)
                yield
                while not (yield dut.payload_executor.ready):
                    yield

                self.assertEqual((yield dut.payload_executor.fetcher.reset_pc), 1)
                yield
                self.assertEqual((yield dut.payload_executor.fetcher.program_counter), 0)
                yield
                self.assertEqual((yield dut.payload_executor.fetcher.program_counter_old), 0)
                yield dut.payload_executor.start.eq(1)
                yield
                yield dut.payload_executor.start.eq(0)
                yield
                while not (yield dut.payload_executor.ready):
                    yield

            run_simulation(
                dut,
                [generator(dut), *dut.get_generators()],
            )

        encoder = Encoder(bankbits=5)
        payload = (
            encoder(OpCode.ACT, timeslice=10, address=encoder.address(bank=1, row=100))
            + encoder(OpCode.READ, timeslice=3, address=encoder.address(bank=1, col=13))
            + encoder(OpCode.PRE, timeslice=10, address=encoder.address(bank=1))
            + encoder(OpCode.REF, timeslice=15)
        )

        dut = PayloadExecutorDDR5DUT(payload)
        run_payload(dut)

        # compare DFI history to what payload should yield
        op_codes = [OpCode.ACT, OpCode.READ, OpCode.PRE, OpCode.REF] * 2
        self.assert_history(dut.dfi_history, op_codes)

    def test_instruction_fetch_jump(self):
        def run_payload(dut, encoder, payload):
            def generator(dut, _encoder, payload):
                yield dut.dfii._control.fields.mode_2n.eq(0)
                yield dut.dfii._control.fields.reset_n.eq(1)
                yield dut.payload_executor.start.eq(1)
                yield
                yield dut.payload_executor.start.eq(0)

                idx = 0
                while idx < len(payload):
                    while (yield dut.payload_executor.stall):
                        yield
                    while (yield dut.payload_executor.bubble):
                        yield

                    instr = payload[idx]
                    instruction_encoded = encoder(instr)
                    self.assertEqual(
                        instruction_encoded[0], (yield dut.payload_executor.instruction)
                    )
                    if hasattr(instr, "jump") and instr.jump > 0 and instr.count > 0:
                        idx -= instr.jump
                        instr.count -= 1
                    else:
                        idx += 1

                    yield

                while not (yield dut.payload_executor.ready):
                    yield

            run_simulation(
                dut,
                [generator(dut, encoder, payload), *dut.get_generators()],
            )

        encoder = Encoder(bankbits=3)
        instrs = [
            encoder.I(OpCode.ACT, timeslice=10, address=encoder.address(bank=0, row=100)),
            encoder.I(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=200)),
            encoder.I(OpCode.LOOP, count=8 - 1, jump=1),  # to READ col=200
            encoder.I(OpCode.PRE, timeslice=30, address=encoder.address(bank=0)),
            encoder.I(OpCode.REF, timeslice=30),
            encoder.I(OpCode.REF, timeslice=30),
            encoder.I(OpCode.LOOP, count=5 - 1, jump=2),
        ]  # to first REF

        dut = PayloadExecutorDDR5DUT(encoder(instrs))
        run_payload(dut, encoder, instrs)

        op_codes = [OpCode.ACT] + 8 * [OpCode.READ] + [OpCode.PRE] + 5 * 2 * [OpCode.REF]
        self.assert_history(dut.dfi_history, op_codes)

    def test_instruction_timings_jump(self):
        # Checks if each instruction is executed at correct cycle
        def run_payload(dut, encoder, payload):
            def generator(dut, _encoder, payload):
                yield dut.dfii._control.fields.mode_2n.eq(0)
                yield dut.dfii._control.fields.reset_n.eq(1)
                yield dut.payload_executor.start.eq(1)
                yield
                yield dut.payload_executor.start.eq(0)

                # Wait for first instruction
                while not (yield dut.payload_executor.executing):
                    yield
                for _ in range(dut.payload_executor.PIPELINE_DELAY):
                    yield

                idx = 0
                while idx < len(payload):
                    # Compare fetched instruction to expected
                    instr = payload[idx]
                    instruction_encoded = encoder(instr)
                    self.assertEqual(
                        instruction_encoded[0], (yield dut.payload_executor.instruction)
                    )

                    # Execute instruction
                    yield

                    if hasattr(instr, "jump") and instr.jump > 0 and instr.count > 0:
                        idx -= instr.jump
                        instr.count -= 1
                        # After jump we need to wait for PIPELINE_DELAY for pipeline to clear
                        for _ in range(dut.payload_executor.PIPELINE_DELAY):
                            yield
                    else:
                        idx += 1
                        # Idle for timeslice-1 cycles
                        if not hasattr(instr, "jump"):
                            for _ in range(max(instr.timeslice - 1, 0)):
                                yield

                while not (yield dut.payload_executor.ready):
                    yield

            run_simulation(
                dut,
                [generator(dut, encoder, payload), *dut.get_generators()],
            )

        encoder = Encoder(bankbits=3)
        instrs = [
            encoder.I(OpCode.ACT, timeslice=10, address=encoder.address(bank=0, row=100)),
            encoder.I(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=200)),
            encoder.I(OpCode.LOOP, count=8 - 1, jump=1),  # to READ col=200
            encoder.I(OpCode.PRE, timeslice=15, address=encoder.address(bank=0)),
            encoder.I(OpCode.NOOP, timeslice=1),
            encoder.I(OpCode.NOOP, timeslice=2),
            encoder.I(OpCode.NOOP, timeslice=3),
            encoder.I(OpCode.NOOP, timeslice=4),
            encoder.I(OpCode.NOOP, timeslice=5),
            encoder.I(OpCode.NOOP, timeslice=6),
            encoder.I(OpCode.NOOP, timeslice=7),
            encoder.I(OpCode.NOOP, timeslice=8),
            encoder.I(OpCode.NOOP, timeslice=9),
            encoder.I(OpCode.NOOP, timeslice=10),
            encoder.I(OpCode.NOOP, timeslice=1000),
            encoder.I(OpCode.REF, timeslice=20),
            encoder.I(OpCode.REF, timeslice=25),
            encoder.I(OpCode.LOOP, count=5 - 1, jump=2),  # to first REF
        ]

        dut = PayloadExecutorDDR5DUT(encoder(instrs))
        run_payload(dut, encoder, instrs)

        op_codes = [OpCode.ACT] + 8 * [OpCode.READ] + [OpCode.PRE] + 5 * 2 * [OpCode.REF]
        self.assert_history(dut.dfi_history, op_codes)


# Interactive tests --------------------------------------------------------------------------------


def run_payload_executor(dut: PayloadExecutorDUT, *, print_period=1):
    info = {}

    def generator(dut):
        yield dut.payload_executor.start.eq(1)
        yield
        yield dut.payload_executor.start.eq(0)
        yield

        cycles = 1  # for previous yield
        while not (yield dut.payload_executor.ready):
            if cycles % print_period == 0:
                pc = yield dut.payload_executor.program_counter
                lc = yield dut.payload_executor.loop_counter
                # ic = (yield dut.payload_executor.idle_counter)
                print(f"PC = {pc:6}  LC = {lc:6}   ", end="\r")
            yield
            cycles += 1

        info["cycles"] = cycles
        info["read_count"] = yield dut.payload_executor.scratchpad.counter
        info["overflow"] = yield dut.payload_executor.scratchpad.overflow

    print(f"Payload length = {len(dut.payload)}")

    print("\nSimulating payload execution ...")
    run_simulation(dut, [generator(dut), dut.dfi_monitor()])
    print("\nFinished")

    print("\nInfo:")
    for k, v in info.items():
        print(f"  {k} = {v}")

    # merge same commands in history
    Group = namedtuple("Group", ["op_code", "entries"])
    groups = []
    for _i, entry in enumerate(dut.dfi_history):
        op_code = entry.cmd.op_code
        prev = groups[-1] if len(groups) > 0 else None
        if prev is not None and prev.op_code == op_code:
            prev.entries.append(entry)
        else:
            groups.append(Group(op_code, [entry]))

    print("\nDFI commands history:")
    cumtime = 0
    for i, group in enumerate(groups):
        start_time = group.entries[0].time
        group_time = None
        if i + 1 < len(groups):
            group_time = groups[i + 1].entries[0].time - start_time
        print(
            f"{group.op_code.name:4} x {len(group.entries):3}:"
            f" start_time = {start_time} group_time = {group_time}"
        )
        cumtime += group_time or 0
    print("Total execution cycles = {}".format(info["cycles"]))


if __name__ == "__main__":
    import argparse

    from rowhammer_tester.scripts.rowhammer import generate_row_hammer_payload
    from rowhammer_tester.scripts.utils import get_litedram_settings

    parser = argparse.ArgumentParser()
    parser.add_argument("row_sequence", nargs="+")
    parser.add_argument("--read-count", default="100")
    parser.add_argument("--payload-size", default="0x1000")
    parser.add_argument("--bank", default="0")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    settings = get_litedram_settings()

    payload_size = int(args.payload_size, 0)
    payload = generate_row_hammer_payload(
        read_count=int(float(args.read_count)),
        row_sequence=[int(r) for r in args.row_sequence],
        timings=settings.timing,
        bankbits=settings.geom.bankbits,
        bank=int(args.bank, 0),
        payload_mem_size=payload_size,
        refresh=args.refresh,
    )

    dut = PayloadExecutorDUT(payload, payload_depth=payload_size // 4)
    run_payload_executor(dut)
