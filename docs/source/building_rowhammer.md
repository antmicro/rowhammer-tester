# Building Rowhammer designs

This chapter provides building instructions for synthesizing the digital design for physical DRAM testers and simulation models.

## Building and uploading the bitstreams

The bitstream building process is coordinated with a `Makefile` located in the main folder of the Rowhammer Tester repository.
Currently, 6 main targets are provided, each targeting a different DRAM type and memory form factor.
Use the tab view below to select a DRAM memory type of interest.
You will be provided with a name of the built target, building instruction and a link to the relevant hardware platform.

````{tab} LPDDR5 (IC)

This targets a single LPDDR5 IC soldered to the [LPDDR5 Test Bed](lpddr5_test_bed.md) that is installed in the [SO-DIMM DDR5 Tester](so_dimm_ddr5_tester.md).

A typical building command is:

```sh
export TARGET=sodimm_lpddr5_tester
make build TARGET_ARGS="--l2-size 256 --build --sys-clk-freq 50e6 --rw-bios --no-sdram-hw-test"
```

The target can be customized with the following build parameters
* ``--l2-size`` sets L2 cache size
* ``--sys-clk-freq`` specifies system clock frequency
* ``--no-sdram-hw-test`` disables hardware accelerated memory test

To upload the bitstream to volatile FPGA configuration RAM use:

```sh
export TARGET=sodimm_lpddr5_tester
make upload
```

To write the bitstream into non-volatile (Q)SPI Flash memory use:

```sh
export TARGET=sodimm_lpddr5_tester
make flash
```
````

````{tab} DDR5 (SO-DIMM)

This targets an off-the-shelf DDR5 SO-DIMMs installed on Antmicro [SO-DIMM DDR5 Tester](so_dimm_ddr5_tester.md).
A typical building command is:

```sh
export TARGET=sodimm_ddr5_tester
make build TARGET_ARGS="--l2-size 256 --build --iodelay-clk-freq 400e6 --bios-lto --rw-bios --no-sdram-hw-test"
```

The target can be customized with the following build parameters
* ``--l2-size`` sets L2 cache size
* ``--iodelayclk-freq`` specifies IODELAY clock frequency
* ``--no-sdram-hw-test`` disables hardware accelerated memory test

To upload the bitstream to volatile FPGA configuration RAM use:

```sh
export TARGET=sodimm_ddr5_tester
make upload
```

To write the bitstream into non-volatile (Q)SPI Flash memory use:

```sh
export TARGET=sodimm_ddr5_tester
make flash
```
````
````{tab} DDR5 (RDIMM)

This targets an off-the-shelf DDR5 RDIMMs installed on Antmicro [RDIMM DDR5 Tester](rdimm_ddr5_tester.md).

```{note}
Currently only revision 1.0 of the RDIMM DDR5 Tester is supported with bitstream target.
Software integration and RDIMM DDR5 PHY development for Artix UltraScale Plus FPGA existing on RDIMM DDR5 Tester in revision 2.0 is currently ongoing.
```

A typical building command is:

```sh
export TARGET=ddr5_tester
make build TARGET_ARGS="--l2-size 256 --build --iodelay-clk-freq 400e6 --bios-lto --rw-bios --module MTC10F1084S1RC --no-sdram-hw-test"
```

The target can be customized with the following build parameters
* ``--l2-size`` sets L2 cache size
* ``--iodelayclk-freq`` specifies IODELAY clock frequency
* ``--module`` specifies RDIMM DDR5 module family
* ``--no-sdram-hw-test`` disables hardware accelerated memory test

To upload the bitstream to volatile FPGA configuration RAM use:

```sh
export TARGET=ddr5_tester
make upload
```

To write the bitstream into non-volatile (Q)SPI Flash memory use:

```sh
export TARGET=ddr5_tester
make flash
```

````

````{tab} DDR5 (IC)

This configuration allows to test a single DDR5 IC.
The hardware setup used in this scenario consist of a [LPDDR4 Tester](lpddr4_test_board.md) with a [DDR5 Test Bed](ddr5_test_bed.md) 
Since DDR5 and LPDDR4 support the same VDDQ IO voltages it is possible to use the Tester Board to interface with a single DDR5 IC.

You can build this target with:

```sh
export TARGET=ddr5_test_board
make build TARGET_ARGS="--l2-size 256 --build --iodelay-clk-freq 400e6 --bios-lto --rw-bios --no-sdram-hw-test"
```

The target can be customized with the following build parameters:
* ``--l2-size`` sets L2 cache size
* ``--no-sdram-hw-test`` disables hardware accelerated memory test

