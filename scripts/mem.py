#!/usr/bin/env python3

import random

from utils import *
from read_level import read_level, default_arty_settings

def _compare(val, ref, fmt, nbytes=4):
    assert fmt in ["bin", "hex"]
    if fmt == "hex":
        print("0x{:0{n}x} {cmp} 0x{:0{n}x}".format(
            val, ref, n=nbytes*2, cmp="==" if val == ref else "!="))
    if fmt == "bin":
        print("{:0{n}b} xor {:0{n}b} = {:0{n}b}".format(
            val, ref, val ^ ref, n=nbytes*8))

# Perform a memory test using a random data pattern and linear addressing
def memtest_random(wb, base=None, length=0x80, inc=8, seed=42, verbose=None):
    sdram_hardware_control(wb)
    if base is None:
        base = wb.mems.main_ram.base

    rng = random.Random(seed)
    refdata = []

    for i in range(length//inc):
        data = [rng.randint(0, 2**32 - 1) for _ in range(inc)]
        wb.write(base + 4*inc*i, data)
        refdata += data

    data = []
    for i in range(length//inc):
        data += wb.read(base + 4*inc*i, inc)
    assert len(refdata) == len(data)

    errors = 0
    for val, ref in zip(data, refdata):
        if val != ref:
            errors += 1
            if verbose is not None:
                print()
                _compare(val, ref, fmt=verbose, nbytes=4)

    return errors

def memtest_basic(wb, base=None, seed=42):
    sdram_hardware_control(wb)
    if base is None:
        base = wb.mems.main_ram.base

    rng = random.Random(seed)
    sdram_pattern = rng.randrange(0x0, 0x100000000)

    wb.write(base, sdram_pattern)
    value = wb.read(base)

    if value != sdram_pattern:
        print('Mem error at 0x{:08x} : 0x{:08x} != 0x{:08x}'
            .format(base, value, sdram_pattern))
        print('x: ' + str(["0x{:08x}".format(w) for w in wb.read(base, 4)]))
    else:
        for i in range(0, 1024):
            wb.write(base + i, 0x55555555)
        for i in range(1024, 2048):
            wb.write(base + i, 0xaaaaaaaa)
        for i in range(0, 1024):
            val = wb.read(base + i)
            assert(val == 0x55555555)
        for i in range(1024, 2048):
            val = wb.read(base + i)
            assert(val == 0xaaaaaaaa)

        print('1. ' + str(["0x{:08x}".format(w) for w in wb.read(base + 1024 - 2 * 4, 4)]))

        for i in range(0, 1024):
            wb.write(base + i, 0xaaaaaaaa)
        for i in range(1024, 2048):
            wb.write(base + i, 0x55555555)
        for i in range(0, 1024):
            val = wb.read(base + i)
            assert(val == 0xaaaaaaaa)
        for i in range(1024, 2048):
            val = wb.read(base + i)
            assert(val == 0x55555555)

        print('2. ' + str(["0x{:08x}".format(w) for w in wb.read(base + 1024 - 2 * 4, 4)]))
        print("Mem ok!")

# ###########################################################################

if __name__ == "__main__":
    import sys
    from litex import RemoteClient

    wb = RemoteClient()
    wb.open()

    if '--no-init' not in sys.argv[1:]:
        print('SDRAM initialization:')
        sdram_init(wb)

        print('\nRead leveling:')
        read_level(wb, default_arty_settings())

    print('\nMemtest (basic):')
    memtest_basic(wb)

    print('\nMemtest (random):')
    errors = memtest_random(wb, length=0x2000)
    print('OK' if errors == 0 else 'FAIL: errors = {}'.format(errors))

    if '--memspeed' in sys.argv[1:]:
        for n in [0x1000//4, 0x10000//4, 0x100000//4]:
            print('Size = 0x{:08x}'.format(n*4))
            memspeed(wb, n)
        # Example results:
        #  Size = 0x00001000
        #   Write speed:  48.14 KB/s (0.0 sec)
        #   Read  speed:   2.08 KB/s (0.1 sec)
        #  Size = 0x00010000
        #   Write speed:  82.45 KB/s (0.0 sec)
        #   Read  speed:   3.09 KB/s (1.3 sec)
        #  Size = 0x00100000
        #   Write speed: 123.88 KB/s (0.5 sec)
        #   Read  speed:   3.04 KB/s (21.6 sec)
        #  Size = 0x01000000
        #   Write speed:  47.24 KB/s (22.2 sec)
        # So reading 1MB takes ~21.6 seconds.
        # We have 256MB DRAM on board, so it should take ~1.5 hour to read.
        # Writing is an order of magnitude faster.

    wb.close()
