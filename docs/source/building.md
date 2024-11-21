# Building the design targets

As the rowhammer attack exploits physical properties of cells in DRAM (draining charges), no bit flips can be observed in simulation mode (see [Simulation section](#simulation)).
However, the simulation mode is useful for testing command sequences during development.

The Makefile can be configured using environmental variables to modify the network configuration used and to select the target.
Currently, 6 boards are supported, each targeting a different DRAM type and form factor:

This chapter provides building instructions for synthesising the digital design for physical DRAM testers and simulation models.
The building process is coordinated with a `Makefile` located in the main folder of the Rowhammer tester repository.

Table below combines the build target names with specific physical hardware platforms used for testing the DRAM memories.

:::

| Hardware Platform             | Memory type      | TARGET                       |
|-------------------------------|------------------|------------------------------|
| Arty A7                       | DDR3             | `arty`                       |
| ZCU104                        | DDR4 (SO-DIMM)   | `zcu104`                     |
| Data Center RDIMM DDR4 Tester | DDR4 (RDIMM)     | `ddr4_datacenter_test_board` |
| LPDDR4 Test Board             | LPDDR4 (SO-DIMM) | `lpddr4_test_board`          |
| Data Center RDIMM DDR5 Tester | DDR5 (RDIMM)     | `ddr5_tester`                |
| DDR5 Test Board               | DDR5 (SO-DIMM)   | `ddr5_test_board`            |

In order to build or write a bistream for a particular board please export a `TARGET` variable pointing to a certain target name from the table above.

```sh
export TARGET=<target-name>
```

Then use the make command for building the bitstream.

```sh
make build
```
The generated bitstream will be stored in a `./build/<target-name>/gateware/` folder located in the root folder of the cloned `rowhammer-tester` repository.

To upload the bitstream to the FPGA configuration RAM on board:

```sh
make upload
```
The FPGA configuration RAM is a volatile memory so you would need to write the generated bitstream every time you power-cycle the board or reset the configuration state of the FPGA.

To load the bitstream into the FPGA configuration flash memory:

```sh
make flash
```

This will write the bistream into a non-volatile (Q)SPI Flash memory located on board.
The on-board FPGA will get automatically configured with a bistream stored in the Flash memory on power-on. 

Please refer to the board-specific chapters for further information on how to connect the board and configure it for uploading the bitstream.

```{note}
Running `make` will generate build files without invoking Vivado.
```




Boards are controlled the same way for both simulation and hardware runs.
In order to communicate with the board via EtherBone, start `litex_server` with the following command:

```sh
export IP_ADDRESS=192.168.100.50  # optional, should match the one used during build
make srv
```

The build files (CSRs address list) must be up-to-date.
The build files can be re-generated with `make` without arguments.

Then, in another terminal, you can use the Python scripts provided.
*Remember to enter the Python virtual environment before running the scripts!*
Also, the `TARGET` variable should be set to load configuration for the given target.
For example, to use the `leds.py` script, run the following:

```sh
source ./venv/bin/activate
export TARGET=arty  # (or zcu104) required to load target configuration
cd rowhammer_tester/scripts/
python leds.py  # stop with Ctrl-C
```

For board-specific instructions, refer to the following sections:

* [Arty-A7](arty.md)
* [LPDDR4 Test Board](lpddr4_test_board.md)
* [LPDDR4 Test Board with DDR5 Testbed](lpddr4_test_board_with_ddr5_testbed.md)
* [Data Center RDIMM DDR4 Tester](data_center_rdimm_ddr4_tester.md)
* [Data Center RDIMM DDR5 Tester](data_center_rdimm_ddr5_tester.md)
* [SO-DIMM DDR5 Tester](so_dimm_ddr5_tester.md)
* [ZCU104](zcu104.md)

## Simulation setup

Select `TARGET`, generate intermediate files & run the simulation:

```sh
export TARGET=arty
make sim
```

This command will generate intermediate files & simulate them with Verilator.
After simulation has finished, a signal dump can be investigated using [gtkwave](http://gtkwave.sourceforge.net/):

```sh
gtkwave build/$TARGET/gateware/sim.fst
```

```{warning}
To run the simulation and the rowhammer scripts on a physical board at the same time, change the ``IP_ADDRESS`` variable, otherwise the simulation can conflict with the communication with your board.
```

```{warning}
The repository contains a wrapper script around `sudo` which disallows LiteX to interfere with
the host network configuration. This forces the user to manually configure a TUN interface for valid
communication with the simulated device.
```

1. Create the TUN interface:

   ```sh
   tunctl -u $USER -t litex-sim
   ```

1. Configure the IP address of the interface:

   ```sh
   ifconfig litex-sim 192.168.100.1/24 up
   ```

1. Optionally allow network traffic on this interface:

   ```sh
   iptables -A INPUT -i litex-sim -j ACCEPT
   iptables -A OUTPUT -o litex-sim -j ACCEPT
   ```

```{note}
Typing `make ARGS="--sim"` will cause LiteX to only generate intermediate files and stop right after.
```
