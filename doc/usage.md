# User guide

This tool can be run on real hardware (FPGAs) or in a simulation mode.
As the rowhammer attack exploits physical properties of cells in DRAM (draining charges), no bit flips can be observed in simulation mode.
However, the simulation mode is useful to test command sequences during the development.

The Makefile can be configured using environmental variables to modify the network configuration used and to select the target.
Currently, 4 boards are supported, each targeting different memory type:
| Board                      | Memory type      | TARGET                       |
|----------------------------|------------------|------------------------------|
| Arty A7                    | DDR3             | `arty`                       |
| ZCU104                     | DDR4 (SO-DIMM)   | `zcu104`                     |
| DDR Datacenter DRAM Tester | DDR4 (RDIMM)     | `ddr4_datacenter_test_board` |
| LPDDR4 Test Board          | LPDDR4 (SO-DIMM) | `lpddr4_test_board`          |

```{note}
Although you choose a target board for the simulation, it doesn't require having a physical board.
Simulation is done entirely on your computer.
```

For board-specific instructions refer to [Arty A7](arty.md), [ZCU104](zcu104.md), [DDR4 Datacenter DRAM Tester](ddr4_datacenter_dram_tester.md) and [LPDDR4 Test Board](lpddr4_tb.md) chapters.
The rest of this chapter describes operations that are common for all supported boards.


## Network USB adapter setup

In order to control the Rowhammer platform an Ethernet connection is necessary. 
In case you want to use an USB Ethernet adapter for this purpose read the instructions below.

1. Make sure you use a 1GbE USB network adapter
2. Figure out the MAC address for the USB network adapter:
   * Run ``sudo lshw -class network -short`` to get the list of all network interfaces
   * Check which of the devices uses the r8152 driver by running ``sudo ethtool -i <device>``
   * Display the link information for the device running ``sudo ip link show <device>`` and look for the mac address next to the ``link/ether`` field
3. Configure the USB network adapter to appear as network device ``fpga0`` using systemd
   * Create ``/etc/systemd/network/10-fpga0.link`` with the following contents:
      ```sh
      [Match]
      # Set this to the MAC address of the USB network adapter
      MACAddress=XX:XX:XX:XX:XX
      
      [Link]
      Name=fpga0
      ```
4. Configure the ``fpga0`` network device with a static IP address, always up (even when disconnected) and ignored by the network manager.
   * Make sure your ``/etc/network/interfaces`` file has the following line:
      ```sh
      source /etc/network/interfaces.d/*
      ```
   * Create ``/etc/network/interfaces.d/fpga0`` with the following contents:
      ```sh
      auto fpga0
      allow-hotplug fpga0
      iface fpga0 inet static
              address 192.168.100.100/24
      ```
   * Check that ``nmcli device`` says the state is ``connected (externally)`` otherwise run ``sudo systemctl restart NetworkManager``
   * Run ``ifup fpga0``
5. Run ``sudo udevadm control --reload`` and then unplug the USB ethernet device and plug it back in
6. Check you have an ``fpga0`` interface and it has the correct IP address by running ``networkctl status``

```{note} 
In case you see ``libusb_open() failed with LIBUSB_ERROR_ACCESS`` when trying to use the rowhammer tester scripts with the USB ethernet adapter then it means that you have a permissions issue and need to allow access to the FTDI USB to serial port chip. Check the group listed for the tty's when running ``ls -l /dev/ttyUSB*`` and add the current user to this group by running ``sudo adduser <username> <group>``.
```
(controlling-the-board)=
## Controlling the board

Board control is the same for both simulation and hardware runs.
In order to communicate with the board via EtherBone, the `litex_server` needs to be started with the following command:

```sh
export IP_ADDRESS=192.168.100.50  # optional, should match the one used during build
make srv
```

```{warning}
If you want to run the simulation and the rowhammer scripts on a physical board at the same time,
you have to change the ``IP_ADDRESS`` variable, otherwise the simulation can conflict with the communication with your board.
```

The build files (CSRs address list) must be up to date. It can be re-generated with `make` without arguments.

Then, in another terminal, you can use the Python scripts provided. *Remember to enter the Python virtual environment before running the scripts!* Also, the `TARGET` variable should be set to load configuration for the given target.
For example, to use the `leds.py` script, run the following:

