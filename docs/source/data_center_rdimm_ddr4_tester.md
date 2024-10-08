# Data Center RDIMM DDR4 Tester

```{image} images/data-center-rdimm-ddr4-tester-1.2.0.png
```

The Data Center RDIMM DDR4 Tester is an open source hardware test platform that enables testing and experimenting with various DDR4 RDIMMs (Registered Dual In-Line Memory Module).

The hardware is open and can be found on GitHub:
<https://github.com/antmicro/data-center-dram-tester/>

The following instructions explain how to set up the board.

## IO map
A map of on-board connectors, status LEDs, control buttons and I/O interfaces is provided below.

:::{figure-md}
![](images/data-center-rdimm-ddr4-tester-descriptions.png)

DDR4 data center dram tester interface map
:::

Connectors:
* [`J3`](#data-center-dram-tester_J3) - main DC barrel jack power connector, voltage between 7-15V is supported
* [`J9`](#data-center-dram-tester_J9) - USB-C debug connector used for programming FPGA or Flash memory
* [`J1`](#data-center-dram-tester_J1) - standard 14-pin JTAG connector used for programming FPGA or Flash memory
* [`J6`](#data-center-dram-tester_J6) - HDMI connector
* [`J2`](#data-center-dram-tester_J2) - Ethernet connector used for data exchange with on-board FPGA and power supply via PoE
* [`U14`](#data-center-dram-tester_U14) - 288-pin RDIMM connector for connecting DDR4 memory modules
* [`J8`](#data-center-dram-tester_J8) - optional 5V fan connector
* [`J7`](#data-center-dram-tester_J7) - socket for SD card
* [`J5`](#data-center-dram-tester_J5) - FMC HPC connector reserved for future use

Switches and buttons:
* Power ON/OFF button [`S3`](#data-center-dram-tester_S3) - push button to power up a device, hold for 8s to turn the device off
* FPGA programming button [`PROG_B1`](#data-center-dram-tester_PROG_B1) - push button to start programming from Flash
* Configuration mode selector [`S2`](#data-center-dram-tester_S2) - Swipe left/right to specify SPI/JTAG programming mode
* HOT SWAP eject button [`S1`](#data-center-dram-tester_S1) - reserved for future use to turn off a DDR memory and allow hot swapping it

LEDs:
* 3V3 Power indicator [`PWR1`](#data-center-dram-tester_PWR1) - indicates presence of stabilized 3.3V voltage
* PoE indicator [`D15`](#data-center-dram-tester_D15) - indicates negotiated PoE voltage supply
* FPGA programming INIT [`D10`](#data-center-dram-tester_D10) - indicates current FPGA configuration state
* FPGA programming DONE [`D1`](#data-center-dram-tester_D1) - indicates completion of FPGA programming
* HOT SWAP status [`D17`](#data-center-dram-tester_D17) - RGY LED indicating status of hot swap process
* 5x User ([`D5`](#data-center-dram-tester_D5), [`D6`](#data-center-dram-tester_D6), [`D7`](#data-center-dram-tester_D7), [`D8`](#data-center-dram-tester_D8), [`D9`](#data-center-dram-tester_D9)) - LEDs for user's definition

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

There is a JTAG/SPI switch [`S2`](#data-center-rdimm-ddr4-tester_S2) on the right side of the board, near JTAG connector.
It defines whether the bitstream will be loaded via JTAG or SPI Flash memory.

Bitstream will be loaded from flash memory upon device power-on or after a [`PROG_B1`](#data-center-dram-tester_PROG_B1) button press.
