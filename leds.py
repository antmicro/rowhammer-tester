#!/usr/bin/env python3

from litex import RemoteClient

wb = RemoteClient()
wb.open()

import time
i = 1
left = True
while True:
    wb.regs.leds_out.write(i)
    time.sleep(150 / 1e3)
    if left:
        i = i << 1
    else:
        i = i >> 1
    if i == 1:
        left = True
    elif i == 8:
        left = False

wb.close()
