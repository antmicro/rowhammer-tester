#!/usr/bin/env python

import os
import pty
import threading
import argparse
import subprocess
import shutil

from litex.tools.litex_term import LiteXTerm

from rowhammer_tester.scripts.utils import RemoteClient, litex_server


def pty2crossover(m, stop):
    while not stop.is_set():
        r = os.read(m, 1)
        wb.regs.uart_xover_rxtx.write(ord(r))


def crossover2pty(m, stop):
    while not stop.is_set():
        if wb.regs.uart_xover_rxempty.read() == 0:
            r = wb.regs.uart_xover_rxtx.read()
            os.write(m, bytes(chr(r).encode("utf-8")))


if __name__ == "__main__":
    term_priority = ['picocom', 'minicom', 'litex_term']
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--srv', action='store_true', help='Start litex server in background')
    parser.add_argument('-b', '--baudrate', default='1e6', help='Serial baud rate')
    parser.add_argument(
        '-t',
        '--term',
        choices=['auto', *term_priority],
        default='auto',
        help='Select serial terminal emulator')
    args = parser.parse_args()

    if args.srv:
        litex_server()

    wb = RemoteClient()
    wb.open()

    m, s = pty.openpty()
    tty = os.ttyname(s)
    print("LiteX Crossover UART created: {}".format(tty))

    stop_event = threading.Event()
    threads = [
        threading.Thread(target=pty2crossover, args=[m, stop_event], daemon=True),
        threading.Thread(target=crossover2pty, args=[m, stop_event], daemon=True),
    ]
    for thread in threads:
        thread.start()

    baudrate = int(float(args.baudrate))

    term = args.term
    if term == 'auto':
        try:
            term = next(filter(lambda t: shutil.which(t) is not None, term_priority))
        except StopIteration:
            term = 'litex_term'

    print('Using serial backend: {}'.format(args.term))
    if term == 'litex_term':
        # installed with latex so no additional dependencies, but it is slow
        term = LiteXTerm(
            serial_boot=False, kernel_image=None, kernel_address=None, json_images=None, safe=True)
        term.open(tty, baudrate)
        term.console.configure()
        term.start()
        term.join()
    elif term == 'picocom':
        subprocess.run(['picocom', '-b', str(baudrate), tty])
    elif term == 'minicom':
        subprocess.run(['minicom', '-b', str(baudrate), '-D', tty])
    else:
        raise ValueError(term)

    stop_event.set()
    for thread in threads:
        thread.join(timeout=0.05)

    wb.close()
