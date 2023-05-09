# Data Center DRAM Tester

```{image} images/ddr4_datacenter_dram_tester.jpg
```

The data center DRAM tester is an open source hardware test platform that enables testing and experimenting with various DDR4 RDIMMs (Registered Dual In-Line Memory Module).

The hardware is open and can be found on GitHub:
<https://github.com/antmicro/data-center-dram-tester/>

The following instructions explain how to set up the board.

## Board configuration

First connect the board USB and Ethernet cables to your computer, plug the board to the socket and turn it on using power switch. Then configure the network. The board's IP address will be `192.168.100.50` (so you could e.g. use `192.168.100.2/24`). The `IP_ADDRESS` environment variable can be used to modify the board's address.
Next, generate the FPGA bitstream:

```sh
export TARGET=ddr4_datacenter_test_board
make build
```

```{note}
By typing `make` (without `build`) LiteX will generate build files without invoking Vivado.
```

The results will be located in: `build/ddr4_datacenter_test_board/gateware/antmicro_datacenter_ddr4_test_board.bit`. To upload it, use:

```sh
export TARGET=ddr4_datacenter_test_board
make upload
```

To save bitstream in flash memory, use:

```sh
export TARGET=ddr4_datacenter_test_board
make flash
```

```{warning}
There is a JTAG/SPI jumper named `MODE2` on the right side of the board.
Unless it's set to the SPI setting, the FPGA will load the bitstream received via JTAG.
```

Bitstream will be loaded from flash memory upon device power-on or after a PROG button press.