To upload the bitstream to volatile FPGA configuration RAM use:

```sh
export TARGET=ddr5_test_board
make upload
```

To write the bitstream into non-volatile (Q)SPI Flash memory use:

```sh
export TARGET=ddr5_test_board
make flash
```

````

````{tab} LPDDR4 (IC)

This targets single LPDDR4 ICs soldered to interchangeable testbeds installed on Antmicro [LPDDR4 Test Board](lpddr4_test_board.md).
You can build the target with:

```sh
export TARGET=lpddr4_test_board
make build
```

To upload the bitstream to volatile FPGA configuration RAM use:

```sh
export TARGET=lpddr4_test_board
make upload
```

To write the bitstream into non-volatile (Q)SPI Flash memory use:

```sh
export TARGET=lpddr4_test_board
make flash
```

````
````{tab} DDR4 (SO-DIMM)

This targets an off-the-shelf DDR4 SO-DIMMs installed on AMD-Xilinx [ZCU104](zcu104.md).
You can build the target with:

```sh
export TARGET=zcu104
make build
```

The generated bitstream file must be named `zcu104.bit` and written to an SD card used for booting the board.
Please refer to the [Loading the bitstream](zcu104.md#loading-the-bitstream) section for more details.

````
````{tab} DDR4 (RDIMM)

This targets an off-the-shelf DDR4 RDIMMs installed on Antmicro [RDIMM DDR4 Tester](rdimm_ddr4_tester.md).
You can build the target with:

```sh
export TARGET=ddr4_datacenter_test_board
make build
```

To upload the bitstream to volatile FPGA configuration RAM use:

```sh
export TARGET=ddr4_datacenter_test_board
make upload
```

To write the bitstream into non-volatile (Q)SPI Flash memory use:

```sh
export TARGET=ddr4_datacenter_test_board
make flash
```
````
````{tab} DDR3 (IC)
This is supported by the Digilent [Arty](arty.md) boards.
In this setup the Rowhammer Tester targets a single DDR3 IC installed on board.
For Arty A7-100T with the XC7A100TCSG324-1 FPGA use:

```sh
export TARGET=arty
make build TARGET_ARGS="--variant a7-100"
```

For Arty A7-35T with the XC7A35TICSG324-1L FPGA use:

```sh
export TARGET=arty
make build
```

To upload the bitstream to volatile FPGA configuration RAM use:

```sh
export TARGET=arty
make upload
```

To write the bitstream into non-volatile (Q)SPI Flash memory use:

```sh
export TARGET=arty
make flash
```

````

```{note}
Running `make` will generate build files without invoking Vivado.
```

The generated bitstreams are stored in the `./build/<target-name>/gateware/` folder named after respective target name used for building.

```{note}
The FPGA configuration RAM is a volatile memory so you would need to write the generated bitstream every time you power-cycle the board or reset the configuration state of the FPGA.
The on-board FPGA will get automatically configured with a bitstream stored in the Flash memory on power-on. 
Please refer to the board-specific chapters (provided along with build instructions) for further information on how to connect the board to a host PC and and how to configure it for uploading the bitstream.
```

## Ethernet connection

The hardware platforms flashed with a generated bitstream can be accessed via Ethernet connection.
The board's default IP address is `192.168.100.50` and you need to ensure the board and a host PC are registered within the same subnet (so, for example, you can use `192.168.100.2/24`).

```{note}
In order to change the default IP address assigned to the board please set the `IP_ADDRESS` environment variable, rebuild the bitstream and re-upload it to the board.
```

Boards are controlled the same way for both simulation and hardware runs.
In order to communicate with the board via EtherBone, start `litex_server` with the following command:

```sh
export IP_ADDRESS=192.168.100.50  # optional, should match the one used during build
make srv
```

The build files (CSRs address list) must be up-to-date.
The build files can be re-generated with `make`.

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

## Packaging the bitstream

To save the bitstream and use it later or share it, use the `make pack` utility target.
It packs the files necessary to load the bitstream and run rowhammer scripts on it.
These files are:

* `build/$TARGET/gateware/$TOP.bit`
* `build/$TARGET/csr.csv`
* `build/$TARGET/defs.csv`
* `build/$TARGET/sdram_init.py`
* `build/$TARGET/litedram_settings.json`

Running `make pack` creates a zip file named, for instance, `$TARGET-$BRANCH-$COMMIT.zip`.

To use a bitstream packaged this way, run `unzip your-bitstream-file.zip`.

## Building for simulation

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
