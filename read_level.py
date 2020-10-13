import random
from operator import or_
from functools import reduce

def delay_select_modules(wb, modules):
    sel = reduce(or_, ((1 << m) for m in modules))
    wb.regs.ddrphy_dly_sel.write(sel)

def read_bitslip_rst(wb):
    wb.regs.ddrphy_rdly_dq_bitslip_rst.write(1)

def read_bitslip_inc(wb):
    wb.regs.ddrphy_rdly_dq_bitslip.write(1)

def read_bitslip_set(wb, value):
    read_bitslip_rst(wb)
    for _ in range(value):
        read_bitslip_inc(wb)

def read_delay_rst(wb):
    wb.regs.ddrphy_rdly_dq_rst.write(1)

def read_delay_inc(wb):
    wb.regs.ddrphy_rdly_dq_inc.write(1)

def read_delay_set(wb, value):
    read_delay_rst(wb)
    for _ in range(value):
        read_delay_inc(wb)

def read_level_test(wb, seed=42, base=0x40000000, length=0x80, inc=8,
                    verbose_hex=False, verbose_bin=False):
    rng = random.Random(seed)
    refdata = []

    for i in range(length//inc):
        data = [rng.randint(0, 2**32 - 1) for _ in range(inc)]
        wb.write(base + 4*inc*i, data)
        refdata += data

    data = []
    for i in range(length//inc):
        data += wb.read(base + 4*inc*i, inc)

    assert len(refdata) == len(data)

    errors = 0
    for val, ref in zip(data, refdata):
        if val != ref:
            errors += 1
            if verbose_hex:
                print("0x{:08x} != 0x{:08x}".format(val, ref))
            if verbose_bin:
                print("{:032b} xor {:032b} = {:032b}".format(val, ref, val ^ ref))

    return errors

def read_level_module(wb, n_bitslips=16, n_delays=32, delays_step=3, **kwargs):
    read_bitslip_rst(wb)

    scores = {}  # {(bitslip, delay): errors, ...}
    for bs in range(n_bitslips):
        read_delay_rst(wb)
        print("Bitslip {:02d}: |".format(bs), end="", flush=True)

        for dly in range(0, n_delays, delays_step):
            errors = read_level_test(wb, **kwargs)
            # errors = memtest(wb, 0x80)
            scores[(bs, dly)] = errors
            print("1" if errors == 0 else "0", end="", flush=True)
            read_delay_inc(wb)

        print("|")
        read_bitslip_inc(wb)

    best = min(scores.keys(), key=lambda bs_dly: scores[bs_dly])
    print("Best: bitslip = {}, delay = {}, errors = {}".format(*best, scores[best]))

    best_bs, best_dly = best
    read_bitslip_set(wb, best_bs)
    read_delay_set(wb, best_dly)

def read_level(wb, n_modules, **kwargs):
    for module in range(n_modules):
        print("Module {}".format(module))
        delay_select_modules(wb, [module])
        read_level_module(wb, **kwargs)

# -----------------------
from litex import RemoteClient

wb = RemoteClient()
wb.open()

read_level(wb, 1)

wb.close()
