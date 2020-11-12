import os
import csv
import sys
import glob
import time
from operator import or_
from functools import reduce

# ###########################################################################

def discover_generated_files_dir():
    # Search for defs.csv file that should have been generated in build directory.
    # Assume that we are building in repo root.
    script_dir = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
    build_dir = os.path.normpath(os.path.join(script_dir, '..', '..', 'build'))
    candidates = os.path.join(build_dir, '*', 'defs.csv')
    results = glob.glob(candidates)
    if not results:
        raise ImportError(
            'Could not find "defs.csv". Make sure to run target generator (from'
            ' rowhammer_tester/targets/) in the root directory of this repository.')
    elif len(results) > 1:
        if 'TARGET' not in os.environ:
            raise ImportError(
                'More than one "defs.csv" file found. Set environmental variable'
                ' TARGET to the name of the target to use (e.g. `export TARGET=arty`).')
        gen_dir = os.path.join(build_dir, os.environ['TARGET'])
    else:
        gen_dir = os.path.dirname(results[0])

    sys.path.append(gen_dir)
    return gen_dir

GENERATED_DIR = discover_generated_files_dir()

# Import sdram_init.py
sys.path.append(GENERATED_DIR)
import sdram_init as sdram_init_defs
from sdram_init import *

def get_generated_file(name):
    # For getting csr.csv/analyzer.csv
    filename = os.path.join(GENERATED_DIR, name)
    if not os.path.isfile(filename):
        raise ImportError('Generated file "{}" not found in directory "{}"'.format(name, GENERATED_DIR))
    return filename

def get_generated_defs():
    with open(get_generated_file('defs.csv'), newline='') as f:
        reader = csv.reader(f)
        return {name: value for name, value in reader}

def RemoteClient(*args, **kwargs):
    from litex import RemoteClient as _RemoteClient
    return _RemoteClient(csr_csv=get_generated_file('csr.csv'), *args, **kwargs)

def litex_server():
    from litex.tools.litex_server import RemoteServer
    from litex.tools.remote.comm_udp import CommUDP
    defs = get_generated_defs()
    comm = CommUDP(server=defs['IP_ADDRESS'], port=int(defs['UDP_PORT']))
    server = RemoteServer(comm, '127.0.0.1', 1234)
    server.open()
    server.start(4)

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
    with open(sdram_init_defs.__file__, 'r') as f:
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
    if bool(getattr(sys, 'ps1', sys.flags.interactive)):
        wb = RemoteClient()
        wb.open()
