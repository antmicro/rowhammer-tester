# Arty-A7 board

The [Arty-A7 board](https://reference.digilentinc.com/reference/programmable-logic/arty-a7/start) allows testing its on-board DDR3 module.
The board is designed around the Artix-7™ Field Programmable Gate Array (FPGA) from Xilinx.

```{image} images/arty-a7.jpg
```

The following instructions explain how to set up the board.

## Board configuration

Connect the board USB and Ethernet cables to your computer and configure the network. The board's IP address will be `192.168.100.50` (so you could e.g. use `192.168.100.2/24`). The `IP_ADDRESS` environment variable can be used to modify the board's address.
Next, generate the FPGA bitstream:

```sh
export TARGET=arty
make build
```

```{note}
This will by default target Arty A7 with the XC7A35TICSG324-1L FPGA. To build for XC7A100TCSG324-1,
use `make build TARGET_ARGS="--variant a7-100"`
```

The results will be located in: `build/arty/gateware/digilent_arty.bit`. To upload it, use:

```sh
export TARGET=arty
make upload
```

```{note}
By typing `make` (without `build`) LiteX will generate build files without invoking Vivado.
```

To save bitstream in flash memory, use:

```sh
export TARGET=arty
make flash
```

Bitstream will be loaded from flash memory upon device power-on or after a PROG button press.
