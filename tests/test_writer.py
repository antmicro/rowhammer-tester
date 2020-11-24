import unittest

from migen import *
from litedram.common import LiteDRAMNativePort
from rowhammer_tester.gateware.bist import Writer, PatternMemory

class TestWriter(unittest.TestCase):
    def test_pattern_1(self):
        class DUT(Module):
            def __init__(self):
                self.dram_port = LiteDRAMNativePort(address_width=32, data_width=32*4, mode='both')
                self.submodules.pattern_mem = PatternMemory(self.dram_port.data_width, 16)
                self.submodules.writer = Writer(self.dram_port, self.pattern_mem)
                self.writer.add_csrs()

                self.data = self.pattern_mem.data.get_port(write_capable=True)
                self.specials += self.data


        def generator(dut):
            yield from dut.writer._count.write(4)

            yield from dut.writer._mem_mask.write(0xffffffff)

            yield from dut.writer._data_mask.write(0x1)


            yield dut.data.adr.eq(0x0)
            yield dut.data.dat_w.eq(0x44444444333333332222222211111111)
            yield dut.data.we.eq(1)
            yield
            yield dut.data.we.eq(0)
            yield


            yield dut.data.adr.eq(0x1)
            yield dut.data.dat_w.eq(0xddddddddccccccccbbbbbbbbaaaaaaaa)
            yield dut.data.we.eq(1)
            yield
            yield dut.data.we.eq(0)
            yield

            yield from dut.writer._start.write(1)
            yield from dut.writer._start.write(0)

            for n in range(0, 200):
                yield


        patterns = dict()
        patterns[0x00000000] = 0x44444444333333332222222211111111
        patterns[0x00000001] = 0xddddddddccccccccbbbbbbbbaaaaaaaa
        patterns[0x00000002] = 0x44444444333333332222222211111111
        patterns[0x00000003] = 0xddddddddccccccccbbbbbbbbaaaaaaaa

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
