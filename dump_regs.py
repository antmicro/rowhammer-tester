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
    control_cmds = [0, 1]

    for i, (comment, a, ba, cmd, delay) in enumerate(init_sequence):
        print(comment)
        wb.regs.sdram_dfii_pi0_address.write(a)
        wb.regs.sdram_dfii_pi0_baddress.write(ba)
        if i in control_cmds:
            wb.regs.sdram_dfii_control.write(cmd)
        else:
            wb.regs.sdram_dfii_pi0_command.write(cmd)
            wb.regs.sdram_dfii_pi0_command_issue.write(1)
        import time
        time.sleep(0.001)

    sdram_hardware_control(wb)

sdram_init(wb)

# Dump all CSR registers of the SoC
for name, reg in wb.regs.__dict__.items():
    print("0x{:08x} : 0x{:08x} {}".format(reg.addr, reg.read(), name))

wb.close()
