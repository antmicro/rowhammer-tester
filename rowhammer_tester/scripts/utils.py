import time
from operator import or_
from functools import reduce

import sdram_init as _sdram_init
from sdram_init import *

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
    with open(_sdram_init.__file__, 'r') as f:
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

def memwrite(wb, data, base=0x40000000, burst=0xff):
    for i in range(0, len(data), burst):
        wb.write(base + 4*i, data[i:i+burst])

def memread(wb, n, base=0x40000000, burst=0xff):
    data = []
    for i in range(0, n, burst):
        data += wb.read(base + 4*i, min(burst, n - i))
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
        ret = fun(wb, n, **kwargs)
        elapsed = time.time() - start
        print('{:5} speed: {:6.2f} KB/s ({:.1f} sec)'.format(name, (n*4)/elapsed / 1e3, elapsed))
        return ret

    measure(memfill, 'Write')
    data = measure(memread, 'Read')
    errors = [(i, w) for i, w in enumerate(data) if w != kwargs.get('pattern', 0xaaaaaaaa)]
    assert len(errors) == 0, len(errors)

def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def word2byte(words, word_size=4):
    for w in words:
        for i in range(word_size):
            yield (w & (0xff << 8*i)) >> 8*i

def memdump(data, base=0x40000000, chunk_len=16):
    def tochar(val):
        return chr(val) if 0x20 <= val <= 0x7e else '.'

    data_bytes = list(word2byte(data))
    for i, chunk in enumerate(chunks(data_bytes, chunk_len)):
        b = " ".join("{:02x}".format(chunk[i] if i < len(chunk) else 0) for i in range(chunk_len))
        c = "".join(tochar(chunk[i] if i < len(chunk) else 0) for i in range(chunk_len))
        print("0x{addr:08x}:  {bytes}  {chars}".format(addr=base + chunk_len*i, bytes=b, chars=c))

################################################################################

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

################################################################################

# Open a remote connection in an interactive session (e.g. when sourced as `ipython -i <thisfile>`)
if __name__ == "__main__":
    import sys

    if bool(getattr(sys, 'ps1', sys.flags.interactive)):
        from litex import RemoteClient

        wb = RemoteClient()
        wb.open()
