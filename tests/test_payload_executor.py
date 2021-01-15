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

# Stores DFI command info
class DFICmd(namedtuple('Cmd', ['cas', 'ras', 'we'])):
    @property
    def op_code(self):
        for op, desc in DFI_COMMANDS.items():
            if tuple(self) == (desc['cas'], desc['ras'], desc['we']):
                return op
        assert False


# Information about DFI command seen on the bus
HistoryEntry = namedtuple('HistoryEntry', ['time', 'phase', 'cmd'])


class PayloadExecutorDUT(Module):
    def __init__(self, payload,
            data_width=128, scratchpad_depth=8, payload_depth=32, instruction_width=32,
            bankbits=3, rowbits=14, colbits=10, nranks=1, dfi_databits=2*16, nphases=4, rdphase=2):
        # store to be able to extract from dut later
        self.params = locals()
        self.payload = payload

        assert len(payload) <= payload_depth, '{} vs {}'.format(len(payload), payload_depth)
        self.mem_scratchpad = Memory(data_width, scratchpad_depth)
        self.mem_payload = Memory(instruction_width, payload_depth, init=payload)
        self.specials += self.mem_scratchpad, self.mem_payload

        self.dfi_sel = Signal()
        self.dfi = dfi.Interface(addressbits=max(rowbits, colbits), bankbits=bankbits,
                nranks=nranks, databits=dfi_databits, nphases=nphases)
        self.submodules.payload_executor = PayloadExecutor(
            self.mem_payload, self.mem_scratchpad, self.dfi, self.dfi_sel,
            nranks=nranks, bankbits=bankbits, rowbits=rowbits, colbits=colbits, rdphase=2)

        self.dfi_history: list[HistoryEntry] = []
        self.cycles = 0

    def get_generators(self):
        return [self.dfi_monitor(), self.cycles_counter()]

    @passive
    def dfi_monitor(self):
        time = 0
        while True:
            for i, phase in enumerate(self.dfi.phases):
                cas = 1 - (yield phase.cas_n)
                ras = 1 - (yield phase.ras_n)
                we = 1 - (yield phase.we_n)
                entry = None
                for op, desc in DFI_COMMANDS.items():
                    if (cas, ras, we) == (desc['cas'], desc['ras'], desc['we']):
                        cmd = DFICmd(cas=cas, ras=ras, we=we)
                        entry = HistoryEntry(time=time, phase=i, cmd=cmd)
                assert entry is not None, 'Unknown DFI command: cas={}, ras={}, we={}'.format(cas, ras, we)
                if entry.cmd.op_code != OpCode.NOOP:  # omit NOOPs
                    self.dfi_history.append(entry)
            yield
            time += 1

    @passive
    def cycles_counter(self):
        self.cycles = 0
        while not (yield self.payload_executor.start):
            yield
        yield
        while not (yield self.payload_executor.ready):
            yield
            self.cycles += 1

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

    def test_timeslice_0_noop_legal(self):
        Encoder(bankbits=3)(OpCode.NOOP, timeslice=0)

    def test_timeslice_0_other_illegal(self):
        with self.assertRaises(AssertionError):
            Encoder(bankbits=3)(OpCode.ACT, timeslice=0)

    def test_payload_simple(self):
        encoder = Encoder(bankbits=3)
        payload = [
            encoder(OpCode.ACT,  timeslice=10, address=encoder.address(bank=1, row=100)),
            encoder(OpCode.READ, timeslice=10, address=encoder.address(bank=1, col=13)),
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=1, col=20)),
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=1, col=20)),
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=1, col=20)),
            encoder(OpCode.PRE,  timeslice=10, address=encoder.address(bank=1)),
        ]

        dut = PayloadExecutorDUT(payload)
        self.run_payload(dut)

        # compare DFI history to what payload should yield
        op_codes = [OpCode.ACT] + 4*[OpCode.READ] + [OpCode.PRE]
        self.assertEqual(len(dut.dfi_history), len(op_codes))
        for entry, op in zip(dut.dfi_history, op_codes):
            self.assertEqual(entry.cmd.op_code, op)

    def test_payload_loop(self):
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

        dut = PayloadExecutorDUT(payload)
        self.run_payload(dut)

        op_codes = [OpCode.ACT] + 2*[OpCode.READ] + [OpCode.PRE] \
            + [OpCode.ACT] + (8+9)*[OpCode.READ] + [OpCode.ACT] + [OpCode.PRE] + 2*[OpCode.REF]
        self.assertEqual(len(dut.dfi_history), len(op_codes))
        for entry, op in zip(dut.dfi_history, op_codes):
            self.assertEqual(entry.cmd.op_code, op)

    def test_stop(self):
        encoder = Encoder(bankbits=3)
        payload = [
            encoder(OpCode.ACT,  timeslice=10, address=encoder.address(bank=1, row=100)),
            encoder(OpCode.READ, timeslice=10, address=encoder.address(bank=1, col=13)),
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=1, col=20)),
            encoder(OpCode.NOOP, timeslice=0),  # STOP instruction
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=1, col=20)),
            encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=1, col=20)),
            encoder(OpCode.PRE,  timeslice=10, address=encoder.address(bank=1)),
        ]

        dut = PayloadExecutorDUT(payload)
        self.run_payload(dut)

        op_codes = [OpCode.ACT] + 2*[OpCode.READ]
        self.assertEqual(len(dut.dfi_history), len(op_codes))
        for entry, op in zip(dut.dfi_history, op_codes):
            self.assertEqual(entry.cmd.op_code, op)

    def test_timeslice_cycles(self):
        encoder = Encoder(bankbits=3)
        payload = [
            encoder(OpCode.ACT,  timeslice=1, address=encoder.address(bank=1, row=100)),
            encoder(OpCode.READ, timeslice=1, address=encoder.address(bank=1, col=20)),
            encoder(OpCode.PRE,  timeslice=1, address=encoder.address(bank=1)),
            encoder(OpCode.NOOP, timeslice=1),  # takes 1 cycle
            encoder(OpCode.NOOP, timeslice=0),  # STOP, takes 1 cycle
        ]

        dut = PayloadExecutorDUT(payload)
        self.run_payload(dut)

        op_codes = [OpCode.ACT, OpCode.READ, OpCode.PRE]
        self.assertEqual(len(dut.dfi_history), len(op_codes))
        for entry, op in zip(dut.dfi_history, op_codes):
            self.assertEqual(entry.cmd.op_code, op)

        self.assertEqual(dut.cycles, 5)

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
                pc = (yield dut.payload_executor.program_counter)
                lc = (yield dut.payload_executor.loop_counter)
                # ic = (yield dut.payload_executor.idle_counter)
                print('PC = {:6}  LC = {:6}   '.format(pc, lc), end='\r')
            yield
            cycles += 1

        info['cycles'] = cycles
        info['read_count'] = (yield dut.payload_executor.scratchpad.counter)
        info['overflow'] = (yield dut.payload_executor.scratchpad.overflow)

    print('Payload length = {}'.format(len(dut.payload)))

    print('\nSimulating payload execution ...')
    run_simulation(dut, [generator(dut), dut.dfi_monitor()])
    print('\nFinished')

    print('\nInfo:')
    for k, v in info.items():
        print('  {} = {}'.format(k, v))

    # merge same commands in history
    Group = namedtuple('Group', ['op_code', 'entries'])
    groups = []
    for i, entry in enumerate(dut.dfi_history):
        op_code = entry.cmd.op_code
        prev = groups[-1] if len(groups) > 0 else None
        if prev is not None and prev.op_code == op_code:
            prev.entries.append(entry)
        else:
            groups.append(Group(op_code, [entry]))

    print('\nDFI commands history:')
    cumtime = 0
    for i, group in enumerate(groups):
        start_time = group.entries[0].time
        group_time = None
        if i+1 < len(groups):
            group_time = groups[i+1].entries[0].time - start_time
        print('{:4} x {:3}: start_time = {} group_time = {}'.format(
            group.op_code.name, len(group.entries), start_time, group_time))
        cumtime += group_time or 0
    print('Total execution cycles = {}'.format(info['cycles']))


if __name__ == "__main__":
    import argparse
    from rowhammer_tester.scripts.rowhammer import generate_row_hammer_payload
    from rowhammer_tester.scripts.utils import get_litedram_settings

    parser = argparse.ArgumentParser()
    parser.add_argument('row_sequence', nargs='+')
    parser.add_argument('--read-count', default='100')
    parser.add_argument('--payload-size', default='0x1000')
    parser.add_argument('--bank', default='0')
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()

    settings = get_litedram_settings()

    payload_size = int(args.payload_size, 0)
    payload = generate_row_hammer_payload(
        read_count       = int(float(args.read_count)),
        row_sequence     = [int(r) for r in args.row_sequence],
        timings          = settings.timing,
        bankbits         = settings.geom.bankbits,
        bank             = int(args.bank, 0),
        payload_mem_size = payload_size,
        refresh          = args.refresh,
    )

    dut = PayloadExecutorDUT(payload, payload_depth=payload_size//4)
    run_payload_executor(dut)
