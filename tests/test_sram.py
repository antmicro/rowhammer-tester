import unittest

from litex.soc.interconnect import wishbone
from migen import READ_FIRST, Memory, Module, run_simulation

from rowhammer_tester.gateware.sram import SRAM


class TestSRAM(unittest.TestCase):
    class DUT(Module):
        def __init__(self, payload_size):
            self.payload_mem = Memory(32, payload_size // 4)
            self.specials += self.payload_mem

            self.bus = wishbone.Interface(data_width=self.payload_mem.width)

            self.submodules.sram = SRAM(
                self.payload_mem,
                bus=self.bus,
                read_only=False,
                mode=READ_FIRST,
            )

    def test_read_write(self):
        def generator(dut, seq):
            for adr, data in seq:
                yield from dut.bus.write(adr, data)
            yield

            for adr, data in seq:
                self.assertEqual((yield from dut.bus.read(adr)), data)
            yield

        dut = self.DUT(32)
        seq = [(0x0, 0x42), (0x1, 0x12), (0x2, 0xFF), (0x3, 0x9)]
        run_simulation(dut, generator(dut, seq))
