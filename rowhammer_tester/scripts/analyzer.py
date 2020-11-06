#!/usr/bin/env python3

import sys
import argparse

from litescope.software.litescope_cli import *

from rowhammer_tester.scripts.utils import RemoteClient, get_generated_file

# Wrapper around litescope_cli
if __name__ == "__main__":
    args = parse_args()

    signals = get_signals(get_generated_file("analyzer.csv"))
    if args.list:
        for signal in signals:
            print(signal)
        sys.exit(0)

    wb = RemoteClient()
    wb.open()

    try:
        analyzer = LiteScopeAnalyzerDriver(wb.regs, "analyzer", debug=True)
        analyzer.configure_group(0)
        analyzer.configure_subsampler(int(args.subsampling, 0))
        if not add_triggers(args, analyzer, signals):
            print("WARNING: no trigger added!")

        analyzer.run(
            offset = int(args.offset, 0),
            length = None if args.length is None else int(args.length, 0)
        )

        analyzer.wait_done()
        analyzer.upload()
        analyzer.save("dump.vcd")
    finally:
        wb.close()
