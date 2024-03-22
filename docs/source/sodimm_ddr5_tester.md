# SO-DIMM DDR5 Tester

```{image} images/sodimm-ddr5-tester.png
```

The SO-DIMM DDR5 tester is an open source hardware test platform that enables testing and experimenting with various DDR5 SO-DIMM modules and Antmicro LPDDR5 testbed.

The hardware is open and can be found on GitHub:
<https://github.com/antmicro/sodimm-ddr5-tester>

## Rowhammer Tester Target Configuration

The following instructions explain how to set up the board.

Connect the board USB-C `J3` and Ethernet `J6` via cable to your computer, plug the board into the power socket `J7` and turn it on using power switch `SW5`. Then configure the network. The board's IP address will be `192.168.100.50` (so you could e.g. use `192.168.100.2/24`). The `IP_ADDRESS` environment variable can be used to modify the board's address.
Next, generate the FPGA bitstream:

```sh
export TARGET=sodimm_ddr5_tester
make build TARGET_ARGS="--l2-size 256 --build --iodelay-clk-freq 400e6 --bios-lto --rw-bios --no-sdram-hw-test"
```

```{note}
--l2-size 256 sets L2 cache size to 256 bytes

--no-sdram-hw-test disables hw accelerated memory test
```

```{note}
By typing `make` (without `build`) LiteX will generate build files without invoking Vivado.
```

The results will be located in: `build/sodimm_ddr5_tester/gateware/antmicro_sodimm_ddr5_tester.bit`. To upload it, use:

```sh
export TARGET=sodimm_ddr5_tester
make upload
```

To save bitstream in flash memory, use:

```sh
export TARGET=sodimm_ddr5_tester
make flash
```

```{warning}
There is a `SW1` `MODE` selector to the right of the FPGA.
If the bitstream needs to be loaded from the Flash memory, select ```Master SPI``` mode. This configuration is set by default

| Configuration mode | MODE[2] | MODE[1] | MODE[0] |
|--------------------|---------|---------|---------|
| Master Serial      | 0       | 0       | 0       |
| Master SPI         | 0       | 0       | 1       |
| Master BPI         | 0       | 1       | 0       |
| Master SelectMAP   | 1       | 0       | 0       |
| JTAG               | 1       | 0       | 1       |
| Slave SelectMAP    | 1       | 1       | 0       |
| Slave Serial       | 1       | 1       | 1       |

Bitstream will be loaded from flash memory upon device power-on or after a PROG button press.
```


