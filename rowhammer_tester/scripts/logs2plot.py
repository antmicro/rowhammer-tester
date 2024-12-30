#!/usr/bin/env python3
"""
This script generates plots from rowhammer attack logs using matplotlib.
Depending on chosen mode, it will generate one or many separate plots.
"""

import argparse
import json
import os
from math import floor
from pathlib import Path
from typing import Optional, List, Tuple
from itertools import repeat, chain

import numpy as np
from logs2dq import DQ_PADS
from logs2dq import plot as plot_dqs
from matplotlib import cm, colors
from matplotlib import pyplot as plt

from rowhammer_tester.scripts.utils import get_generated_file

dq_data: list = []
PLOT_STYLE = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "antmicro.mplstyle"
)


def plot_single_attack(
    data: dict, rows: int, cols: int, col_step=32, max_row_cnt=128, title=""
):
    affected_rows_count = len(data["errors_in_rows"])

    # row_labels correspond to actual row numbers, but row_vals
    # start from 0, to prevent displaying rows between them
    row_labels: list[str] = []
    row_vals: list[int] = []

    # cols_vals are normal column numbers
    col_vals: list[int] = []

    row_step = (
        1 if affected_rows_count <= max_row_cnt else affected_rows_count // max_row_cnt
    )
    last_row = None
    last_num = 0
    begin_row = None
    y_edges: list[int] = []
    count = -1

    for i, (row, row_errors) in enumerate(data["errors_in_rows"].items()):
        if row_step > 1 and count == -1:
            begin_row = row
            y_edges.append(i)
        count += 1
        last_row = row
        last_num = i
        if row_step > 1 and count == row_step - 1:
            row_labels.append(f"{begin_row}...{last_row}")
        elif row_step == 1:
            row_labels.append(row)
        if count == row_step - 1:
            count = -1
        for col, col_errors in row_errors["col"].items():
            for _ in col_errors:
                row_vals.append(i)
                col_vals.append(int(col))

    if row_step > 1:
        y_edges.append(last_num + 1)
        if count > -1:
            row_labels.append(f"{begin_row}...{last_row}")

    # Set to 0 if no errors encountered
    min_row_val = min(row_vals) if row_vals else 0
    max_row_val = max(row_vals) if row_vals else rows - 1

    bins = [
        range(0, cols + 1, col_step),
        np.arange(min_row_val - 0.5, max_row_val + 1, 1) if row_step == 1 else y_edges,
    ]

    # custom cmap with white color for 0
    custom_cmap = colors.ListedColormap(["white", *cm.get_cmap("viridis").colors])
    h, _, _, _ = plt.hist2d(
        col_vals,
        row_vals,
        bins=bins,
        range=[[0, cols // col_step], [min_row_val, max_row_val]],
        cmap=custom_cmap,
    )

    plt.xlabel("Column")
    plt.xticks(range(0, cols + 1, col_step))

    plt.ylabel("Row")
    plt.yticks(range(0, affected_rows_count, row_step), row_labels)

    # limit number of colorbar ticks
    # if left unchanged they can be floats, which looks bad
    max_errors = int(h.max())
    ticks_step = max(1, int(max_errors // 20))
    plt.colorbar(
        mappable=cm.ScalarMappable(norm=colors.Normalize(0, max_errors + 1)),
        ticks=range(0, max_errors + 1, ticks_step),
    )

    plt.title(title)
    plt.show()


def plot_aggressors_vs_victims_single(data: dict, annotate: str = "bitflips"):
    aggressors = data.pop("aggressors")
    dqs: list[int] = []
    rows: list[int] = []
    bitflips: list[int] = []
    plt.style.use(PLOT_STYLE)

    # Aggressors (a) with victims (v) and bitflips (b) packed into tuple (a, v, b)
    avb_packed: list[tuple(int, int, int)] = []

    # Put aggressors and its victims into lists for hist2d
    for row, bits in data.items():
        for idx, flip_count in enumerate(bits):

            rows.append(row)
            dqs.append(idx)
            bitflips.append(flip_count)

            # Pack data for annotation
            avb_packed.append((row, idx, flip_count))

    min_victim = min(sorted(rows)) if rows else 0
    max_victim = max(sorted(rows)) if rows else 0
    min_aggressor = min(sorted(aggressors)) if dqs else 0
    max_aggressor = max(sorted(aggressors)) if dqs else 0

    bins = [DQ_PADS, max_victim - min_victim + 1]
    hist_range = [
        [-0.5, DQ_PADS - 0.5],
        [min_victim - 0.5, max_victim + 0.5],
    ]

    # Custom color map with white color for 0
    custom_cmap = colors.ListedColormap(["#2E303E", *cm.get_cmap("plasma").colors])

    fig, ax = plt.subplots()
    fig.set_size_inches(16, 4)

    h, _, _, _ = ax.hist2d(
        dqs,
        rows,
        bins=bins,
        range=hist_range,
        weights=bitflips,
        cmap=custom_cmap,
    )
    y_ax: List[int] = []
    for ag in aggressors:
        y_ax.extend(repeat(ag, DQ_PADS))
    sc = ax.scatter(list(repeat(range(0, DQ_PADS), len(aggressors))), y_ax, marker="x")

    # Do not annotate by default since it slows down a plot and it makes it hard
    # to read without zooming in
    if annotate == "bitflips":
        for a, v, b in avb_packed:
            if b == 0:
                continue
            ax.text(
                v,
                a,
                f"{int(b)}",
                color="w",
                ha="center",
                va="center",
                fontweight="bold",
            )

    ax.set_ylabel("Row")
    yt = range(
        min(min_victim, min_aggressor - 1) - 1, max(max_victim, max_aggressor) + 2
    )
    ax.set_yticks(yt)
    plt.ylim(min(yt), max(yt))

    ax.set_xlabel("DQ")
    ax.set_xticks(range(0, DQ_PADS))
    ax.set_aspect("equal", adjustable="box")
    # Limit number of colorbar ticks
    # if left unchanged they can be floats, which looks bad
    max_errors = int(h.max())
    ticks_step = max(1, int(max_errors // 20))

    ax.grid(visible=True, which="both", color="gray", alpha=0.2, linestyle="-")

    plt.colorbar(
        mappable=cm.ScalarMappable(
            norm=colors.Normalize(0, max_errors), cmap=custom_cmap
        ),
        ticks=range(0, max_errors + 1, ticks_step),
        location="bottom",
    )
    if len(aggressors) == 1:
        plt.title(f"Single Sided Attack (Attacker row: {aggressors[0]})")
    else:
        plt.title(
            f"Dual Sided Attack (Attacker rows: {aggressors[0]}, {aggressors[1]})"
        )

    plt.show()


def plot_aggressors_vs_victims(
    data: List[Tuple[List[int], list]], annotate: str, png: Optional[str]
):
    aggressors: list[list[int]] = []
    victims: list[int] = []
    bitflips: list[int] = []
    attempts: list[int] = []
    plt.style.use(PLOT_STYLE)

    # Aggressors (a) with victims (v) and bitflips (b) packed into tuple (a, v, b)
    avb_packed: list[tuple(int, int, int)] = []

    dq_data.clear()
    # Put aggressors and its victims into lists for hist2d
    attempt = -1
    for aggressor, victim in data:
        # Each victim must have its corresponding aggressor
        attempt += 1
        attack = {"aggressors": aggressor}
        aggressors.append(aggressor)
        for v in victim:
            # From json file - v[1] is a single victim row hierarchy
            bitflip_amount = v[1]["bitflips"]
            row_number = v[1]["row"]
            cols = v[1]["col"]

            victims.append(row_number)
            bitflips.append(bitflip_amount)
            attempts.append(attempt)

            # Pack data for annotation
            avb_packed.append((attempt, row_number, bitflip_amount))

            # Save DQ data for single aggressor vs victim
            dq_counters = count_bitflips_per_dq(cols)
            attack[row_number] = dq_counters
        dq_data.append(attack)

    min_attempts, max_attempts = 0, len(aggressors) - 1
    min_victim = min(victims) if victims else 0
    max_victim = max(victims) if victims else 0
    min_aggressor = min(min(aggressors)) if aggressors else 0
    max_aggressor = max(max(aggressors)) if aggressors else 0

    bins = [(max_attempts - min_attempts + 1) * 2, max_victim - min_victim + 1]
    hist_range = [
        [min_attempts - 0.25, max_attempts + 0.75],
        [min_victim - 0.5, max_victim + 0.5],
    ]

    # Custom color map with white color for 0
    custom_cmap = colors.ListedColormap(["#2E303E", *cm.get_cmap("plasma").colors])

    fig, ax = plt.subplots()
    fig.set_size_inches(16, 12)
    fig.canvas.mpl_connect("button_press_event", on_click)

    h, _, _, _ = ax.hist2d(
        attempts,
        victims,
        bins=bins,
        range=hist_range,
        weights=bitflips,
        cmap=custom_cmap,
    )
    aggressors_all = range(min_aggressor, max_aggressor + 1)
    xat = []
    yag = []
    for idx in range(len(aggressors)):
        xat.extend(repeat(idx, len(aggressors[idx])))
        yag.extend(aggressors[idx])
    sc = ax.scatter(xat, yag, marker="x")
    ax.legend([sc], ["Row under attack"], fontsize="small", loc="upper left")

    # Do not annotate by default since it slows down a plot and it makes it hard
    # to read without zooming in
    if annotate == "bitflips":
        for a, v, b in avb_packed:
            ax.text(
                a,
                v,
                f"{b}",
                color="w",
                ha="center",
                va="center",
                fontweight="bold",
            )

    ax.set_ylabel("Victim")
    ax.set_yticks(
        range(min(min_victim, min_aggressor - 1), max(max_victim, max_aggressor) + 1)
    )

    ax.set_xlabel("Target")
    ax.set_xticks(range(min_attempts, max_attempts + 1))
    plt.xlim(min_attempts - 0.25, max_attempts + 0.25)

    # Limit number of colorbar ticks
    # if left unchanged they can be floats, which looks bad
    max_errors = int(h.max())
    ticks_step = max(1, int(max_errors // 20))

    ax.grid(visible=True, which="both", color="gray", alpha=0.2, linestyle="-")

    plt.colorbar(
        mappable=cm.ScalarMappable(
            norm=colors.Normalize(0, max_errors), cmap=custom_cmap
        ),
        ticks=range(0, max_errors + 1, ticks_step),
    )
    plt.title(
        f"Aggressors ({min_aggressor}, {max_aggressor}) vs victims ({min_victim}, {max_victim})"
    )

    if png is None:
        plt.show()
    else:
        plt.savefig(png, dpi=600)


def count_bitflips_per_dq(data: dict):
    """Count bitflips per DQ pad in data of a single aggressor vs victim"""
    counts = np.zeros(DQ_PADS)

    for _, single_read in data.items():
        for bitflip in single_read:
            counts[bitflip % DQ_PADS] += 1

    return counts


def on_click(event):
    if plt.get_current_fig_manager().toolbar.mode != "":
        return
    try:
        if 0.25 <= event.xdata % 1 < 0.75:
            raise TypeError
        x = floor(event.xdata + 0.5)
        y = floor(event.ydata + 0.5)
        dq_counters = dq_data[x]
        plot_aggressors_vs_victims_single(dq_counters)
    except KeyError:
        print(f"No data about attack - aggressor({x}) vs victim({y}).")
        return
    except TypeError:
        print("Press detected out of bounds.")
        return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("log_file", help="file with log output")
    parser.add_argument(
        "--plot-columns",
        type=int,
        default=32,
        help="how many columns to show in resulting grid",
    )
    parser.add_argument(
        "--aggressors-vs-victims",
        action="store_true",
        help="Plot agressors against their victims.",
    )
    parser.add_argument(
        "--annotate",
        type=str,
        default="color",
        choices=["color", "bitflips"],
        help="Annotate heat map with number of bitflips or just a color (default: color).",
    )
    parser.add_argument(
        "--plot-max-rows",
        type=int,
        default=128,
        help="how many rows to show in resulting grid",
    )
    parser.add_argument(
        "-p",
        "--png",
        nargs="?",
        const="plot.png",
        default=None,
        help="Export plot to png file instead displaying (default: './plot.png').",
    )
    args = parser.parse_args()

    settings_file = Path(get_generated_file("litedram_settings.json"))
    with settings_file.open() as fd:
        settings = json.load(fd)

    COLS = 2 ** settings["geom"]["colbits"]
    ROWS = 2 ** settings["geom"]["rowbits"]

    log_file = Path(args.log_file)
    with log_file.open() as fd:
        log_data = json.load(fd)

    for _, attack_set_results in log_data.items():
        aggressors_vs_victims = []
        # Remove read_count as it's only disturbing here
        if "read_count" in attack_set_results:
            attack_set_results.pop("read_count")

        # Single attack hierarchy
        for attack, attack_results in attack_set_results.items():
            if attack.startswith("pair"):
                hammered_rows = [
                    attack_results["hammer_row_1"],
                    attack_results["hammer_row_2"],
                ]
                title = f"Hammered rows: {hammered_rows}"
            elif attack.startswith("sequential"):
                start_row = attack_results["row_pairs"][0][1]
                end_row = attack_results["row_pairs"][-1][1]
                title = f"Sequential attack on rows from {start_row} to {end_row}"

                if args.aggressors_vs_victims:
                    print(
                        "ERROR: Sequential attacks are not hammering a single row."
                        " Unable to compare aggressors against victims."
                    )
                    exit()

            # Collect all attack data into one dict if we plot aggressors vs victims
            if args.aggressors_vs_victims:
                # We don't need anything but victim rows hierarchy to generate plot
                victim_rows = []
                for row in attack_results["errors_in_rows"].items():
                    victim_rows.append(row)

                aggressors_vs_victims.append((hammered_rows, victim_rows))

            # Otherwise plot single attack immediately
            else:
                plot_single_attack(
                    attack_results,
                    ROWS,
                    COLS,
                    COLS // args.plot_columns,
                    args.plot_max_rows,
                    title=title,
                )
        if args.aggressors_vs_victims:
            plot_aggressors_vs_victims(aggressors_vs_victims, args.annotate, args.png)
