#!/usr/bin/env python3

from rowhammer_tester.scripts.utils import RemoteClient, memread

if __name__ == "__main__":
    wb = RemoteClient()
    wb.open()

    # Maximal identification info size is 256
    buildinfo = memread(wb, 256, wb.bases.identifier_mem)

    # Info is stored as a \0 terminated string
    # truncate it
    string_term_idx = buildinfo.index(0)
    buildinfo = buildinfo[:string_term_idx]

    # Map int values to ASCII characters
    print(''.join(map(chr, buildinfo)))

    wb.close()
