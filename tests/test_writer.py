import unittest

from migen import *
from writer import *

class TestWriter(unittest.TestCase):
    def test_pattern_1(self):
        class DUT(Module):
            def __init__(self):
                from litedram.common import LiteDRAMNativePort
                self.dram_port = LiteDRAMNativePort(address_width=32, data_width=32*4, mode='both')
                self.submodules.writer = Writer(self.dram_port)

                self.w0 = self.writer.memory_w0.get_port(write_capable=True)
                self.w1 = self.writer.memory_w1.get_port(write_capable=True)
                self.w2 = self.writer.memory_w2.get_port(write_capable=True)
                self.w3 = self.writer.memory_w3.get_port(write_capable=True)
                self.specials += self.w0, self.w1, self.w2, self.w3


        def generator(dut):
            yield from dut.writer.reset.write(1)
            yield from dut.writer.reset.write(0)

            yield from dut.writer.count.write(4)

            yield from dut.writer.mem_base.write(0x30000000)
            yield from dut.writer.mem_mask.write(0xffffffff)

            yield from dut.writer.data_mask.write(0x1)


            yield dut.w0.adr.eq(0x0)
            yield dut.w0.dat_w.eq(0x11111111)
            yield dut.w0.we.eq(1)
            yield
            yield dut.w0.we.eq(0)
            yield

            yield dut.w1.adr.eq(0x0)
            yield dut.w1.dat_w.eq(0x22222222)
            yield dut.w1.we.eq(1)
            yield
            yield dut.w1.we.eq(0)
            yield

            yield dut.w2.adr.eq(0x0)
            yield dut.w2.dat_w.eq(0x33333333)
            yield dut.w2.we.eq(1)
            yield
            yield dut.w2.we.eq(0)
            yield

            yield dut.w3.adr.eq(0x0)
            yield dut.w3.dat_w.eq(0x44444444)
            yield dut.w3.we.eq(1)
            yield
            yield dut.w3.we.eq(0)
            yield


            yield dut.w0.adr.eq(0x1)
            yield dut.w0.dat_w.eq(0xaaaaaaaa)
            yield dut.w0.we.eq(1)
            yield
            yield dut.w0.we.eq(0)
            yield

            yield dut.w1.adr.eq(0x1)
            yield dut.w1.dat_w.eq(0xbbbbbbbb)
            yield dut.w1.we.eq(1)
            yield
            yield dut.w1.we.eq(0)
            yield

            yield dut.w2.adr.eq(0x1)
            yield dut.w2.dat_w.eq(0xcccccccc)
            yield dut.w2.we.eq(1)
            yield
            yield dut.w2.we.eq(0)
            yield

            yield dut.w3.adr.eq(0x1)
            yield dut.w3.dat_w.eq(0xdddddddd)
            yield dut.w3.we.eq(1)
            yield
            yield dut.w3.we.eq(0)
            yield


            yield from dut.writer.start.write(1)
            yield from dut.writer.start.write(0)

            for n in range(0, 200):
                yield


        patterns = dict()
        patterns[0x30000000] = 0x44444444333333332222222211111111
        patterns[0x30000001] = 0xddddddddccccccccbbbbbbbbaaaaaaaa
        patterns[0x30000002] = 0x44444444333333332222222211111111
        patterns[0x30000003] = 0xddddddddccccccccbbbbbbbbaaaaaaaa

        @passive
        def write_handler(dram_port):
            address = 0
            pending = 0
            yield dram_port.cmd.ready.eq(0)
            while True:
                yield dram_port.wdata.ready.eq(0)
                if pending:
                    while (yield dram_port.wdata.valid) == 0:
                        yield
                    yield dram_port.wdata.ready.eq(1)
                    yield
                    #self._write(address, (yield dram_port.wdata.data), (yield dram_port.wdata.we))
                    data = (yield dram_port.wdata.data)
                    self.assertEqual(patterns[address], data,
                        '{:08x}: {:032x} != {:032x}'.format(address, data, patterns[address]))
                    yield dram_port.wdata.ready.eq(0)
                    yield
                    pending = 0
                    yield
                elif (yield dram_port.cmd.valid):
                    pending = (yield dram_port.cmd.we)
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
            write_handler(dut.dram_port),
        ]

        run_simulation(dut, generators)
