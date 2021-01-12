import unittest
import itertools

from migen import *
from litedram.common import LiteDRAMNativePort
from rowhammer_tester.gateware.bist import Reader, Writer, PatternMemory


# DUT ----------------------------------------------------------------------------------------------

class BISTDUT(Module):
    def __init__(self, address_width=32, data_width=128, pattern_mem_length=32, pattern_init=None):
        self.address_width = address_width
        self.data_width = data_width
        self.pattern_mem_length = pattern_mem_length

        self.submodules.pattern_mem = PatternMemory(data_width, pattern_mem_length,
            addr_width=address_width, pattern_init=pattern_init)

        self.data = self.pattern_mem.data.get_port(write_capable=True)
        self.addr = self.pattern_mem.addr.get_port(write_capable=True)
        self.specials += self.data, self.addr

        self.read_port = LiteDRAMNativePort(address_width=address_width, data_width=data_width, mode='read')
        self.submodules.reader = Reader(self.read_port, self.pattern_mem)
        self.reader.add_csrs()

        self.write_port = LiteDRAMNativePort(address_width=address_width, data_width=data_width, mode='write')
        self.submodules.writer = Writer(self.write_port, self.pattern_mem)
        self.writer.add_csrs()

        # storage for port_handler (addr, we, data)
        self.commands = []

    @staticmethod
    def mem_write(mem, addr, data):
        yield mem.we.eq(1)
        yield mem.adr.eq(addr)
        yield mem.dat_w.eq(data)
        yield
        yield mem.we.eq(0)

    def default_port_handlers(self):
        return [self.write_handler(), self.read_handler()]

    @passive
    def read_handler(self, rdata_callback=None, read_delay=1):
        if rdata_callback is None:
            rdata_callback = lambda addr: 0xbaadc0de
        if not callable(rdata_callback):  # passed a single value to always be returned
            data = rdata_callback
            rdata_callback = lambda addr: data

        while True:
            while not (yield self.read_port.cmd.valid):
                yield

            addr = (yield self.read_port.cmd.addr)
            we = (yield self.read_port.cmd.we)

            if we:
                yield
                continue

            yield self.read_port.cmd.ready.eq(1)
            yield
            yield self.read_port.cmd.ready.eq(0)

            for _ in range(read_delay):
                yield

            data = rdata_callback(addr)
            yield self.read_port.rdata.data.eq(data)
            yield self.read_port.rdata.valid.eq(1)
            yield
            while not (yield self.read_port.rdata.ready):
                yield
            yield self.read_port.rdata.valid.eq(0)
            yield

            self.commands.append((addr, we, data))

    @passive
    def write_handler(self, write_delay=1):
        while True:
            while not (yield self.write_port.cmd.valid):
                yield

            addr = (yield self.write_port.cmd.addr)
            we = (yield self.write_port.cmd.we)

            if not we:
                yield
                continue

            yield self.write_port.cmd.ready.eq(1)
            yield
            yield self.write_port.cmd.ready.eq(0)

            while not (yield self.write_port.wdata.valid):
                yield
            for _ in range(write_delay):
                yield
            data = (yield self.write_port.wdata.data)
            _ = (yield self.write_port.wdata.we)  # not storing it
            yield self.write_port.wdata.ready.eq(1)
            yield
            yield self.write_port.wdata.ready.eq(0)

            self.commands.append((addr, we, data))

# Common -------------------------------------------------------------------------------------------

PATTERNS_ADDR_0 = [
    (0x00, 0x33333333222222221111111100000000),
    (0x00, 0x77777777666666665555555544444444),
    (0x00, 0xbbbbbbbbaaaaaaaa9999999988888888),
    (0x00, 0xffffffffeeeeeeeeddddddddcccccccc),
]

PATTERNS_ADDR_INC = [
    (0x00, 0x33333333222222221111111100000000),
    (0x01, 0x77777777666666665555555544444444),
    (0x02, 0xbbbbbbbbaaaaaaaa9999999988888888),
    (0x03, 0xffffffffeeeeeeeeddddddddcccccccc),
]

def wait_or_timeout(timeout, check_ready):
    cycles = 0
    while not (yield from check_ready()):
        yield
        cycles += 1
        if cycles > timeout:
            raise TimeoutError("Timeout after {} cycles".format(timeout))

def access_pattern_test(bist_name, mem_inc, pattern, count):
    mem_mask = 0xffffffff if mem_inc else 0x00000000

    def test(self):
        assert (len(pattern) & (len(pattern) - 1)) == 0, 'Must be power of 2'

        def generator(dut):
            module = getattr(dut, bist_name)

            if bist_name == 'reader':
                yield from module._skip_fifo.write(1)  # not errors checking

            yield from module._count.write(count)
            yield from module._mem_mask.write(mem_mask)
            yield from module._data_mask.write(len(pattern) - 1)  # cycle through pattern

            yield from module._start.write(1)
            yield from module._start.write(0)

            yield from wait_or_timeout(100, module._ready.read)

        dut = BISTDUT(pattern_init=pattern)
        generators = [generator(dut), *dut.default_port_handlers()]
        run_simulation(dut, generators)

        we = 0 if bist_name == 'reader' else 1
        pattern_cycle = itertools.cycle(pattern)
        if mem_inc:
            expected = [(count + addr, we, data) for count, (addr, data) in zip(range(count), pattern_cycle)]
        else:
            expected = [(addr, we, data) for _, (addr, data) in zip(range(count), pattern_cycle)]
        if bist_name == 'reader':
            expected = [(addr, we, 0xbaadc0de) for (addr, we, _) in expected]
        self.assertEqual(dut.commands, expected)

    return test