```sh
source ./venv/bin/activate
export TARGET=arty  # (or zcu104) required to load target configuration
cd rowhammer_tester/scripts/
python leds.py  # stop with Ctrl-C
```

## Hammering

Rowhammer attacks can be run against a DRAM module. It can be then used for measuring cell retention.
For the complete list of scripts' modifiers, see `--help`.

There are two versions of a rowhammer script:

- `rowhammer.py` - this one uses regular memory access via EtherBone to fill/check the memory (slower)
- `hw_rowhammer.py` - BIST blocks will be used to fill/check the memory (much faster, but with some limitations regarding fill pattern)

BIST blocks are faster and are the intended way of running Row Hammer Tester.

Hammering of a row is done by reading it. There are two ways to specify a number of reads:

- `--read_count N`           - one pass of `N` reads
- `--read_count_range K M N` - multiple passes of reads, as generated by `range(K, M, N)`

Regardless of which one is used, the number of reads in one pass is divided equally between hammered rows.
If a user specifies `--read_count 1000`, then each row will be hammered 500 times.

Normally hammering is being performed via DMA, but there is also an alternative way with `--payload-executor`.
It bypasses the DMA and directly talks with the PHY.
That allows the user to issue specific activation, refresh and precharge commands.


### Attack modes

Different attack and row selection modes can be used, but only one of them can be specified at the same time.

- `--hammer-only`

  Only hammers a pair of rows, without doing any error checks or reports.

  For example following command will hammer rows 4 and 6 1000 times total (so 500 times each):

  ```sh
  (venv) $ python hw_rowhammer.py --hammer-only 4 6 --read_count 1000
  ```

- `--all-rows`

  Row pairs generated from `range(start-row, nrows - row-pair-distance, row-jump)` expression will be hammered.

  Generated pairs are of form `(i, i + row-pair-distance)`.
  Default values for used arguments are:

  | argument              | default |
  | --------------------- | ------- |
  | `--start-row`         | 0       |
  | `--row-jump`          | 1       |
  | `--row-pair-distance` | 2       |

  So you can run following command to hammer rows `(0, 2), (1, 3), (2, 4)`:

  ```sh
  (venv) $ python hw_rowhammer.py --all-rows --nrows 5
  ```

  And in case of:

  ```sh
  (venv) $ python hw_rowhammer.py --all-rows --start-row 10 --nrows 16 --row-jump 2 --row-distance 3
  ```

  hammered pairs would be: `(10, 13), (12, 15)`.

  In a special case, where `--row-pair-distance` is 0, you can check how hammering a single row affects other rows.
  Normally activations and deactivations are achieved with row reads using the DMA, but in this case it is not possible.
  Because the same row is being read all the time, no deactivation command would be sent by the DMA.
  In this case, `--payload-executor` is required as it bypasses the DMA and sends deactivation commands on its own.

  ```sh
  (venv) $ python hw_rowhammer.py --all-rows --nrows 5 --row-pair-distance 0 --payload-executor
  ```

- `--row-pairs sequential`

  Hammers pairs of `(start-row, start-row + n)`, where `n` is from 0 to `nrows`.

  ```sh
  (venv) $ python hw_rowhammer.py --row-pairs sequential --start-row 4 --nrows 10
  ```

  Command above, would hammer following set of row pairs:

  ```
  (4, 4 + 0)
  (4, 4 + 1)
  ...
  (4, 4 + 9)
  (4, 4 + 10)
  ```

- `--row-pairs const`

  Two rows specified with the `const-rows-pair` parameter will be hammered:

  ```sh
  (venv) $ python hw_rowhammer.py --row-pairs const --const-rows-pair 4 6
  ```

- `--row-pairs random`

  `nrows` pairs of random rows will be hammered. Row numbers will be between `start-row` and `start-row + nrows`.

  ```sh
  (venv) $ python hw_rowhammer.py --row-pairs random --start-row 4 --nrows 10
  ```

### Patterns

User can choose a pattern that memory will be initially filled with:

