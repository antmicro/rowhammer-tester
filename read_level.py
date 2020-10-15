import random
from operator import or_
from functools import reduce
from collections import defaultdict

from sdram_init import *

# DRAM commands ----------------------------------

def sdram_software_control(wb):
    wb.regs.sdram_dfii_control.write(dfii_control_cke|dfii_control_odt|dfii_control_reset_n)

def sdram_cmd(wb, a, ba, command):
    sdram_software_control(wb)
    wb.regs.sdram_dfii_pi0_baddress.write(ba)
    wb.regs.sdram_dfii_pi0_address.write(a)
    wb.regs.sdram_dfii_pi0_command.write(command)
    wb.regs.sdram_dfii_pi0_command_issue.write(1)

def dfii_px(wb, phase, signal):
    return getattr(wb.regs, "sdram_dfii_pi{}_{}".format(phase, signal))

def dfii_write(wb, phase_datas, wrphase):
    for p, data in enumerate(phase_datas):
        dfii_px(wb, p, "wrdata").write(data)
    dfii_px(wb, wrphase, "address").write(0)
    dfii_px(wb, wrphase, "baddress").write(0)
    dfii_px(wb, wrphase, "command").write(dfii_command_cas|dfii_command_we|dfii_command_cs|dfii_command_wrdata)
    dfii_px(wb, wrphase, "command_issue").write(1)

def dfii_read(wb, nphases, rdphase):
    dfii_px(wb, rdphase, "address").write(0)
    dfii_px(wb, rdphase, "baddress").write(0)
    dfii_px(wb, rdphase, "command").write(dfii_command_cas|dfii_command_cs|dfii_command_rddata)
    dfii_px(wb, rdphase, "command_issue").write(1)
    return [dfii_px(wb, p, "rddata").read() for p in range(nphases)]

# PHY delay/bitslip settings ---------------------

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

# Read leveling (software control) ---------------

def get_byte(i, data):
    return (data & (0xff << (8*i))) >> (8*i)

class Settings:
    def __init__(self, nmodules, bitslips, delays, nphases, wrphase, rdphase):
        # Defined by:
        # `#define SDRAM_PHY_MODULES` in sdram_phy.h
        # `#define DFII_PIX_DATA_BYTES DFII_PIX_DATA_SIZE*CSR_DATA_BYTES` in sdram.c
        # `#define CSR_DATA_BYTES CONFIG_CSR_DATA_WIDTH/8` in sdram.c
        # `#define CONFIG_CSR_DATA_WIDTH` in soc.h
        # `#define DFII_PIX_DATA_SIZE` in soc.h
        # `#define DFII_PIX_DATA_SIZE CSR_SDRAM_DFII_PI0_WRDATA_SIZE` in sdram_phy.h
        # `#define CSR_SDRAM_DFII_PI0_WRDATA_SIZE 8` in csr.h
        self.nmodules = nmodules
        # Defined by:
        # `#define SDRAM_PHY_DELAYS` in sdram_phy.h
        self.bitslips = bitslips
        # Defined by:
        # `#define SDRAM_PHY_BITSLIPS` in sdram_phy.h
        self.delays = delays
        # from PhySettings
        self.nphases = nphases
        self.wrphase = wrphase
        self.rdphase = rdphase

# Perform single read+write and return number of errors
def read_level_test(wb, settings, module, seed=42, verbose=None):
    rng = random.Random(seed)

    # generate pattern
    data_pattern = []
    phase_bytes = wb.regs.sdram_dfii_pi0_wrdata.data_width // 8
    for p in range(settings.nphases):
        for b in range(phase_bytes):
            data_pattern.append(rng.randint(0, 256))

    def per_phase(data):
        for p in range(settings.nphases):
            val = 0
            for b in range(phase_bytes):
                val <<= 8
                val |= data_pattern[p*phase_bytes + b]
            yield val

    # activate row
    sdram_cmd(wb, 0, 0, dfii_command_ras | dfii_command_cs)

    # send write command
    dfii_write(wb, list(per_phase(data_pattern)), wrphase=settings.wrphase)

    # send read command
    rdatas = dfii_read(wb, settings.nphases, rdphase=settings.rdphase)

    if verbose is not None:
        print()
    errors = 0
    for rdata, wdata in zip(rdatas, per_phase(data_pattern)):
        for i in [1, 2]:
            rbyte = get_byte(i*settings.nmodules + module, rdata)
            wbyte = get_byte(i*settings.nmodules + module, wdata)
            if rbyte != wbyte:
                errors += 1
                if verbose is not None:
                    _compare(rbyte, wbyte, fmt=verbose, nbytes=1)

    # precharge row
    sdram_cmd(wb, 0, 0, dfii_command_ras | dfii_command_we | dfii_command_cs)

    return errors

# Find best bitslip+delay configuration based on leveling results
# scores: {bitslip: {delay: errors}, ...}
def read_level_find_best(scores):
    bs_windows = {}
    for bs, dly_scores in scores.items():
        # find read windows
        windows = []
        window_start = None
        in_window = False
        for dly, errors in dly_scores.items():
            if errors == 0 and not in_window:
                window_start = dly
                in_window = True
            elif in_window and errors != 0:
                windows.append((window_start, dly))
                in_window = False
        if in_window:
            windows.append((window_start, dly))

        # find longest window
        best_window = None
        if len(windows):
            best_window = max(windows, key=lambda win_range: win_range[1] - win_range[0])
        bs_windows[bs] = best_window

    def cmp_bs_windows(bs):
        if bs_windows[bs] is None:
            return -1
        length = bs_windows[bs][1] - bs_windows[bs][0]
        return length

    best_bs = max(bs_windows, key=cmp_bs_windows)
    if bs_windows[best_bs] is None:
        return None

    # best delay is in the middle of the window
    best_delay = (bs_windows[best_bs][0] + bs_windows[best_bs][1]) // 2
    best_length = bs_windows[best_bs][1] - bs_windows[best_bs][0]
    return best_bs, best_delay, best_length

# Read level current module
def read_level_module(wb, settings, module, delays_step=1, **kwargs):
    read_bitslip_rst(wb)

    scores = defaultdict(dict)  # {bitslip: {delay: errors}, ...}
    for bs in range(settings.bitslips):
        read_delay_rst(wb)
        print("Bitslip {:02d}: |".format(bs), end="", flush=True)

        for dly in range(settings.delays):
            if dly % delays_step == 0:
                errors = read_level_test(wb, settings, module, **kwargs)
                scores[bs][dly] = errors
                print("1" if errors == 0 else "0", end="", flush=True)
            read_delay_inc(wb)

        print("|")
        read_bitslip_inc(wb)

    best = read_level_find_best(scores)
    if best is None:
        print("Read leveling failed")
        return

    best_bs, best_dly, best_len = best
    print("Best: bitslip = {}, delay = {} (+-{})".format(best_bs, best_dly, best_len//2))
    read_bitslip_set(wb, best_bs)
    read_delay_set(wb, best_dly)

# Perform whole read leveling procedure
def read_level(wb, settings, **kwargs):
    sdram_software_control(wb)
    for module in range(settings.nmodules):
        print("Module {}".format(module))
        delay_select_modules(wb, [module])
        read_level_module(wb, settings, module, **kwargs)

# -----------------------

def default_arty_settings():
    return Settings(
        nmodules = 2,
        bitslips = 8,
        delays   = 32,
        nphases  = 4,
        rdphase  = 2,
        wrphase  = 3,
    )

if __name__ == "__main__":
    from litex import RemoteClient

    wb = RemoteClient()
    wb.open()

    read_level(wb, default_arty_settings())

    wb.close()
