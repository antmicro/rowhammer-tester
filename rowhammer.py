import time
import random
from math import ceil
from operator import or_
from functools import reduce

from utils import memfill, memcheck

class DRAMAddressConverter:
    def __init__(self, colbits=10, rowbits=14, bankbits=3,
                 address_mapping='ROW_BANK_COL', address_align=3):
        # FIXME: generate these from BaseSoC
        # soc.sdram.controller.settings
        self.colbits = colbits
        self.rowbits = rowbits
        self.bankbits = bankbits
        self.address_mapping = address_mapping
        self.address_align = address_align

        assert self.address_mapping == 'ROW_BANK_COL'

    def _encode(self, bank, row, col):
        assert bank < 2**self.bankbits
        assert col < 2**self.colbits
        assert row < 2**self.rowbits

        def masked(value, width, offset):
            masked = value & (2**width - 1)
            assert masked == value, "Value larger than value bit-width"
            return masked << offset

        return reduce(or_, [
            masked(row,  self.rowbits,  self.bankbits + self.colbits),
            masked(bank, self.bankbits, self.colbits),
            masked(col,  self.colbits,  0),
        ])

    def encode_bus(self, *, bank, row, col, base=0x40000000, bus_align=2):
        assert bus_align <= self.address_align
        address = self._encode(bank, row, col)
        return base + (address << (self.address_align - bus_align))

    def encode_dma(self, *, bank, row, col):
        address = self._encode(bank, row, col)
        return address >> self.address_align

    def _decode(self, address):
        def extract(value, width, offset):
            mask = 2**width - 1
            return (value & (mask << offset)) >> offset

        row = extract(address, self.rowbits, self.bankbits + self.colbits)
        bank = extract(address, self.bankbits, self.colbits)
        col = extract(address, self.colbits, 0)

        return bank, row, col

    def decode_bus(self, address, base=0x40000000, bus_align=2):
        address -= base
        address >>= self.address_align - bus_align
        return self._decode(address)

    def decode_dma(self, address):
        return self._decode(address << self.address_align)

def row_hammer_attack(wb, converter, *, bank, rows, col, read_count, rowbits, i=None, niter=None):
    assert len(rows) == 2

    wb.regs.rowhammer_enabled.write(0)
    wb.regs.rowhammer_address0.write(converter.encode_dma(bank=bank, row=rows[0], col=col))
    wb.regs.rowhammer_address1.write(converter.encode_dma(bank=bank, row=rows[1], col=col))
    wb.regs.rowhammer_enabled.write(1)

    row_w = len(str(2**rowbits - 1))
    if niter is not None:
        assert i is not None
        iter_w = len(str(niter))

    def print_step(current_count):
        if niter is not None:
            iter_fmt = 'Iter {:{n}} / {:{n}}, '.format(i, niter, n=iter_w)
        else:
            iter_fmt = ''
        s = '  {it}Rows = ({:{n}d},{:{n}d}), Count = {:5.2f}M / {:5.2f}M'.format(
            *rows, current_count/1e6, read_count/1e6, n=row_w, it=iter_fmt)
        print(s, end='  \r')

    while True:
        count = wb.regs.rowhammer_count.read()
        print_step(count)
        if count >= read_count:
            break

    wb.regs.rowhammer_enabled.write(0)
    print_step(wb.regs.rowhammer_count.read())  # also clears the value
    print()

def patterns_const(rows, value):
    return {row: value for row in rows}

def patterns_alternating_per_row(rows):
    return {row: 0xffffffff if row % 2 == 0 else 0x00000000 for row in rows}

def patterns_random_per_row(rows, seed=42):
    rng = random.Random(seed)
    return {row: rng.randint(0, 2**32 - 1) for row in rows}

