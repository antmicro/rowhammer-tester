#!/usr/bin/env python3

import argparse
import itertools
import random
import sys
import time

from rowhammer_tester.scripts.utils import (
    RemoteClient,
    compare,
    litex_server,
    memread,
    memspeed,
    memwrite,
    read_ident,
    sdram_hardware_control,
)


# Perform a memory test using a random data pattern and linear addressing
def memtest(wb, length, *, generator, base=None, verbose=None, burst=255):
    sdram_hardware_control(wb)
    if base is None:
        base = wb.mems.main_ram.base

    refdata = list(itertools.islice(generator, length))
    memwrite(wb, refdata, base=base, burst=burst)

    data = memread(wb, length, base=base, burst=burst)
    assert len(refdata) == len(data)

    errors = 0
    for val, ref in zip(data, refdata):
        if val != ref:
            errors += 1
            if verbose is not None:
                compare(val, ref, fmt=verbose, nbytes=4)

    return errors


# ###########################################################################

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--srv", action="store_true", help="Start litex server")
    parser.add_argument("--size", default="0x2000", help="Memtest size")
    parser.add_argument("--memspeed", action="store_true", help="Run memroy speed test")
    parser.add_argument(
        "--no-cpu-uart",
        action="store_true",
        help="Do not print the stdout of CPU during DRAM initialization",
    )
    args = parser.parse_args()

    if args.srv:
        litex_server()

    wb = RemoteClient()
    wb.open()
    print("Board info:", read_ident(wb))

    print(" === Waiting for CPU to initialize DRAM ===")
    if hasattr(wb.regs, "uart_xover_rxempty"):
        while wb.regs.ddrctrl_init_done.read() != 1:
            if wb.regs.uart_xover_rxempty.read() == 0:
                r = wb.regs.uart_xover_rxtx.read()
                if not args.no_cpu_uart:
                    sys.stdout.write(chr(r))
                    sys.stdout.flush()
    else:
        while wb.regs.ddrctrl_init_done.read() != 1:
            time.sleep(0.001)

    if wb.regs.ddrctrl_init_error.read() == 1:
        print(" === Initialization failed ===")
        sys.exit(1)
    else:
        print(" === Initialization succeeded. ===")
        print("Proceeding ...")

    memtest_size = int(args.size, 0)
    ret = 0

    def run_memtest(name, generator, **kwargs):
        global ret
        print(f"\nMemtest ({name})")
        errors = memtest(wb, length=memtest_size, generator=generator, **kwargs)
        print("OK" if errors == 0 else f"FAIL: errors = {errors}")
        if errors != 0:
            ret = 1

    def rand_generator(seed):
        rng = random.Random(seed)
        while True:
            yield rng.randint(0, 2**32 - 1)

    run_memtest("basic", itertools.cycle([0xAAAAAAAA, 0x55555555]))
    run_memtest("random", rand_generator(42))

    if args.memspeed:
        for n in [0x1000 // 4, 0x10000 // 4, 0x100000 // 4]:
            print(f"Size = 0x{n * 4:08x}")
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

    sys.exit(ret)
