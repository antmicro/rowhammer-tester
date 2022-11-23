#!/usr/bin/env python3

from rowhammer_tester.scripts.utils import RemoteClient, read_ident

if __name__ == "__main__":
    wb = RemoteClient()
    wb.open()
    print("Board info:", read_ident(wb))

    # Dump all CSR registers of the SoC
    for name, reg in wb.regs.__dict__.items():
        print("0x{:08x}: 0x{:08x} {}".format(reg.addr, reg.read(), name))

    wb.close()
