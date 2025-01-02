#!/usr/bin/env python3
"""
This script generates plots from rowhammer attack logs using matplotlib.
Depending on chosen mode, it will generate one or many separate plots.
"""

import argparse
import json
import os
from math import floor, ceil
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
    os.path.abspath(os.path.dirname(__file__)), "resources", "antmicro.mplstyle"
)
# Custom color map with aubergine background color for 0
CMAP = colors.ListedColormap(["#2E303E", *cm.get_cmap("plasma").colors])


def plot_single_attack(
    data: dict,
    annotate: str = "bitflips",
    xlabel="DQ",
    png: Optional[str] = None,
    colorbar: bool = True,
    col_chunk: int = 128,
    col_count: int = 1024,
    group_rows: Optional[int] = None,
    group_cols: Optional[int] = None,
):
    aggressors = data.pop("aggressors")
    plt.style.use(PLOT_STYLE)

    columns = len(next(iter(data.values()))) if data.values() else col_count
    chunk_size = min(col_chunk, columns)  # if group_cols is None else columns
    chunks = ceil(columns / chunk_size)

    xdata: list[list[int]] = [[] for _ in range(chunks)]
    rows: list[list[int]] = [[] for _ in range(chunks)]
    bitflips: list[list[int]] = [[] for _ in range(chunks)]
    # Aggressors (a) with victims (v) and bitflips (b) packed into tuple (a, v, b)
    avb_packed: list[list[tuple(int, int, int)]] = [[] for _ in range(chunks)]
    max_flips = 0
    # Put aggressors and its victims into lists for hist2d
    for row, bits in data.items():
        for idx, flip_count in enumerate(bits):
            ch = floor(idx / chunk_size)
            rows[ch].append(row)
            xdata[ch].append(idx)
            bitflips[ch].append(flip_count)
            max_flips = max(max_flips, int(flip_count))

            # Pack data for annotation
            avb_packed[ch].append((row, idx, flip_count))
    min_victim = min(min(rows)) if rows and rows[0] else 0
    max_victim = max(max(rows)) if rows and rows[0] else 0
    min_aggressor = min(aggressors) if aggressors else 0
    max_aggressor = max(aggressors) if aggressors else 0

    fig, axs = plt.subplots(nrows=chunks)
    fig.set_size_inches(16, 4 * chunks)
    yt = range(
        min(min_victim, min_aggressor - 1) - 1, max(max_victim, max_aggressor) + 2
    )

    def reset_axes():
        for chunk in range(chunks):
            ax = axs[chunk] if chunks > 1 else axs
            plt.sca(ax)
            plt.ylim(min(yt), max(yt))
            chmin, chmax = chunk_size * chunk, chunk_size * (chunk + 1)
            plt.xlim(-0.5 + chmin, chmax - 0.5)

    def draw_plot():
        for chunk in range(chunks):
            ax = axs[chunk] if chunks > 1 else axs
            plt.sca(ax)
            xlim, ylim = plt.xlim(), plt.ylim()
            ax.clear()
            chmin, chmax = chunk_size * chunk, chunk_size * (chunk + 1)
            ch_rows = rows[chunk]
            ch_xdata = xdata[chunk]
            ch_bitflips = bitflips[chunk]
            ch_avb_packed = avb_packed[chunk]
            xlim = floor(xlim[0]), ceil(xlim[1])
            ylim = floor(ylim[0]), ceil(ylim[1])
            bins = [
                int(xlim[1] - xlim[0]),
                int(ylim[1] - ylim[0] + 1),
            ]
            
            bins[0] = bins[0] if group_cols is None else int(bins[0]/ceil(bins[0]/group_cols))
            bins[1] = bins[1] if group_rows is None else int(bins[1]/ceil(bins[1]/group_rows))
            new_avb=np.zeros(bins[0], bins[1])
            for a, v, b in ch_avb_packed:
                if (
                    b == 0
                    or not (xlim[0] <= v <= xlim[1])
                    or not (ylim[0] <= a <= ylim[1])
                ):
                    continue
                new_avb[(v-xlim[0])//bins[0]][(a-ylim[0])//bins[1]]+=b

            hist_range = [
                [-0.5 + xlim[0], xlim[1] - 0.5],
                [ylim[0] - 0.5, ylim[1] + 0.5],
            ]

            h, _, _, _ = ax.hist2d(
                ch_xdata,
                ch_rows,
                bins=bins,
                range=hist_range,
                weights=ch_bitflips,
                vmin=0,
                vmax=max_flips,
                cmap=CMAP,
            )
            y_ax: List[int] = []
            for ag in aggressors:
                y_ax.extend(repeat(ag, chunk_size))
            sc = ax.scatter(
                list(repeat(range(chmin, chmax), len(aggressors))), y_ax, 10, marker="x"
            )

            # Do not annotate by default since it slows down a plot and it makes it hard
            # to read without zooming in
            if annotate == "bitflips":
                for a, v, b in ch_avb_packed:
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
            ax.set_yticks(yt)

            ax.set_xlabel(xlabel)

            ax.set_xticks(range(chmin, chmax, ceil((chmax - chmin) / 64)))
            ax.grid(visible=True, which="both", color="gray", alpha=0.2, linestyle="-")
            plt.xlim(xlim)
            plt.ylim(ylim)
            ax.set_aspect("equal", adjustable="box")

    reset_axes()
    draw_plot()

    if colorbar:
        # Limit number of colorbar ticks
        # if left unchanged they can be floats, which looks bad
        ticks_step = max(1, int(max_flips // 20))
        if chunks > 1:
            fig.subplots_adjust(right=0.9)
            cbar_ax = fig.add_axes([0.92, 0.06, 0.05, 0.9])
            fig.colorbar(
                mappable=cm.ScalarMappable(
                    norm=colors.Normalize(0, max_flips), cmap=CMAP
                ),
                ticks=range(0, max_flips + 1, ticks_step),
                cax=cbar_ax,
                location="right",
            )
        else:
            fig.colorbar(
                mappable=cm.ScalarMappable(
                    norm=colors.Normalize(0, max_flips), cmap=CMAP
                ),
                ticks=range(0, max_flips + 1, ticks_step),
                location="bottom",
            )

    if len(aggressors) == 1:
        plt.suptitle(f"Single Sided Attack (Attacker row: {aggressors[0]})")
    else:
        plt.suptitle(
            f"Dual Sided Attack (Attacker rows: {aggressors[0]}, {aggressors[1]})"
        )

    toolbar = fig.canvas.toolbar

    def new_home(*args, **kwargs):
        print("Reset view")
        reset_axes()
        draw_plot()
        plt.draw()

    if toolbar is not None:
        toolbar._update_view = new_home
    fig.canvas.mpl_connect("button_release_event", lambda event: draw_plot())
    if png is None:
        plt.show()
    else:
        plt.savefig(png, dpi=600)


def plot_aggressors_vs_victims(
    data: List[Tuple[List[int], list]],
    annotate: str,
    png: Optional[str],
    colorbar: bool = True,
    group_rows: Optional[int] = None,
    group_cols: Optional[int] = None,
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

    fig, ax = plt.subplots()
    fig.set_size_inches(16, 12)
    fig.canvas.mpl_connect("button_press_event", on_click)

    h, _, _, _ = ax.hist2d(
        attempts,
        victims,
        bins=bins,
        range=hist_range,
        weights=bitflips,
        cmap=CMAP,
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

    ax.grid(visible=True, which="both", color="gray", alpha=0.2, linestyle="-")

    if colorbar:
        # Limit number of colorbar ticks
        # if left unchanged they can be floats, which looks bad
        max_errors = int(h.max())
        ticks_step = max(1, int(max_errors // 20))
        plt.colorbar(
            mappable=cm.ScalarMappable(norm=colors.Normalize(0, max_errors), cmap=CMAP),
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
        "--column-chunk",
        type=int,
        default=128,
        help="Number of columns to be put into a single subplot",
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
        nargs="?",
        const=32,
        default=None,
        help="Group rows into N groups (default N: 32)",
    )
    parser.add_argument(
        "-gc",
        "--group-columns",
        type=int,
        nargs="?",
        const=128,
        default=None,
        help="Group columns into N groups (default N: 128)",
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
                data = {"aggressors": hammered_rows}
                for row in attack_results["errors_in_rows"].values():
                    row_number = row["row"]
                    cols = row["col"]
                    data[row_number] = list(repeat(0, COLS))
                    for _, single_read in cols.items():
                        for c in single_read:
                            data[row_number][c] += 1

                plot_single_attack(
                    data,
                    annotate=args.annotate,
                    xlabel="Column",
                    png=args.png,
                    colorbar=not args.no_colorbar,
                    col_chunk=args.column_chunk,
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
