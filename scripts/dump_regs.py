#!/usr/bin/env python3

from litex import RemoteClient

wb = RemoteClient()
wb.open()

# Trigger a reset of the SoC
#wb.regs.ctrl_reset.write(1)

# Dump all CSR registers of the SoC
for name, reg in wb.regs.__dict__.items():
    print("0x{:08x} : 0x{:08x} {}".format(reg.addr, reg.read(), name))

wb.close()
