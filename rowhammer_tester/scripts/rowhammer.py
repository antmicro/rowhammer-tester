#!/usr/bin/env python3

import time
import random
from math import ceil

from rowhammer_tester.gateware.payload_executor import Encoder, OpCode, Decoder
from .utils import memfill, memcheck, memwrite, DRAMAddressConverter

################################################################################

class RowHammer:
    def __init__(self, wb, *, nrows, bankbits, rowbits, colbits, column, bank,
                 rows_start=0, no_refresh=False, verbose=False, plot=False,
                 payload_executor=False):
        for name, val in locals().items():
            setattr(self, name, val)
        self.converter = DRAMAddressConverter(colbits=colbits, rowbits=rowbits)
        self.addresses_per_row = self._addresses_per_row()

    @property
    def rows(self):
        return list(range(self.rows_start, self.nrows))

    def _addresses_per_row(self):
        addresses = {}
        for row in self.rows:
            addresses[row] = [self.converter.encode_bus(bank=self.bank, col=col, row=row)
                              for col in range(2**self.colbits)]
        return addresses

    def attack(self, row1, row2, read_count, progress_header=''):
        # Make sure that the row hammer module is in reset state
        self.wb.regs.rowhammer_enabled.write(0)
        self.wb.regs.rowhammer_count.read()  # clears the value

        # Configure the row hammer attacker
        addresses = [self.converter.encode_dma(bank=self.bank, col=self.column, row=r)
                     for r in [row1, row2]]
        self.wb.regs.rowhammer_address1.write(addresses[0])
        self.wb.regs.rowhammer_address2.write(addresses[1])
        self.wb.regs.rowhammer_enabled.write(1)

        row_strw = len(str(2**self.rowbits - 1))

        def progress(count):
            s = '  {}'.format(progress_header + ' ' if progress_header else '')
            s += 'Rows = ({:{n}d},{:{n}d}), Count = {:5.2f}M / {:5.2f}M'.format(
                row1, row2, count/1e6, read_count/1e6, n=row_strw)
            print(s, end='  \r')

        while True:
            count = self.wb.regs.rowhammer_count.read()
            progress(count)
            if count >= read_count:
                break

        self.wb.regs.rowhammer_enabled.write(0)
        progress(self.wb.regs.rowhammer_count.read())  # also clears the value
        print()

    def row_access_iterator(self, burst=16):
        for row, addresses in self.addresses_per_row.items():
            n = (max(addresses) - min(addresses)) // 4
            base_addr = addresses[0]
            yield row, n, base_addr

    def check_errors(self, row_patterns, row_progress=16):
        row_errors = {}
        for row, n, base in self.row_access_iterator():
            row_errors[row] = memcheck(self.wb, n, pattern=row_patterns[row], base=base, burst=255)
            if row % row_progress == 0:
                print('.', end='', flush=True)
        return row_errors

    def errors_count(self, row_errors):
        return sum(1 if len(e) > 0 else 0 for e in row_errors.values())

    def display_errors(self, row_errors):
        for row in row_errors:
            if len(row_errors[row]) > 0:
                print("row_errors for row={:{n}}: {}".format(
                    row, len(row_errors[row]), n=len(str(2**self.rowbits-1))))
            if self.verbose:
                for i, word in row_errors[row]:
                    base_addr = min(self.addresses_per_row[row])
                    addr = base_addr + 4*i
                    bank, _row, col = self.converter.decode_bus(addr)
                    print("Error: 0x{:08x}: 0x{:08x} (row={}, col={})".format(
                        addr, word, _row, col))

        if self.plot:
            from matplotlib import pyplot as plt
            row_err_counts = [len(row_errors.get(row, [])) for row in self.rows]
            plt.bar(self.rows, row_err_counts, width=1)
            plt.grid(True)
            plt.xlabel('Row')
            plt.ylabel('Errors')
            plt.show()

    def run(self, row_pairs, pattern_generator, read_count, row_progress=16, verify_initial=False):
        print('\nPreparing ...')
        row_patterns = pattern_generator(self.rows)

        print('\nFilling memory with data ...')
        for row, n, base in self.row_access_iterator():
            memfill(self.wb, n, pattern=row_patterns[row], base=base, burst=255)
            if row % row_progress == 0:
                print('.', end='', flush=True)

        if verify_initial:
            print('\nVerifying written memory ...')
            errors = self.check_errors(row_patterns, row_progress=row_progress)
            if self.errors_count(errors) == 0:
                print('OK')
            else:
                print()
                self.display_errors(errors)
                return

        if self.no_refresh:
            print('\nDisabling refresh ...')
            self.wb.regs.controller_settings_refresh.write(0)

        print('\nRunning row hammer attacks ...')
        for i, (row1, row2) in enumerate(row_pairs):
            s = 'Iter {:{n}} / {:{n}}'.format(i, len(row_pairs), n=len(str(len(row_pairs))))
            if self.payload_executor:
                self.payload_executor_attack(read_count=read_count, row=row1)
            else:
                self.attack(row1, row2, read_count=read_count, progress_header=s)

        if self.no_refresh:
            print('\nReenabling refresh ...')
            self.wb.regs.controller_settings_refresh.write(1)

        print('\nVerifying attacked memory ...')
        errors = self.check_errors(row_patterns, row_progress=row_progress)
        if self.errors_count(errors) == 0:
            print('OK')
        else:
            print()
            self.display_errors(errors)
            return

    def payload_executor_attack(self, read_count, row):
        # FIXME: read from dedicated status registers
        tras = 5
        trp = 3
        encoder = Encoder(bankbits=self.bankbits)
        payload = [
            encoder(OpCode.NOOP, timeslice=30),
        ]

        # fill payload so that we have >= desired read_count
        count_max = 2**Decoder.LOOP_COUNT - 1
        n_loops = ceil(read_count / (count_max + 1))
        for _ in range(n_loops):
            payload.extend([
                encoder(OpCode.ACT,  timeslice=tras, address=encoder.address(bank=self.bank, row=row)),
                encoder(OpCode.PRE,  timeslice=trp, address=encoder.address(col=1 << 10)),  # all
                encoder(OpCode.LOOP, count=count_max, jump=2),
            ])
        payload.append(encoder(OpCode.NOOP, timeslice=30))

        toggle_count = (count_max + 1) * n_loops
        print('  Payload size = {:5.2f}KB / {:5.2f}KB'.format(4*len(payload)/2**10, self.wb.mems.payload.size/2**10))
        print('  Payload row toggle count = {:5.2f}M'.format(toggle_count/1e6))
        assert len(payload) < self.wb.mems.payload.size//4
        payload += [0] * (self.wb.mems.payload.size//4 - len(payload))  # fill with NOOPs

        print('\nTransferring the payload ...')
        memwrite(self.wb, payload, base=self.wb.mems.payload.base)

        def ready():
            status = self.wb.regs.payload_executor_status.read()
            return (status & 1) != 0

        print('\nExecuting ...')
        assert ready()
        self.wb.regs.payload_executor_start.write(1)
        while not ready():
            time.sleep(0.001)

################################################################################

def patterns_const(rows, value):
    return {row: value for row in rows}

def patterns_alternating_per_row(rows):
    return {row: 0xffffffff if row % 2 == 0 else 0x00000000 for row in rows}

def patterns_random_per_row(rows, seed=42):
    rng = random.Random(seed)
    return {row: rng.randint(0, 2**32 - 1) for row in rows}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--nrows', type=int, default=0, help='Number of rows to consider')
    parser.add_argument('--bank', type=int, default=0, help='Bank number')
    parser.add_argument('--column', type=int, default=512, help='Column to read from')
    parser.add_argument('--colbits', type=int, default=10, help='Number of column bits')  # FIXME: take from our design
    parser.add_argument('--rowbits', type=int, default=14, help='Number of row bits')  # FIXME: take from our design
    parser.add_argument('--bankbits', type=int, default=3, help='Number of bank bits')  # FIXME: take from our design
    parser.add_argument('--start-row', type=int, default=0, help='Starting row (range = (start, start+nrows))')
    parser.add_argument('--read_count', type=float, default=10e6, help='How many reads to perform for single address pair')
    parser.add_argument('--hammer-only', nargs=2, type=int, help='Run only the row hammer attack')
    parser.add_argument('--no-refresh', action='store_true', help='Disable refresh commands during the attacks')
    parser.add_argument('--pattern', default='01_per_row',
                        choices=['all_0', 'all_1', '01_in_row', '01_per_row', 'rand_per_row'],
                        help='Pattern written to DRAM before running attacks')
    parser.add_argument('--row-pairs', choices=['sequential', 'const', 'random'], default='sequential',
                        help='How the rows for subsequent attacks are selected')
    parser.add_argument('--const-rows-pair', type=int, nargs=2, required=False, help='When using --row-pairs constant')
    parser.add_argument('--plot', action='store_true', help='Plot errors distribution') # requiers matplotlib and pyqt5 packages
    parser.add_argument('--payload-executor', action='store_true', help='Do the attack using Payload Executor (1st row only)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Be more verbose')
    parser.add_argument("--srv", action="store_true", help='Start LiteX server')
    parser.add_argument("--experiment-no", type=int, default=0, help='Run preconfigured experiment #no')
    args = parser.parse_args()

    if args.experiment_no == 1:
        args.nrows = 512
        args.read_count = 15e6
        args.pattern = '01_in_row'
        args.row_pairs = 'const'
        args.const_rows_pair = 88, 99
        args.no_refresh = True

    if args.srv:
        from wrapper import litex_srv
        litex_srv()

    from litex import RemoteClient

    wb = RemoteClient()
    wb.open()

    row_hammer = RowHammer(wb,
        nrows            = args.nrows,
        bankbits         = args.bankbits,
        rowbits          = args.rowbits,
        colbits          = args.colbits,
        column           = args.column,
        bank             = args.bank,
        rows_start       = args.start_row,
        verbose          = args.verbose,
        plot             = args.plot,
        no_refresh       = args.no_refresh,
        payload_executor = args.payload_executor,
    )

    if args.hammer_only:
        row_hammer.attack(*args.hammer_only, read_count=args.read_count)
    else:
        rng = random.Random(42)
        def rand_row():
            return rng.randint(args.start_row, args.start_row + args.nrows)

        assert not (args.row_pairs == 'const' and not args.const_rows_pair), 'Specify --const-rows-pair'
        row_pairs = {
            'sequential': [(0 + args.start_row, i + args.start_row) for i in range(args.nrows)],
            'const': [tuple(args.const_rows_pair)],
            'random': [(rand_row(), rand_row()) for i in range(args.nrows)],
        }[args.row_pairs]

        pattern = {
            'all_0': lambda rows: patterns_const(rows, 0x00000000),
            'all_ones': lambda rows: patterns_const(rows, 0xffffffff),
            '01_in_row': lambda rows: patterns_const(rows, 0xaaaaaaaa),
            '01_per_row': patterns_alternating_per_row,
            'rand_per_row': patterns_random_per_row,
        }[args.pattern]

        row_hammer.run(row_pairs=row_pairs, read_count=args.read_count, pattern_generator=pattern)

    wb.close()
