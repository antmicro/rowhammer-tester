# Performing attacks (hammering)

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

## Attack modes

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
  {numref}`default-all-rows-arguments` shows default values for arguments:

:::{table} Default values for arguments
:name: default-all-rows-arguments
:header-rows: 1

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

## Patterns

You can choose a pattern that memory will be initially filled with:

* `all_0` - all bits set to 0
* `all_1` - all bits set to 1
* `01_in_row` - alternating 0s and 1s in a row (`0xaaaaaaaa` in hex)
* `01_per_row` - all 0s in odd-numbered rows, all 1s in even rows
* `rand_per_row` - random values for all rows

## Example output

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

## Row selection examples

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

## Cell retention measurement examples

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

## DRAM modules

When building one of the targets available in [rowhammer_tester/targets](https://github.com/antmicro/rowhammer-tester/tree/master/rowhammer_tester/targets), you can specify a custom DRAM module using the `--module` argument.
To find the default modules for each target, check the output of `--help`.

```{note}
Specifying different DRAM module makes most sense on boards that allow to easily replace the DRAM module,
such as on ZCU104. On other boards it would be necessary to desolder the DRAM chip and solder a new one.
```

### Adding new modules

The [LiteDRAM](https://github.com/enjoy-digital/litedram) controller provides out-of-the-box support for various DRAM modules.
The supported modules are listed in [litedram/modules.py](https://github.com/antmicro/litedram/blob/rowhammer-tester/litedram/modules.py).
If a module is not listed there, you can add a new definition.

To make development more convenient, modules can be added in the rowhammer-tester repository directly in file [rowhammer_tester/targets/modules.py](https://github.com/antmicro/rowhammer-tester/blob/master/rowhammer_tester/targets/modules.py).
These definitions will be used before definitions in LiteDRAM.

```{note}
After ensuring that the module works correctly, a Pull Request to LiteDRAM should be created to add support for the module.
```

To add a new module definition, use the existing ones as a reference.
A new module class should derive from `SDRAMModule` (or the helper classes, e.g. `DDR4Module`).
Timing/geometry values for a module have to be obtained from the relevant DRAM module's datasheet.
The timings in classes deriving from `SDRAMModule` are specified in nanoseconds.
The timing value can also be specified as a 2-element tuple `(ck, ns)`, in which case `ck` is the number of clock cycles and `ns` is the number of nanoseconds (and can be `None`).
The highest of the resulting timing values will be used.

### SPD EEPROM

For boards that use DIMM/SO-DIMM modules (e.g. ZCU104), it is possible to read the contents of DRAM module [SPD EEPROM memory](https://en.wikipedia.org/wiki/Serial_presence_detect).
SPD contains several essential module parameters that the memory controller needs in order to use the DRAM module.
SPD EEPROM can be read over an I2C bus.

#### Reading SPD EEPROM

To read the SPD memory, use the `rowhammer_tester/scripts/spd_eeprom.py` script.
First, prepare the environment as described in the [Controlling the board](usage.md#controlling-the-board) section.
Then, use the following command to read the contents of SPD EEPROM and save it to a file, for example:

```sh
python rowhammer_tester/scripts/spd_eeprom.py read MTA4ATF51264HZ-3G2J1.bin
```

The contents of the file can then be used to get DRAM module parameters.
Use the following command to examine the parameters:

```sh
python rowhammer_tester/scripts/spd_eeprom.py show MTA4ATF51264HZ-3G2J1.bin 125e6
```

Note that system clock frequency must be passed as an argument to determine timing values in controller clock cycles.

#### Using SPD data

The memory controller is able to set the timings read from an SPD EEPROM during system boot.
The only requirement here is that the SoC is built with an I2C controller and the I2C pins are routed to the (R)DIMM module.
There is no additional action required and the timings will be set automatically.

## Utilities

Some scripts are simple and do not take command line arguments, others will provide help via `<script_name>.py --help` or `<script_name>.py -h`.

Few of the scripts accept a `--srv` option.
With this option enabled, a program will start its own instance of `litex_server` (the user doesn't need to run `make srv` to [control the board](board_control.md)).

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

1. Copy it to the target's build directory before using `analyzer.py`.

   ```sh
   cp analyzer.csv build/arty_litescope/
   ```

1. Start `litex-server` with:

   ```sh
   make srv
   ```

1. Execute the analyzer script in a separate shell:

   ```sh
   export TARGET=arty_litescope
   python rowhammer_tester/scripts/analyzer.py
   ```

   Results will be stored in the `dump.vcd` file and can be viewed using `gtkwave`:

   ```sh
   gtkwave dump.vcd
   ```