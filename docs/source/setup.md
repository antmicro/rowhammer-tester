# Installation and setup

## Installing dependencies

Make sure you have Python 3 installed with the `venv` module, and the dependencies required to build
[verilator](https://github.com/verilator/verilator), [openFPGALoader](https://github.com/trabucayre/openFPGALoader)
and [OpenOCD](https://github.com/openocd-org/openocd).
To install the dependencies on Ubuntu 18.04 LTS, run:

```sh
apt install git build-essential autoconf cmake flex bison libftdi-dev libjson-c-dev libevent-dev libtinfo-dev uml-utilities python3 python3-venv python3-wheel protobuf-compiler libcairo2 libftdi1-2 libftdi1-dev libhidapi-hidraw0 libhidapi-dev libudev-dev pkg-config tree zlib1g-dev zip unzip help2man curl ethtool
```

````{note}
On some Debian-based systems, there's a problem with a broken dependency:

  ```sh
  libc6-dev : Breaks: libgcc-9-dev (< 9.3.0-5~) but 9.2.1-19 is to be installed
  ```

`gcc-9-base` package installation solves the problem.
````

On Ubuntu 22.04 LTS the following dependencies may also be required:

```sh
apt install libtool libusb-1.0-0-dev pkg-config
```

## Install Rowhammer tester

Clone the `rowhammer-tester` repository and install the rest of the required dependencies:

```sh
git clone --recursive https://github.com/antmicro/rowhammer-tester.git
cd rowhammer-tester
make deps
```

The last command will download and build all the dependencies (including a RISC-V GCC toolchain)
and set up a [Python virtual environment](https://docs.python.org/3/library/venv.html) under
the `./venv` directory with all the required packages installed.

The virtual environment allows you to use Python without installing the packages system-wide.
To enter the environment, you have to run `source venv/bin/activate` in each new shell.
You can also use the provided `make env` target, which will start a new Bash shell with the virtualenv already sourced.
You can install packages inside the virtual environment by entering the environment and then using `pip`.

To build the bitstream, you will also need to have Vivado (version 2020.2 or newer) installed and the `vivado` command available in your `PATH`.
To configure Vivado in the current shell, you need to `source /PATH/TO/Vivado/VERSION/settings64.sh`.
Then include it in your `.bashrc` or other shell init script.

To make the process automatic without hard-coding in the shell init script, you can use tools like [direnv](https://github.com/direnv/direnv).
A sample `.envrc` file looks like so:

```sh
source venv/bin/activate
source /PATH/TO/Vivado/VERSION/settings64.sh
```

All other commands assume that you run Python from the virtual environment with `vivado` in your `PATH`.

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
You can then view the documentation in a browser at `http://127.0.0.1:8000`.
```

## Unit tests

To run unit tests for rowhammer tester modules, use:

```sh
make test
```

## Network USB adapter setup

In order to control the Rowhammer platform, an Ethernet connection is necessary.
In case you want to use an USB Ethernet adapter for this purpose, follow the instructions below.

1. Make sure you use a 1GbE USB network adapter.
1. Determine the MAC address for the USB network adapter:
   * Run `sudo lshw -class network -short` to get the list of all network interfaces
   * Check which of the devices uses the r8152 driver by running `sudo ethtool -i <device>`
   * Display the link information for the device running `sudo ip link show <device>` and look for the mac address next to the `link/ether` field.
1. Configure the USB network adapter to appear as network device `fpga0` using systemd
   * Create `/etc/systemd/network/10-fpga0.link` with the following contents:
  
    ```sh
    [Match]
    # Set this to the MAC address of the USB network adapter
    MACAddress=XX:XX:XX:XX:XX
    
    [Link]
    Name=fpga0
    ```

1. Configure the `fpga0` network device with a static IP address, always up (even when disconnected) and ignored by the network manager.
   * Run the following command, assuming your system uses NetworkManager:
  
      ```sh
      nmcli con add type ethernet con-name 'Rowhammer Tester' ifname fpga0 ipv4.method manual ipv4.addresses 192.168.100.100/24
      ```
  
   * Alternatively, if your system supports the legacy `interfaces` configuration file:
       1. Make sure your `/etc/network/interfaces` file contains the following line:
  
           ```sh
           source /etc/network/interfaces.d/*
           ```
  
       1. Create `/etc/network/interfaces.d/fpga0` with the following contents:
  
           ```sh
           auto fpga0
           allow-hotplug fpga0
           iface fpga0 inet static
                   address 192.168.100.100/24
           ```
  
       1. Check that `nmcli device` says the state is `connected (externally)` otherwise run `sudo systemctl restart NetworkManager`
   * Run `ifup fpga0`
1. Run `sudo udevadm control --reload` and then unplug the USB Ethernet device and plug it back in
1. Check whether an `fpga0` interface is present with the correct IP address by running `networkctl status`

```{note}
In case you see `libusb_open() failed with LIBUSB_ERROR_ACCESS` when trying to use the rowhammer tester scripts with the USB Ethernet adapter, it indicates a permissions issue.
To remedy it, allow access to the FTDI USB to serial port chip. 
Run `ls -l /dev/ttyUSB*`, check the listed group for tty's and add the current user to this group by running ``sudo adduser <username> <group>``.
```
