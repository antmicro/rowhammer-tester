#!/usr/bin/env python3

import time
import random
import argparse

from datetime import datetime

from rowhammer_tester.scripts.utils import RemoteClient, litex_server, hw_memset, hw_memtest, get_litedram_settings

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--srv', action='store_true')
    parser.add_argument('--dbg', action='store_true')
    parser.add_argument('--test-modules', action='store_true')
    parser.add_argument('--test-memory', action='store_true')
    args = parser.parse_args()

    if args.srv:
        litex_server()

    wb = RemoteClient()
    wb.open()

    mem_base = wb.mems.main_ram.base
    mem_range = wb.mems.main_ram.size  # bytes

    # we are limited to multiples of DMA data width
    settings = get_litedram_settings()
    dma_data_width = settings.phy.dfi_databits * settings.phy.nphases
    nbytes = dma_data_width // 8

    if args.test_modules:
        hw_memset(wb, 0x0, mem_range, [0xffffffff], args.dbg)

        # --------------------------- Introduce error ------------------------
        rng = random.Random(datetime.now())
        offsets = []
        for i, n in enumerate(range(0, 5000)):
            print('Generated {:d} offsets'.format(i), end='\r')
            offset = rng.randrange(0x0, mem_range - 4)
            offset &= ~0b11  # must be 32-bit aligned
            if offset // nbytes not in offsets:
                offsets.append(offset // nbytes)
                if args.dbg:
                    print('dbg: offset: ' + str(offset))
                wb.write(mem_base + offset, wb.read(mem_base + offset) ^ 0x000010000)
        print()

        # Corner case
        #offsets.append((mem_range - 4)//16)
        #wb.write(mem_base + mem_range - 4, wb.read(mem_base + mem_range - 4) ^ 0x00100000)
        #if args.dbg:
        #    print('dbg: 0x{:08x}: 0x{:08x}'.format(mem_base + mem_range - 4, wb.read(mem_base + mem_range - 4)))

        print('dbg: offsets: {:d}'.format(len(offsets)))
        # --------------------------------------------------------------------

        start_time = time.time()
        errors = hw_memtest(wb, 0x0, mem_range, [0xffffffff], args.dbg)
        end_time = time.time()

        if args.dbg:
            print('dbg: errors: {:d}, offsets: {:d}'.format(len(errors), len(offsets)))

        print('dbg: errors: {:d}, offsets: {:d}'.format(len(errors), len(offsets)))
        if len(errors) != len(offsets):
            missing = []
            for off in offsets:
                if off not in [e.offset for e in errors]:
                    missing.append(off)

            for off in missing:
                print('dbg: Missing offsets: 0x{:08x}'.format(off))

        assert len(errors) == len(offsets)

        for off, err in zip(sorted(offsets), errors):  # errors should be already sorted
            if args.dbg:
                print('dbg: 0x{:08x} == 0x{:08x}'.format(off, err.offset))
            assert off == err.offset

        print(
            'Execution time: {:.3f} s ({:.3f} errors / s)'.format(
                end_time - start_time,
                len(offsets) / (end_time - start_time)))
        print("Test OK!")

    elif args.test_memory:
        for p in [0xffffffff, 0xaaaaaaaa, 0x00000000, 0x55555555, \
                  0x11111111, 0x22222222, 0x33333333, 0x44444444, \
                  0x55555555, 0x66666666, 0x77777777, 0x88888888, \
                  0x99999999, 0xaaaaaaaa, 0xbbbbbbbb, 0xcccccccc, \
                  0xdddddddd, 0xeeeeeeee, 0xffffffff, 0x00000000]:
            print('Testing with 0x{:08x} pattern'.format(p))
            hw_memset(wb, 0x0, mem_range, [p], args.dbg)
            #if p == 0x77777777: wb.write(mem_base + mem_range - 32, 0x77787777) # Inject error
            errors = hw_memtest(wb, 0x0, mem_range, [p], args.dbg)
            if len(errors) > 0:
                print('!!! Failed pattern: {:08x} !!!'.format(p))
                for e in errors:
                    print(
                        'Failed: 0x{:08x} == 0x{:08x}'.format(
                            mem_base + e.offset * nbytes, wb.read(mem_base + e.offset * nbytes)))
                    print('  data     = 0x{:x}'.foramt(e.data))
                    print('  expected = 0x{:x}'.foramt(e.expected))
            else:
                print("Test pattern OK!")

    wb.close()
