#!/usr/bin/env python3

from rowhammer_tester.scripts.utils import RemoteClient, read_ident

if __name__ == "__main__":
    wb = RemoteClient()
    wb.open()
    print("Board info:", read_ident(wb))

    # Dump all CSR registers of the SoC
    for name, reg in wb.regs.__dict__.items():
        print(f"0x{reg.addr:08x}: 0x{reg.read():08x} {name}")

    wb.close()
