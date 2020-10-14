#!/usr/bin/env python3

from litex import RemoteClient

wb = RemoteClient()
wb.open()

# Trigger a reset of the SoC
#wb.regs.ctrl_reset.write(1)

# Dump all CSR registers of the SoC
for name, reg in wb.regs.__dict__.items():
    print("0x{:08x} : 0x{:08x} {}".format(reg.addr, reg.read(), name))

#wb.write(0x40000000, 0xdeadbeef)
## test rowhammer
#import time
#wb.regs.rowhammer_enabled.write(1)
#time.sleep(200 / 1e3) # 200 ms
#wb.regs.rowhammer_enabled.write(0)
#print('rowhammer: ' + str(["0x{:08x}".format(w) for w in wb.read(0x40000000, 4)]))
#wb.write(0x40000000, 0xbadc0de)

wb.close()
