# General board control

Boards are controlled the same way for both simulation and hardware runs.
In order to communicate with the board via EtherBone, start `litex_server` with the following command:

```sh
export IP_ADDRESS=192.168.100.50  # optional, should match the one used during build
make srv
```

```{warning}
To run the simulation and the rowhammer scripts on a physical board at the same time, change the ``IP_ADDRESS`` variable, otherwise the simulation can conflict with the communication with your board.
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
