#!/usr/bin/env python3

from rowhammer_tester.scripts.utils import RemoteClient, read_ident

if __name__ == "__main__":
    wb = RemoteClient()
    wb.open()

    print(read_ident(wb))

    wb.close()