# Writer -------------------------------------------------------------------------------------------

class TestWriter(unittest.TestCase):
    # Verify correctness of access pattern depending on pattern addresses and mem_mask
    test_mem_inc_pattern_noinc = access_pattern_test('writer', mem_inc=True, pattern=PATTERNS_ADDR_0, count=13)
    test_mem_inc_pattern_inc = access_pattern_test('writer', mem_inc=True, pattern=PATTERNS_ADDR_INC, count=13)
    test_mem_noinc_pattern_noinc = access_pattern_test('writer', mem_inc=False, pattern=PATTERNS_ADDR_0, count=13)
    test_mem_noinc_pattern_inc = access_pattern_test('writer', mem_inc=False, pattern=PATTERNS_ADDR_INC, count=13)

# Reader -------------------------------------------------------------------------------------------

class TestReader(unittest.TestCase):
    # Verify correctness of access pattern depending on pattern addresses and mem_mask
    test_mem_inc_pattern_noinc = access_pattern_test('reader', mem_inc=True, pattern=PATTERNS_ADDR_0, count=13)
    test_mem_inc_pattern_inc = access_pattern_test('reader', mem_inc=True, pattern=PATTERNS_ADDR_INC, count=13)
    test_mem_noinc_pattern_noinc = access_pattern_test('reader', mem_inc=False, pattern=PATTERNS_ADDR_0, count=13)
    test_mem_noinc_pattern_inc = access_pattern_test('reader', mem_inc=False, pattern=PATTERNS_ADDR_INC, count=13)

    def test_error_detection(self):
        # Verify correct detections of memory errors
        errors = [0x3, 0x5, 0xa]

        def rdata_callback(addr):
            # generate unexpected data for some patterns
            if addr in errors:
                return 0xfffffffffffffffeffffffffffffffff
            return 0xffffffffffffffffffffffffffffffff

        count = 0x10
        pattern = [(0x00, 0xffffffffffffffffffffffffffffffff)]   # expecting same value everywhere

        def generator(dut):
            yield from dut.reader._count.write(count)
            yield from dut.reader._mem_mask.write(0xffffffff)
            yield from dut.reader._data_mask.write(0x00000000)  # use single (addr, data) pair
            yield from dut.reader._skip_fifo.write(0)

            self.assertEqual((yield from dut.reader._error_ready.read()), 0, msg='FIFO not empty after reset')
            self.assertEqual((yield from dut.reader._ready.read()), 1, msg='Reader not ready after reset')

            yield from dut.reader._start.write(1)
            yield
            yield from dut.reader._start.write(0)

            for error in errors:
                yield from wait_or_timeout(50, dut.reader._error_ready.read)

                self.assertEqual((yield from dut.reader._error_offset.read()), error)
                self.assertEqual((yield from dut.reader._error_data.read()), 0xfffffffffffffffeffffffffffffffff)
                self.assertEqual((yield from dut.reader._error_expected.read()), 0xffffffffffffffffffffffffffffffff)

                yield from dut.reader._error_continue.write(1)
                yield

            yield from wait_or_timeout(50, dut.reader._ready.read)
            self.assertEqual((yield from dut.reader._done.read()), count)

        dut = BISTDUT(pattern_init=pattern)
        generators = [generator(dut), dut.read_handler(rdata_callback)]
        run_simulation(dut, generators)

    def test_row_hammer_attack_pattern(self):
        count = 13
        row_addresses = [
            0x01, 0x03, 0x07, 0x03,
        ]

        def generator(dut):
            yield from dut.reader._skip_fifo.write(1)  # not checking errors here
            yield from dut.reader._count.write(count)

            # do not increment DRAM memory addresses
            yield from dut.reader._mem_mask.write(0)

            # mask to cycle through row_addresses
            assert len(row_addresses) & (len(row_addresses) - 1) == 0, 'Pattern length must be power of 2'
            yield from dut.reader._data_mask.write(len(row_addresses) - 1)

            for i, addr in enumerate(row_addresses):
                yield from dut.mem_write(dut.addr, addr=i, data=addr)

            yield from dut.reader._start.write(1)
            yield from dut.reader._start.write(0)

            while not (yield from dut.reader._ready.read()):
                yield

        dut = BISTDUT(pattern_init=[(addr, 0) for addr in row_addresses])
        generators = [
            generator(dut),
            dut.read_handler(0),
        ]
        run_simulation(dut, generators)

        # BIST Reader should cycle through the list of addresses
        we = 0
        expected = [(addr, we, 0) for _, addr in zip(range(count), itertools.cycle(row_addresses))]
        self.assertEqual(dut.commands, expected)
