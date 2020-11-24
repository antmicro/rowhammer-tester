import unittest

from migen import *
from litedram.common import LiteDRAMNativePort
from rowhammer_tester.gateware.bist import Reader, PatternMemory

class TestReader(unittest.TestCase):
    def test_pattern_1(self):
        class DUT(Module):
            def __init__(self):
                self.dram_port = LiteDRAMNativePort(address_width=32, data_width=32*4, mode='both')
                self.submodules.pattern_mem = PatternMemory(self.dram_port.data_width, 16)
                self.submodules.reader = Reader(self.dram_port, self.pattern_mem)
                self.reader.add_csrs()

                self.data = self.pattern_mem.data.get_port(write_capable=True)
                self.addr = self.pattern_mem.addr.get_port(write_capable=True)
                self.specials += self.data, self.addr


        def generator(dut):
            yield from dut.reader._count.write(8)

            yield from dut.reader._mem_mask.write(0xffffffff)
            yield from dut.reader._data_mask.write(0x00000000)
            yield from dut.reader._skip_fifo.write(0)

            yield dut.data.adr.eq(0x0)
            yield dut.data.dat_w.eq(0xffffffffffffffffffffffffffffffff)
            yield dut.data.we.eq(1)
            yield
            yield dut.data.we.eq(0)
            yield

            yield dut.addr.adr.eq(0x0)
            yield dut.addr.dat_w.eq(0)
            yield dut.addr.we.eq(1)
            yield
            yield dut.addr.we.eq(0)
            yield

            # Fifo should be empty
            self.assertEqual((yield from dut.reader._error_ready.read()), 0)

            yield from dut.reader._start.write(1)

            # Fixme sync with read_handler
            for n in range(0, 200):
                yield

            #ptr = yield from dut.reader.pointer.read()
            #self.assertEqual(ptr, 5)

            # Check if ready
            self.assertEqual((yield from dut.reader._done.read()), 8)
            self.assertEqual((yield from dut.reader._ready.read()), 1)

            self.assertEqual((yield from dut.reader._error_ready.read()), 1)
            self.assertEqual((yield from dut.reader._error_offset.read()), 3)

            for n in range(0, 13): yield

            self.assertEqual((yield from dut.reader._error_ready.read()), 1)
            self.assertEqual((yield from dut.reader._error_offset.read()), 5)

            for n in range(0, 17): yield

            self.assertEqual((yield from dut.reader._error_ready.read()), 0)

            for n in range(0, 23): yield

        @passive
        def read_handler(dram_port):
            address = 0
            pending = 0
            yield dram_port.cmd.ready.eq(0)
            while True:
                yield dram_port.rdata.valid.eq(0)
                if pending:
                    yield dram_port.rdata.valid.eq(1)
                    #yield dram_port.rdata.data.eq(self._read(address))

                    #print('RD: {:08x}'.format(address))

                    # FIXME: Make this more generic and use counter_shift
                    if address == 0x5 or address == 0x3:
                        yield dram_port.rdata.data.eq(0xfffffffffffffffeffffffffffffffff)
                    else:
                        yield dram_port.rdata.data.eq(0xffffffffffffffffffffffffffffffff)

                    yield
                    yield dram_port.rdata.valid.eq(0)
                    yield dram_port.rdata.data.eq(0)
                    pending = 0
                elif (yield dram_port.cmd.valid):
                    pending = not (yield dram_port.cmd.we)
                    address = (yield dram_port.cmd.addr)
                    if pending:
                        yield dram_port.cmd.ready.eq(1)
                        yield
                        yield dram_port.cmd.ready.eq(0)
                yield


        dut = DUT()
        dut.finalize()

        generators = [
            generator(dut),
            read_handler(dut.dram_port),
        ]

        run_simulation(dut, generators)
