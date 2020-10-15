# LiteX Row Hammer Tester

The aim of this project is to provide a platform for testing the [DRAM "Row Hammer" vulnerability](https://users.ece.cmu.edu/~yoonguk/papers/kim-isca14.pdf).


## Setup

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

## Usage

Currently, scripts support one FPGA board: Arty-A7 (xc7a35t) and one simulation (based on Arty-A7).

### Preparations

Download submodules and build helper software:
```
make deps
```

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

### Using scripts

Some example scripts included in the repository:

#### Leds

Turn the leds on Arty-A7 board on, off, and on again:
```
make leds
```

### Register dump

Dumps registers values located in uploaded design:
```
make dump_regs
```

### Basic memory test

Configures (without read/write leveling) memory and tests it:
```
make mem
```
