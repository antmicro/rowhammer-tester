#!/usr/bin/env python3

import argparse
import json
import os
import random
import subprocess
import time
from pathlib import Path

from rowhammer_tester.scripts.playbook.lib import generate_payload_from_row_list
from rowhammer_tester.scripts.utils import (
    DRAMAddressConverter,
    RemoteClient,
    _progress,
    execute_payload,
    get_generated_defs,
    get_litedram_settings,
    litex_server,
    memcheck,
    memfill,
    read_ident,
)

################################################################################


class RowHammer:
    """
    Base class for running rowhammer attacks.
    It uses wishbone bridge connection to write patterns to the memory.

    Other classes can inherit from this class to change attack method.
    """

    def __init__(
        self,
        wb,
        *,
        settings,
        nrows,
        column,
        bank,
        rows_start=0,
        no_refresh=False,
        verbose=False,
        payload_executor=False,
        no_attack_time=None,
        data_inversion=False,
    ):
        for name, val in locals().items():
            setattr(self, name, val)
        self.converter = DRAMAddressConverter.load()
        self._addresses_per_row = {}
        self.bitflip_found = False
        self.log_directory = None
        self.err_summary = {}

    @property
    def rows(self):
        """
        Read only list of rows to attack.
        """

        return list(range(self.rows_start, self.rows_start + self.nrows))

    def addresses_per_row(self, row):
        """Returns a list of column addresses for a given row"""

        # Calculate the addresses lazily and cache them
        if row not in self._addresses_per_row:
            addresses = [
                self.converter.encode_bus(bank=self.bank, col=col, row=row)
                for col in range(2**self.settings.geom.colbits)
            ]
            self._addresses_per_row[row] = addresses
        return self._addresses_per_row[row]

    def attack(self, row_tuple, read_count, progress_header=""):
        """
        Performs the actual attack.
        Uses *rowhammer*tester/gateware/rowhammer.py* underneath to perform reads via the DMA.

        ``row_tuple`` is a pair of rows to be hammered (attacked row is between them)
        ``row_count`` is divided between hammered rows, so specifying ``read_count = 2e5`` means,
        that each row will be hammered ``1e5`` times
        """
        # FIXME: describe what progress_header does

        # Make sure that the Rowhammer module is in reset state
        self.wb.regs.rowhammer_enabled.write(0)
        self.wb.regs.rowhammer_count.read()  # clears the value

        # Configure the Rowhammer attacker
        assert (
            len(row_tuple) == 2
        ), "Use BIST modules/Payload Executor to hammer different number of rows than 2"
        addresses = [
            self.converter.encode_dma(bank=self.bank, col=self.column, row=r) for r in row_tuple
        ]
        self.wb.regs.rowhammer_address1.write(addresses[0])
        self.wb.regs.rowhammer_address2.write(addresses[1])
        self.wb.regs.rowhammer_enabled.write(1)

        # row_strw = len(str(2**self.settings.geom.rowbits - 1))

        def progress(count):
            s = f"  {progress_header}{' ' if progress_header else ''}"
            s += f"Rows = {row_tuple}, Count = {count / 1e6:5.2f}M / {read_count / 1e6:5.2f}M"
            print(s, end="  \r")

        # Wait for hammering to finish
        while True:
            count = self.wb.regs.rowhammer_count.read()
            progress(count)
            if count >= read_count:
                break

        self.wb.regs.rowhammer_enabled.write(0)
        progress(self.wb.regs.rowhammer_count.read())  # also clears the value
        print()

    def row_access_iterator(self, _burst=16):
        """
        Generates a sequence of tuples of three:

        0. row number
        1. number of 32-bit words in a row
        2. address of first word in a row

        Sequence is generated only for rows in ``self.rows`` list, so rows to attack.
        """

        for row in self.rows:
            addresses = self.addresses_per_row(row)
            n = (max(addresses) - min(addresses)) // 4
            base_addr = addresses[0]
            yield row, n, base_addr

    def check_errors(self, row_patterns, row_progress=16):
        """
        Checks errors in rows from ``self.rows`` list.
        This means, that if any row had bitflips, but wasn't a target,
        there would be no error checks for it.
        """

        row_errors = {}
        for row, n, base in self.row_access_iterator():
            errors = memcheck(self.wb, n, pattern=row_patterns[row], base=base, burst=255)
            row_errors[row] = [(addr, data, row_patterns[row]) for addr, data in errors]
            if row % row_progress == 0:
                print(".", end="", flush=True)
        return row_errors

    def errors_count(self, row_errors):
        """Counts number of rows with bitflips."""

        return sum(1 if len(e) > 0 else 0 for e in row_errors.values())

    @staticmethod
    def bitcount(x):
        """Counts set bits in ``x``."""

        return bin(x).count("1")  # seems faster than operations on integers

    @classmethod
    def bitflips(cls, val, ref):
        """Counts differing bits between ``val`` and ``ref``."""

        return cls.bitcount(val ^ ref)

    def errors_bitcount(self, row_errors):
        """Counts number of differing bits in rows from ``row_errors``."""

        return sum(
            sum(self.bitflips(value, expected) for addr, value, expected in e)
            for e in row_errors.values()
        )

    @staticmethod
    def bitflip_list(val, exp):
        # FIXME: add docstring

        expr = f"{val ^ exp:#0{len(bin(exp))}b}"
        return [i for i, c in enumerate(expr[2:]) if c == "1"]

    def display_errors(self, row_errors, _read_count, do_error_summary=False):
        # FIXME: add docstring

        err_dict = {}
        for row in row_errors:
            cols = {}
            if len(row_errors[row]) > 0:
                flips = sum(
                    self.bitflips(value, expected) for addr, value, expected in row_errors[row]
                )
                n = len(str(2**self.settings.geom.rowbits - 1))
                print(f"Bit-flips for row {row:{n}}: {flips}")
            if self.verbose or do_error_summary:
                for i, word, expected in row_errors[row]:
                    base_addr = min(self.addresses_per_row(row))
                    addr = base_addr + 4 * i
                    bank, _row, col = self.converter.decode_bus(addr)
                    if self.verbose:
                        print(f"Error: 0x{addr:08x}: 0x{word:08x} (row={_row}, col={col})")
                    bitflips = self.bitflip_list(word, expected)
                    cols[col] = bitflips
            if do_error_summary:
                err_dict[str(row)] = {"row": _row, "col": cols, "bitflips": flips}

        if do_error_summary:
            return err_dict

    def no_attack_sleep(self):
        sleep_time = self.no_attack_time / 1e9
        print(f"\nSleeping for {sleep_time} s as `--no-attack-time` flag was used ...")

        for slept in range(int(10 * sleep_time)):  # refresh every 0.1 s
            time.sleep(0.1)
            _progress((slept + 1) / 10, sleep_time, last=False, opt=f"Sleeping for {sleep_time} s")

        print()

    def prepare_memory(self, row_patterns, read_count, row_progress=16, verify_initial=False):
        print("\nPreparing ...")
        print("\nFilling memory with data ...")
        for row, n, base in self.row_access_iterator():
            memfill(self.wb, n, pattern=row_patterns[row], base=base, burst=255)
            if row % row_progress == 0:
                print(".", end="", flush=True)
            # makes sure to synchronize with the writes (without it for slower connection
            # we may have a timeout on the first read after writing)
            self.wb.regs.ctrl_scratch.read()

        if verify_initial:
            print("\nVerifying written memory ...")
            errors = self.check_errors(row_patterns, row_progress=row_progress)
            if self.errors_count(errors) == 0:
                print("OK")
            else:
                print()
                self.display_errors(errors, read_count)
                return

    def run(self, row_pairs, pattern_generator, read_count, row_progress=16, verify_initial=False):
        """
        Main part of the script.
        First fills the memory with specified patterns, then optionally checks its integrity.
        It disables refreshes if requested.
        Next it executes the attack, one row pair at a time.
        If refreshes were disabled, it reenables them.
        It checks for errors, and if any were found, displays them.
        """

        # TODO: need to invert data when writing/reading,
        # make sure Python integer inversion works correctly
        if self.data_inversion:
            raise NotImplementedError("Currently only HW rowhammer supports data inversion")

        row_patterns = pattern_generator(self.rows)
        self.prepare_memory(row_patterns, read_count, row_progress, verify_initial)

        if self.no_refresh:
            print("\nDisabling refresh ...")
            self.wb.regs.controller_settings_refresh.write(0)

        if self.no_attack_time is not None:
            self.no_attack_sleep()
        else:
            print("\nRunning Rowhammer attacks ...")
            for i, row_tuple in enumerate(row_pairs, start=1):
                n = len(str(len(row_pairs)))
                s = f"Iter {i:{n}} / {len(row_pairs):{n}}"
                if self.payload_executor:
                    self.payload_executor_attack(read_count=read_count, row_tuple=row_tuple)
                else:
                    self.attack(row_tuple, read_count=read_count, progress_header=s)

        if self.no_refresh:
            print("\nReenabling refresh ...")
            self.wb.regs.controller_settings_refresh.write(1)

        print("\nVerifying attacked memory ...")
        errors = self.check_errors(row_patterns, row_progress=row_progress)
        if self.errors_count(errors) == 0:
            print("OK")
            self.bitflip_found = False
            return {}
        else:
            print()
            errors_in_rows = self.display_errors(errors, read_count, bool(self.log_directory))
            self.bitflip_found = True
            return errors_in_rows

    def payload_executor_attack(self, read_count, row_tuple):
        """
        Performs the attack using payload executor
        """

        sys_clk_freq = float(get_generated_defs()["SYS_CLK_FREQ"])
        payload = generate_payload_from_row_list(
            read_count=read_count,
            row_sequence=row_tuple,
            timings=self.settings.timing,
            bankbits=self.settings.geom.bankbits,
            bank=self.bank,
            nranks=self.settings.phy.nranks,
            rank=0,
            payload_mem_size=self.wb.mems.payload.size,
            refresh=not self.no_refresh,
            sys_clk_freq=sys_clk_freq,
            verbose=self.verbose,
        )

        execute_payload(self.wb, payload)


