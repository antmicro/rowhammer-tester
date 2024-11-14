#!/usr/bin/env python3

import random
import time
from collections import defaultdict
from functools import reduce
from operator import or_

from rowhammer_tester.scripts.utils import (
    RemoteClient,
    compare,
    get_litedram_settings,
    read_ident,
    sdram_software_control,
)

# Fetch DFII command signals form the generated sdram_init.py file
try:
    from sdram_init import *
except ModuleNotFoundError:
    raise ModuleNotFoundError("sdram_init not loaded")

# DRAM commands ----------------------------------


def sdram_cmd(wb, a, ba, command, enable_software_control=True):
    if enable_software_control:
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
    dfii_px(wb, wrphase, "command").write(
        dfii_command_cas | dfii_command_we | dfii_command_cs | dfii_command_wrdata
    )
    dfii_px(wb, wrphase, "command_issue").write(1)


def dfii_read(wb, nphases, rdphase):
    dfii_px(wb, rdphase, "address").write(0)
    dfii_px(wb, rdphase, "baddress").write(0)
    dfii_px(wb, rdphase, "command").write(dfii_command_cas | dfii_command_cs | dfii_command_rddata)
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
    return (data & (0xFF << (8 * i))) >> (8 * i)


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

    @classmethod
    def load(cls):
        settings = get_litedram_settings()
        if settings.phy.phytype in ["USDDRPHY", "USPDDRPHY"]:
            bitslips = 8
            delays = 512
        elif settings.phy.phytype in ["A7DDRPHY", "K7DDRPHY", "V7DDRPHY"]:
            bitslips = 8
            delays = 32
        elif phytype in ["ECP5DDRPHY"]:
            bitslips = 4
            delays = 8
        return cls(
            nmodules=settings.phy.databits // 8,
            bitslips=bitslips,
            delays=delays,
            nphases=settings.phy.nphases,
            wrphase=settings.phy.wrphase,
            rdphase=settings.phy.rdphase,
        )


# Perform single read+write and return number of errors
def read_level_test(wb, settings, module, seed=42, verbose=None):
    rng = random.Random(seed)

    # generate pattern
    data_pattern = []
    phase_bytes = (
        wb.regs.sdram_dfii_pi0_wrdata.data_width * wb.regs.sdram_dfii_pi0_wrdata.length
    ) // 8
    for p in range(settings.nphases):
        for b in range(phase_bytes):
            data_pattern.append(rng.randint(0, 256))

    def per_phase(data):
        for p in range(settings.nphases):
            val = 0
            for b in range(phase_bytes):
                val <<= 8
                val |= data[p * phase_bytes + b]
            yield val

    # activate row
    sdram_cmd(wb, 0, 0, dfii_command_ras | dfii_command_cs, enable_software_control=False)
    time.sleep(0.001)

    # send write command
    dfii_write(wb, list(per_phase(data_pattern)), wrphase=settings.wrphase)
    time.sleep(0.001)

    # send read command
    rdatas = dfii_read(wb, settings.nphases, rdphase=settings.rdphase)
    time.sleep(0.001)

    if verbose is not None:
        print()
    errors = 0
    for rdata, wdata in zip(rdatas, per_phase(data_pattern)):
        for i in [1, 2]:
            rbyte = get_byte(i * settings.nmodules + module, rdata)
            wbyte = get_byte(i * settings.nmodules + module, wdata)
            if rbyte != wbyte:
                errors += 1
                if verbose is not None:
                    compare(rbyte, wbyte, fmt=verbose, nbytes=1)

    # precharge row
    sdram_cmd(
        wb,
        0,
        0,
        dfii_command_ras | dfii_command_we | dfii_command_cs,
        enable_software_control=False,
    )
    time.sleep(0.001)

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
    print("Best: bitslip = {}, delay = {} (+-{})".format(best_bs, best_dly, best_len // 2))
    read_bitslip_set(wb, best_bs)
    read_delay_set(wb, best_dly)


# Perform whole read leveling procedure
def read_level(wb, settings, **kwargs):
    sdram_software_control(wb)
    for module in range(settings.nmodules):
        print("Module {}".format(module))
        delay_select_modules(wb, [module])
        read_level_module(wb, settings, module, **kwargs)


def read_level_hardcoded(wb, config):
    for module, (bitslip, delay) in enumerate(config):
        print("Module {}: bitslip={}, delay={}".format(module, bitslip, delay))
        delay_select_modules(wb, [module])
        read_bitslip_set(wb, bitslip)
        read_delay_set(wb, delay)


# -----------------------


def write_delay_rst(wb):
    wb.regs.ddrphy_wdly_dq_rst.write(1)
    wb.regs.ddrphy_wdly_dqs_rst.write(1)
    for _ in range(wb.regs.ddrphy_half_sys8x_taps.read()):
        wb.regs.ddrphy_wdly_dqs_inc.write(1)


def write_delay_inc(wb):
    wb.regs.ddrphy_wdly_dq_inc.write(1)
    wb.regs.ddrphy_wdly_dqs_inc.write(1)


def write_delay_set(wb, value):
    write_delay_rst(wb)
    for _ in range(value):
        write_delay_inc(wb)


def cdly_rst(wb):
    wb.regs.ddrphy_cdly_rst.write(1)


def cdly_inc(wb):
    wb.regs.ddrphy_cdly_inc.write(1)


def cdly_set(wb, value):
    cdly_rst(wb)
    for _ in range(value):
        cdly_inc(wb)


DDRX_MR1 = 769


def write_leveling_on(wb):
    sdram_cmd(
        wb,
        DDRX_MR1 | (1 << 7),
        1,
        dfii_command_ras | dfii_command_cas | dfii_command_we | dfii_command_cs,
    )
    wb.regs.ddrphy_wlevel_en.write(1)


def write_leveling_off(wb):
    sdram_cmd(
        wb, DDRX_MR1, 1, dfii_command_ras | dfii_command_cas | dfii_command_we | dfii_command_cs
    )
    wb.regs.ddrphy_wlevel_en.write(0)


# TODO: proper leveling, now use hardcoded results
def write_level_hardcoded(wb, cdly, delays):
    sdram_software_control(wb)
    print("Cmd/Clk delay: {}".format(cdly))
    cdly_set(wb, cdly)

    for i, delay in enumerate(delays):
        print("Module {}: delay {}".format(i, delay))
        delay_select_modules(wb, [i])
        write_delay_set(wb, delay)

    write_leveling_off(wb)


# -----------------------

if __name__ == "__main__":
    wb = RemoteClient()
    wb.open()
    print("Board info:", read_ident(wb))

    read_level(wb, Settings.load())

    wb.close()
