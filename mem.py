#!/usr/bin/env python3

from litex import RemoteClient

wb = RemoteClient()
wb.open()

sdram_base    = 0x40000000

from random import randrange
sdram_pattern = randrange(0x0, 0x100000000)

#sdram_pattern = 0x12345678

# Access SDRAM (with wb.mems and base address)
#wb.write(wb.mems.main_ram.base, 0x12345678)
#value = wb.read(wb.mems.main_ram.base)

# Access SDRAM
wb.write(sdram_base, sdram_pattern)
value = wb.read(sdram_base)
if value != sdram_pattern:
    print('Mem error at 0x{:08x} : 0x{:08x} != 0x{:08x}'
        .format(sdram_base, value, sdram_pattern))
    print('x: ' + str(["0x{:08x}".format(w) for w in wb.read(0x40000000, 4)]))
else:
    for i in range(0, 1024):
        wb.write(wb.mems.main_ram.base + i, 0x55555555)
    for i in range(1024, 2048):
        wb.write(wb.mems.main_ram.base + i, 0xaaaaaaaa)
    for i in range(0, 1024):
        val = wb.read(wb.mems.main_ram.base + i)
        assert(val == 0x55555555)
    for i in range(1024, 2048):
        val = wb.read(wb.mems.main_ram.base + i)
        assert(val == 0xaaaaaaaa)

    print('1. ' + str(["0x{:08x}".format(w) for w in wb.read(0x40000000 + 1024 - 2 * 4, 4)]))

    for i in range(0, 1024):
        wb.write(wb.mems.main_ram.base + i, 0xaaaaaaaa)
    for i in range(1024, 2048):
        wb.write(wb.mems.main_ram.base + i, 0x55555555)
    for i in range(0, 1024):
        val = wb.read(wb.mems.main_ram.base + i)
        assert(val == 0xaaaaaaaa)
    for i in range(1024, 2048):
        val = wb.read(wb.mems.main_ram.base + i)
        assert(val == 0x55555555)

    print('2. ' + str(["0x{:08x}".format(w) for w in wb.read(0x40000000 + 1024 - 2 * 4, 4)]))
    print("Mem ok!")

# test rowhammer
import time
wb.regs.rowhammer_enabled.write(1)
time.sleep(200 / 1e3) # 200 ms
wb.regs.rowhammer_enabled.write(0)
print('rowhammer: ' + str(["0x{:08x}".format(w) for w in wb.read(0x40000000, 4)]))

wb.close()
