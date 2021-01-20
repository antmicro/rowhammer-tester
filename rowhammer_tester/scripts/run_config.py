#!/usr/bin/env python3

import argparse
from collections import defaultdict
from rowhammer_tester.scripts.payload_generator import PayloadGenerator
from rowhammer_tester.scripts.row_list_payload_generator import RowListPayloadGenerator
from rowhammer_tester.scripts.hammer_tolerance_payload_generator import HammerTolerancePayloadGenerator
from rowhammer_tester.scripts.utils import (RemoteClient, setup_inverters, get_litedram_settings,
                                            hw_memset, hw_memtest, validate_keys,
                                            execute_payload, DRAMAddressConverter,
                                            get_generated_defs)

def get_value_or_default(config, key, default):
    if key in config.keys():
        return config[key]
    else:
        return default

_addresses_per_row = {}

def addresses_per_row(settings, converter, bank, row):
    # Calculate the addresses lazily and cache them
    if row not in _addresses_per_row:
        addresses = [converter.encode_bus(bank=bank, col=col, row=row)
                     for col in range(2**settings.geom.colbits)]
        _addresses_per_row[row] = addresses
    return _addresses_per_row[row]

def check_errors(wb, settings, converter, bank, row_pattern):
    dma_data_width = settings.phy.dfi_databits * settings.phy.nphases
    dma_data_bytes = dma_data_width // 8

    errors = hw_memtest(wb, 0x0, wb.mems.main_ram.size, [row_pattern])

    row_errors = defaultdict(list)
    for e in errors:
        addr = wb.mems.main_ram.base + e.offset * dma_data_bytes
        bank, row, col = converter.decode_bus(addr)
        base_addr = min(addresses_per_row(settings, converter, bank, row))
        row_errors[row].append(((addr - base_addr)//4, e.data, e.expected))

    return dict(row_errors)

def main():
    valid_keys = set(["payload_generator", "payload_generator_config",
                      "inversion_divisor", "inversion_mask", "row_pattern"])
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", type=open)
    args = parser.parse_args()
    config = eval(args.config_file.read())
    assert validate_keys(config, valid_keys)
    args.config_file.close()
    pg = PayloadGenerator.get_by_name(config["payload_generator"])
    pg.initialize(config)
    wb = RemoteClient()
    wb.open()
    inversion_divisor = 0
    inversion_mask = 0
    inversion_divisor = get_value_or_default(config, "inversion_divisor", 0)
    inversion_mask = get_value_or_default(config, "inversion_mask", 0)
    row_pattern = get_value_or_default(config, "row_pattern", 0)
    setup_inverters(wb, inversion_divisor, inversion_mask)
    while not pg.done():
        hw_memset(wb, 0x0, wb.mems.main_ram.size, [row_pattern])
        settings = get_litedram_settings()
        converter = DRAMAddressConverter.load()
        bank = 0
        sys_clk_freq = float(get_generated_defs()['SYS_CLK_FREQ'])
        payload = pg.get_payload(settings = settings, bank = bank,
                             payload_mem_size =  wb.mems.payload.size, sys_clk_freq = sys_clk_freq)

        execute_payload(wb, payload)
        row_errors = check_errors(wb, settings, converter, bank, row_pattern)
        pg.process_errors(settings, row_errors)

    pg.summarize()
    wb.close()


if __name__ == "__main__":
    main()
