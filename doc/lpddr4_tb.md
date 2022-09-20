# LPDDR4 Test Board

```{image} lpddr4-test-board.jpg
```

LPDDR4 Test Board is a platform developed by Antmicro for testing LPDDR4 memory.
It uses Xilinx Kintex-7 FPGA (XC7K70T-FBG484) and by default includes a custom SO-DIMM module with Micron's MT53E256M16D1 LPDDR4 DRAM.

The hardware is open and can be found on GitHub:

- Test board: <https://github.com/antmicro/lpddr4-test-board>
- Testbed: <https://github.com/antmicro/lpddr4-testbed>

## Board configuration

First insert the LPDDDR4 DRAM module into the socket and make sure that jumpers are set in correct positions:

- VDDQ (J10) should be set in position 1V1
- MODE2 should be set in position FLASH

Then connect the board USB and Ethernet cables to your computer and configure the network. The board's IP address will be `192.168.100.50` (so you could e.g. use `192.168.100.2/24`). The `IP_ADDRESS` environment variable can be used to modify the board's address.
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

To load bitstream from flash memory press PROG_B1 button on LPDDR4 Test Board. MODE2 jumper must be in FLASH position.
