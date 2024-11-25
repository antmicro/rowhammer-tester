#!/usr/bin/env python3

import argparse
import random
import time
from datetime import datetime

from rowhammer_tester.scripts.utils import (
    RemoteClient,
    get_litedram_settings,
    hw_memset,
    hw_memtest,
    litex_server,
    read_ident,
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--srv", action="store_true")
    parser.add_argument("--dbg", action="store_true")
    parser.add_argument("--test-modules", action="store_true")
    parser.add_argument("--test-memory", action="store_true")
    args = parser.parse_args()

    if args.srv:
        litex_server()

    wb = RemoteClient()
    wb.open()
    print("Board info:", read_ident(wb))

    mem_base = wb.mems.main_ram.base
    mem_range = wb.mems.main_ram.size  # bytes

    # we are limited to multiples of DMA data width
    settings = get_litedram_settings()
    dma_data_width = settings.phy.dfi_databits * settings.phy.nphases
    nbytes = dma_data_width // 8

    if args.test_modules:
        hw_memset(wb, 0x0, mem_range, [0xFFFFFFFF], args.dbg)

        # --------------------------- Introduce error ------------------------
        rng = random.Random(datetime.now())
        offsets = []
        for i, _n in enumerate(range(0, 5000)):
            print(f"Generated {i:d} offsets", end="\r")
            offset = rng.randrange(0x0, mem_range - 4)
            offset &= ~0b11  # must be 32-bit aligned
            if offset // nbytes not in offsets:
                offsets.append(offset // nbytes)
                if args.dbg:
                    print("dbg: offset: " + str(offset))
                wb.write(mem_base + offset, wb.read(mem_base + offset) ^ 0x000010000)
        print()

        # Corner case
        # offsets.append((mem_range - 4)//16)
        # wb.write(mem_base + mem_range - 4, wb.read(mem_base + mem_range - 4) ^ 0x00100000)
        # if args.dbg:
        #    print(
        #        "dbg: 0x{:08x}: 0x{:08x}".format(
        #            mem_base + mem_range - 4, wb.read(mem_base + mem_range - 4)
        #        )
        #    )

        print(f"dbg: offsets: {len(offsets):d}")
        # --------------------------------------------------------------------

        start_time = time.time()
        errors = hw_memtest(wb, 0x0, mem_range, [0xFFFFFFFF], args.dbg)
        end_time = time.time()

        if args.dbg:
            print(f"dbg: errors: {len(errors):d}, offsets: {len(offsets):d}")

        print(f"dbg: errors: {len(errors):d}, offsets: {len(offsets):d}")
        if len(errors) != len(offsets):
            missing = []
            for off in offsets:
                if off not in [e.offset for e in errors]:
                    missing.append(off)

            for off in missing:
                print(f"dbg: Missing offsets: 0x{off:08x}")

        assert len(errors) == len(offsets)

        for off, err in zip(sorted(offsets), errors):  # errors should be already sorted
            if args.dbg:
                print(f"dbg: 0x{off:08x} == 0x{err.offset:08x}")
            assert off == err.offset

        print(
            f"Execution time: {end_time - start_time:.3f} s"
            f" ({len(offsets) / (end_time - start_time):.3f} errors / s)"
        )
        print("Test OK!")

    elif args.test_memory:
        for p in [
            0xFFFFFFFF,
            0xAAAAAAAA,
            0x00000000,
            0x55555555,
            0x11111111,
            0x22222222,
            0x33333333,
            0x44444444,
            0x55555555,
            0x66666666,
            0x77777777,
            0x88888888,
            0x99999999,
            0xAAAAAAAA,
            0xBBBBBBBB,
            0xCCCCCCCC,
            0xDDDDDDDD,
            0xEEEEEEEE,
            0xFFFFFFFF,
            0x00000000,
        ]:
            print("Testing with 0x{p:08x} pattern")
            hw_memset(wb, 0x0, mem_range, [p], args.dbg)
            # if p == 0x77777777: wb.write(mem_base + mem_range - 32, 0x77787777) # Inject error
            errors = hw_memtest(wb, 0x0, mem_range, [p], args.dbg)
            if len(errors) > 0:
                print(f"!!! Failed pattern: {p:08x} !!!")
                for e in errors:
                    print(
                        f"Failed: 0x{mem_base + e.offset * nbytes:08x}"
                        f" == 0x{wb.read(mem_base + e.offset * nbytes):08x}"
                    )
                    print(f"  data     = 0x{e.data:x}")
                    print(f"  expected = 0x{e.expected:x}")
            else:
                print("Test pattern OK!")

    wb.close()
