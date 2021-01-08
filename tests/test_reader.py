import unittest
import itertools

from migen import *
from litedram.common import LiteDRAMNativePort
from rowhammer_tester.gateware.bist import Reader, PatternMemory


class BISTReaderDUT(Module):
    def __init__(self, address_width=32, data_width=128, pattern_mem_length=32):
        self.dram_port = LiteDRAMNativePort(address_width=address_width, data_width=data_width, mode='both')
        self.submodules.pattern_mem = PatternMemory(self.dram_port.data_width, pattern_mem_length)
        self.submodules.reader = Reader(self.dram_port, self.pattern_mem)
        self.reader.add_csrs()

        self.data = self.pattern_mem.data.get_port(write_capable=True)
        self.addr = self.pattern_mem.addr.get_port(write_capable=True)
        self.specials += self.data, self.addr

    def mem_write(self, mem, addr, data):
        yield mem.we.eq(1)
        yield mem.adr.eq(addr)
        yield mem.dat_w.eq(data)
        yield
        yield mem.we.eq(0)

    @passive
    def read_generator(self, data_callback, read_delay=1):
        if not callable(data_callback):  # passed a single value to always be returned
            data = data_callback
            data_callback = lambda addr: data

        while True:
            while not (yield self.dram_port.cmd.valid):
                yield

            assert not (yield self.dram_port.cmd.we), 'WRITE command found'
            addr = (yield self.dram_port.cmd.addr)

            yield self.dram_port.cmd.ready.eq(1)
            yield
            yield self.dram_port.cmd.ready.eq(0)

            for _ in range(read_delay):
                yield

            data = data_callback(addr)
            yield self.dram_port.rdata.data.eq(data)
            yield self.dram_port.rdata.valid.eq(1)
            yield
            while not (yield self.dram_port.rdata.ready):
                yield
            yield self.dram_port.rdata.valid.eq(0)
            yield


class TestReader(unittest.TestCase):
    def test_error_detection(self):
        def generator(dut):
            yield from dut.reader._count.write(8)
            yield from dut.reader._mem_mask.write(0xffffffff)
            yield from dut.reader._data_mask.write(0x00000000)
            yield from dut.reader._skip_fifo.write(0)

            yield from dut.mem_write(dut.data, addr=0, data=0xffffffffffffffffffffffffffffffff)
            yield from dut.mem_write(dut.addr, addr=0, data=0)

            # Fifo should be empty
            self.assertEqual((yield from dut.reader._error_ready.read()), 0)

            yield from dut.reader._start.write(1)

            for _ in range(50): yield

            # Check if ready
            self.assertEqual((yield from dut.reader._done.read()), 8)
            self.assertEqual((yield from dut.reader._ready.read()), 1)

            self.assertEqual((yield from dut.reader._error_ready.read()), 1)
            self.assertEqual((yield from dut.reader._error_offset.read()), 3)
            self.assertEqual((yield from dut.reader._error_data.read()), 0xfffffffffffffffeffffffffffffffff)
            self.assertEqual((yield from dut.reader._error_expected.read()), 0xffffffffffffffffffffffffffffffff)
            yield from dut.reader._error_continue.write(1)

            for _ in range(0, 13): yield

            self.assertEqual((yield from dut.reader._error_ready.read()), 1)
            self.assertEqual((yield from dut.reader._error_offset.read()), 5)
            self.assertEqual((yield from dut.reader._error_data.read()), 0xfffffffffffffffeffffffffffffffff)
            self.assertEqual((yield from dut.reader._error_expected.read()), 0xffffffffffffffffffffffffffffffff)
            yield from dut.reader._error_continue.write(1)

            for _ in range(0, 17): yield

            self.assertEqual((yield from dut.reader._error_ready.read()), 0)

        def data_callback(addr):
            if addr in [0x5, 0x3]:
                return 0xfffffffffffffffeffffffffffffffff
            return 0xffffffffffffffffffffffffffffffff

        dut = BISTReaderDUT()
        generators = [
            generator(dut),
            dut.read_generator(data_callback),
        ]
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

        accesses = []

        def data_callback(addr):
            accesses.append(addr)
            return 0  # we don't care about data here

        dut = BISTReaderDUT()
        generators = [
            generator(dut),
            dut.read_generator(data_callback),
        ]
        run_simulation(dut, generators)

        # BIST Reader should cycle through the list of addresses
        expected = itertools.cycle(row_addresses)
        expected = [next(expected) for _ in range(count)]
        self.assertEqual(accesses, expected)
