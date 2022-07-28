#!/usr/bin/env python3
"""
This script decodes SPD dump of DDR5 DIMM and prints information about it.
"""

import argparse
from math import ceil

parser = argparse.ArgumentParser()
parser.add_argument("binary", help="binary dump of the SPD")
parser.add_argument("--speedgrade", type=int, default=4800, help="data speed in MT/s")
parser.add_argument(
    "--print-bytes", action="store_true", help="print hex representation of decoded bytes")

args = parser.parse_args()

with open(args.binary, "rb") as fd:
    b = fd.read()


def print_byte(offset: int, name: str = args.binary):
    """Helper function to reduce common code"""

    if args.print_bytes:
        print(f"\n{name}[{offset}] = 0x{b[offset]:x}")


def print_bytes(first: int, last: int, name: str = args.binary):
    """Helper function to reduce common code"""

    if args.print_bytes:
        print(f"\n{name}[{first}:{last+1}] = 0x{b[first:last+1][::-1].hex()}")


def get_bits(bits: int, first_bit: int, last_bit: int) -> int:
    """
    Extract field from an integer

    bits      : integer to extract bits from
    first_bit : index of first bit to extract
    last_bit  : index of last bit to extract
    """

    field_offset = first_bit
    field_length = last_bit - first_bit + 1
    mask = ((1 << field_length) - 1) << field_offset
    return (bits & mask) >> field_offset


def print_supported(name: str, is_supported: bool):
    """Helper function to reduce common code"""

    not_str = "" if is_supported else "not "
    print(f"{name}: {not_str}supported")


assert b[2] == 0x12, "Only DDR5 modules are supported"

print_bytes(521, 550)
module_part_number = b[521:551].decode("ascii").strip()
print("Module part number:", module_part_number)

print_byte(0)
beta_level = (get_bits(b[0], 7, 7) << 4) | get_bits(b[0], 0, 3)
print("Beta level:", beta_level)
spd_bytes_total = {
    0b000: "Undefined",
    0b001: 256,
    0b010: 512,
    0b011: 1024,
    0b100: 2048,
}[get_bits(b[0], 4, 6)]
print("SPD bytes total:", spd_bytes_total)

print_byte(1)
spd_revision_minor = get_bits(b[1], 0, 3)
spd_revision_major = get_bits(b[1], 4, 7)
print(f"SPD Revision: {spd_revision_major}.{spd_revision_minor}")

print_byte(2)
module_type = {
    18: "DDR5 SDRAM",
}[b[2]]
print("Module Type:", module_type)

print_byte(3)
base_module_type = {
    0b0001: "RDIMM",
    0b0010: "UDIMM",
    0b0011: "SODIMM",
    0b0100: "LRDIMM",
    0b1010: "DDDIMM",
    0b1011: "Solder down",
}[get_bits(b[3], 0, 3)]
print("Base Module Type:", base_module_type)
hybrid_media = {
    0b000: "not hybrid",
    0b001: "NVDIMM-N Hybrid",
    0b010: "NVDIMM-P Hybrid",
}[get_bits(b[3], 4, 6)]
print("Hybrid Media:", hybrid_media)
is_hybrid_media = bool(get_bits(b[3], 7, 7))

is_asymmetrical = bool(get_bits(b[234], 6, 6))
ranks = [("even", 0), ("odd", 4)] if is_asymmetrical else [("all", 0)]

for oddity, offset in ranks:
    print_byte(4 + offset)
    dram_density_per_die = {
        0b00000: 0,
        0b00001: 4,
        0b00010: 8,
        0b00011: 12,
        0b00100: 16,
        0b00101: 24,
        0b00110: 32,
        0b00111: 48,
        0b01000: 64,
    }[get_bits(b[4 + offset], 0, 4)]
    print(f"Density Per Die ({oddity}):", dram_density_per_die, "Gb")
    die_per_package = {
        0b000: 1,
        0b010: 2,
        0b011: 4,
        0b100: 8,
        0b101: 16,
    }[get_bits(b[4 + offset], 5, 7)]
    print(f"Die Per Package ({oddity}):", die_per_package)

    print_byte(5 + offset)
    row_address_bits = {
        0b00000: 16,
        0b00001: 17,
        0b00010: 18,
    }[get_bits(b[5 + offset], 0, 4)]
    print(f"Row Address Bits ({oddity}):", row_address_bits)
    column_address_bits = {
        0b000: 10,
        0b001: 11,
    }[get_bits(b[5 + offset], 5, 7)]
    print(f"Column Address Bits ({oddity}):", column_address_bits)

    print_byte(6 + offset)
    sdram_io_width = {
        0b000: "x4",
        0b001: "x8",
        0b010: "x16",
        0b011: "x32",
    }[get_bits(b[6 + offset], 5, 7)]
    print(f"I/O Width ({oddity}):", sdram_io_width)

    print_byte(7 + offset)
    banks_per_group = {
        0b000: 1,
        0b001: 2,
        0b010: 4,
    }[get_bits(b[7 + offset], 0, 2)]
    print(f"Banks Per Bank Group ({oddity}):", banks_per_group)
    bank_groups = {
        0b000: 1,
        0b001: 2,
        0b010: 4,
        0b011: 8,
    }[get_bits(b[7 + offset], 5, 7)]
    print(f"Bank Groups ({oddity}):", bank_groups)

print_byte(12)
print_supported("MBIST/mPPR", bool(get_bits(b[12], 1, 1)))
print_supported("BL32", bool(get_bits(b[12], 4, 4)))
print_supported("sPPR Undo/Lock", bool(get_bits(b[12], 5, 5)))
print(
    "sPPR Granularity: one repair element per",
    {
        0b0: "bank group",
        0b1: "bank",
    }[get_bits(b[b[12]], 7, 7)],
)

