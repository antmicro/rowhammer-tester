#!/usr/bin/env python3

from rowhammer_tester.scripts.utils import RemoteClient

if __name__ == "__main__":
    wb = RemoteClient()
    wb.open()

    # Dump all CSR registers of the SoC
    for name, reg in wb.regs.__dict__.items():
        print("0x{:08x}: 0x{:08x} {}".format(reg.addr, reg.read(), name))

    wb.close()
