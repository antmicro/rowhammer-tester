# LPDDR4 Test Board

```{image} images/lpddr4-test-board.jpg
```

LPDDR4 Test Board is a platform developed by Antmicro for testing LPDDR4 memory.
It uses Xilinx Kintex-7 FPGA (XC7K70T-FBG484) and by default includes a custom SO-DIMM module with Micron's MT53E256M16D1 LPDDR4 DRAM.

The hardware is open and can be found on GitHub:

- Test board: <https://github.com/antmicro/lpddr4-test-board>
- Testbed: <https://github.com/antmicro/lpddr4-testbed>

## Board configuration

First insert the LPDDR4 DRAM module into the socket [``](#lpddr4-test-board_) and make sure that jumpers are set in correct positions:

- VDDQ switch ([`J7`](#lpddr4-test-board_J7)) should be set in position 1V1
- [`MODE1`](#lpddr4-test-board_MODE1) switch should be set in position FLASH

Connect power supply (7-15VDC) to [`J6`](#lpddr4-test-board_J6) barrel jack.
Then connect the board's USB-C [`J1`](#lpddr4-test-board_J1) and Ethernet [`J5`](#lpddr4-test-board_J5) interfaces to your computer.
Turn the board on using power switch [`S1`](#lpddr4-test-board_S1).
Then configure the network. The board's IP address will be `192.168.100.50` (so you could e.g. use `192.168.100.2/24`). The `IP_ADDRESS` environment variable can be used to modify the board's address.
Next, generate the FPGA bitstream:

```sh
export TARGET=lpddr4_test_board
make build
```

The results will be located in: `build/lpddr4_test_board/gateware/antmicro_lpddr4_test_board.bit`. To upload it, use:

```sh
export TARGET=lpddr4_test_board
make upload
```

```{note}
By typing `make` (without `build`) LiteX will generate build files without invoking Vivado.
```

To save bitstream in flash memory, use:

```sh
export TARGET=lpddr4_test_board
make flash
```

```{warning}
There is a JTAG/FLASH jumper [`MODE1`](#lpddr4-test-board_MODE1) on the right side of the board.
Unless it's set to the FLASH setting, the FPGA will load the bitstream received via JTAG ([`J4`](#lpddr4-test-board_J4)).
```

Bitstream will be loaded from flash memory upon device power-on or after a PROG button ([`PROG_B1`](#lpddr4-test-board_PROG_B1)) press.
