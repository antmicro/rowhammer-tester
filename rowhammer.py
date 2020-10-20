import time
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

def row_hammer_attack(wb, converter, *, bank, rows, col, read_count):
    assert len(rows) == 2

    wb.regs.rowhammer_enabled.write(0)
    wb.regs.rowhammer_address0.write(converter.encode_dma(bank=bank, row=rows[0], col=col))
    wb.regs.rowhammer_address1.write(converter.encode_dma(bank=bank, row=rows[1], col=col))
    wb.regs.rowhammer_enabled.write(1)

    def print_step(current_count):
        print('  Rows = ({:3d},{:3d}), Count = {:5.1f}M / {:5.1f}M'.format(
            *rows, current_count/1e6, read_count/1e6), end='  \r', flush=True)

    while True:
        count = wb.regs.rowhammer_count.read()
        print_step(count)
        time.sleep(0.05)
        if count >= read_count:
            break

    wb.regs.rowhammer_enabled.write(0)
    print_step(wb.regs.rowhammer_count.read())  # also clears the value
    print()

def row_hammer(wb, *, rows, column=512, bank=0, colbits=10, read_count=10e6):
    rows = list(rows)

    converter = DRAMAddressConverter()
    burst_width = 2*16 * 4  # 2 (DDR) * databits (DQ pins) * nphases (1:4 freq ratio)
    # col_width = 16
    bus_width = 32
    burst_len = burst_width // bus_width

    def row_pattern(row):
        return 0x55555555 if row % 2 == 0 else 0xaaaaaaaa

    address_lists = {
        row: [converter.encode_bus(bank=bank, row=row, col=col) for col in range(2**colbits)]
        for row in rows
    }

    print('\nFilling memory with data ...')
    for row, address_list in address_lists.items():
        n = (max(address_list) - min(address_list)) // 4
        # extend to whole bursts
        n = ceil(n / 4) * 4
        pattern = row_pattern(row)
        memfill(wb, n, pattern=pattern, base=address_list[0])
        if row % 16 == 0:
            print('.', end='', flush=True)

    def check():
        ok = True
        for row, address_list in address_lists.items():
            n = (max(address_list) - min(address_list)) // 4
            errors = memcheck(wb, n, pattern=row_pattern(row), base=address_list[0])
            for i, word in errors:
                ok = False
                addr = 0x40000000 + 4*i
                bank, row, col = converter.decode_bus(addr)
                print("Error: 0x{:08x}: 0x{:08x} (row={}, col={})".format(
                    addr, word, row, col))
            if row % 16 == 0:
                print('.', end='', flush=True)
        return ok

    print('\nVerifying memory ...')
    if check():
        print('OK')
    else:
       print("ERROR")
       return

    print('\nRunning row hammer attack ...')
    # for i in range(len(rows) - 1):
    #     rh_rows = rows[i:i+2]
    for i in range(len(rows)//2):
        rh_rows = rows[2*i:2*i + 2]
        row_hammer_attack(wb, converter, bank=bank, rows=rh_rows, col=column, read_count=read_count)

    print('\nChecking tested rows ...')
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
    parser.add_argument('--read_count', type=float, default=10e6, help='How many reads to perform for single address pair')
    parser.add_argument('--hammer-only', action='store_true', help='Run only the row hammer sequence on rows (nrows, nrows+1)')
    args = parser.parse_args()

    from litex import RemoteClient

    wb = RemoteClient()
    wb.open()

    rows = range(args.nrows)
    bank = args.bank
    column = args.column
    colbits = args.colbits
    read_count = args.read_count

    if args.hammer_only:
        converter = DRAMAddressConverter()
        rows = [args.nrows, args.nrows + 1]
        row_hammer_attack(wb, converter, bank=bank, rows=rows, col=column, read_count=read_count)
    else:
        row_hammer(wb, rows=rows, bank=bank, column=column, colbits=colbits, read_count=read_count)

    wb.close()
