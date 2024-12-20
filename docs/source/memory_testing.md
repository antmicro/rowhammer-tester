
This chapter provides a comprehensive guide to performing memory tests. The memory testing process is designed to validate the integrity and performance of various memory modules. 
This procedure employs unified testing scenario involving three short tests and one extended test to ensure thorough evaluation.

## Tools and Equipment
The following tools and equipment are required for the memory testing procedure:

|   | Item | Manufacturer | MPN |
|---|-------------------|----------|--------------|
| 1 | Tester platform | Antmicro | - |
| 2 | DUT(Device under test) | - | - |
| 2 | USB C Hub with network adapter | i-tec | C31METALG3HUB |
| 3 | RJ-45 cat 6a cable | Goobay | 91582 |
| 4 | USB C cable | Goobay | 41073 |
| 6 | USB C to USB A adapter (optional) | i-tec | C31TYPEA |

---

## Procedure for Running Memory Tests

## Prepare testing platform

First follow the instructions in [Installation and setup](installation-and-setup) and [Building Rowhammer Design](building-rowhammer-design) chapters.

1. Activate venv

```bash
source venv/bin/activate
```

2. Export target

```bash
TARGET=ddr5_tester
```

3. Flash the board

```bash
make upload
```
(Upload to SRAM) or 

```bash
make flash
```
(Write to (Q)SPI Flash memory) - To start from flash please ensure that `MODE` jumper is set to `FLASH`

## Running Memory Tests

The unified testing procedure consists of three short memory tests followed by one extended test:

1. Short Test
Run each of the following commands:
```bash
python3 rowhammer_tester/scripts/mem.py --srv --size 0x200000
```
Repeat this command three times to ensure consistency.

2. Extended Test
Run the following command:
```bash
python3 rowhammer_tester/scripts/mem.py --srv --size 0x800000
```
---

## Testing Parameters and Their Purpose
The following parameters are used in the testing scripts:

| Parameter        | Description                                                                          |
|------------------|--------------------------------------------------------------------------------------|
| `--srv`          | Program will start its own instance of litex_server                                  |
| `--size`         | Specifies the memory size to be tested. For short tests, 0x200000 is used.           |
|                  | For extended tests, 0x800000 is specified to a larger memory range.                  |

Selected size parameters ensure a balance between execution time and test coverage.

---

## RDIMM DDR5 Coverage Table

The following [Memory coverage table](csv/dimm_coverage_table.csv) outlines the DDR5 RDIMM modules that have passed all of the above tests.

| # | Memory MPN | Manufacturer | Short memtest (Basic) | Short memtest (Random) | Extended memtest (Basic) | Extended memtest (Random) | Rowhammer-tester commit SHA |
|---|---|---|---|---|---|---|---|
| 1 | MTC10F1084S1RC48BA1_JHCC | Micron | OK | OK | OK | OK | [35bfd92](https://github.com/antmicro/rowhammer-tester/tree/35bfd9252417346e4b1f38a753c22e0541185b9e) |
| 2 | MTC10F1084S1RC48BA1_NGCC | Micron | OK | OK | OK | OK | [35bfd92](https://github.com/antmicro/rowhammer-tester/tree/35bfd9252417346e4b1f38a753c22e0541185b9e) |
| 3 | MTC20F2085S1RC48BA1_PGCC | Micron | OK | OK | OK | OK | [35bfd92](https://github.com/antmicro/rowhammer-tester/tree/35bfd9252417346e4b1f38a753c22e0541185b9e) |
| 4 | M321R4GA3BB6-CQKMG | Samsung | OK | OK | OK | OK | [35bfd92](https://github.com/antmicro/rowhammer-tester/tree/35bfd9252417346e4b1f38a753c22e0541185b9e) |
| 5 | M329R8GA0BB0-CQKVG | Samsung | OK | OK | OK | OK | [35bfd92](https://github.com/antmicro/rowhammer-tester/tree/35bfd9252417346e4b1f38a753c22e0541185b9e) |
| 6 | MTC20F2085S1RC48BA1_JHCC | Micron | OK | OK | OK | OK | [35bfd92](https://github.com/antmicro/rowhammer-tester/tree/35bfd9252417346e4b1f38a753c22e0541185b9e) |
| 7 | HMCG84MEBRA112NBB | SK hynix | OK | OK | OK | OK | [35bfd92](https://github.com/antmicro/rowhammer-tester/tree/35bfd9252417346e4b1f38a753c22e0541185b9e) |
| 8 | HMCG88AGBRA188NAA | SK hynix | OK | OK | OK | OK | [bd05e52](https://github.com/antmicro/rowhammer-tester/tree/bd05e520f30fea3b554e495bb3a92d60d0a08c97) |
| 9 | M321R4GA3BB6-CQKET | Samsung | OK | OK | OK | OK | [bd05e52](https://github.com/antmicro/rowhammer-tester/tree/bd05e520f30fea3b554e495bb3a92d60d0a08c97) |
| 10 | M321R4GA0BB0-CQKMS | Samsung | OK | OK | OK | OK | [bd05e52](https://github.com/antmicro/rowhammer-tester/tree/bd05e520f30fea3b554e495bb3a92d60d0a08c97) |
| 11 | MTC18F104S1PC48BA2_NGCC | Micron | OK | OK | OK | OK | [bd05e52](https://github.com/antmicro/rowhammer-tester/tree/bd05e520f30fea3b554e495bb3a92d60d0a08c97) |
| 12 | MTC10F1084S1RC48BA1_NHFF | Micron | OK | OK | OK | OK | [bd05e52](https://github.com/antmicro/rowhammer-tester/tree/bd05e520f30fea3b554e495bb3a92d60d0a08c97) |
