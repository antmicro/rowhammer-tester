# SO-DIMM DDR5 Tester

```{image} images/sodimm-ddr5-tester.png
```

The SO-DIMM DDR5 tester is an open source hardware test platform that enables testing and experimenting with various DDR5 SO-DIMM modules and Antmicro LPDDR5 testbed.

The hardware is open and can be found on GitHub:
<https://github.com/antmicro/sodimm-ddr5-tester>

The following instructions explain how to set up the board.

```{warning}
There is a `SW1` `MODE` selector on the right close to FPGA.
The default configuration mode is set to ```JTAG```. If the bitstream needs to be loaded from the Flash memory, select ```Master SPI``` mode.

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



