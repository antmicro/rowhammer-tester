import unittest

from migen import *
from rowhammer_tester.gateware.reader import *

class TestReader(unittest.TestCase):
    def test_pattern_1(self):
        class DUT(Module):
            def __init__(self):
                from litedram.common import LiteDRAMNativePort
                self.dram_port = LiteDRAMNativePort(address_width=32, data_width=32*4, mode='both')
                self.submodules.reader = Reader(self.dram_port)

                self.w0 = self.reader.memory_w0.get_port(write_capable=True)
                self.w1 = self.reader.memory_w1.get_port(write_capable=True)
                self.w2 = self.reader.memory_w2.get_port(write_capable=True)
                self.w3 = self.reader.memory_w3.get_port(write_capable=True)
                self.adr = self.reader.memory_adr.get_port(write_capable=True)
                self.specials += self.w0, self.w1, self.w2, self.w3, self.adr


        def generator(dut):
            yield from dut.reader.reset.write(1)
            yield
            yield from dut.reader.reset.write(0)
            yield

            yield from dut.reader.count.write(8)

            yield from dut.reader.mem_mask.write(0xffffffff)
            yield from dut.reader.gen_mask.write(0x00000000)
            yield from dut.reader.skipfifo.write(0)

            yield dut.w0.adr.eq(0x0)
            yield dut.w0.dat_w.eq(0xffffffff)
            yield dut.w0.we.eq(1)
            yield
            yield dut.w0.we.eq(0)
            yield

            yield dut.w1.adr.eq(0x0)
            yield dut.w1.dat_w.eq(0xffffffff)
            yield dut.w1.we.eq(1)
            yield
            yield dut.w1.we.eq(0)
            yield

            yield dut.w2.adr.eq(0x0)
            yield dut.w2.dat_w.eq(0xffffffff)
            yield dut.w2.we.eq(1)
            yield
            yield dut.w2.we.eq(0)
            yield

            yield dut.w3.adr.eq(0x0)
            yield dut.w3.dat_w.eq(0xffffffff)
            yield dut.w3.we.eq(1)
            yield
            yield dut.w3.we.eq(0)
            yield

            yield dut.adr.adr.eq(0x0)
            yield dut.adr.dat_w.eq(0)
            yield dut.adr.we.eq(1)
            yield
            yield dut.adr.we.eq(0)
            yield

            # Fifo should be empty
            self.assertEqual((yield from dut.reader.err_rdy.read()), 0)

            yield from dut.reader.start.write(1)
            yield from dut.reader.start.write(0)

            # Fixme sync with read_handler
            for n in range(0, 200):
                yield

            #ptr = yield from dut.reader.pointer.read()
            #self.assertEqual(ptr, 5)

            # Check if ready
            self.assertEqual((yield from dut.reader.done.read()), 8)
            self.assertEqual((yield from dut.reader.ready.read()), 1)

            self.assertEqual((yield from dut.reader.err_rdy.read()), 1)
            self.assertEqual((yield from dut.reader.err_rd.read()), 3)

            for n in range(0, 13): yield

            self.assertEqual((yield from dut.reader.err_rdy.read()), 1)
            self.assertEqual((yield from dut.reader.err_rd.read()), 5)

            for n in range(0, 17): yield

            self.assertEqual((yield from dut.reader.err_rdy.read()), 0)

            for n in range(0, 23): yield

            yield from dut.reader.reset.write(1)
            yield
            yield from dut.reader.reset.write(0)
            yield


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