print_byte(13)
print(
    "Supported DCA Types:",
    {
        0b00: "not supported",
        0b01: "single/2-phase internal clock(s)",
        0b10: "4-phase internal clock(s)",
    }[get_bits(b[13], 0, 1)],
)
print_supported("PASR", bool(get_bits(b[13], 4, 4)))

print_byte(14)
print_supported("Bounded Fault", bool(get_bits(b[14], 0, 0)))
print(
    "x4 RMW/ECS Writeback Suppression MR Selector:",
    {
        0b0: "MR9",
        0b1: "MR15",
    }[get_bits(b[14], 1, 1)],
)
print_supported("x4 RMW/ECS Writeback Suppression", bool(get_bits(b[14], 2, 2)))
print_supported("Wide Temperature Sense", bool(get_bits(b[14], 3, 3)))

# byte 15 is reserved

print_byte(16)
assert b[16] == 0, "Values other than 0x00 are reserved"
print("SDRAM Nominal Voltage, VDD: 1.1 V")
print_byte(17)
assert b[17] == 0, "Values other than 0x00 are reserved"
print("SDRAM Nominal Voltage, VDDQ: 1.1 V")
print_byte(18)
assert b[18] == 0, "Values other than 0x00 are reserved"
print("SDRAM Nominal Voltage, VPP: 1.8 V")

print_byte(19)
print_supported("Non standard timings", bool(get_bits(b[19], 0, 0)))

print_bytes(24, 28)
supported_cl_bits = int.from_bytes(b[24:29], "little")
supported_cl: list[int] = []
for i, cl in enumerate(range(20, 98 + 1, 2)):
    if get_bits(supported_cl_bits, i, i):
        supported_cl.append(cl)
print("Supported CL:", *supported_cl)

# TIMINGS


def rounding_algorithm(parameter_nominal: int) -> int:
    tck_real = 1e6 / (args.speedgrade / 2)
    return ceil(parameter_nominal * 0.997 / tck_real)


def word(lsb: int, msb: int) -> int:
    """Combine two bytes into one word"""
    return msb << 8 | lsb


# 2 byte timings
timings_2b = {
    20: ("Minimum Cycle Time (tCKAVG_min)", "ps"),
    22: ("Maximum Cycle Time (tCKAVG_min)", "ps"),
    30: ("Minimum CAS Latency Time (tAA_min)", "ps"),
    32: ("Minimum RAS to CAS Delay Time (tRCD_min)", "ps"),
    34: ("Minimum Row Precharge Delay Time (tRP_min)", "ps"),
    36: ("Minimum Active to Precharge Delay Time (tRAS_min)", "ps"),
    38: ("Minimum Active to Active/Refresh Delay Time (tRC_min)", "ps"),
    40: ("Minimum Write Recovery Time (tWR_min)", "ps"),
    42: ("Minimum Refresh Recovery Delay Time (tRFC1_min, tRFC1_slr_min)", "ns"),
    44: ("Minimum Refresh Recovery Delay Time (tRFC2_min, tRFC2_slr_min)", "ns"),
    46: ("Minimum Refresh Recovery Delay Time (tRFCsb_min, tRFCsb_slr_min)", "ns"),
}

is_3ds = get_bits(b[4], 5, 7) or get_bits(b[8], 5, 7)
if is_3ds:
    timings_2b |= {
        48:
        ("Minimum Refresh Recovery Delay Time, 3DS Different Logical Rank (tRFC1_dlr_min)", "ns"),
        50:
        ("Minimum Refresh Recovery Delay Time, 3DS Different Logical Rank (tRFC2_dlr_min)", "ns"),
        52:
        ("Minimum Refresh Recovery Delay Time, 3DS Different Logical Rank (tRFCsb_dlr_min)", "ns"),
    }

for offset, (desc, unit) in timings_2b.items():
    print_bytes(offset, offset + 2)
    lsb, msb = b[offset:offset + 2]
    value = word(lsb, msb)
    nominal = value if unit == "ps" else value * 1000
    target_nck = rounding_algorithm(nominal)
    print(f"{desc}: {value} {unit} (nCK: {target_nck})")

# TODO: bytes 54~69
print_byte(54)
print(
    "Refresh Management:",
    {
        0b0: "required",
        0b1: "not required",
    }[get_bits(b[54], 0, 0)],
)

print("start of 3 byte timings")

# 3 byte timings
timings_3b = {
    70: "Minimum Active to Active Command Delay Time, Same Bank Group (tRRD_L_min)",
    73: "Minimum Read to Read Command Delay Time, Same Bank Group (tCCD_L_min)",
    76: "Minimum Write to Write Command Delay Time, Same Bank Group (tCCD_L_WR_min)",
    79:
    "Minimum Write to Write Command Delay Time, Second Write not RMW, Same Bank Group (tCCD_L_WR2_min)",
    82: "Minimum Four Activate Window (tFAW_min)",
    85: "Minimum Write to Read Command Delay Time, Same Bank Group (tCCD_L_WTR_min)",
    88: "Minimum Write to Read Command Delay Time, Different Bank Group (tCCD_S_WTR_min)",
    91: "Minimum Read to Precharge Command Delay Time, (tRTP_min)",
}

for offset, desc in timings_3b.items():
    print_bytes(offset, offset + 3)
    lsb, msb, min_nck = b[offset:offset + 3]
    value = word(lsb, msb)
    nck = rounding_algorithm(value)
    print(f"{desc}: {value} ps (nCK: max({min_nck}, {nck}) = {max(min_nck, nck)})")
