#!/usr/bin/env python3
"""
This script generates visualization from rowhammer attack logs using F4PGA Database Visualizer
Each attack is a separate visualization
"""

import os
import argparse
import json
import datetime

from pathlib import Path

from rowhammer_tester.scripts.utils import get_generated_file


def get_dqs_on_col(data: dict, dq_pads: int = 64):
    dq_flips: list[str] = []

    # Calculate DQ from each single bitflip
    for flip in data:
        dq = flip % dq_pads
        dq_flips.append(f"dq[{dq}]")

    # Different bitflips might occur on the same DQ
    # Remove duplicates
    dq_flips = list(dict.fromkeys(dq_flips))

    return dq_flips


def process_aggr_vs_vict(data: dict, dq_pads: int = 64):
    vis_data: list = []
    rows_affected: list(int) = []
    aggressors: list[int] = []
    all_victims: list[int] = []
    bitflips: list[int] = []
    columns: list[list[int]] = []

    # Put aggressors and its victims into lists for hist2d
    for aggressor, victims in data.items():
        rows_affected.append(aggressor)

        # Each aggressor must have its own tile
        vis_data.append([aggressor, aggressor, 1, "TGT", "Target", f"Target row {aggressor}", []])

        # Each victim must have its own tile
        for victim in victims:
            # From json logs - victim[1] is a single victim row hierarchy
            bitflip_amount = victim[1]["bitflips"]
            victim_row = victim[1]["row"]
            columns = victim[1]["col"]

            # Collect single victim, its aggressor and bitflips to global
            # lists that contain all of these
            all_victims.append(victim_row)
            aggressors.append(aggressor)
            bitflips.append(bitflip_amount)

            desc: list = [f"# Total {bitflip_amount} bits affected"]
            for col, flips in columns.items():
                # Process which DQs flipped based on word indexes
                dq_flips = get_dqs_on_col(flips)

                # Add bitflips to description formatted as [dq[X], dq[Y]]
                desc.append({f"Column {col}": "%s" % ', '.join(map(str, dq_flips))})
                vis_data.append(
                    [
                        victim_row,
                        aggressor,
                        1,
                        "FLIP",
                        str(bitflip_amount),
                        f"Aggressor ({aggressor}) vs victim ({victim_row})",
                        desc,
                    ])
    # Victims are in grid columns so calculate cols_range from all victims
    cols_range = [[min(sorted(all_victims)), max(sorted(all_victims))]]

    return vis_data, rows_affected, cols_range


