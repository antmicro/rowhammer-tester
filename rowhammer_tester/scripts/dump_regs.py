#!/usr/bin/env python3

import argparse
import itertools
import json
import os
import time

import pandas as pd
import pexpect

from rowhammer_tester.scripts.utils import (
    RemoteClient,
    get_litedram_settings,
    litex_server,
    read_ident,
)

WIDTH = 8
MRS = {
    # Number of Mode Registers | Number of devices
    "DDR5": (255, 4),
    "LPDDR5": (61, 1),
}


def print_int(value):
    if not isinstance(value, int):
        return value
    mask = 2**8 - 1
    res = [(value >> (i * 8)) & mask for i in range(WIDTH // 8)]
    return " ".join(f"{r:08b}" for r in res)


def read_registers(console, num_of_mrs, num_of_devices, num_of_channels):
    prompt = "^.*litex[^>]*> "  # '92;1mlitex\x1b[0m> '

    def mr_read(device, channel, register_no):
        console.sendline(f"sdram_mr_read {channel} {device} {register_no}")
        console.expect("Switching SDRAM to software control.")
        console.expect(f"Reading from channel:{channel} device:{device} MR{register_no}")
        console.expect("Value:")
        console.expect(prompt)

        value = None
        for line in console.after.decode().splitlines():
            line = line.strip()
            try:
                value = int(line, 16)
            except Exception:
                continue
        return value

    console.sendline()
    console.expect(prompt)

    # Cells are displayed as "XXXXXXXX XXXXXXXX XXXXXXXX..."
    # Actual row width (binary number width + spaces) - length for MSB on the right side
    cell_length = WIDTH + WIDTH // 8 - 1 - 2
    header = "{:<{}} {}".format(WIDTH-1, cell_length, 0)
    mr_dump = {}
    for chan in range(num_of_channels):
        regs_per_chan = {}
        for dev in range(num_of_devices):
            regs_per_dev = {"": header}
            for i in range(num_of_mrs):
                regs_per_dev[f"MR{i}"] = mr_read(dev, chan, i)
            regs_per_chan[f"Device {dev}"] = regs_per_dev
        mr_dump[f"Channel {'B' if chan else 'A'}"] = regs_per_chan
    return mr_dump


def report_mrs():
    settings = get_litedram_settings().phy
    memtype = settings.memtype
    sub_channels = settings.with_sub_channels

    if memtype not in MRS:
        raise ValueError(f"Reading mode registers is not supported for {memtype}.")

    print(f"Reading {memtype} mode registers...")
    script_dir = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
    console = pexpect.spawn("python bios_console.py -t litex_term", cwd=script_dir, timeout=30)

    spinner = itertools.cycle("/-\\-")
    spinner_fmt = "[{}] Waiting for CPU to finish memory training"
    while hasattr(wb.regs, "ddrctrl_init_done") and not wb.regs.ddrctrl_init_done.read():
        print(spinner_fmt.format(next(spinner)), end="\r")
        time.sleep(1)

    print("Ready", " " * len(spinner_fmt), flush=True)
    return read_registers(console, *MRS[memtype], 1 if not sub_channels else 2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mr-regs-out-file",
        default="mr_regs.json",
        help="File to save mode registers contents to (JSON)",
    )
    parser.add_argument(
        "--soc-regs-out-file",
        default="soc_regs.json",
        help="File to SoC registers contents to (JSON)",
    )
    parser.add_argument("--srv", action="store_true", help="Start litex server in background")
    args = parser.parse_args()

    if args.srv:
        litex_server()

    wb = RemoteClient()
    wb.open()
    print("Board info:", read_ident(wb))

    # Dump all CSR registers of the SoC
    soc_regs = {}
    print("SoC Control / Status registers:")
    for name, reg in wb.regs.__dict__.items():
        val = reg.read()
        print(f"0x{reg.addr:08x}: 0x{val:08x} {name}")
        soc_regs[hex(reg.addr)] = {"value": val, "name": name}

    with open(args.soc_regs_out_file, "w") as f:
        json.dump(soc_regs, f)
    print(f"SoC Registers values saved to file: {args.soc_regs_out_file}")

    pd.set_option("colheader_justify", "center")
    mrs = report_mrs()
    dfs = []
    for chan in mrs.keys():
        df = pd.DataFrame.from_dict(mrs[chan], orient="index").transpose()
        # Display numbers in binary format
        dfs.append(df.map(print_int))
    print(pd.concat(dfs, keys=mrs.keys(), axis=1).to_string())

    with open(args.mr_regs_out_file, "w") as f:
        json.dump(mrs, f)
    print(f"Mode Registers values saved to file: {args.mr_regs_out_file}")
    wb.close()
