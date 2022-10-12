#!/usr/bin/env python

import os
import sys
import math
import time
import argparse

import pexpect
from pexpect import replwrap

from litedram.modules import parse_spd_hexdump, SDRAMModule

from rowhammer_tester.scripts.utils import get_generated_defs, RemoteClient, litex_server

SCRIPT_DIR = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))

SPD_COMMANDS = {
    # on ZCU104 first configure the I2C switch to select DDR4 SPD EEPROM, which than has base address 0b001
    'zcu104': (1, ['i2c_write 0x74 0x80']),
    'ddr4_datacenter_test_board': (0, None),
    'ddr5_tester': (0, None, True),
}


def read_spd(console, spd_addr, init_commands=None, ddr5=False):
    assert 0 <= spd_addr < 0b111, 'SPD EEPROM max address is 0b111 (defined by A0, A1, A2 pins)'
    prompt = '^.*litex[^>]*> '  # '92;1mlitex\x1b[0m> '
    console.sendline()
    console.expect(prompt)
    if ddr5:

        def add_page_to_address(dump):
            ret = []
            for line in dump.splitlines():
                if line.strip().startswith('0x'):
                    line = list(line)
                    line[7] = f'{page:x}'
                    modified_line = ''.join(line)
                    ret.append(modified_line)
            return '\n'.join(ret)

        spd_data = ''
        for page in range(8):
            print(f"Reading page {page}")
            console.sendline(f'i2c_write 0x50 0x0b {page:x}')
            console.expect(prompt)
            console.sendline('i2c_read 0x50 0x80 128')
            console.expect('Memory dump:')
            console.expect(prompt)
            modified_dump = add_page_to_address(console.after.decode())
            spd_data += '\n' + modified_dump
    else:
        for cmd in init_commands or []:
            console.sendline(cmd)
            console.expect(prompt)
        console.sendline('sdram_spd {}'.format(spd_addr))
        console.expect('Memory dump:')
        console.expect(prompt)
        spd_data = console.after.decode()
    return spd_data


def parse_hexdump(string):
    prev_addr = -1
    found = False
    for line in string.split('\n'):
        # whole memory dump will be a single block of following lines
        # find it and stop when another line is found
        if not found and not line.strip().startswith('0x'):
            continue
        found = True
        if not line.strip().startswith('0x'):
            break

        tokens = line.strip().split()
        addr = int(tokens[0], 16)
        assert addr > prev_addr
        for byte in tokens[1:17]:
            yield int(byte, 16)
        prev_addr = addr


def dump_object(obj, show_hidden=False, header=True):
    bold = '\033[1m'
    clear = '\033[0m'
    if header:
        print('{}{}:{}'.format(bold, obj.__class__.__name__, clear))
    d = obj if isinstance(obj, dict) else vars(obj)
    for var, val in d.items():
        if var == "self" or (var.startswith('_') and not show_hidden):
            continue
        print("  {}: {}".format(var, val))


def show_module(spd_data, clk_freq):
    module = SDRAMModule.from_spd_data(spd_data, clk_freq=clk_freq)
    dump_object(module)
    dump_object(module.__class__, header=False)
    dump_object(module.technology_timings)
    dump_object(module.speedgrade_timings['default'])
    dump_object(module.geom_settings)
    dump_object(module.timing_settings)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='cmd')
    read = subparsers.add_parser('read')
    show = subparsers.add_parser('show')
    read.add_argument('output_file', help='File to save SPD data to')
    read.add_argument('--srv', action='store_true', help='Start litex server in background')
    show.add_argument('input_file', help='File with SPD data')
    read.add_argument(
        '--mem-timeout', default=25, type=int, help='Time to wait for memory initialization')
    show.add_argument('clk_freq', help='DRAM controller clock frequency')
    args = parser.parse_args()

    if args.cmd == 'read':
        if args.srv:
            litex_server()

        defs = get_generated_defs()
        target = defs['TARGET']
        if target not in SPD_COMMANDS:
            raise NotImplementedError('SPD commands not available for target: {}'.format(target))

        print('Reading SPD EEPROM ...')
        console = pexpect.spawn('python bios_console.py -t litex_term', cwd=SCRIPT_DIR, timeout=6)
        wb = RemoteClient()
        wb.open()
        if not wb.regs.ddrctrl_init_done.read():
            print('Wating for CPU to finish memory training ...')
            for i in range(args.mem_timeout):
                time.sleep(1)
                print('{:3} s'.format(args.mem_timeout - i - 1), end=' \r', flush=True)
                # print('.', end='', flush=True)
                if wb.regs.ddrctrl_init_done.read():
                    print('Ready    ', end=' \r', flush=True)
                    break
            print()
            time.sleep(2)
        wb.close()

        output = read_spd(console, *SPD_COMMANDS[target])
        spd_data = list(parse_hexdump(output))

        with open(args.output_file, 'wb') as f:
            f.write(bytes(spd_data))

        print('SPD saved to file: {}'.format(args.output_file))
    elif args.cmd == 'show':
        with open(args.input_file, 'rb') as f:
            spd_data = f.read()

        clk_freq = float(args.clk_freq)
        module = SDRAMModule.from_spd_data(spd_data, clk_freq=clk_freq)
        dump_object(module)
        dump_object(module.__class__, header=False)
        dump_object(module.technology_timings)
        dump_object(module.speedgrade_timings['default'])
        dump_object(module.geom_settings)
        dump_object(module.timing_settings)
    else:
        parser.print_usage()
