# Arty-A7 board

The [Arty-A7 board](https://reference.digilentinc.com/reference/programmable-logic/arty-a7/start) allows testing its on-board DDR3 module.
The board is designed around the Artix-7 Field Programmable Gate Array (FPGA) from AMD(Xilinx).

:::{figure-md} arty-a7
![arty-a7](images/arty-a7.jpg)

Arty-A7 board
:::

The following instructions explain how to set up the board.
For FPGA digital design documentation for this board, refer to the [Digital design](build/arty/documentation/index.rst) chapter.

## Board configuration

Connect the board USB and Ethernet cables to your computer and configure the netiwork.
The bitstream will be loaded from flash memory upon device power-on or after pressing the PROG button.
