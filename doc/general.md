# General

The aim of this project is to provide a platform for testing [DRAM vulnerability to rowhammer attacks](https://users.ece.cmu.edu/~yoonguk/papers/kim-isca14.pdf).

(architecture)=
## Architecture

The setup consists of FPGA gateware and application side software.
The following diagram illustrates the general system architecture.

```{image} ./images/architecture.png
:alt: Architecture diagram
:target: ./images/architecture.png
```

The DRAM is connected to [LiteDRAM](https://github.com/enjoy-digital/litedram), which provides swappable PHYs and a DRAM controller implementation.

In the default bulk transfer mode the LiteDRAM controller is connected to PHY and ensures correct DRAM traffic.
Bulk transfers can be controlled using dedicated Control & Status Registers (CSRs) and use LiteDRAM DMA to ensure fast operation.

The Payload Executor allows executing a user-provided sequence of commands.
It temporarily disconnects the DRAM controller from PHY, executes the instructions stored in the SRAM memory,
translating them into DFI commands and finally reconnects the DRAM controller.

The application side consists of a set of Python scripts communicating with the FPGA using the LiteX EtherBone bridge.

## Installing dependencies

Make sure you have Python 3 installed with the `venv` module, and the dependencies required to build
[verilator](https://github.com/verilator/verilator), [openFPGALoader](https://github.com/trabucayre/openFPGALoader)
and [OpenOCD](https://github.com/openocd-org/openocd).
To install the dependencies on Ubuntu 18.04 LTS, run:

```sh
apt install git build-essential autoconf cmake flex bison libftdi-dev libjson-c-dev libevent-dev libtinfo-dev uml-utilities python3 python3-venv python3-wheel protobuf-compiler libcairo2 libftdi1-2 libftdi1-dev libhidapi-hidraw0 libhidapi-dev libudev-dev pkg-config tree zlib1g-dev zip unzip help2man curl ethtool
```

````{note}
On some Debian-based systems there's a problem with a broken dependency:

  ```
  libc6-dev : Breaks: libgcc-9-dev (< 9.3.0-5~) but 9.2.1-19 is to be installed
  ```

`gcc-9-base` package installation solves the problem.
````

On Ubuntu 22.04 LTS the following dependencies may also be required:

```sh
apt install libtool libusb-1.0-0-dev pkg-config
```

### Rowhammer tester

Now clone the `rowhammer-tester` repository and install the rest of the required dependencies:

```sh
git clone --recursive https://github.com/antmicro/rowhammer-tester.git
cd rowhammer-tester
make deps
```

The last command will download and build all the dependencies (including a RISC-V GCC toolchain)
and will set up a [Python virtual environment](https://docs.python.org/3/library/venv.html) under
the `./venv` directory with all the required packages installed.

The virtual environment allows you to use Python without installing the packages system-wide.
To enter the environment, you have to run `source venv/bin/activate` in each new shell.
You can also use the provided `make env` target, which will start a new Bash shell with the virtualenv already sourced.
You can install packages inside the virtual environment by entering the environment and then using `pip`.

To build the bitstream you will also need to have Vivado (version 2020.2 or newer) installed and the `vivado` command available in your `PATH`.
To configure Vivado in the current shell, you need to `source /PATH/TO/Vivado/VERSION/settings64.sh`.
This can be put in your `.bashrc` or other shell init script.

To make the process automatic without hard-coding these things in shell init script,
tools like [direnv](https://github.com/direnv/direnv) can be used. A sample `.envrc` file would then look like this:

```sh
source venv/bin/activate
source /PATH/TO/Vivado/VERSION/settings64.sh
```

All other commands assume that you run Python from the virtual environment with `vivado` in your `PATH`.

## Packaging the bitstream

If you want to save the bitstream and use it later or share it with someone, there is an utility target `make pack`.
It packs files necessary to load the bitstream and run rowhammer scripts on it.
Those files are:
 - `build/$TARGET/gateware/$TOP.bit`
 - `build/$TARGET/csr.csv`
 - `build/$TARGET/defs.csv`
 - `build/$TARGET/sdram_init.py`
 - `build/$TARGET/litedram_settings.json`

After running `make pack`, you should have a zip file named like `$TARGET-$BRANCH-$COMMIT.zip`.

Next time you want to use a bitstream packaged in such way, all you need to do is to run
`unzip your-bitstream-file.zip` and you are all set.

## Local documentation build

The gateware part of the documentation is auto-generated from source files.
Other files are static and are located in the `doc/` directory.
To build the documentation, enter:

```sh
source venv/bin/activate
pip install -r requirements.txt
python -m sphinx -b html doc build/documentation/html
```

The documentation will be located in `build/documentation/index.html`.

```{note}
For easier development one can use [sphinx-autobuild](https://pypi.org/project/sphinx-autobuild)
using command `sphinx-autobuild -b html doc build/documentation/html --re-ignore 'doc/build/.*'`.
The documentation can be then viewed in a browser at `http://127.0.0.1:8000`.
```

## Tests

To run project tests use:

```sh
make test
```
