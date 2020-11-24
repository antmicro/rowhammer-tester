#!/usr/bin/env python3

import time
import random
import argparse
from math import ceil

from rowhammer_tester.gateware.payload_executor import Encoder, OpCode, Decoder
from rowhammer_tester.scripts.utils import (hw_memset, hw_memtest, DRAMAddressConverter,
                                            litex_server, RemoteClient)
from rowhammer_tester.scripts.rowhammer import RowHammer, main

################################################################################

class HwRowHammer(RowHammer):
    def attack(self, row1, row2, read_count, progress_header=''):
        addresses = [self.converter.encode_dma(bank=self.bank, col=self.column, row=r)
                     for r in [row1, row2]]
        row_strw = len(str(2**self.rowbits - 1))

        # FIXME: ------------------ move to utils ----------------------------
        # Flush error fifo
        self.wb.regs.reader_skip_fifo.write(1)
        time.sleep(0.1)
        # Enable error FIFO
        self.wb.regs.reader_skip_fifo.write(0)

        assert self.wb.regs.reader_ready.read() == 1

        # Skip errors fifo
        self.wb.regs.reader_skip_fifo.write(1)

        # Do not increment memory address
        self.wb.regs.reader_mem_mask.write(0x00000000)
        self.wb.regs.reader_data_mask.write(0x00000001)

        # Attacked addresses
        self.wb.write(self.wb.mems.pattern_addr.base + 0x0, addresses[0])
        self.wb.write(self.wb.mems.pattern_addr.base + 0x4, addresses[1])

        # how many
        print('read_count: ' + str(int(read_count)))
        self.wb.regs.reader_count.write(int(read_count))

        self.wb.regs.reader_start.write(1)
        self.wb.regs.reader_start.write(0)
        # FIXME: --------------------------- move to utils ------------------

        def progress(count):
            s = '  {}'.format(progress_header + ' ' if progress_header else '')
            s += 'Rows = ({:{n}d},{:{n}d}), Count = {:5.2f}M / {:5.2f}M'.format(
                row1, row2, count/1e6, read_count/1e6, n=row_strw)
            print(s, end='  \r')

        while True:
            r_count = self.wb.regs.reader_done.read()
            progress(r_count)
            if self.wb.regs.reader_ready.read():
                break
            else:
                time.sleep(10 / 1e3)

        progress(self.wb.regs.reader_done.read())  # also clears the value
        print()

    def check_errors(self, row_patterns, row_progress=16):
        row_errors = {}
        for row, n, base in self.row_access_iterator():
            #print('x {:08x} {:08x} {:08x}'.format(row, n, base))
            assert base & 0xf0000000 == 0x40000000
            assert n == 0x1ff

            # FIXME: verify this
            row_errors[row] = hw_memtest(self.wb, base - 0x40000000, 0x200 * 4, [row_patterns[row]], dbg=False)
            if row % row_progress == 0:
                print('.', end='', flush=True)

        return row_errors

    def errors_count(self, row_errors):
        #for e in row_errors.values():
        #    print('row_errors.values(): ' + str(e))
        return super(row_errors)

    def run(self, row_pairs, pattern_generator, read_count, row_progress=16, verify_initial=False, use_bist=False):
        print('\nPreparing ...')
        row_patterns = pattern_generator(self.rows)

        #for row, n, base in self.row_access_iterator():
        #    print('itr: {:4d} {:5d} {:08x}'.format(row, n, base))

        print('\nFilling memory with data ...')
        #for row, n, base in self.row_access_iterator():
        #    assert (base & 0xf0000000) == 0x40000000
        #    assert n == 0x1ff
        #    hw_memset(self.wb, base - 0x40000000, 0x200 * 4, [row_patterns[row]])
        #    if row % row_progress == 0:
        #        print('.', end='', flush=True)
        hw_memset(self.wb, 0x0, self.wb.mems.main_ram.size, [row_patterns[0]])

        if verify_initial:
            print('\nVerifying written memory ...')
            #errors = self.check_errors(row_patterns, row_progress=row_progress)
            #if self.errors_count(errors) == 0:
            #    print('OK')
            #else:
            #    print('Error!')
            #    #self.display_errors(errors)
            #    return
            errors = hw_memtest(self.wb, 0x0, self.wb.mems.main_ram.size, [row_patterns[0]])
            if len(errors):
                print('Error!')
            else:
                print('OK')

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
        #errors = self.check_errors(row_patterns, row_progress=row_progress)
        errors = hw_memtest(self.wb, 0x0, self.wb.mems.main_ram.size, [row_patterns[0]])
        if len(errors):
            print('Errors')
            row_errors = {}
            for err in errors:
                addr = err * 16 + 0x40000000
                bank, row, col = self.converter.decode_bus(addr)
                #print('err: 0x{:08x} = bank: {:d}, row: {:d}, col: {:d}'.format(addr, bank, row, col))
                if row not in row_errors:
                    row_errors[row] = []
                row_errors[row].append(addr)

            for r in row_errors:
                row_errors[r] = [(i, o) for i, o in enumerate(row_errors[r])]

            self.display_errors(row_errors)
            print()

        else:
            print('OK')

        #if self.errors_count(errors) == 0:
        #    print('OK')
        #else:
        #    print()
        #    self.display_errors(errors)
        #    return

################################################################################

if __name__ == "__main__":
    main(row_hammer_cls=HwRowHammer)
