#!/usr/bin/env python3

import time

from rowhammer_tester.scripts.utils import RemoteClient

if __name__ == "__main__":
    wb = RemoteClient()
    wb.open()

    # Timestamp is in minutes
    # we need to convert it to seconds
    # Read it as UTC time
    timetup = time.gmtime(wb.regs.buildinfo_stamp.read() * 60)
    iso = time.strftime('UTC timestamp: %Y-%m-%d %H:%M', timetup)
    print(iso)

    wb.close()
