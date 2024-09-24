# Data Center RDIMM DDR4 Tester

```{image} images/data-center-rdimm-ddr4-tester-1.2.0.png
```

The Data Center RDIMM DDR4 Tester is an open source hardware test platform that enables testing and experimenting with various DDR4 RDIMMs (Registered Dual In-Line Memory Module).

The hardware is open and can be found on GitHub:
<https://github.com/antmicro/data-center-dram-tester/>

The following instructions explain how to set up the board.

## Board configuration

Connect power supply (7-15VDC) to [`J3`](#data-center-dram-tester_J3) barrel jack. Then connect the board USB cable ([`J9`](#data-center-dram-tester_J9)) and Ethernet cable ([`J2`](#data-center-dram-tester_J2)) to your computer and insert the memory module to the socket [`U14`](#data-center-dram-tester_U14).
To turn the board on, use power switch [`S3`](#data-center-dram-tester_S3). 

After power is up, configure the network. The board's IP address will be `192.168.100.50` (so you could e.g. use `192.168.100.2/24`). The `IP_ADDRESS` environment variable can be used to modify the board's address.

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

Bitstream will be loaded from flash memory upon device power-on or after a [`PROG_B1`](#data-center-dram-tester_PROG_B1) button press.
