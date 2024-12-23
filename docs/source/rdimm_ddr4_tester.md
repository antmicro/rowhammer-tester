# RDIMM DDR4 Tester

:::{figure-md} data-center-rdimm-ddr4-tester
![](images/rdimm-ddr4-tester-1.2.0.png)

Data Center RDIMM DDR4 Tester
:::

The Data Center RDIMM DDR4 Tester is an open source hardware test platform that enables testing and experimenting with various DDR4 RDIMMs (Registered Dual In-Line Memory Module).

The hardware is open and can be found on GitHub:
<https://github.com/antmicro/rdimm-ddr4-tester>

The following instructions explain how to set up the board.

For FPGA digital design documentation for this board, refer to the [Digital design](build/ddr4_datacenter_test_board/documentation/index.rst) chapter.

## IO map

A map of on-board connectors, status LEDs, control buttons and I/O interfaces is provided in {numref}`rdimm-ddr4-tester-interface-map` below.

:::{figure-md} rdimm-ddr4-tester-interface-map
![DDR4 data center dram tester interface map](images/rdimm-ddr4-tester-1.2.0-descriptions.png)

DDR4 data center dram tester interface map
:::

Connectors:

* [`J3`](#rdimm-ddr4-tester-1.2.0_J3) - main DC barrel jack power connector, voltage between 7-15V is supported
* [`J9`](#rdimm-ddr4-tester-1.2.0_J9) - USB-C debug connector used for programming FPGA or Flash memory
* `J1` - standard 14-pin JTAG connector used for programming FPGA or Flash memory
* [`J6`](#rdimm-ddr4-tester-1.2.0_J6) - HDMI connector
* [`J2`](#rdimm-ddr4-tester-1.2.0_J2) - Ethernet connector used for data exchange with on-board FPGA and power supply via PoE
* [`U14`](#rdimm-ddr4-tester-1.2.0_U14) - 288-pin RDIMM connector for connecting DDR4 memory modules
* `J8` - optional 5V fan connector
* [`J7`](#rdimm-ddr4-tester-1.2.0_J7) - socket for SD card
* [`J5`](#rdimm-ddr4-tester-1.2.0_J5) - FMC HPC connector reserved for future use

Switches and buttons:

* Power ON/OFF button [`S3`](#rdimm-ddr4-tester-1.2.0_S3) - push button to power up the device, hold for 8s to turn off the device
* FPGA programming button [`PROG_B1`](#rdimm-ddr4-tester-1.2.0_PROG_B1) - push button to start programming from Flash
* Configuration mode selector `S2` - Switch left/right to specify SPI/JTAG programming mode
* HOT SWAP eject button [`S1`](#rdimm-ddr4-tester-1.2.0_S1) - reserved for future use to turn off DDR memory and allow hot swapping it

LEDs:

* 3V3 Power indicator [`PWR1`](#rdimm-ddr4-tester-1.2.0_PWR1) - indicates presence of stabilized 3.3V voltage
* PoE indicator [`D15`](#rdimm-ddr4-tester-1.2.0_D15) - indicates negotiated PoE voltage supply
* FPGA programming INIT [`D10`](#rdimm-ddr4-tester-1.2.0_D10) - indicates current FPGA configuration state
* FPGA programming DONE [`D1`](#rdimm-ddr4-tester-1.2.0_D1) - indicates completion of FPGA programming
* HOT SWAP status [`D17`](#rdimm-ddr4-tester-1.2.0_D17) - RGY LED indicating status of hot swap process
* 5x User ([`D5`](#rdimm-ddr4-tester-1.2.0_D5), [`D6`](#rdimm-ddr4-tester-1.2.0_D6), [`D7`](#rdimm-ddr4-tester-1.2.0_D7), [`D8`](#rdimm-ddr4-tester-1.2.0_D8), [`D9`](#rdimm-ddr4-tester-1.2.0_D9)) - user-configurable LEDs

## Board configuration

Connect power supply (7-15VDC) to [`J3`](#rdimm-ddr4-tester-1.2.0_J3) barrel jack.
Then connect the board USB cable ([`J9`](#rdimm-ddr4-tester-1.2.0_J9)) and Ethernet cable ([`J2`](#rdimm-ddr4-tester-1.2.0_J2)) to your computer and insert the memory module to the socket [`U14`](#rdimm-ddr4-tester-1.2.0_U14).
To turn the board on, use power switch [`S3`](#rdimm-ddr4-tester-1.2.0_S3).

After power is up, configure the network and prepare the board for uploading the bitstream.

A JTAG/SPI switch `S2` on the right side of the board (near the JTAG connector) defines whether the bitstream is loaded via JTAG or SPI Flash memory.
Bitstream will be loaded from flash memory upon device power-on or after pressing the [`PROG_B1`](#rdimm-ddr4-tester-1.2.0_PROG_B1) button.
