# LiteX Row Hammer Tester

The aim of this project is to provide a platform for testing the [DRAM "Row Hammer" vulnerability](https://users.ece.cmu.edu/~yoonguk/papers/kim-isca14.pdf).


## Archtecture

The setup consists of FPGA gateware and application side software.
The following diagram illustrates the general system architecture.

![Archtecture diagram](./doc/architecture.png)

The DRAM is connected to [LiteDRAM](https://github.com/enjoy-digital/litedram) which provides swappable PHYs and a DRAM controller implementation.

In the default bulk transfer mode the LiteDRAM controller is connected to PHY and ensures correct DRAM traffic.
Bulk transfers can be controlled using dedicated Control & Status Registers (CSRs) and use LiteDRAM DMA to ensure fast operation.

Payload Executor allow executing a user-provided sequence of commands.
It temporarily disconnects the DRAM controller from PHY, executes the instructions stored in the SRAM memory
translating them into DFI commands and finally reconnects the DRAM controller.

The application side consists of a set of Python scripts communicating with the FPGA using the LiteX EtherBone bridge.

## Installing dependencies

Make sure you have Python 3 installed with the `venv` module, and the dependencies required to build
[verilator](https://github.com/verilator/verilator) and [xc3sprog](https://github.com/matrix-io/xc3sprog).
To install the dependencies on Ubuntu 18.04 LTS run:
```
apt install build-essential cmake flex bison libftdi-dev libjson-c-dev uml-utilities python3 python3-venv
```

Then run:
```
make deps
```
This will download and build all the dependencies and setup a [Python virtual environment](https://docs.python.org/3/library/venv.html) under `./venv` directory with all the required packages installed.

Virtual environment allows you to use Python without installing the packages system-wide.
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

## Usage

Currently, scripts support one FPGA board: Arty-A7 (xc7a35t) and one simulation (based on Arty-A7).

### Arty-A7 board

Connect the board USB and Ethernet cables to your computer, then configure the network. The board IP address will be `192.168.100.50` (so you could e.g. use `192.168.100.2/24`).
Then generate the FPGA bitstream:
```
make build
```
the results will be located in directory: `build/arty/gateware/arty.bit`. To upload it use:
```
make upload
```

> TIP: By typing `make` (without `build`) LiteX will generate build files without invoking Vivado.

### Arty-A7 simulation

Generate intermediate files & run simulation:

```
make sim
```

This command will generate intermediate files & simulate them with Verilator.

WARNING: The repository contains a wrapper script around `sudo` which disallows LiteX to interfere with
the host network configuration. This forces the user to manually configure TUN interface for valid
communication with the simulated device:

1. Create TUN interface:
```
tunctl -u $USER -t arty
```

2. Configure IP address of a interface:
```
ifconfig arty 192.168.100.1/24 up
```

3. (Optionally) allow network traffic on this interface:
```
iptables -A INPUT -i arty -j ACCEPT
iptables -A OUTPUT -o arty -j ACCEPT
```

TIP: By typing `make ARGS="--sim"` LiteX will generate only intermediate files and stop right after.

### Controlling the board

Board control is the same for both simulation and hardware runs.
In order to communicate with the board via EtherBone, the `litex_server` needs to be started with the following command:
```
make srv
```
The build files (CSRs address list) must be up to date. It can be re-generated with `make` without arguments.

Then in another terminal you can use the Python scripts provided. *Remember to enter the Python virtual environment before running the scripts!*
For example to use the `leds.py` script run the following:
```
source ./venv/bin/activate
cd scripts/
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

To perform a row hammer attack sequence use the `rowhammer.py` script (see `--help`), e.g:
```
python rowhammer.py 512 --read_count 10e6 --pattern 01_in_row --row-pairs const --const-rows-pair 54 133 --no-refresh
```
To generate a plot (requires `pip install -r requirements-dev.txt`) one can use:
```
python rowhammer.py 512 --read_count 10e6 --pattern 01_in_row --row-pairs const --const-rows-pair 54 133 --no-refresh --plot
```
