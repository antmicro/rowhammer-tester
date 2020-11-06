#!/usr/bin/env python3

import time
import argparse

from rowhammer_tester.scripts.utils import RemoteClient, litex_server

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--time-ms', type=int, default=150)
    parser.add_argument('--srv', action='store_true')
    args = parser.parse_args()

    if args.srv:
        litex_server()

    wb = RemoteClient()
    wb.open()

    i = 1
    left = True
    while True:
        wb.regs.leds_out.write(i)
        time.sleep(args.time_ms / 1e3)
        if left:
            i = i << 1
        else:
            i = i >> 1
        if i == 1:
            left = True
        elif i == 8:
            left = False

    wb.close()
