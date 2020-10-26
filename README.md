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

## Documentation

The gareware documentation for the `master` branch is hosted on Github Pages [here](https://antmicro.github.io/litex-rowhammer-tester/).

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

To enter the environment you have to `source venv/bin/activate`
and to build the bitstream you need to `source /PATH/TO/Vivado/VERSION/settings64.sh`.
This can be automated with tools like [direnv](https://github.com/direnv/direnv) with the following `.envrc` file:
```
source venv/bin/activate
source /PATH/TO/Vivado/VERSION/settings64.sh
```

All other commands assume that you run Python from the virtual environment with `vivado` in your `PATH`.
## Usage

Currently, scripts support one FPGA board: Arty-A7 (xc7a35t) and one simulation (based on Arty-A7).

### Build & upload gateware for Arty-A7

Generate bitstream for FPGA:

```
make build
```

the results will be located in directory: `build/arty/gateware/arty.bit`

Upload gateware to Arty-A7:
```
make upload
```

TIP: By typing `make` (without `build`) LiteX will generate build files without invoking Vivado.

### Build & run simulation based on Arty-A7

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

### Build documentation

The html documentation will be available in `build/documentation/html/index.html`:
```
make doc
```

### Using scripts

To use the scripts located in `scripts/` directory you first need to start `litex_server` in another terminal:
```
make srv
```

The you can use the provided scripts to control the FPGA:

* `leds.py` - Turn the leds on Arty-A7 board on, off, and on again
* `dump_regs.py` - Dump the values of all CSRs
* `mem.py` - Memory initialzation and test (use `--no-init` to avoid initialzation, e.g. in simulation)
* `rowhammer.py` - Perform a row hammer attack (use `--help` for script options)
