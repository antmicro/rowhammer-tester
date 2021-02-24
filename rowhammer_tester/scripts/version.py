#!/usr/bin/env python3

from rowhammer_tester.scripts.utils import RemoteClient

if __name__ == "__main__":
    wb = RemoteClient()
    wb.open()

    # Read CSR register containing git revision
    print("{:08x}".format(wb.regs.buildinfo_hash.read()))

    wb.close()
