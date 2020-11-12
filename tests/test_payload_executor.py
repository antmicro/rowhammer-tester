import unittest
from collections import namedtuple

from migen import *
from litex.gen.sim import *
from litedram.phy import dfi
from migen.genlib.coding import Decoder as OneHotDecoder

from rowhammer_tester.gateware.payload_executor import *

class Hex:
    # Helper for constructing readable hex integers, e.g. 0x11111111
    def __init__(self, num, width):
        num %= 16
        self.string = '{:x}'.format(num) * (width // 4)

    def __add__(self, other):
        new = Hex(0, 0)
        new.string = self.string + other.string
        return new

    def int(self):
        return int('0x{}'.format(self.string), 16)

    @staticmethod
    def error(int1, int2, width):
        return '\n{:{w}x}\n{:{w}x}'.format(int1, int2, w=width)

DFI_COMMANDS = {
    OpCode.NOOP: dict(cas=0, ras=0, we=0),
    OpCode.ACT:  dict(cas=0, ras=1, we=0),
    OpCode.READ: dict(cas=1, ras=0, we=0),
    OpCode.PRE:  dict(cas=0, ras=1, we=1),
    OpCode.REF:  dict(cas=1, ras=1, we=0),
    OpCode.ZQC:  dict(cas=0, ras=0, we=1),
}

# Scratchpad -------------------------------------------------------------------

class TestScratchpad(unittest.TestCase):
    class DUT(Module):
        def __init__(self):
            self.mem = Memory(128, 8)
            self.read_port = self.mem.get_port()
            self.specials += self.mem, self.read_port
            self.dfi = dfi.Interface(addressbits=14, bankbits=3, nranks=1, databits=2*16, nphases=4)
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
                yield from dut.receive_read(i+1)
            yield

            expected = [
                (Hex(1, 32) + Hex(2, 32) + Hex(3, 32) + Hex(4, 32)).int(),
                (Hex(2, 32) + Hex(3, 32) + Hex(4, 32) + Hex(5, 32)).int(),
                (Hex(3, 32) + Hex(4, 32) + Hex(5, 32) + Hex(6, 32)).int(),
            ]

            for i, e in enumerate(expected):
                memdata = (yield from dut.mem_read(i))
                self.assertEqual(memdata, e, msg=Hex.error(memdata, e, 32))

        dut = self.DUT()
        run_simulation(dut, generator(dut))

# Decoder ----------------------------------------------------------------------

class TestDecoder(unittest.TestCase):
    class DUT(Module):
        def __init__(self):
            self.instruction = Signal(32)
            self.submodules.decoder = Decoder(
                self.instruction, rankbits=0, bankbits=3, rowbits=14, colbits=10)

    def test_op_code(self):
        def generator(dut):
            encoder = Encoder(bankbits=3)

            for op in OpCode:
                kwargs = dict(count=1, jump=1) if op == OpCode.LOOP else dict(timeslice=1)
                yield dut.instruction.eq(encoder(op, **kwargs))
                yield
                self.assertEqual((yield dut.decoder.op_code), op)

        dut = self.DUT()
        run_simulation(dut, generator(dut))

    def test_loop(self):
        def generator(dut):
            encoder = Encoder(bankbits=3)

            yield dut.instruction.eq(encoder(OpCode.LOOP, count=3, jump=9))
            yield
            self.assertEqual((yield dut.decoder.loop_count), 3)
            self.assertEqual((yield dut.decoder.loop_jump),  9)

            count_max = 2**Decoder.LOOP_COUNT - 1
            yield dut.instruction.eq(encoder(OpCode.LOOP, count=count_max, jump=9))
            yield
            self.assertEqual((yield dut.decoder.loop_count), count_max)
            self.assertEqual((yield dut.decoder.loop_jump),  9)

            jump_max = 2**Decoder.LOOP_JUMP - 1
            yield dut.instruction.eq(encoder(OpCode.LOOP, count=3, jump=jump_max))
            yield
            self.assertEqual((yield dut.decoder.loop_count), 3)
            self.assertEqual((yield dut.decoder.loop_jump),  jump_max)

        dut = self.DUT()
        run_simulation(dut, generator(dut))

    def test_noop_timeslice(self):
        def generator(dut):
            encoder = Encoder(bankbits=3)

            timeslice_max = 2**Decoder.TIMESLICE_NOOP - 1
            yield dut.instruction.eq(encoder(OpCode.NOOP, timeslice=timeslice_max))
            yield
            self.assertEqual((yield dut.decoder.timeslice), timeslice_max)

        dut = self.DUT()
        run_simulation(dut, generator(dut))

    def test_dfi_timeslice(self):
        def generator(dut):
            encoder = Encoder(bankbits=3)

            timeslice_max = 2**Decoder.TIMESLICE - 1
            yield dut.instruction.eq(encoder(OpCode.ACT, timeslice=timeslice_max))
            yield
            self.assertEqual((yield dut.decoder.timeslice), timeslice_max)

        dut = self.DUT()
        run_simulation(dut, generator(dut))

    def test_dfi_address(self):
        def generator(dut):
            encoder = Encoder(bankbits=3)
            bank, row, col = (2**3 - 1, 2** 14 - 1, 2**10 - 1)

            yield dut.instruction.eq(encoder(OpCode.ACT, timeslice=3, address=encoder.address(
                bank=bank, row=row)))
            yield
            self.assertEqual((yield dut.decoder.timeslice), 3)
            self.assertEqual((yield dut.decoder.dfi_bank), bank)
            self.assertEqual((yield dut.decoder.dfi_address), row)

            yield dut.instruction.eq(encoder(OpCode.READ, timeslice=4, address=encoder.address(
                bank=bank, col=col)))
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
                    kwargs['address'] = 11
                yield dut.instruction.eq(encoder(op, timeslice=5, **kwargs))
                yield
                self.assertEqual((yield dut.decoder.timeslice), 5)
                self.assertEqual((yield dut.decoder.cas), desc['cas'])
                self.assertEqual((yield dut.decoder.ras), desc['ras'])
                self.assertEqual((yield dut.decoder.we), desc['we'])

        dut = self.DUT()
        run_simulation(dut, generator(dut))

# DFIExecutor ------------------------------------------------------------------

class TestDFIExecutor(unittest.TestCase):
    class DUT(TestDecoder.DUT):
        def __init__(self):
            super().__init__()
            self.dfi = dfi.Interface(addressbits=14, bankbits=3, nranks=1, databits=2*16, nphases=4)
            self.submodules.rank_decoder = OneHotDecoder(1)
            self.submodules.executor = DFIExecutor(self.dfi, self.decoder, self.rank_decoder)

    def test_inactive(self):
        def generator(dut):
            encoder = Encoder(bankbits=3)
            yield dut.executor.exec.eq(0)
            yield dut.instruction.eq(encoder(OpCode.NOOP, timeslice=1))
            yield

            for phase in dut.dfi.phases:
                self.assertEqual((yield phase.cke), 1)
                self.assertEqual((yield phase.odt), 1)
                self.assertEqual((yield phase.reset_n), 1)
                self.assertEqual((yield phase.cs_n), 1)
                self.assertEqual((yield phase.cas_n), 1)
                self.assertEqual((yield phase.ras_n), 1)
                self.assertEqual((yield phase.we_n), 1)

            yield dut.instruction.eq(encoder(OpCode.ACT, timeslice=1, address=2))
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
            yield dut.instruction.eq(encoder(OpCode.ACT, timeslice=1, address=2))
            yield dut.executor.phase.eq(0)
            yield dut.executor.exec.eq(1)
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

class TestPayloadExecutor(unittest.TestCase):
    class Cmd(namedtuple('Cmd', ['cas', 'ras', 'we'])):
        @property
        def op_code(self):
            for op, desc in DFI_COMMANDS.items():
                if tuple(self) == (desc['cas'], desc['ras'], desc['we']):
                    return op
            assert False

    HistoryEntry = namedtuple('HistoryEntry', ['time', 'phase', 'cmd'])

    class DUT(Module):
        def __init__(self, payload):
            self.mem_scratchpad = Memory(128, 8)
            self.mem_payload = Memory(32, 32, init=payload)
            self.specials += self.mem_scratchpad, self.mem_payload

            self.dfi = dfi.Interface(addressbits=14, bankbits=3, nranks=1, databits=2*16, nphases=4)
            self.dfi_sel = Signal()
            self.submodules.payload_executor = PayloadExecutor(
                self.mem_payload, self.mem_scratchpad, self.dfi, self.dfi_sel,
                nranks=1, bankbits=3, rowbits=14, colbits=10, rdphase=2)

            self.dfi_history: list[HistoryEntry] = []

        @passive
        def dfi_monitor(self):
            Cmd, HistoryEntry = TestPayloadExecutor.Cmd, TestPayloadExecutor.HistoryEntry
            time = 0
            while True:
                for i, phase in enumerate(self.dfi.phases):
                    cas = 1 - (yield phase.cas_n)
                    ras = 1 - (yield phase.ras_n)
                    we = 1 - (yield phase.we_n)
                    entry = None
                    for op, desc in DFI_COMMANDS.items():
                        if (cas, ras, we) == (desc['cas'], desc['ras'], desc['we']):
                            cmd = Cmd(cas=cas, ras=ras, we=we)
                            entry = HistoryEntry(time=time, phase=i, cmd=cmd)
                    assert entry is not None, 'Unknown DFI command: cas={}, ras={}, we={}'.format(cas, ras, we)
                    if entry.cmd.op_code != OpCode.NOOP:  # omit NOOPs
                        self.dfi_history.append(entry)
                yield
                time += 1

    def test_payload(self):
        def generator(dut):
            yield dut.payload_executor.start.eq(1)
            yield
            yield dut.payload_executor.start.eq(0)
            yield

            while not (yield dut.payload_executor.ready):
                yield

        encoder = Encoder(bankbits=3)
        payload = [
            encoder(OpCode.NOOP, timeslice=50),

            encoder(OpCode.ACT,  timeslice=10, address=encoder.address(bank=1, row=100)),
            encoder(OpCode.READ, timeslice=10, address=encoder.address(bank=1, col=13)),
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=1, col=20)),
            encoder(OpCode.PRE,  timeslice=10, address=encoder.address(bank=1)),

            encoder(OpCode.ACT,  timeslice=10, address=encoder.address(bank=0, row=100)),
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=200)),
            encoder(OpCode.LOOP, count=8 - 1, jump=1),  # to READ col=200
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=208)),
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=216)),
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=224)),
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=232)),
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=240)),
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=248)),
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=256)),
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=264)),
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=300 | (1 << 10))),  # auto precharge

            encoder(OpCode.ACT,  timeslice=60, address=encoder.address(bank=2, row=150)),

            encoder(OpCode.PRE,  timeslice=10, address=encoder.address(col=1 << 10)),  # all
            encoder(OpCode.REF,  timeslice=50),
            encoder(OpCode.REF,  timeslice=50),

            encoder(OpCode.NOOP, timeslice=50),
        ]

        dut = self.DUT(payload)
        run_simulation(dut, [generator(dut), dut.dfi_monitor()])

        # compare DFI history to what payload should yield
        op_codes = [OpCode.ACT] + 2*[OpCode.READ] + [OpCode.PRE] \
            + [OpCode.ACT] + (8+9)*[OpCode.READ] + [OpCode.ACT] + [OpCode.PRE] + 2*[OpCode.REF]
        self.assertEqual(len(dut.dfi_history), len(op_codes))
        for entry, op in zip(dut.dfi_history, op_codes):
            self.assertEqual(entry.cmd.op_code, op)
