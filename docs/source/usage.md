# User guide

This tool can be run on real hardware (FPGAs) or in a simulation mode.
As the rowhammer attack exploits physical properties of cells in DRAM (draining charges), no bit flips can be observed in simulation mode (see [Simulation section](#simulation)).
However, the simulation mode is useful for testing command sequences during development.

The Makefile can be configured using environmental variables to modify the network configuration used and to select the target.
Currently, 6 boards are supported, each targeting a different memory type:

:::

| Board                      | Memory type      | TARGET                       |
|----------------------------|------------------|------------------------------|
| Arty A7                    | DDR3             | `arty`                       |
| ZCU104                     | DDR4 (SO-DIMM)   | `zcu104`                     |
| DDR Datacenter DRAM Tester | DDR4 (RDIMM)     | `ddr4_datacenter_test_board` |
| LPDDR4 Test Board          | LPDDR4 (SO-DIMM) | `lpddr4_test_board`          |
| DDR5 Tester                | DDR5 (RDIMM)     | `ddr5_tester`                |
| DDR5 Test Board            | DDR5 (SO-DIMM)   | `ddr5_test_board`            |

```{note}
Although you choose a target board for the simulation, it doesn't require having a physical board.
Simulation is done entirely on your computer.
```

For board-specific instructions refer to [Arty A7](arty.md), [ZCU104](zcu104.md), [DDR4 Datacenter DRAM Tester](ddr4_datacenter_dram_tester.md), [LPDDR4 Test Board](lpddr4_tb.md), [DDR5 Tester](ddr5_tester.md) and [DDR5 Test Board](ddr5_test_board.md) chapters.
The rest of this chapter describes operations that are common for all supported boards.

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

### Install Rowhammer tester

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

## Tests

To run project tests use:

```sh
make test
```

## Network USB adapter setup

In order to control the Rowhammer platform, an Ethernet connection is necessary.
In case you want to use an USB Ethernet adapter for this purpose, follow the instructions below.

1. Make sure you use a 1GbE USB network adapter.
2. Determine the MAC address for the USB network adapter:
   * Run `sudo lshw -class network -short` to get the list of all network interfaces
   * Check which of the devices uses the r8152 driver by running `sudo ethtool -i <device>`
   * Display the link information for the device running `sudo ip link show <device>` and look for the mac address next to the `link/ether` field.
3. Configure the USB network adapter to appear as network device `fpga0` using systemd
   * Create `/etc/systemd/network/10-fpga0.link` with the following contents:
  
    ```sh
    [Match]
    # Set this to the MAC address of the USB network adapter
    MACAddress=XX:XX:XX:XX:XX
    
    [Link]
    Name=fpga0
    ```

4. Configure the `fpga0` network device with a static IP address, always up (even when disconnected) and ignored by the network manager.
   * Run the following command, assuming your system uses NetworkManager:
  
      ```sh
      nmcli con add type ethernet con-name 'Rowhammer Tester' ifname fpga0 ipv4.method manual ipv4.addresses 192.168.100.100/24
      ```
  
   * Alternatively, if your system supports the legacy `interfaces` configuration file:
       1. Make sure your `/etc/network/interfaces` file contains the following line:
  
           ```sh
           source /etc/network/interfaces.d/*
           ```
  
       2. Create `/etc/network/interfaces.d/fpga0` with the following contents:
  
           ```sh
           auto fpga0
           allow-hotplug fpga0
           iface fpga0 inet static
                   address 192.168.100.100/24
           ```
  
       3. Check that `nmcli device` says the state is `connected (externally)` otherwise run `sudo systemctl restart NetworkManager`
   * Run `ifup fpga0`
5. Run `sudo udevadm control --reload` and then unplug the USB Ethernet device and plug it back in
6. Check whether an `fpga0` interface is present with the correct IP address by running `networkctl status`

```{note}
In case you see `libusb_open() failed with LIBUSB_ERROR_ACCESS` when trying to use the rowhammer tester scripts with the USB Ethernet adapter, it indicates a permissions issue.
To remedy it, allow access to the FTDI USB to serial port chip. 
Run `ls -l /dev/ttyUSB*`, check the listed group for tty's and add the current user to this group by running ``sudo adduser <username> <group>``.
```

(controlling-the-board)=
## Controlling the board

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

## Hammering

Rowhammer attacks can be run against a DRAM module.
It can be then used for measuring cell retention.
For the complete list of script modifiers, see `--help`.

There are two versions of the rowhammer script:

* `rowhammer.py` - uses regular memory access via EtherBone to fill/check the memory (slower)
* `hw_rowhammer.py` - BIST blocks will be used to fill/check the memory (much faster, but with some limitations regarding fill pattern)

BIST blocks are faster and are the intended way of running Rowhammer tester.

Hammering of a row is done by reading it. 
There are two ways to specify a number of reads:

* `--read_count N` - one pass of `N` reads
* `--read_count_range K M N` - multiple passes of reads, as generated by `range(K, M, N)`

Regardless of which one is used, the number of reads in one pass is divided equally between the hammered rows.
If a user specifies `--read_count 1000`, then each row will be hammered 500 times.

As standard, hammering is performed via DMA, but there is an alternative way with `--payload-executor` which bypasses the DMA and talks directly with the PHY.
That allows the user to issue specific activation, refresh and precharge commands.

### Attack modes

Several attack and row selection modes are available, but only one mode can be specified at a time.

* `--hammer-only`

  Hammers rows without error checks or reports.
  When run with `rowhammer.py`, the attack is limited to one row pair.
  `hw_rowhammer.py` can attack up to 32 rows.
  With `--payload-executor` enabled, the row limit is dictated by the payload memory size.

  For example, the following command will hammer rows 4 and 6 1000 times total (so 500 times each):

  ```sh
  (venv) $ python hw_rowhammer.py --hammer-only 4 6 --read_count 1000
  ```

* `--all-rows`

  Row pairs generated from the `range(start-row, nrows - row-pair-distance, row-jump)` expression will be hammered.

  The generated pairs come in the format of `(i, i + row-pair-distance)`.
  Table {numref}`default-all-rows-arguments` shows default values for arguments:

:::{table} default-all-rows-arguments

  | argument              | default |
  | --------------------- | ------- |
  | `--start-row`         | 0       |
  | `--row-jump`          | 1       |
  | `--row-pair-distance` | 2       |

:::

  For instance, to hammer rows `(0, 2), (1, 3), (2, 4)`, run the following command:

  ```sh
  (venv) $ python hw_rowhammer.py --all-rows --nrows 5
  ```

  And to hammer rows `(10, 13), (12, 15)`, run:

  ```sh
  (venv) $ python hw_rowhammer.py --all-rows --start-row 10 --nrows 16 --row-jump 2 --row-distance 3
  ```

  Setting `--row-pair-distance` to 0 lets you check how hammering a single row affects other rows.
  Normally, activations and deactivations are achieved with row reads using the DMA, but in this case this is not possible.
  Since a single row is being read all the time, no deactivation command would be sent by the DMA.
  In this case, the `--payload-executor` argument is required as it bypasses the DMA and sends deactivation commands on its own:

  ```sh
  (venv) $ python hw_rowhammer.py --all-rows --nrows 5 --row-pair-distance 0 --payload-executor
  ```

* `--row-pairs sequential`

  Hammers pairs of `(start-row, start-row + n)`, where `n` is a value from `0` to `nrows`, e.g.:

  ```sh
  (venv) $ python hw_rowhammer.py --row-pairs sequential --start-row 4 --nrows 10
  ```

  The command above will hammer the following set of row pairs:

  ```  
  (4, 4 + 0)
  (4, 4 + 1)
  ...
  (4, 4 + 9)
  (4, 4 + 10)
  ```

* `--row-pairs const`

  Two rows specified with the `const-rows-pair` parameter will be hammered:

  ```sh
  (venv) $ python hw_rowhammer.py --row-pairs const --const-rows-pair 4 6
  ```

* `--row-pairs random`

  `nrows` pairs of random rows will be hammered. Row numbers will be between `start-row` and `start-row + nrows`.

  ```sh
  (venv) $ python hw_rowhammer.py --row-pairs random --start-row 4 --nrows 10
  ```

* `--no-attack-time <time>`

  Instead of performing a rowhammer attack, the script will load the RAM with selected pattern and sleep for `time` nanoseconds.
  After this time, it will check for any bitflips that could have happened.
  This option does not imply `--no-refresh`.

  ```sh
  (venv) $ python hw_rowhammer.py --no-attack-time 100e9 --no-refresh
  ```

### Patterns

You can choose a pattern that memory will be initially filled with:

* `all_0` - all bits set to 0
* `all_1` - all bits set to 1
* `01_in_row` - alternating 0s and 1s in a row (`0xaaaaaaaa` in hex)
* `01_per_row` - all 0s in odd-numbered rows, all 1s in even rows
* `rand_per_row` - random values for all rows

### Example output

```sh
(venv) $ python hw_rowhammer.py --nrows 512 --read_count 10e6 --pattern 01_in_row --row-pairs const --const-rows-pair 54 133 --no-refresh
Preparing ...
WARNING: only single word patterns supported, using: 0xaaaaaaaa
Filling memory with data ...
Progress: [========================================] 16777216 / 16777216
Verifying written memory ...
Progress: [========================================] 16777216 / 16777216 (Errors: 0)
OK
Disabling refresh ...
Running Rowhammer attacks ...
read_count: 10000000
  Iter 0 / 1 Rows = (54, 133), Count = 10.00M / 10.00M
Reenabling refresh ...
Verifying attacked memory ...
Progress: [========================================] 16777216 / 16777216 (Errors: 30)
Bit-flips for row    53: 5
Bit-flips for row    55: 11
Bit-flips for row   132: 12
Bit-flips for row   134: 3
```

### Row selection examples

```{warning}
Attacks are performed on a single bank - bank 0 by default.
To change the bank that is being attacked use the `--bank` flag.
```

* Select row pairs from row 3 (`--start-row`) to row 59 (`--nrows`) where the next pair is 5 rows over (`--row-jump`) from the previous one:

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --all-rows --start-row 3 --nrows 60 --row-jump 5 --no-refresh --read_count 10e4
  ```

* Select row pairs from row 3 to row 59 without a distance between subsequent pairs (no `--row-jump`), which means that rows pairs are incremented by 1:

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --all-rows --start-row 3 --nrows 60 --no-refresh --read_count 10e4
  ```

* Select all row pairs (from `0` to `nrows - 1`):

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --all-rows --nrows 512 --no-refresh --read_count 10e4
  ```

* Select all row pairs (from `0` to `nrows - 1`) and save the error summary in JSON format to the `test` directory:

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --all-rows --nrows 512 --no-refresh --read_count 10e4 --log-dir ./test
  ```

* Select a single row (42 in this case) and save the error summary in JSON format to the `test` directory:

  ```sh
  (venv) $ python hw_rowhammer.py --pattern all_1 --row-pairs const --const-rows-pair 42 42 --no-refresh --read_count 10e4 --log-dir ./test
  ```

* Select all rows (from `0` to `nrows - 1`) and hammer them one by one 1M times each.

  ```sh
  (venv) $ python hw_rowhammer.py --all-rows --nrows 100 --row-pair-distance 0 --payload-executor --no-refresh --read_count 1e6
  ```

```{note}
Since for a single ended attack row activation needs to be triggered the `--payload-executor` switch is required.
The size of the payload memory is set by default to 1024 bytes and can be changed using the `--payload-size` switch.
```

### Cell retention measurement examples

* Select all row pairs (from 0 to nrows - 1) and perform a set of tests for different read count values, starting from 10e4 and ending at 10e5 with a step of 20e4 (`--read_count_range [start stop step]`):

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --all-rows --nrows 512 --no-refresh --read_count_range 10e4 10e5 20e4
  ```

* Perform a set of tests for different read count values in a given range for one row pair (50, 100):

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --row-pairs const --const-rows-pair 50 100 --no-refresh --read_count_range 10e4 10e5 20e4
  ```

* Perform a set of tests for different read count values in a given range for one row pair (50, 100) and stop the test execution as soon as a bitflip is found:

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --row-pairs const --const-rows-pair 50 100 --no-refresh --read_count_range 10e4 10e5 20e4 --exit-on-bit-flip
  ```

* Perform a set of tests for different read count values in a given range for one row pair (50, 100) and save the error summary in JSON format to the `test` directory:

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --row-pairs const --const-rows-pair 50 100 --no-refresh --read_count_range 10e4 10e5 20e4 --log-dir ./test
  ```

* Perform a set of tests for different read count values in a given range for a sequence of attacks for different pairs, where the first row of a pair is 40 and the second one is a row of a number from range (40, nrows - 1):

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --row-pairs sequential --start-row 40 --nrows 512 --no-refresh --read_count_range 10e4 10e5 20e4
  ```

## Utilities

Some scripts are simple and do not take command line arguments, others will provide help via `<script_name>.py --help` or `<script_name>.py -h`.

Few of the scripts accept a `--srv` option.
With this option enabled, a program will start its own instance of `litex_server` (the user doesn't need to run `make srv` to [control the board](#controlling-the-board)).

### Run LEDs demo - `leds.py`

Displays a simple "bouncing" animation using the LEDs on Arty-A7 board, with the light moving from side to side.

`-t TIME_MS` or `--time-ms TIME_MS` option can be used to adjust LED switching interval.

### Check version - `version.py`

Prints the data stored in the LiteX identification memory:

* hardware platform identifier
* source code git hash
* build date

Example output:

```sh
(venv) python version.py
Rowhammer tester SoC on xc7k160tffg676-1, git: e7854fdd16d5f958e616bbb4976a97962ee9197d 2022-07-24 15:46:52
```

### Check CSRs - `dump_regs.py`

Dumps values of all CSRs.
Example output of `dump_regs.py`:

```sh
0x82000000: 0x00000000 ctrl_reset
0x82000004: 0x12345678 ctrl_scratch
0x82000008: 0x00000000 ctrl_bus_errors
0x82002000: 0x00000000 uart_rxtx
0x82002004: 0x00000001 uart_txfull
0x82002008: 0x00000001 uart_rxempty
0x8200200c: 0x00000003 uart_ev_status
0x82002010: 0x00000000 uart_ev_pending
...
```

```{note}
Note that the `ctrl_scratch` value is `0x12345678`. This is the reset value of this register.
If you are getting a different value, it may indicate a problem.
```

### Initialize memory - `mem.py`

Before the DRAM memory can be used, perform initialization and leveling using the `mem.py` script.

Expected output:

```sh
(venv) $ python mem.py
(LiteX output)
--========== Initialization ============--
Initializing SDRAM @0x40000000...
Switching SDRAM to software control.
Read leveling:
  m0, b0: |11111111111110000000000000000000| delays: 06+-06
  m0, b1: |00000000000000111111111111111000| delays: 21+-08
  m0, b2: |00000000000000000000000000000011| delays: 31+-01
  m0, b3: |00000000000000000000000000000000| delays: -
  m0, b4: |00000000000000000000000000000000| delays: -
  m0, b5: |00000000000000000000000000000000| delays: -
  m0, b6: |00000000000000000000000000000000| delays: -
  m0, b7: |00000000000000000000000000000000| delays: -
  best: m0, b01 delays: 21+-07
  m1, b0: |11111111111111000000000000000000| delays: 07+-07
  m1, b1: |00000000000000111111111111111000| delays: 22+-08
  m1, b2: |00000000000000000000000000000001| delays: 31+-00
  m1, b3: |00000000000000000000000000000000| delays: -
  m1, b4: |00000000000000000000000000000000| delays: -
  m1, b5: |00000000000000000000000000000000| delays: -
  m1, b6: |00000000000000000000000000000000| delays: -
  m1, b7: |00000000000000000000000000000000| delays: -
  best: m1, b01 delays: 22+-08
Switching SDRAM to hardware control.
Memtest at 0x40000000 (2MiB)...
  Write: 0x40000000-0x40200000 2MiB
  Read: 0x40000000-0x40200000 2MiB
Memtest OK
Memspeed at 0x40000000 (2MiB)...
  Write speed: 12MiB/s
  === Initialization succeeded. ===
Proceeding ...

Memtest (basic)
OK

Memtest (random)
OK
```

### Enter BIOS - `bios_console.py`

It may happen that memory initialization fails when running the `mem.py` script.
This is most likely due to using boards that allow to swap memory modules, such as the ZCU104.

The memory initialization procedure is performed by the CPU instantiated inside the FPGA fabric.
The CPU runs the LiteX BIOS.
In case of memory training failure, it may be helpful to access the LiteX BIOS console.

If the script cannot find a serial terminal emulator program on the host system, it will fall back to `litex_term` which ships with LiteX.
It is however advised to install `picocom`/`minicom` as `litex_term` has worse performance.

In the BIOS console, use the `help` command to get information about other available commands.
To re-run memory initialization and training, type `reboot`.

```{note}
To close picocom/minicom, use the CTRL+A+X key combination.
```

Example:

```sh
(venv) $ python bios_console.py
LiteX Crossover UART created: /dev/pts/4
Using serial backend: auto
picocom v3.1

port is        : /dev/pts/4
flowcontrol    : none
baudrate is    : 1000000
parity is      : none
databits are   : 8
stopbits are   : 1
escape is      : C-a
local echo is  : no
noinit is      : no
noreset is     : no
hangup is      : no
nolock is      : no
send_cmd is    : sz -vv
receive_cmd is : rz -vv -E
imap is        :
omap is        :
emap is        : crcrlf,delbs,
logfile is     : none
initstring     : none
exit_after is  : not set
exit is        : no

Type [C-a] [C-h] to see available commands
Terminal ready
ad speed: 9MiB/s

--============== Boot ==================--
Booting from serial...
Press Q or ESC to abort boot completely.
sL5DdSMmkekro
            Timeout
No boot medium found

--============= Console ================--

litex>
```

#### Perform memory tests from the BIOS

After entering the BIOS, you may want to perform a memory test using utilities built into the BIOS.
There are several ways to do it:

* `mem_test` - performs a series of writes and reads to check if values read back are the same as those previously written.
  It is limited by a 32-bit address bus, so only 4 GiB of address space can be tested.
  You can get the origin of the RAM space using `mem_list` command.
* `sdram_test` - essentially `mem_test` but predefined for the first 1/32 of the defined RAM region size.
* `sdram_hw_test` - similar to `mem_test`, but accesses the SDRAM directly using DMAs, so it is not limited to 4 GiB.
  
  It requires passing 2 arguments (`origin` and `size`) with a 3rd optional argument, `burst_length`.
  When using `sdram_hw_test` you don't have to offset the `origin` like in the case of `mem_test`.
  `size` is a number of bytes to test and `burst_length` is a number of full transfer writes to the SDRAM before reading and checking the written content.
  The default value for `burst_length` is 1, which means that after every write, a check is performed.
  Generally, higher `burst_length` values mean faster operation.

### Test with BIST - `mem_bist.py`

A script written to test the BIST block functionality.
Two tests are available:

* `test-modules` - the memory is initialized and then a series of errors is introduced.
  Then BIST is used to check the contents of the memory.
  If the number of errors detected is equal to the number of errors introduced, the test is passed.
* `test-memory` - a simple test that writes a pattern in the memory, reads it, and checks whether the content is correct.
  Both write and read operations are done via BIST.

### Run benchmarks - `benchmark.py`

Benchmarks memory access performance. There are two subcommands available:

* `etherbone` - measure performance of the EtherBone bridge
* `bist` - measure performance of DMA DRAM access using the BIST modules

Example output:

```sh
(venv) $  python benchmark.py etherbone read 0x10000 --burst 255
Using generated target files in: build/lpddr4_test_board
Running measurement ...
Elapsed = 4.189 sec
Size    = 256.000 KiB
Speed   = 61.114 KiBps

(venv) $  python benchmark.py bist read
Using generated target files in: build/lpddr4_test_board
Filling memory before reading measurements ...
Progress: [========================================] 16777216 / 16777216
Running measurement ...
Progress: [========================================] 16777216 / 16777216 (Errors: 0)
Elapsed = 1.591 sec
Size    = 512.000 MiB
Speed   = 321.797 MiBps
```

### Use logic analyzer - `analyzer.py`

This script utilizes the Litescope functionality to gather debug information about signals in the LiteX system.
In-depth Litescope documentation is available on [GitHub](https://github.com/enjoy-digital/litex/wiki/Use-LiteScope-To-Debug-A-SoC).

Litescope analyzer needs to be instantiated in your design.
A sample design with the analyzer added is provided as the `arty_litescope` TARGET and can be run using the Arty-A7 board.
You can use `rowhammer_tester/targets/arty_litescope.py` as a reference for your own Litescope-enabled targets.

To build the `arty_litescope` sample and upload it to device, follow the instructions below:

1. In the root directory, run:

   ```sh
   export TARGET=arty_litescope
   make build
   make upload
   ```

   the `analyzer.csv` file will be created in the root directory.

2. Copy it to the target's build directory before using `analyzer.py`.

   ```sh
   cp analyzer.csv build/arty_litescope/
   ```

3. Start `litex-server` with:

   ```sh
   make srv
   ```

4. Execute the analyzer script in a separate shell:

   ```sh
   export TARGET=arty_litescope
   python rowhammer_tester/scripts/analyzer.py
   ```

   Results will be stored in the `dump.vcd` file and can be viewed using `gtkwave`:

   ```sh
   gtkwave dump.vcd
   ```

## Simulation

Select `TARGET`, generate intermediate files & run the simulation:

```sh
export TARGET=arty # (or zcu104)
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

2. Configure the IP address of the interface:

   ```sh
   ifconfig litex-sim 192.168.100.1/24 up
   ```

3. Optionally allow network traffic on this interface:

   ```sh
   iptables -A INPUT -i litex-sim -j ACCEPT
   iptables -A OUTPUT -o litex-sim -j ACCEPT
   ```

```{note}
Typing `make ARGS="--sim"` will cause LiteX to only generate intermediate files and stop right after.
```