- `all_0` - all bits set to 0
- `all_1` - all bits set to 1
- `01_in_row` - alternating 0's and 1's in a row (`0xaaaaaaaa` in hex)
- `01_per_row` - all 0's in odd-numbered rows, all 1's in even rows
- `rand_per_row` - random values for all rows

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
Attacks are performd on a single bank.
By default it is bank 0.
To change the bank that is being attacked use the `--bank` flag.
```

- Select row pairs from row 3 (`--start-row`) to row 59 (`--nrows`) where the next pair is 5 rows away (`--row-jump`) from the previous one:

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --all-rows --start-row 3 --nrows 60 --row-jump 5 --no-refresh --read_count 10e4
  ```

- Select row pairs from row 3 to to row 59 without a distance between subsequent pairs (no `--row-jump`), which means that rows pairs are incremented by 1:

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --all-rows --start-row 3 --nrows 60 --no-refresh --read_count 10e4
  ```

- Select all row pairs (from 0 to nrows - 1):

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --all-rows --nrows 512 --no-refresh --read_count 10e4
  ```

- Select all row pairs (from 0 to nrows - 1) and save the error summary in JSON format to the `test` directory:

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --all-rows --nrows 512 --no-refresh --read_count 10e4 --log-dir ./test
  ```

- Select only one row (42 in this case) and save the error summary in JSON format to the `test` directory:

  ```sh
  (venv) $ python hw_rowhammer.py --pattern all_1 --row-pairs const --const-rows-pair 42 42 --no-refresh --read_count 10e4 --log-dir ./test
  ```

- Select all rows (from 0 to nrows - 1) and hammer them one by one 1M times each.

  ```sh
  (venv) $ python hw_rowhammer.py --all-rows --nrows 100 --row-pair-distance 0 --payload-executor --no-refresh --read_count 1e6
  ```

```{note}
Since for a single ended attack row activation needs to be triggered the `--payload-executor` switch is required.
The size of the payload memory is set by default to 1024 bytes and can be changed using the `--payload-size` switch.
```

### Cell retention measurement examples

- Select all row pairs (from 0 to nrows - 1) and perform a set of tests for different read count values, starting from 10e4 and ending at 10e5 with a step of 20e4 (`--read_count_range [start stop step]`):

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --all-rows --nrows 512 --no-refresh --read_count_range 10e4 10e5 20e4
  ```

- Perform set of tests for different read count values in a given range for one row pair (50, 100):

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --row-pairs const --const-rows-pair 50 100 --no-refresh --read_count_range 10e4 10e5 20e4
  ```

- Perform set of tests for different read count values in a given range for one row pair (50, 100) and stop the test execution as soon as a bitflip is found:

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --row-pairs const --const-rows-pair 50 100 --no-refresh --read_count_range 10e4 10e5 20e4 --exit-on-bit-flip
  ```

- Perform set of tests for different read count values in a given range for one row pair (50, 100) and save the error summary in JSON format to the `test` directory:

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --row-pairs const --const-rows-pair 50 100 --no-refresh --read_count_range 10e4 10e5 20e4 --log-dir ./test
  ```

- Perform set of tests for different read count values in a given range for a sequence of attacks for different pairs, where the first row of a pair is 40 and the second one is a row of a number from range (40, nrows - 1):

  ```sh
  (venv) $ python hw_rowhammer.py --pattern 01_in_row --row-pairs sequential --start-row 40 --nrows 512 --no-refresh --read_count_range 10e4 10e5 20e4
  ```

## Utilities

Some of the scripts are simple and do not take command line arguments, others will provide help via `<script_name>.py --help` or `<script_name>.py -h`.

Few of the scripts accept a `--srv` option. With this option enabled, a program will start it's own instance of `litex_server` (the user doesn't need to run `make srv` to {ref}`control the board <controlling the board>`)

### Run LEDs demo - `leds.py`

Displays a simple "bouncing" animation using the LEDs on Arty-A7 board, with the light moving from side to side.

`-t TIME_MS` or `--time-ms TIME_MS` option can be used to adjust LED switching interval.

### Check version - `version.py`

Prints the data stored in the LiteX identification memory:

- hardware platform identifier
- source code git hash
- build date

Example output:

```sh
(venv) python version.py
Row Hammer Tester SoC on xc7k160tffg676-1, git: e7854fdd16d5f958e616bbb4976a97962ee9197d 2022-07-24 15:46:52
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
Note that ctrl_scratch value is 0x12345678. This is the reset value of this register.
If you are getting a different, this may indicate a problem.
```

### Initialize memory - `mem.py`

Before the DRAM memory can be used, the initialization and leveling must be performed. The `mem.py` script serves this purpose.

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

Sometimes it may happen that memory initialization fails when running the `mem.py` script.
This is most likely due to using boards that allow to swap memory modules, such as ZCU104.

Memory initialization procedure is performed by the CPU instantiated inside the FPGA fabric.
The CPU runs the LiteX BIOS.
In case of memory training failure it may be helpful to access the LiteX BIOS console.

If the script cannot find a serial terminal emulator program on the host system, it will fall back
to `litex_term` which is shipped with LiteX. It is however advised to install `picocom`/`minicom`
as `litex_term` has worse performance.

In the BIOS console use the `help` command to get information about other available commands.
To re-run memory initialization and training type `reboot`.

```{note}
To close picocom/minicom enter CTRL+A+X key combination.
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

