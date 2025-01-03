#!/usr/bin/env python3
"""
This script generates plots from rowhammer attack logs using matplotlib.
Depending on chosen mode, it will generate one or many separate plots.
"""

import argparse
import json
import os
from copy import deepcopy
from itertools import repeat
from math import ceil, floor
from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np
from logs2dq import DQ_PADS
from matplotlib import cm, colors
from matplotlib import pyplot as plt

from rowhammer_tester.scripts.utils import get_generated_file

dq_data: list = []
PLOT_STYLE = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "resources", "antmicro.mplstyle"
)


def plot_interactive(
    rows: List[int],
    aggressors: Union[List[int], List[List[int]]],
    xdata: List[int],
    bitflips: List[int],
    avb_packed: List[Tuple[int, int, int]],
    column_count: int,
    xlabel: str,
    title: str,
    annotate: str,
    colorbar: bool,
    png: Optional[str],
    group_cols: int,
    group_rows: int,
    avv: bool = False,
):

    min_victim = min(rows) if rows else 0
    max_victim = max(rows) if rows else 0
    x_ax: List[int] = []
    y_ax: List[int] = []
    if all(isinstance(ag, int) for ag in aggressors):
        min_aggressor = min(aggressors) if aggressors else 0
        max_aggressor = max(aggressors) if aggressors else 0
        for ag in aggressors:
            y_ax.extend(repeat(ag, column_count))  # type: ignore
        x_ax = [x for rep in repeat(range(column_count), len(aggressors)) for x in rep]
    else:
        assert all(isinstance(ag, list) for ag in aggressors)
        min_aggressor = min(min(aggressors)) if aggressors else 0  # type: ignore
        max_aggressor = max(max(aggressors)) if aggressors else 0  # type: ignore
        for idx in range(len(aggressors)):
            x_ax.extend(repeat(idx, len(aggressors[idx])))  # type: ignore
            y_ax.extend(aggressors[idx])  # type: ignore

    fig, ax = plt.subplots()
    fig.set_size_inches(16, 16)
    abs_ylim = (
        min(min_victim, min_aggressor) - 1,  # type: ignore
        max(max_victim, max_aggressor) + 1,  # type: ignore
    )
    cbar = None
    press_callback_en = False

    def reset_axes():
        plt.ylim(abs_ylim)
        plt.xlim(-0.5, column_count - 0.5)

    def draw_plot():
        nonlocal cbar, press_callback_en
        press_callback_en = False
        xlim, ylim = list(plt.xlim()), list(plt.ylim())
        ax.clear()
        xlim[0] = int(floor(xlim[0]) + 0.5)
        ylim[0] = int(floor(ylim[0]) + 0.5)
        xl = xlim[1] - xlim[0] + 0.5
        xstep = ceil(xl / group_cols)
        xl = ceil(xl / xstep) * xstep
        xlim[1] = int(xl + xlim[0])

        yl = ylim[1] - ylim[0]
        ystep = ceil(yl / group_rows)
        yl = ceil(yl / ystep) * ystep
        ylim[1] = int(yl + ylim[0])

        bins = [int(xl / xstep), int(yl / ystep)]
        qbins = deepcopy(bins)

        hist_range = [[xlim[0], xlim[1]], [ylim[0], ylim[1]]]
        qxdata, qrows, qbitflips = [], [], []
        for i in reversed(range(len(xdata))):
            if (xlim[0] <= xdata[i] < xlim[1]) and (ylim[0] <= rows[i] < ylim[1]):
                qxdata.append(xdata[i])
                qrows.append(rows[i])
                qbitflips.append(bitflips[i])

        if avv and xstep == 1 and ystep == 1:
            press_callback_en = True
            qbins[0] = bins[0] * 2 + 1
            hist_range[0] = [xlim[0] - 0.25, xlim[1] + 0.25]
            qxdata = [x + 0.5 for x in qxdata]

        h, _, _, _ = ax.hist2d(
            qxdata,
            qrows,
            bins=qbins,
            range=hist_range,
            weights=qbitflips,
            cmap="plasma",
            cmin=1,
        )
        sc = ax.scatter(
            [x + xstep / 2 for x in x_ax],
            [y + ystep / 2 for y in y_ax],
            10,
            marker="x",
        )
        _xticks = range(xlim[0], xlim[1] + 1, xstep)
        xticks = [x + xstep / 2 for x in _xticks]
        xticks_str = [f"{x}" if xstep == 1 else f"{x}..{x+xstep -1}" for x in _xticks]
        _yticks = range(ylim[0], ylim[1] + 1, ystep)
        yticks = [y + ystep / 2 for y in _yticks]
        yticks_str = [f"{y}" if ystep == 1 else f"{y}..{y+ystep -1}" for y in _yticks]

        ax.set_xlabel(xlabel)
        ax.set_xticks(xticks, xticks_str)
        ax.tick_params(axis="x", labelrotation=45)
        ax.set_ylabel("Row")
        ax.set_yticks(yticks, yticks_str)

        # Do not annotate by default since it slows down a plot and it makes it hard
        # to read without zooming in
        if annotate == "bitflips":
            new_avb = np.zeros((bins[0], bins[1]))
            xlb = (xlim[1] - xlim[0]) / (bins[0])
            ylb = (ylim[1] - ylim[0]) / (bins[1])
            for a, v, b in avb_packed:
                if (
                    b == 0
                    or not (xlim[0] <= v < xlim[1])
                    or not (ylim[0] <= a < ylim[1])
                ):
                    continue
                new_avb[int(floor((v - xlim[0]) / xlb))][
                    int(floor((a - ylim[0]) / ylb))
                ] += b
            for i in range(new_avb.shape[0]):
                for j in range(new_avb.shape[1]):
                    if new_avb[i][j] == 0:
                        continue
                    ax.text(
                        xticks[i],
                        yticks[j],
                        f"{int(new_avb[i][j])}",
                        color="w",
                        ha="center",
                        va="center",
                        fontweight="bold",
                    )

        ax.grid(visible=True, which="both", color="gray", alpha=0.2, linestyle="-")
        plt.xlim(xlim[0] - 0.5, xlim[1] + 0.5)
        plt.ylim(ylim[0] - 0.5, ylim[1] + 0.5)
        ax.set_aspect(xstep / ystep, adjustable="box")
        ax.legend([sc], ["Row under attack"], fontsize="small")
        if colorbar:
            # Limit number of colorbar ticks
            # if left unchanged they can be floats, which looks bad
            min_flips = int(np.nanmin(h))
            max_flips = max(int(np.nanmax(h)), min_flips + 1)
            ticks_step = max(1, int((max_flips - min_flips) // 20))
            cbar = fig.colorbar(
                mappable=cm.ScalarMappable(
                    norm=colors.Normalize(min_flips, max_flips), cmap="plasma"
                ),
                ticks=range(min_flips, max_flips + 1, ticks_step),
                ax=ax,
                cax=None if cbar is None else cbar.ax,
                fraction=0.02,
                pad=0.02,
                aspect=40,
            )

    reset_axes()
    draw_plot()
    plt.suptitle(title)

    toolbar = fig.canvas.toolbar

    def new_home(*_args, **_kwargs):
        print("Reset view")
        reset_axes()
        draw_plot()
        plt.draw()

    if toolbar is not None:
        toolbar._update_view = new_home
    fig.canvas.mpl_connect(
        "button_release_event",
        lambda _event: None if press_callback_en else draw_plot(),
    )
    fig.canvas.mpl_connect(
        "button_press_event",
        lambda event: on_click(event) if press_callback_en else None,
    )
    if png is None:
        plt.show()
    else:
        plt.savefig(png, dpi=600)


def plot_single_attack(
    data: dict,
    annotate: str = "bitflips",
    xlabel="DQ",
    png: Optional[str] = None,
    colorbar: bool = True,
    col_count: int = 1024,
    group_rows: int = 64,
    group_cols: int = 64,
):
    aggressors = data["aggressors"]
    plt.style.use(PLOT_STYLE)

    columns = (
        len(next(iter(data["victims"].values())))
        if data["victims"].values()
        else col_count
    )

    xdata: list[int] = []
    rows: list[int] = []
    bitflips: list[int] = []
    # Aggressors (a) with victims (v) and bitflips (b) packed into tuple (a, v, b)
    avb_packed: List[Tuple[int, int, int]] = []
    # Put aggressors and its victims into lists for hist2d
    for row, bits in data["victims"].items():
        for idx, flip_count in enumerate(bits):
            rows.append(row)
            xdata.append(idx)
            bitflips.append(flip_count)

            # Pack data for annotation
            avb_packed.append((row, idx, flip_count))

    if len(aggressors) == 1:
        title = f"Single Sided Attack (Attacker row: {aggressors[0]})"
    else:
        title = f"Dual Sided Attack (Attacker rows: {aggressors[0]}, {aggressors[1]})"

    plot_interactive(
        rows,
        aggressors,
        xdata,
        bitflips,
        avb_packed,
        columns,
        xlabel,
        title,
        annotate,
        colorbar,
        png,
        group_cols,
        group_rows,
    )


def plot_aggressors_vs_victims(
    data: List[Tuple[List[int], list]],
    annotate: str,
    png: Optional[str],
    colorbar: bool = True,
    group_rows: int = 64,
    group_cols: int = 64,
):
    aggressors: list[list[int]] = []
    victims: list[int] = []
    bitflips: list[int] = []
    attempts: list[int] = []
    plt.style.use(PLOT_STYLE)

    # Aggressors (a) with victims (v) and bitflips (b) packed into tuple (a, v, b)
    avb_packed: List[Tuple[int, int, int]] = []

    dq_data.clear()
    # Put aggressors and its victims into lists for hist2d
    attempt = -1
    for aggressor, victim in data:
        # Each victim must have its corresponding aggressor
        attempt += 1
        aggressors.append(aggressor)
        attack_victims = {}
        for v in victim:
            # From json file - v[1] is a single victim row hierarchy
            bitflip_amount = v[1]["bitflips"]
            row_number = v[1]["row"]
            cols = v[1]["col"]

            victims.append(row_number)
            bitflips.append(bitflip_amount)
            attempts.append(attempt)

            # Pack data for annotation
            avb_packed.append((row_number, attempt, bitflip_amount))

            # Save DQ data for single aggressor vs victim
            dq_counters = count_bitflips_per_dq(cols)
            attack_victims[row_number] = dq_counters
        attack = {"aggressors": aggressor, "victims": attack_victims}
        dq_data.append(attack)
    amin, amax = min(min(aggressors)), max(max(aggressors))
    title = f"Aggressors ({amin}, {amax}) vs victims ({min(victims)}, {max(victims)})"
    plot_interactive(
        victims,
        aggressors,
        attempts,
        bitflips,
        avb_packed,
        max(attempts),
        "Attempt",
        title,
        annotate,
        colorbar,
        png,
        group_cols,
        group_rows,
        True,
    )


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
        x = floor(event.xdata - 0.5)
        y = floor(event.ydata - 0.5)
        dq_counters = dq_data[x]
    except KeyError:
        print(f"No data about attack - aggressor({x}) vs victim({y}).")
        return
    except TypeError:
        print("Press detected out of bounds.")
        return
    plot_single_attack(dq_counters)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("log_file", help="file with log output")
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
        "-p",
        "--png",
        nargs="?",
        const="plot.png",
        default=None,
        help="Export plot to png file instead of displaying it (default: './plot.png').",
    )
    parser.add_argument(
        "--no-colorbar",
        action="store_true",
        help="Do not add color bar to plot",
    )
    parser.add_argument(
        "-gr",
        "--group-rows",
        type=int,
        default=64,
        help="Group rows into N groups (default N: 64)",
    )
    parser.add_argument(
        "-gc",
        "--group-columns",
        type=int,
        default=64,
        help="Group columns into N groups (default N: 64)",
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
                hammered_rows = [r[1] for r in attack_results["row_pairs"]]
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
                victims = {}
                for row in attack_results["errors_in_rows"].values():
                    row_number = row["row"]
                    cols = row["col"]
                    victims[row_number] = list(repeat(0, COLS))
                    for _, single_read in cols.items():
                        for c in single_read:
                            victims[row_number][c] += 1
                data = {"aggressors": hammered_rows, "victims": victims}

                plot_single_attack(
                    data,
                    annotate=args.annotate,
                    xlabel="Column",
                    png=args.png,
                    colorbar=not args.no_colorbar,
                    col_count=COLS,
                    group_rows=args.group_rows,
                    group_cols=args.group_columns,
                )
        if args.aggressors_vs_victims:
            plot_aggressors_vs_victims(
                aggressors_vs_victims,
                args.annotate,
                args.png,
                colorbar=not args.no_colorbar,
                group_rows=args.group_rows,
                group_cols=args.group_columns,
            )
