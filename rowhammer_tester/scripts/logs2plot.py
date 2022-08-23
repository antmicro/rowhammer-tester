#!/usr/bin/env python3
"""
This script generates plots from rowhammer attack logs using matplotlib
Each attack is a separate plot
"""

import os
import argparse
import json

from pathlib import Path
from matplotlib import cm
from matplotlib import colors
from matplotlib import pyplot as plt
import numpy as np

from rowhammer_tester.scripts.utils import get_generated_file


def plot(data: dict, _rows: int, cols: int, col_step=32, title=""):
    affected_rows_count = len(data["errors_in_rows"])

    # row_labels correspond to actual row numbers, but row_vals
    # start from 0, to prevent displaying rows between them
    row_labels: list[str] = []
    row_vals: list[int] = []

    # cols_vals are normal column numbers
    col_vals: list[int] = []

    for i, (row, row_errors) in enumerate(data["errors_in_rows"].items()):
        row_labels.append(row)
        for col, col_errors in row_errors["col"].items():
            for _ in col_errors:
                row_vals.append(i)
                col_vals.append(int(col))

    bins = [range(0, cols + 1, col_step), np.arange(min(row_vals) - 0.5, max(row_vals) + 1, 1)]

    # custom cmap with white color for 0
    custom_cmap = colors.ListedColormap(["white", *cm.get_cmap("viridis").colors])

    h, _, _, _ = plt.hist2d(
        col_vals,
        row_vals,
        bins=bins,
        range=[[0, cols // col_step], [min(row_vals), max(row_vals)]],
        cmap=custom_cmap)

    plt.xlabel('Column')
    plt.xticks(range(0, cols + 1, col_step))

    plt.ylabel('Row')
    plt.yticks(range(affected_rows_count), row_labels)

    # limit number of colorbar ticks
    # if left unchanged they can be floats, which looks bad
    max_errors = int(h.max())
    ticks_step = max(1, int(max_errors // 20))
    plt.colorbar(ticks=range(0, max_errors + 1, ticks_step))

    plt.title(title)
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("log_file", help="file with log output")
    parser.add_argument(
        "--plot-columns", type=int, default=32, help="how many columns to show in resulting grid")
    # TODO: add option to save plots to files without showing GUI
    args = parser.parse_args()

    settings_file = Path(get_generated_file("litedram_settings.json"))
    with settings_file.open() as fd:
        settings = json.load(fd)

    COLS = 2**settings["geom"]["colbits"]
    ROWS = 2**settings["geom"]["rowbits"]

    log_file = Path(args.log_file)
    with log_file.open() as fd:
        log_data = json.load(fd)

    # read_count / read_count_range level
    for read_count, attack_set_results in log_data.items():
        # remove read_count as it's only interrupting here
        if "read_count" in attack_set_results:
            attack_set_results.pop("read_count")

        # single attack level
        for attack, attack_results in attack_set_results.items():
            if attack.startswith("pair"):
                hammered_rows = (attack_results["hammer_row_1"], attack_results["hammer_row_2"])
                title = f"Hammered rows: {hammered_rows}"
            elif attack.startswith("sequential"):
                start_row = attack_results["row_pairs"][0][1]
                end_row = attack_results["row_pairs"][-1][1]
                title = f"Sequential attack on rows from {start_row} to {end_row}"

            plot(
                attack_results,
                ROWS,
                COLS,
                COLS // args.plot_columns,
                title=title,
            )