After entering the BIOS, you may want to perform a memory test using utilities built into the BIOS itself.
There are a couple ways to do such:

- `mem_test` - performs a series of writes and reads to check if values read back are the same as those previously written.
  It is limited by a 32-bit address bus, so only 4 GiB of address space can be tested.
  You can get origin of the RAM space using `mem_list` command.
- `sdram_test` - basically `mem_test`, but predefined for first 1/32 of defined RAM region size.
- `sdram_hw_test` - similar to `mem_test`, but accesses the SDRAM directly using DMAs, so it is not limited to 4 GiB.
  It requires passing 2 arguments (`origin` and `size`) with a 3rd optional argument being `burst_length`.
  When using `sdram_hw_test` you don't have to offset the `origin` like in the case of `mem_test`.
  `size` is a number of bytes to test and `burst_length` is a number of full transfer writes to the SDRAM, before reading and checking written content.
  The default value for `burst_length` is 1, which means that after every write, a check is performed.
  Generally, bigger `burst_length` means faster operation.

### Test with BIST - `mem_bist.py`

A script written to test BIST block functionality. Two tests are available:

- `test-modules` - memory is initialized and then a series of errors is introduced (on purpose).
  Then BIST is used to check the content of the memory. If the number of errors detected is equal to the number
  of errors introduced, the test is passed.
- `test-memory` - simple test that writes a pattern in the memory, reads it, and checks if the content is correct.
  Both write and read operations are done via BIST.

### Run benchmarks - `benchmark.py`

Benchmarks memory access performance. There are two subcommands available:

- `etherbone` - measure performance of the EtherBone bridge
- `bist` - measure performance of DMA DRAM access using the BIST modules

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

This script utilizes the Litescope functionality to gather debug information about
signals in the LiteX system. In-depth Litescope documentation [is here](https://github.com/enjoy-digital/litex/wiki/Use-LiteScope-To-Debug-A-SoC).

As you can see in Litescope documentation, Litescope analyzer needs to be instantiated in your design. Example design with analyzer added was provided as `arty_litescope` TARGET.
As the name implies it can be run using Arty board. You can use `rowhammer_tester/targets/arty_litescope.py` as a reference for your own Litescope-enabled targets.

To build `arty_litescope` example and upload it to device, follow instructions below:

1. In root directory run:

   ```sh
   export TARGET=arty_litescope
   make build
   make upload
   ```

   `analyzer.csv` file will be created in the root directory.

2. We need to copy it to target's build dir before using `analyzer.py`.

   ```sh
   cp analyzer.csv build/arty_litescope/
   ```

3. Then start litex-server with:

   ```sh
   make srv
   ```

4. And execute analyzer script in a separate shell:

   ```sh
   export TARGET=arty_litescope
   python rowhammer_tester/scripts/analyzer.py
   ```

   Results will be stored in `dump.vcd` file and can be viewed with gtkwave:

   ```sh
   gtkwave dump.vcd
   ```


## Simulation

Select `TARGET`, generate intermediate files & run simulation:

```sh
export TARGET=arty # (or zcu104)
make sim
```

This command will generate intermediate files & simulate them with Verilator.
After simulation has finished, a signals dump can be investigated using [gtkwave](http://gtkwave.sourceforge.net/):

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
Typing `make ARGS="--sim"` will cause LiteX to generate only intermediate files and stop right after that.
```
