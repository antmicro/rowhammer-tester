# LiteX Row Hammer Tester

The aim of this project is to provide a platform for testing the [DRAM "Row Hammer" vulnerability](https://users.ece.cmu.edu/~yoonguk/papers/kim-isca14.pdf).


## Archtecture

The setup consists of FPGA gateware and application side software.
The following diagram illustrates the general system architecture.

![Archtecture diagram](./doc/architecture.png)

The DRAM is connected to [LiteDRAM](https://github.com/enjoy-digital/litedram) which provides swappable PHYs and a DRAM controller implementation.

In the default bulk transfer mode the LiteDRAM controller is connected to PHY and ensures correct DRAM traffic.
Bulk transfers can be controlled using dedicated Control & Status Registers (CSRs) and use LiteDRAM DMA to ensure fast operation.

The Payload Executor allows executing a user-provided sequence of commands.
It temporarily disconnects the DRAM controller from PHY, executes the instructions stored in the SRAM memory
translating them into DFI commands and finally reconnects the DRAM controller.

The application side consists of a set of Python scripts communicating with the FPGA using the LiteX EtherBone bridge.

## Installing dependencies

Make sure you have Python 3 installed with the `venv` module, and the dependencies required to build
[verilator](https://github.com/verilator/verilator) and [xc3sprog](https://github.com/matrix-io/xc3sprog).
To install the dependencies on Ubuntu 18.04 LTS run:
```
apt install git build-essential autoconf cmake flex bison libftdi-dev libjson-c-dev libevent-dev libtinfo-dev uml-utilities python3 python3-venv python3-wheel protobuf-compiler
```

Then run:
```
make deps
```
This will download and build all the dependencies and setup a [Python virtual environment](https://docs.python.org/3/library/venv.html) under the `./venv` directory with all the required packages installed.

The virtual environment allows you to use Python without installing the packages system-wide.
To enter the environment you have to run `source venv/bin/activate` in each new shell.
You can also use the provided `make env` target which will start a new Bash shell with the virtualenv already sourced.
You can install packages inside the virtual environment by entering the environment and then using `pip`.

> Some options to the scripts may require additional Python dependencies. To install them run `pip install -r requirements-dev.txt` inside the virtual environment.

To build the bitstream you will also need to have Vivado installed and the `vivado` command available in your `PATH`.
To configure Vivado in the current shell you need to `source /PATH/TO/Vivado/VERSION/settings64.sh`.
This can be put in your `.bashrc` or other shell init script.

To make the process automatic without hard-coding these things in shell init script,
tools like [direnv](https://github.com/direnv/direnv) can be used. A sample `.envrc` file would then look like this:
```
source venv/bin/activate
source /PATH/TO/Vivado/VERSION/settings64.sh
```

All other commands assume that you run Python from the virtual environment with `vivado` in your `PATH`.

## Documentation

The gareware documentation for the `master` branch is hosted on Github Pages [here](https://antmicro.github.io/litex-rowhammer-tester/).
To build the documentation from sources, use:
```
make doc
```
The documentation will be located in `build/documentation/html/index.html`.

## Tests

To run project tests use:
```
make test
```

## Usage

The Makefile can be configured using environmental variables to modify the network configuration used and to select the target.
Currently, only the Arty-A7 (xc7a35t) FPGA board is supported (`TARGET=arty`). It can be run on hardware or in simulation.

### Arty-A7 board

Connect the board USB and Ethernet cables to your computer, then configure the network. The board'w IP address will be `192.168.100.50` (so you could e.g. use `192.168.100.2/24`). The `IP_ADDRESS` environment variable can be used to modify the board's address.
Then generate the FPGA bitstream:
```
export TARGET=arty
make build
```
The results will be located in: `build/arty/gateware/arty.bit`. To upload it use:
```
export TARGET=arty
make upload
```

> TIP: By typing `make` (without `build`) LiteX will generate build files without invoking Vivado.

### ZCU104 board

Currently ZCU104 is not yet fully functional, as it uses UART for communication instead of Ethernet.
Connect the power supply and microUSB cable and run:
```
export TARGET=zcu104
make build
make upload
```
Use all the scripts normally, but instead of starting the `litex_server` as described below, use:
```
litex_server --uart --uart-baudrate 1e6 --uart-port /dev/ttyUSB3   # use proper USB serial port
```

### Simulation

Select `TARGET`, generate intermediate files & run simulation:

```
export TARGET=arty
make sim
```

This command will generate intermediate files & simulate them with Verilator.
After simulation has finished, a signals dump can be investigated using [gtkwave](http://gtkwave.sourceforge.net/):
```
gtkwave build/$TARGET/gateware/sim.fst
```

WARNING: The repository contains a wrapper script around `sudo` which disallows LiteX to interfere with
the host network configuration. This forces the user to manually configure a TUN interface for valid
communication with the simulated device:

1. Create the TUN interface:
```
tunctl -u $USER -t litex-sim
```

2. Configure the IP address of the interface:
```
ifconfig litex-sim 192.168.100.1/24 up
```

3. (Optionally) allow network traffic on this interface:
```
iptables -A INPUT -i litex-sim -j ACCEPT
iptables -A OUTPUT -o litex-sim -j ACCEPT
```

TIP: By typing `make ARGS="--sim"` LiteX will generate only intermediate files and stop right after that.

### Controlling the board

Board control is the same for both simulation and hardware runs.
In order to communicate with the board via EtherBone, the `litex_server` needs to be started with the following command:
```
export IP_ADDRESS=192.168.100.50  # optional, should match the one used during build
make srv
```
The build files (CSRs address list) must be up to date. It can be re-generated with `make` without arguments.

Then, in another terminal, you can use the Python scripts provided. *Remember to enter the Python virtual environment before running the scripts!* Also, the `TARGET` variable should be set to load configuration for the given target.
For example to use the `leds.py` script run the following:
```
source ./venv/bin/activate
export TARGET=arty  # required to load target configuration
cd rowhammer_tester/scripts/
python leds.py  # stop with Ctrl-C
```

Some scripts are simple and do not take command line arguments, others will provide help via `SCRIPT.PY --help`.

#### Examples

Simple scripts:

* `leds.py` - Turn the leds on Arty-A7 board on, off, and on again
* `dump_regs.py` - Dump the values of all CSRs

Before the DRAM memory can be used the initialization and leveling must be performed. To do this run:
```
python mem.py
```

> NOTE: when running in simulation running the read leveling will fail. To avoid it use `python mem.py --no-init`

To perform a Row Hammer attack sequence use the `rowhammer.py` script (see `--help`), e.g:
```
python rowhammer.py --nrows 512 --read_count 10e6 --pattern 01_in_row --row-pairs const --const-rows-pair 54 133 --no-refresh
```
To generate a plot (requires `pip install -r requirements-dev.txt`) you can use:
```
python rowhammer.py --nrows 512 --read_count 10e6 --pattern 01_in_row --row-pairs const --const-rows-pair 54 133 --no-refresh --plot
```

To make use of BIST modules to fill/check the memory one can use:
```
python hw_rowhammer.py --nrows 512 --read_count 10e6 --pattern 01_in_row --row-pairs const --const-rows-pair 54 133 --no-refresh
```
