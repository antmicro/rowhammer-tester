from functools import reduce
from operator import or_

class DRAMAddress:
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

    def encode(self, bank, row, col, base=0x40000000, bus_align=2):
        assert bank < 2**self.bankbits
        assert col < 2**self.colbits
        assert row < 2**self.rowbits
        assert bus_align <= self.address_align

        def prepare(value, width, offset):
            mask = 2**width - 1
            masked = value & mask
            assert masked == value
            return masked << offset

        parts = [ # (address, width, offset)
            (row, self.rowbits, self.bankbits + self.colbits),
            (bank, self.bankbits, self.colbits),
            (col, self.colbits, 0),
        ]
        address = reduce(or_, [prepare(*part) for part in parts])

        return base + (address << (self.address_align - bus_align))

    def decode(self, address, base=0x40000000, bus_align=2):
        def extract(value, width, offset):
            mask = 2**width - 1
            return (value & (mask << offset)) >> offset

        address -= base
        address >>= self.address_align - bus_align

        row = extract(address, self.rowbits, self.bankbits + self.colbits)
        bank = extract(address, self.bankbits, self.colbits)
        col = extract(address, self.colbits, 0)

        return bank, row, col

if __name__ == "__main__":
    from litex import RemoteClient

    wb = RemoteClient()
    wb.open()

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

    dram_address = DRAMAddress()

    for col in [16, 32]:
        for bank in [1, 2]:
            for row in [3, 4]:
                address = dram_address.encode(bank, row, col)

                bank_dec, row_dec, col_dec = dram_address.decode(address)

                # print(' bank: {:3} vs {:3}'.format(bank_dec, bank))
                # print(' row:  {:3} vs {:3}'.format(row_dec, row))
                # print(' col:  {:3} vs {:3}'.format(col_dec, col))

                # print(' bank: {:08b} vs {:08b}'.format(bank_dec, bank))
                # print(' row:  {:08b} vs {:08b}'.format(row_dec, row))
                # print(' col:  {:08b} vs {:08b}'.format(col_dec, col))

                word = next(data)
                print("0x{:08x}: 0x{:08x}  (bank={:{fmt}}, row={:{fmt}}, col={:{fmt}})".format(
                    address, word, bank, row, col, fmt='08b'))
                wb.write(address, word)

                # import time
                # time.sleep(0.1)

    wb.close()