################################################################################


def patterns_const(rows, value):
    """Same pattern for each row."""
    return {row: value for row in rows}


def patterns_alternating_per_row(rows):
    """Even rows all 1's, odd rows all 0's."""
    return {row: 0xFFFFFFFF if row % 2 == 0 else 0x00000000 for row in rows}


def patterns_random_per_row(rows, seed=42):
    """Random pattern per row."""
    rng = random.Random(seed)
    return {row: rng.randint(0, 2**32 - 1) for row in rows}


def main(row_hammer_cls):
    parser = argparse.ArgumentParser()
    parser.add_argument("--nrows", type=int, default=0, help="Number of rows to consider")
    parser.add_argument("--bank", type=int, default=0, help="Bank number")
    parser.add_argument("--column", type=int, default=512, help="Column to read from")
    parser.add_argument(
        "--start-row", type=int, default=0, help="Starting row (range = (start, start+nrows))"
    )
    read_count_group = parser.add_mutually_exclusive_group()
    read_count_group.add_argument(
        "--read_count", type=float, help="How many reads to perform for single address pair"
    )
    read_count_group.add_argument(
        "--read_count_range",
        type=float,
        nargs=3,
        help="Range of how many reads to perform for single address pair in a set of tests,"
        " given as [start] [stop] [step]",
    )
    parser.add_argument(
        "--no-refresh", action="store_true", help="Disable refresh commands during the attacks"
    )
    parser.add_argument(
        "--pattern",
        default="01_per_row",
        choices=["all_0", "all_1", "01_in_row", "01_per_row", "rand_per_row"],
        help="Pattern written to DRAM before running attacks",
    )
    row_selector_group = parser.add_mutually_exclusive_group()
    row_selector_group.add_argument(
        "--hammer-only",
        nargs="+",
        type=int,
        help="Run only the Rowhammer attack. "
        "If BIST or DMA mode is used exactly 2 rows must be provided."
        "If payload executor is used, any number of rows can be provided",
    )
    row_selector_group.add_argument(
        "--row-pairs",
        choices=["sequential", "const", "random"],
        help="How the rows for subsequent attacks are selected",
    )
    parser.add_argument(
        "--const-rows-pair",
        type=int,
        nargs=2,
        required=False,
        help="When using --row-pairs constant",
    )
    row_selector_group.add_argument(
        "--all-rows",
        action="store_true",
        help="Run whole test sequence on all rows. Optionally, set --row-jump and --start-row",
    )
    row_selector_group.add_argument(
        "--no-attack-time", type=float, help="Don't attack. Instead sleep for provided nanoseconds"
    )
    parser.add_argument(
        "--row-pair-distance",
        type=int,
        default=2,
        required=False,
        help="Distance between hammered rows in each generated pair",
    )
    parser.add_argument(
        "--row-jump",
        type=int,
        default=1,
        required=False,
        help="Jump between rows when using --all-rows",
    )
    parser.add_argument(
        "--payload-executor", action="store_true", help="Do the attack using Payload Executor"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Be more verbose")
    parser.add_argument("--srv", action="store_true", help="Start LiteX server")
    parser.add_argument(
        "--experiment-no", type=int, default=0, help="Run preconfigured experiment #no"
    )
    parser.add_argument(
        "--data-inversion", nargs=2, help="Invert pattern data for victim rows (divisor, mask)"
    )
    parser.add_argument(
        "--exit-on-bit-flip",
        action="store_true",
        help="Exit tests as soon as bitflip is found",
    )
    parser.add_argument(
        "--log-dir",
        help="Directory for output files."
        " If not given, the output files (e.g. error summary) won't be written",
    )
    args = parser.parse_args()

    if args.experiment_no == 1:
        args.nrows = 512
        args.read_count = 15e6
        args.pattern = "01_in_row"
        args.row_pairs = "const"
        args.const_rows_pair = 88, 99
        args.no_refresh = True

    if args.hammer_only:
        row_pairs = [tuple(args.hammer_only)]
    elif args.all_rows:
        if args.row_pair_distance < 0:
            parser.error("Row distance can't be negative")

        row_pairs = [
            (i, i + args.row_pair_distance)
            for i in range(
                args.start_row,
                args.nrows - args.row_pair_distance,
                args.row_jump,
            )
        ]
    elif args.row_pairs == "sequential":
        if args.nrows <= 0:
            parser.error("Using --row-pairs=sequential requires specifying --nrows larger than 0")
        print(
            f"First row of hammered pair will be {args.start_row},",
            f"second row will be from range [{args.start_row}, {args.start_row + args.nrows})",
        )

        row_pairs = [(args.start_row, args.start_row + i) for i in range(args.nrows)]
    elif args.row_pairs == "const":
        if not args.const_rows_pair:
            parser.error("Using --row-pairs=const requires specifying --const-rows-pair")

        row_pairs = [tuple(args.const_rows_pair)]
    elif args.row_pairs == "random":
        if args.nrows <= 0:
            parser.error("Using --row-pairs=random requires specifying --nrows larger than 0")
        elif args.row_pairs == "random" and args.nrows == 1:
            print(
                "\nWARNING: row numbers are generated from range [start-row, start-row + nrows)",
                f"\nRight now the only row number that would be generated is {args.start_row}!",
            )
        print(
            f"\nGenerating row numbers from range [{args.start_row}, {args.start_row + args.nrows})"
        )

        rng = random.Random(42)

        def rand_row():
            return rng.randint(args.start_row, args.start_row + args.nrows)

        row_pairs = [(rand_row(), rand_row()) for i in range(args.nrows)]
    elif args.no_attack_time is not None:
        if args.no_attack_time < 0:
            parser.error("No attack time can't be negative")
    else:
        parser.error("No operation specified")

    if args.srv:
        litex_server()

    wb = RemoteClient()
    wb.open()
    print("Board info:", read_ident(wb))

    if wb.regs.ddrctrl_init_done.read() != 1:
        scripts_dir = os.path.dirname(os.path.realpath(__file__))
        mem_script = os.path.join(scripts_dir, "mem.py")
        subprocess.check_call(["python3", mem_script])

    row_hammer = row_hammer_cls(
        wb,
        nrows=args.nrows,
        settings=get_litedram_settings(),
        column=args.column,
        bank=args.bank,
        rows_start=args.start_row,
        verbose=args.verbose,
        no_refresh=args.no_refresh,
        payload_executor=args.payload_executor,
        data_inversion=args.data_inversion,
        no_attack_time=args.no_attack_time,
    )

    if args.log_dir:
        log_dir = Path(args.log_dir)
        if not log_dir.is_dir():
            log_dir.mkdir(parents=True)
        row_hammer.log_directory = args.log_dir

    pattern = {
        "all_0": lambda rows: patterns_const(rows, 0x00000000),
        "all_1": lambda rows: patterns_const(rows, 0xFFFFFFFF),
        "01_in_row": lambda rows: patterns_const(rows, 0xAAAAAAAA),
        "01_per_row": patterns_alternating_per_row,
        "rand_per_row": patterns_random_per_row,
    }[args.pattern]

    if args.read_count_range:
        count_start, count_stop, count_step = map(int, args.read_count_range)
    else:
        count_start = int(args.read_count or 10e6)
        count_stop = count_start
        count_step = 1

    for count in range(count_start, count_stop + 1, count_step):
        row_hammer.err_summary[str(count)] = {"read_count": count}
        if args.hammer_only:
            pair = row_pairs[0]
            if args.payload_executor:
                row_hammer.payload_executor_attack(read_count=count, row_tuple=pair)
            else:
                row_hammer.attack(row_tuple=pair, read_count=count)
        elif args.all_rows:
            for pair in row_pairs:
                err_in_rows = row_hammer.run(
                    row_pairs=[pair], read_count=count, pattern_generator=pattern
                )

                row_hammer.err_summary[str(count)][f"pair_{pair[0]}_{pair[1]}"] = {
                    "hammer_row_1": pair[0],
                    "hammer_row_2": pair[1],
                    "errors_in_rows": err_in_rows,
                }
        elif args.no_attack_time is not None:
            err_in_rows = row_hammer.run(  # dummy row pair and read count
                row_pairs=[(0, 0)], read_count=0, pattern_generator=pattern
            )

            row_hammer.err_summary = {
                "no_attack_time": {
                    str(args.no_attack_time): {
                        "errors_in_rows": err_in_rows,
                    },
                },
            }
        else:
            err_in_rows = row_hammer.run(
                row_pairs=row_pairs, read_count=count, pattern_generator=pattern
            )
            if args.row_pairs == "const":
                pair = row_pairs[0]
                row_hammer.err_summary[str(count)][f"pair_{pair[0]}_{pair[1]}"] = {
                    "hammer_row_1": pair[0],
                    "hammer_row_2": pair[1],
                    "errors_in_rows": err_in_rows,
                }
            else:
                row_hammer.err_summary[str(count)]["sequential_attacks"] = {
                    "row_pairs": row_pairs,
                    "errors_in_rows": err_in_rows,
                }

        if row_hammer.bitflip_found and args.exit_on_bit_flip:
            break

    if row_hammer.log_directory:
        with open(
            f"{row_hammer.log_directory}/error_summary_{time.time()}.json", "w"
        ) as write_file:
            json.dump(row_hammer.err_summary, write_file, indent=4)

    wb.close()


if __name__ == "__main__":
    main(row_hammer_cls=RowHammer)
