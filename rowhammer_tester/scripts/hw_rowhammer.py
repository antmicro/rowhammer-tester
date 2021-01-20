#!/usr/bin/env python3

import time
import random
import argparse
from math import ceil
from collections import defaultdict

from rowhammer_tester.gateware.payload_executor import Encoder, OpCode, Decoder
from rowhammer_tester.scripts.utils import (hw_memset, hw_memtest, DRAMAddressConverter,
                                            litex_server, memwrite, RemoteClient,
                                            setup_inverters)
from rowhammer_tester.scripts.rowhammer import RowHammer, main

################################################################################

class HwRowHammer(RowHammer):
    def attack(self, row_tuple, read_count, progress_header=''):
        addresses = [self.converter.encode_dma(bank=self.bank, col=self.column, row=r)
                     for r in row_tuple]
        row_strw = len(str(2**self.settings.geom.rowbits - 1))

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
        self.wb.regs.reader_data_mask.write(len(row_tuple) - 1)

        # Attacked addresses
        memwrite(self.wb, addresses, base=self.wb.mems.pattern_addr.base)

        # how many
        print('read_count: ' + str(int(read_count)))
        self.wb.regs.reader_count.write(int(read_count))

        self.wb.regs.reader_start.write(1)
        self.wb.regs.reader_start.write(0)
        # FIXME: --------------------------- move to utils ------------------

        def progress(count):
            s = '  {}'.format(progress_header + ' ' if progress_header else '')
            s += 'Rows = {}, Count = {:5.2f}M / {:5.2f}M'.format(
                row_tuple, count/1e6, read_count/1e6, n=row_strw)
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

    def check_errors(self, row_pattern):
        dma_data_width = self.settings.phy.dfi_databits * self.settings.phy.nphases
        dma_data_bytes = dma_data_width // 8

        errors = hw_memtest(self.wb, 0x0, self.wb.mems.main_ram.size, [row_pattern])

        row_errors = defaultdict(list)
        for e in errors:
            addr = self.wb.mems.main_ram.base + e.offset * dma_data_bytes
            bank, row, col = self.converter.decode_bus(addr)
            base_addr = min(self.addresses_per_row(row))
            row_errors[row].append(((addr - base_addr)//4, e.data, e.expected))

        return dict(row_errors)

    def run(self, row_pairs, pattern_generator, read_count, row_progress=16, verify_initial=True):
        setup_inverters(self.wb, self.data_inversion)

        print('\nPreparing ...')
        row_pattern = pattern_generator([self.rows[0]])[0]
        print('WARNING: only single word patterns supported, using: 0x{:08x}'.format(row_pattern))
        print('\nFilling memory with data ...')
        hw_memset(self.wb, 0x0, self.wb.mems.main_ram.size, [row_pattern])

        if verify_initial:
            print('\nVerifying written memory ...')
            errors = self.check_errors(row_pattern)
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
        for i, row_tuple in enumerate(row_pairs):
            s = 'Iter {:{n}} / {:{n}}'.format(i, len(row_pairs), n=len(str(len(row_pairs))))
            if self.payload_executor:
                self.payload_executor_attack(read_count=read_count, row_tuple=row_tuple)
            else:
                if len(row_tuple) & (len(row_tuple) - 1) != 0:
                    print("ERROR: BIST only supports power of 2 rows\n")
                    return

                self.attack(row_tuple, read_count=read_count, progress_header=s)

        if self.no_refresh:
            print('\nReenabling refresh ...')
            self.wb.regs.controller_settings_refresh.write(1)

        print('\nVerifying attacked memory ...')
        errors = self.check_errors(row_pattern)
        if self.errors_count(errors) == 0:
            print('OK')
        else:
            print()
            self.display_errors(errors)
            return

################################################################################

if __name__ == "__main__":
    main(row_hammer_cls=HwRowHammer)
