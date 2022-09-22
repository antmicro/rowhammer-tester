#!/usr/bin/env python3
"""
This script generates plots from rowhammer attack logs using matplotlib
Each attack is a separate plot representing bitflips grouped per DQ pad.
Bars represent DQ pads and are colored to differentiate modules.
"""

import argparse
import json

from pathlib import Path
from matplotlib import pyplot as plt
import numpy as np

DQ_PADS = 64
DQ_RATIO = 4


def plot(
    values: np.ndarray,
    stderror: np.ndarray = None,
    title: str = "",
    log_scale: bool = False,
):
    """Show plot with DQ pads grouped per module"""
    modules = int(DQ_PADS / DQ_RATIO)

    fig, ax = plt.subplots()
    ax.set_xlabel("DQ pad")
    ax.set_xticks(list(range(0, DQ_PADS, DQ_RATIO)) + [DQ_PADS - 1])
    ax.set_ylabel("Bitflips")

    for m in range(modules):
        start, end = DQ_RATIO * m, DQ_RATIO * (m + 1)
        x = range(start, end)
        y = values[start:end]

        if stderror is not None:
            std = stderror[start:end]
            lower_std = [a - 1e-9 if a < b else b for a, b in zip(y, std)]
            yerr = (lower_std, std)
        else:
            yerr = None

        ax.bar(x, y, yerr=yerr)

    if log_scale:
        ax.set_yscale("log")

    ax.set_title(title)

    fig.show()


def count_bitflips_per_dq(data: dict):
    """Count bitflips per DQ pad in data from a single attack"""
    counts = np.zeros(DQ_PADS)

    for _, row_errors in data["errors_in_rows"].items():
        for _, single_read in row_errors["col"].items():
            for bitflip in single_read:
                counts[bitflip % DQ_PADS] += 1

    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("log_file", help="file with log output")
    parser.add_argument("--per-attack", action="store_true", help="show plot for each attack")
    parser.add_argument("--log-scale", action="store_true", help="use logarithmic sale for Y axis")
    parser.add_argument("--dq", default=4, type=int, help="DQ to DQS ratio")
    args = parser.parse_args()

    DQ_RATIO = args.dq

    log_file = Path(args.log_file)
    with log_file.open() as fd:
        log_data = json.load(fd)

    all_dq_counters = np.zeros((0, DQ_PADS))
    # read_count / read_count_range level
    for read_count, attack_set_results in log_data.items():
        # remove read_count as it's only interrupting here
        if "read_count" in attack_set_results:
            attack_set_results.pop("read_count")

        # single attack level
        for attack, attack_results in attack_set_results.items():
            dq_counters = count_bitflips_per_dq(attack_results)
            if args.per_attack:
                if attack.startswith("pair"):
                    hammered_rows = (attack_results["hammer_row_1"], attack_results["hammer_row_2"])
                    title = f"Hammered rows: {hammered_rows}"
                elif attack.startswith("sequential"):
                    start_row = attack_results["row_pairs"][0][1]
                    end_row = attack_results["row_pairs"][-1][1]
                    title = f"Sequential attack on rows from {start_row} to {end_row}"
                plot(dq_counters, title=title, log_scale=args.log_scale)
            all_dq_counters = np.append(all_dq_counters, [dq_counters], axis=0)

    all_mean = all_dq_counters.mean(axis=0)
    all_stdev = all_dq_counters.std(axis=0)
    plot(all_mean, all_stdev, "Mean bitflips across all attacks", log_scale=args.log_scale)