def process_standard(data: dict, cols: int, col_step: int = 32):
    vis_data: list = []
    rows_affected: list(int) = []

    for row_errors in data["errors_in_rows"].values():
        row = row_errors["row"]
        rows_affected.append(row)

        # Pack columns into `col_step` wide packages
        for col in range(0, cols, col_step):
            desc: list = ["# Bits affected"]
            flips_in_chunk = 0

            # Check bitflips on every single column
            for i in range(col_step):
                col_str = str(col + i)
                col_errors = row_errors["col"].get(col_str, [])
                flips_in_chunk += len(col_errors)

                # If bitflips occured, calculate affected DQs and add these to description
                # formatted as [dq[X], dq[Y]]
                if len(col_errors):
                    dq_flips = get_dqs_on_col(col_errors)
                    desc.append({f"Column {col_str}": "%s" % ', '.join(map(str, dq_flips))})

            if flips_in_chunk > 0:
                cell_type = "FLIP"
                cell_label = str(flips_in_chunk)
            else:
                cell_type = "OK"
                cell_label = "OK"

            vis_data.append(
                [
                    col // col_step,
                    row,
                    1,
                    cell_type,
                    cell_label,
                    f"Columns {col} to {col+col_step-1}",
                    desc,
                ])

    # Add hammered rows to all rows
    if "hammer_row_1" in data and "hammer_row_2" in data:
        rows_affected.append(data["hammer_row_1"])
        if data["hammer_row_1"] != data["hammer_row_2"]:
            rows_affected.append(data["hammer_row_2"])
        for row in (data["hammer_row_1"], data["hammer_row_2"]):
            # add "TGT" cells for rows that were hammered
            vis_data.append([0, row, cols // col_step, "TGT", "Target", "Target row", []])
    cols_range = [[0, cols // col_step - 1]]

    return vis_data, rows_affected, cols_range


def get_vis_data(
        data: dict,
        no_empty_rows: bool,
        aggressors_vs_victims: bool,
        cols: int,
        col_step: int = 32,
        dq_pads: int = 64) -> tuple[list, list, list]:
    """
    Generates ``vis_data``, which is a list of cell descriptions
    Each cell is a list of parameters:
        col: int
        row: int
        width: int
        type: str
        label: str
        title: str
        description: list
    """

    vis_data: list = []

    if aggressors_vs_victims:
        vis_data, rows_affected, cols_affected = process_aggr_vs_vict(data, dq_pads)
    else:
        vis_data, rows_affected, cols_affected = process_standard(data, cols, col_step)

    # If we want to omit empty rows, pass `rows_affected` unchanged since it's prepared
    # as that fromat. Otherwise take lowest and highest of all rows as a range.
    rows_affected = sorted(rows_affected)
    if not no_empty_rows:
        rows_affected = [[rows_affected[0], rows_affected[-1]]]

    return vis_data, rows_affected, cols_affected


def get_vis_config(entries: list[Path]) -> dict[str, list[dict[str, str]]]:
    return {
        'dataFilesList': [{
            "name": e.stem,
            "url": e.name
        } for e in entries],
    }


def get_vis_metadata(rows: list[int], cols: int, data_file: str, rows_name: str = "rowsRange"):
    return {
        'buildDate': datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        'grids': {
            'rowhammer': {
                'name': 'Rowhammer',
                'colsRange': cols,
                rows_name: rows,
                'cells': {
                    'fieldOrder':
                    ['col', 'row', 'width', 'type', 'name', 'fullName', 'description'],
                    'fieldTemplates': {
                        'color': '{get(COLORS, type)}'
                    },
                    'templateConsts': {
                        'COLORS': {
                            'OK': 19,
                            'FLIP': 1,
                            'TGT': 3
                        }
                    },
                    'data': {
                        '@import': data_file
                    }
                }
            }
        }
    }


def generate_output_files(
        data: dict, no_empty_rows: bool, aggressors_vs_victims: bool, dq_pads: int, cols: int,
        cols_step: int, vis_dir: str, output_name: str):
    # generate visualization data from logs of all attacks
    vis_data, rows, cols = get_vis_data(
        data, no_empty_rows, aggressors_vs_victims, cols, cols_step, dq_pads=dq_pads)

    # write data file
    data_file = (vis_dir / output_name).with_suffix(".data.json")
    with data_file.open("w") as fd:
        json.dump(vis_data, fd)

    vis_meta = get_vis_metadata(rows, cols, data_file.name, rows_name)
    # write meta file
    meta_file = (vis_dir / output_name).with_suffix(".json")
    meta_files.append(meta_file)
    with meta_file.open("w") as fd:
        json.dump(vis_meta, fd)

    return meta_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("log_file", help="file with log output")
    parser.add_argument("vis_dir", help="directory where to put visualization json files")
    parser.add_argument(
        "--vis-columns", type=int, default=32, help="how many columns to show in resulting grid")
    parser.add_argument(
        "--no-empty-rows", action="store_true", help="exclude empty rows from visualizer")
    parser.add_argument(
        "--aggressors-vs-victims",
        action="store_true",
        help="visualize single aggressor attacks and their victims")
    parser.add_argument("--dq-pads", type=int, default=64, help="number of memory DQ pads")
    args = parser.parse_args()

    # get module settings to calculate total number of rows and columns
    settings_file = Path(get_generated_file("litedram_settings.json"))
    with settings_file.open() as fd:
        settings = json.load(fd)

    COLS = 2**settings["geom"]["colbits"]
    ROWS = 2**settings["geom"]["rowbits"]

    log_file = Path(args.log_file)
    with log_file.open() as fd:
        log_data = json.load(fd)

    vis_dir = Path(args.vis_dir).resolve()
    vis_dir.mkdir(parents=True, exist_ok=True)

    # list of meta file names
    # only files listed in viewer config can be browsed
    meta_files: list[Path] = []

    if args.no_empty_rows:
        rows_name = "rows"
    else:
        rows_name = "rowsRange"

    # read_count / read_count_range level
    for read_count, attack_set_results in log_data.items():
        aggressors_vs_victims = {}
        # Remove read_count as it's only disturbing here
        if "read_count" in attack_set_results:
            attack_set_results.pop("read_count")

        # Single attack hierarchy
        for attack, attack_results in attack_set_results.items():
            if args.aggressors_vs_victims:
                if attack.startswith("pair"):
                    # Collect all rows data into single dict for later processing
                    victim_rows = []
                    for row in attack_results["errors_in_rows"].items():
                        victim_rows.append(row)

                    hammered_row_1 = attack_results["hammer_row_1"]
                    hammered_row_2 = attack_results["hammer_row_2"]
                    aggressors_vs_victims[hammered_row_1] = victim_rows

                    if hammered_row_1 != hammered_row_2:
                        print(
                            "ERROR: Attacks are not hammering single rows. Unable to plot aggressors "
                            "against their victims. Use `--row-pair-distance 0` to target single row at once."
                        )
                        exit()
                else:
                    print(
                        "ERROR: Sequential attacks are not hammering a single row. Unable to compare aggressors against victims."
                    )
                    exit()
            else:
                meta_files = generate_output_files(
                    attack_results,
                    args.no_empty_rows,
                    args.aggressors_vs_victims,
                    args.dq_pads,
                    COLS,
                    COLS // args.vis_columns,
                    vis_dir,
                    output_name=f"{read_count}_{attack}")

    if args.aggressors_vs_victims:
        meta_files = generate_output_files(
            aggressors_vs_victims,
            args.no_empty_rows,
            args.aggressors_vs_victims,
            args.dq_pads,
            COLS,
            cols_step=1,
            vis_dir=vis_dir,
            output_name=f"{read_count}_aggressors_vs_victims")

    # write config file
    vis_config = get_vis_config(meta_files)
    config_file = vis_dir / "sdbv.config.json"
    with config_file.open("w") as fd:
        json.dump(vis_config, fd)
