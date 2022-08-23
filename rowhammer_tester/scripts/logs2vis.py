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


def get_vis_data(data: dict, rows: int, cols: int, col_step: int = 32) -> tuple[list, int, int]:
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

    vis_data = []

    first_row: int = rows - 1
    last_row: int = 0
    for row_errors in data["errors_in_rows"].values():
        row = row_errors["row"]

        # we keep track of first and last row,
        # to limit the number of displayed rows
        if row < first_row:
            first_row = row
        if row > last_row:
            last_row = row

        for col in range(0, cols, col_step):
            desc: list = ["# Bits affected"]

            flips_in_chunk = 0
            for i in range(col_step):
                col_str = str(col + i)
                col_errors = row_errors["col"].get(col_str, [])

                flips_in_chunk += len(col_errors)
                if len(col_errors):
                    desc.append({f"Column {col_str}": f"{col_errors}"})

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

    if "hammer_row_1" in data and "hammer_row_2" in data:
        for row in (data["hammer_row_1"], data["hammer_row_2"]):
            # hammered row could have been at one of the ends
            if row < first_row:
                first_row = row
            if row > last_row:
                last_row = row

            # add "TGT" cells for rows that were hammered
            vis_data.append([0, row, cols // col_step, "TGT", "Target", "Target row", []])

    return vis_data, first_row, last_row


def get_vis_config(entries: list[Path]) -> dict[str, list[dict[str, str]]]:
    return {
        'dataFilesList': [{
            "name": e.stem,
            "url": e.name
        } for e in entries],
    }


def get_vis_metadata(first_row: int, last_row: int, cols: int, data_file: str):
    return {
        'buildDate': datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        'grids': {
            'rowhammer': {
                'name': 'Rowhammer',
                'colsRange': cols - 1,
                'rowsRange': [first_row, last_row],
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("log_file", help="file with log output")
    parser.add_argument("vis_dir", help="directory where to put visualization json files")
    parser.add_argument(
        "--vis-columns", type=int, default=32, help="how many columns to show in resulting grid")
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

    # read_count / read_count_range level
    for read_count, attack_set_results in log_data.items():
        # remove read_count as it's only interrupting here
        if "read_count" in attack_set_results:
            attack_set_results.pop("read_count")

        # pair hammering level
        for pair, attack_results in attack_set_results.items():
            output_name = f"{read_count}_{pair}"

            # generate visualization data from logs of hammering
            # a single pair of rows
            vis_data, first_row, last_row = get_vis_data(
                attack_results,
                ROWS,
                COLS,
                COLS // args.vis_columns,
            )
            # write data file
            data_file = (vis_dir / output_name).with_suffix(".data.json")
            with data_file.open("w") as fd:
                json.dump(vis_data, fd)

            vis_meta = get_vis_metadata(first_row, last_row, args.vis_columns, data_file.name)
            # write meta file
            meta_file = (vis_dir / output_name).with_suffix(".json")
            meta_files.append(meta_file)
            with meta_file.open("w") as fd:
                json.dump(vis_meta, fd)

    # write config file
    vis_config = get_vis_config(meta_files)
    config_file = vis_dir / "sdbv.config.json"
    with config_file.open("w") as fd:
        json.dump(vis_config, fd)
