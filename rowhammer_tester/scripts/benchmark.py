#!/usr/bin/env python3

import argparse
import cProfile
import os
import time

from rowhammer_tester.scripts.utils import (
    RemoteClient,
    hw_memset,
    hw_memtest,
    memread,
    memwrite,
    read_ident,
)


def human_size(num):
    for prefix in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return (num, prefix)
        num /= 1024.0
    return (num, "Yi")


def measure(runner, nbytes):
    print("Running measurement ...")
    start = time.time()
    runner()
    elapsed = time.time() - start

    bytes_per_sec = nbytes / elapsed
    print("Elapsed = {:.3f} sec".format(elapsed))
    print("Size    = {:.3f} {}B".format(*human_size(nbytes)))
    print("Speed   = {:.3f} {}Bps".format(*human_size(bytes_per_sec)))


def run_etherbone(wb, is_write, n, *, burst, profile, profile_dir="profiling"):
    datas = list(range(n))

    ctx = locals()
    ctx["wb"] = wb
    ctx["memread"] = memread
    ctx["memwrite"] = memwrite

    fname = "{}/{}_0x{:x}_b{}.profile".format(profile_dir, "wr" if is_write else "rd", n, burst)
    os.makedirs(os.path.dirname(fname), exist_ok=True)
    command = {
        False: "memread(wb, n, burst=burst)",
        True: "memwrite(wb, datas, burst=burst)",
    }[is_write]

    def runner():
        if profile:
            cProfile.runctx(command, {}, ctx, fname)
        else:
            if is_write:
                memwrite(wb, datas, burst=burst)
            else:
                _ = memread(wb, n, burst=burst)

    measure(runner, 4 * n)

    if profile:
        print("Profiling results saved to: {}".format(fname))


def run_bist(wb, is_write, pattern):
    n = wb.mems.main_ram.size
    pattern = [pattern]

    def runner():
        if is_write:
            hw_memset(wb, 0, n, pattern)
        else:
            hw_memtest(wb, 0, n, pattern)

    if not is_write:
        print("Filling memory before reading measurements ...")
        hw_memset(wb, 0, n, pattern)
    measure(runner, n)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark EtherBone/BIST DRAM access performance")
    subparsers = parser.add_subparsers(help="Benchmark type subcommands", dest="subcommand")
    etherbone = subparsers.add_parser("etherbone", help="Measure EtherBone bridge performance")
    etherbone.add_argument("rw", choices=["read", "write"], help="Transfer type")
    etherbone.add_argument("n", help="Number of 32-bit words transferred")
    etherbone.add_argument("--burst", required=True, help="Burst size")
    etherbone.add_argument("--profile", action="store_true", help="Profile the code with cProfile")
    bist = subparsers.add_parser("bist", help="Measure BIST transfer performance")
    bist.add_argument("rw", choices=["read", "write"], help="Transfer type")
    bist.add_argument("--pattern", default="0x55555555", help="Data pattern used in BIST transfers")
    args = parser.parse_args()

    wb = RemoteClient()
    wb.open()
    print("Board info:", read_ident(wb))

    if args.subcommand is None:
        parser.error("Select subcommand")

    if args.rw == "write":
        is_write = True
    elif args.rw == "read":
        is_write = False
    else:
        raise ValueError(args.rw)

    if args.subcommand == "etherbone":
        run_etherbone(wb, is_write, int(args.n, 0), burst=int(args.burst, 0), profile=args.profile)
    elif args.subcommand == "bist":
        run_bist(wb, is_write, pattern=int(args.pattern, 0))
    else:
        raise ValueError(args.subcommand)

    wb.close()
