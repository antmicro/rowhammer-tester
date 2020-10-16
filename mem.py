#!/usr/bin/env python3

import time
import random
from sdram_init import *

from read_level import read_level, default_arty_settings

# ###########################################################################

def sdram_software_control(wb):
    wb.regs.sdram_dfii_control.write(dfii_control_cke|dfii_control_odt|dfii_control_reset_n)

def sdram_hardware_control(wb):
    wb.regs.sdram_dfii_control.write(dfii_control_sel)

def sdram_init(wb):
    sdram_software_control(wb)

    # we cannot check for the string "DFII_CONTROL" as done when generating C code,
    # so this is hardcoded for now
    # update: Hacky but works
    control_cmds = []
    with open('sdram_init.py', 'r') as f:
        n = 0
        while True:
            line = f.readline()
            if not line: break
            line = line.strip().replace(' ', '')
            if len(line) and line[0] == '(':
                if line.find('_control_') > 0:
                    control_cmds.append(n)
                n = n + 1

    print('control_cmds: ' + str(control_cmds))
    for i, (comment, a, ba, cmd, delay) in enumerate(init_sequence):
        wb.regs.sdram_dfii_pi0_address.write(a)
        wb.regs.sdram_dfii_pi0_baddress.write(ba)
        if i in control_cmds:
            print(comment + ' (ctrl)')
            wb.regs.sdram_dfii_control.write(cmd)
        else:
            print(comment + ' (cmd)')
            wb.regs.sdram_dfii_pi0_command.write(cmd)
            wb.regs.sdram_dfii_pi0_command_issue.write(1)
        time.sleep(0.001)

    sdram_hardware_control(wb)

# ###########################################################################

def memwrite(wb, data, base=0x40000000, burst=16):
    for i in range(0, len(data), burst):
        wb.write(base + 4*i, data[i:i+burst])

def memread(wb, n, base=0x40000000, burst=16):
    data = []
    for i in range(0, n, burst):
        data += wb.read(base + 4*i, burst)
    return data

def memfill(wb, n, pattern=0xaaaaaaaa, **kwargs):
    memwrite(wb, [pattern] * n, **kwargs)

def memcheck(wb, n, pattern=0xaaaaaaaa, **kwargs):
    data = memread(wb, n, **kwargs)
    errors = [(i, w) for i, w in enumerate(data) if w != pattern]
    return errors

def memspeed(wb, n, **kwargs):
    def measure(fun, name):
        start = time.time()
        fun(wb, n, **kwargs)
        elapsed = time.time() - start
        print('{:5} speed: {:6.2f} KB/s ({:.1f} sec)'.format(name, (n//4)/elapsed / 1e3, elapsed))

    def memcheck_assert(*args, **kwargs):
        errors = memcheck(*args, **kwargs)
        assert len(errors) == 0

    measure(memfill, 'Write')
    measure(memcheck_assert, 'Read')

# ###########################################################################

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
