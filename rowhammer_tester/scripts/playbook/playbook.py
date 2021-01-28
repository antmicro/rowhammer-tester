#!/usr/bin/env python3

import argparse
from collections import defaultdict
import json
from rowhammer_tester.scripts.playbook.payload_generators import PayloadGenerator
from rowhammer_tester.scripts.playbook.payload_generators.row_list import RowListPayloadGenerator
from rowhammer_tester.scripts.playbook.payload_generators.hammer_tolerance import HammerTolerancePayloadGenerator
from rowhammer_tester.scripts.playbook.payload_generators.half_double_analysis import HalfDoubleAnalysisPayloadGenerator
from rowhammer_tester.scripts.utils import (
    RemoteClient, setup_inverters, get_litedram_settings, hw_memset, hw_memtest, validate_keys,
    execute_payload, DRAMAddressConverter, get_generated_defs)

_addresses_per_row = {}


def addresses_per_row(settings, converter, bank, row):
    # Calculate the addresses lazily and cache them
    if row not in _addresses_per_row:
        addresses = [
            converter.encode_bus(bank=bank, col=col, row=row)
            for col in range(2**settings.geom.colbits)
        ]
        _addresses_per_row[row] = addresses
    return _addresses_per_row[row]


def decode_errors(wb, settings, converter, bank, errors):
    dma_data_width = settings.phy.dfi_databits * settings.phy.nphases
    dma_data_bytes = dma_data_width // 8

    row_errors = defaultdict(list)
    for e in errors:
        addr = wb.mems.main_ram.base + e.offset * dma_data_bytes
        bank, row, col = converter.decode_bus(addr)
        base_addr = min(addresses_per_row(settings, converter, bank, row))
        row_errors[row].append(((addr - base_addr) // 4, e.data, e.expected))

    return dict(row_errors)


def main():
    valid_keys = set(
        [
            "payload_generator", "payload_generator_config", "inversion_divisor", "inversion_mask",
            "row_pattern"
        ])
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", type=open)
    args = parser.parse_args()
    config_string = ""
    config_lines = args.config_file.readlines()
    for line in config_lines:
        index = line.find('#')
        if index >= 0:
            line = line[0:index]
            line += '\n'
        config_string += line
    config = json.loads(config_string)
    assert validate_keys(config, valid_keys)
    args.config_file.close()
    pg = PayloadGenerator.get_by_name(config["payload_generator"])
    pg.initialize(config)
    wb = RemoteClient()
    wb.open()
    settings = get_litedram_settings()
    inversion_divisor = 0
    inversion_mask = 0
    inversion_divisor = config.get("inversion_divisor", 0)
    inversion_mask = int(config.get("inversion_mask", "0"), 0)
    row_pattern = config.get("row_pattern", 0)
    setup_inverters(wb, inversion_divisor, inversion_mask)
    while not pg.done():
        offset, size = pg.get_memset_range(wb, settings)
        hw_memset(wb, offset, size, [row_pattern])
        converter = DRAMAddressConverter.load()
        bank = 0
        sys_clk_freq = float(get_generated_defs()['SYS_CLK_FREQ'])
        payload = pg.get_payload(
            settings=settings,
            bank=bank,
            payload_mem_size=wb.mems.payload.size,
            sys_clk_freq=sys_clk_freq)

        execute_payload(wb, payload)
        offset, size = pg.get_memtest_range(wb, settings)
        errors = hw_memtest(wb, offset, size, [row_pattern])
        row_errors = decode_errors(wb, settings, converter, bank, errors)
        pg.process_errors(settings, row_errors)

    pg.summarize()
    wb.close()


if __name__ == "__main__":
    main()
