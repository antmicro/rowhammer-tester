#!/usr/bin/env python3

from litex import RemoteClient

wb = RemoteClient()
wb.open()

# Trigger a reset of the SoC
#wb.regs.ctrl_reset.write(1)

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

#sdram_init(wb)

# Dump all CSR registers of the SoC
#for name, reg in wb.regs.__dict__.items():
#    print("0x{:08x} : 0x{:08x} {}".format(reg.addr, reg.read(), name))

wb.write(0x40000000, 0xdeadbeef)
# test rowhammer
import time
wb.regs.rowhammer_enabled.write(1)
time.sleep(200 / 1e3) # 200 ms
wb.regs.rowhammer_enabled.write(0)
print('rowhammer: ' + str(["0x{:08x}".format(w) for w in wb.read(0x40000000, 4)]))
wb.write(0x40000000, 0xbadc0de)

wb.close()
