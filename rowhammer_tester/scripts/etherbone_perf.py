import time
import cProfile

import argparse

from .utils import memread, memwrite

def run(wb, rw, n, *, burst, profile=True):
    datas = list(range(n))

    ctx = locals()
    ctx['wb'] = wb
    ctx['memread'] = memread
    ctx['memwrite'] = memwrite

    fname = 'tmp/profiling/{}_0x{:x}_b{}.profile'.format(rw, n, burst)
    command = {
        'memread': 'memread(wb, n, burst=burst)',
        'memwrite': 'memwrite(wb, datas, burst=burst)',
    }[rw]

    def runner():
        if profile:
            cProfile.runctx(command, {}, ctx, fname)
        else:
            if rw == 'memread':
                x = len(memread(wb, n, burst=burst))
                print(x)
            else:
                memwrite(wb, datas, burst=burst)

    measure(runner, 4*n)

def measure(runner, nbytes):
    start = time.time()
    runner()
    elapsed = time.time() - start

    bytes_per_sec = nbytes / elapsed
    print('Elapsed = {:.3f} sec'.format(elapsed))

    def human(val):
        if val > 2**20:
            return (val / 2**20, 'M')
        elif val > 2**10:
            return (val / 2**10, 'K')
        return (val, '')

    print('Size    = {:.3f} {}B'.format(*human(nbytes)))
    print('Speed   = {:.3f} {}Bps'.format(*human(bytes_per_sec)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Measure EtherBone bridge performance')
    parser.add_argument('rw', choices=['memread', 'memwrite'], help='Transfer type')
    parser.add_argument('n', help='Number of 32-bit words transfered')
    parser.add_argument('--burst', help='Burst size')
    parser.add_argument('--profile', action='store_true', help='Profile the code with cProfile')
    args = parser.parse_args()

    from litex import RemoteClient

    wb = RemoteClient()
    wb.open()

    run(wb, args.rw, int(args.n, 0), burst=int(args.burst, 0), profile=args.profile)

    wb.close()
