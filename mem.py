#!/usr/bin/env python3

from litex import RemoteClient

wb = RemoteClient()
wb.open()

# ###########################################################################
from sdram_init import *

def sdram_software_control(wb):
    wb.regs.sdram_dfii_control.write(0)

def sdram_hardware_control(wb):
    wb.regs.sdram_dfii_control.write(dfii_control_sel)

def sdram_init(wb):
    sdram_software_control(wb)

    # we cannot check for the string "DFII_CONTROL" as done when generating C code,
    # so this is hardcoded for now
    # update: Hacky but works
    control_cmds = []
    with open('sdram_init.py', 'r') as f:
        n = 0
        while True:
            line = f.readline()
            if not line: break
            line = line.strip().replace(' ', '')
            if len(line) and line[0] == '(':
                if line.find('_control_') > 0:
                    control_cmds.append(n)
                n = n + 1


    print('control_cmds: ' + str(control_cmds))
    for i, (comment, a, ba, cmd, delay) in enumerate(init_sequence):
        wb.regs.sdram_dfii_pi0_address.write(a)
        wb.regs.sdram_dfii_pi0_baddress.write(ba)
        if i in control_cmds:
            print(comment + ' (ctrl)')
            wb.regs.sdram_dfii_control.write(cmd)
        else:
            print(comment + ' (cmd)')
            wb.regs.sdram_dfii_pi0_command.write(cmd)
            wb.regs.sdram_dfii_pi0_command_issue.write(1)
        import time
        time.sleep(0.001)

    sdram_hardware_control(wb)

sdram_init(wb)
# ###########################################################################

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

wb.close()