def row_hammer(wb, *, row_pairs, column=512, bank=0, colbits=10, rowbits=14,
               read_count=10e6, pattern=patterns_alternating_per_row,
               verify_initial=True, verbose_errors=False, error_histogram=False):
    print('\nPreparing ...')
    # get all the rows we will be attacking
    rows = set()
    for row1, row2 in row_pairs:
        rows.add(row1)
        rows.add(row2)
    rows = list(rows)
    # get row patterns and address lists
    row_patterns = pattern(rows)
    converter = DRAMAddressConverter()
    address_lists = {
        row: [converter.encode_bus(bank=bank, row=row, col=col) for col in range(2**colbits)]
        for row in rows
    }

    def row_accesses():
        for row, address_list in address_lists.items():
            n = (max(address_list) - min(address_list)) // 4
            # extend to whole bursts
            n = ceil(n / 4) * 4
            base_addr = address_list[0]
            yield row, n, base_addr

    print('\nFilling memory with data ...')
    for row, n, base in row_accesses():
        memfill(wb, n, pattern=row_patterns[row], base=base)
        if row % 16 == 0:
            print('.', end='', flush=True)

    def check():
        errors = {}
        for row, n, base in row_accesses():
            errors[row] = memcheck(wb, n, pattern=row_patterns[row], base=base)
            if row % 16 == 0:
                print('.', end='', flush=True)
        for row in errors:
            if len(errors[row]) > 0:
                print("Errors for row={:{n}}: {}".format(
                    row, len(errors[row]), n=len(str(2**rowbits-1))))
            if verbose_errors:
                for i, word in errors[row]:
                    addr = base + 4*i
                    bank, _row, col = converter.decode_bus(addr)
                    print("Error: 0x{:08x}: 0x{:08x} (row={}, col={})".format(
                        addr, word, _row, col))

        n_errors = sum(1 if len(e) > 0 else 0 for e in errors.values())
        if n_errors > 0 and error_histogram:
            from matplotlib import pyplot as plt
            row_errors = [len(errors.get(row, [])) for row in rows]
            plt.bar(rows, row_errors, width=1)
            plt.grid(True)
            plt.xlabel('row')
            plt.ylabel('errors')
            plt.show()

        return n_errors == 0

    if verify_initial:
        print('\nVerifying written memory ...')
        if check():
            print('OK')
        else:
            print("ERROR")
            return

    print('\nRunning row hammer attack ...')
    for i, (row1, row2) in enumerate(row_pairs):
        row_hammer_attack(wb, converter, bank=bank, rows=[row1, row2], col=column,
                          read_count=read_count, rowbits=rowbits, i=i, niter=len(row_pairs))

    print('\nChecking tested memory ...')
    print('OK') if check() else print("ERROR")

def encode_decode_test(wb):
    data = [
        0x11111111,
        0x22222222,
        0x33333333,
        0x44444444,
        0x55555555,
        0x66666666,
        0x77777777,
        0x88888888,
    ]
    data = (d for d in data)

    converter = DRAMAddressConverter()

    for col in [16, 32]:
        for bank in [1, 2]:
            for row in [3, 4]:
                address = converter.encode_bus(bank=bank, row=row, col=col)

                bank_dec, row_dec, col_dec = converter.decode_bus(address)

                # print(' bank: {:3} vs {:3}'.format(bank_dec, bank))
                # print(' row:  {:3} vs {:3}'.format(row_dec, row))
                # print(' col:  {:3} vs {:3}'.format(col_dec, col))

                word = next(data)
                print("0x{:08x}: 0x{:08x}  (bank={:{fmt}}, row={:{fmt}}, col={:{fmt}})".format(
                    # address, word, bank, row, col, fmt='08b'))
                    address, word, bank, row, col, fmt='2d'))
                wb.write(address, word)

                # import time
                # time.sleep(0.1)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('nrows', type=int, help='Number of rows to consider')
    parser.add_argument('--bank', type=int, default=0, help='Bank number')
    parser.add_argument('--column', type=int, default=512, help='Column to read from')
    parser.add_argument('--colbits', type=int, default=10, help='Number of column bits')  # FIXME: take from our design
    parser.add_argument('--rowbits', type=int, default=14, help='Number of row bits')  # FIXME: take from our design
    parser.add_argument('--read_count', type=float, default=10e6, help='How many reads to perform for single address pair')
    parser.add_argument('--hammer-only', action='store_true', help='Run only the row hammer sequence on rows (nrows, nrows+1)')
    parser.add_argument('--pattern', choices=['all_zeros', 'all_ones', 'alternating_in_row', 'alternating_per_row', 'random_per_row'],
                        default='alternating_per_row', help='Pattern written to DRAM before running attacks')
    parser.add_argument('--row-pairs', choices=['sequential', 'random'], default='sequential',
                        help='How the rows for subsequent attacks are selected')
    args = parser.parse_args()

    from litex import RemoteClient

    wb = RemoteClient()
    wb.open()

    if args.hammer_only:
        converter = DRAMAddressConverter()
        rows = [args.nrows, args.nrows + 1]
        row_hammer_attack(wb, converter, bank=args.bank, rows=rows, col=args.column,
                          rowbits=args.rowbits, read_count=args.read_count)
    else:
        rng = random.Random(42)
        def rand_row():
            return rng.randint(0, 2**args.rowbits - 1)

        row_pairs = {
            'sequential': [(0, i) for i in range(args.nrows)],
            'random': [(rand_row(), rand_row()) for i in range(args.nrows)],
        }[args.row_pairs]

        pattern = {
            'all_zeros': lambda rows: patterns_const(rows, 0x00000000),
            'all_ones': lambda rows: patterns_const(rows, 0xffffffff),
            'alternating_in_row': lambda rows: patterns_const(rows, 0xaaaaaaaa),
            'alternating_per_row': patterns_alternating_per_row,
            'random_per_row': patterns_random_per_row,
        }[args.pattern]

        row_hammer(wb, row_pairs=row_pairs, bank=args.bank, column=args.column, colbits=args.colbits,
                   rowbits=args.rowbits, read_count=args.read_count, pattern=pattern)

    wb.close()
