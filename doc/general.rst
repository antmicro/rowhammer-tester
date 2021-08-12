General usage guide
===================

The aim of this project is to provide a platform for testing `DRAM vulnerability to rowhammer attacks <https://users.ece.cmu.edu/~yoonguk/papers/kim-isca14.pdf>`_.

.. _architecture:

Architecture
------------

The setup consists of FPGA gateware and application side software.
The following diagram illustrates the general system architecture.


.. image:: ./architecture.png
   :target: ./architecture.png
   :alt: Archtecture diagram


The DRAM is connected to `LiteDRAM <https://github.com/enjoy-digital/litedram>`_, which provides swappable PHYs and a DRAM controller implementation.

In the default bulk transfer mode the LiteDRAM controller is connected to PHY and ensures correct DRAM traffic.
Bulk transfers can be controlled using dedicated Control & Status Registers (CSRs) and use LiteDRAM DMA to ensure fast operation.

The Payload Executor allows executing a user-provided sequence of commands.
It temporarily disconnects the DRAM controller from PHY, executes the instructions stored in the SRAM memory,
translating them into DFI commands and finally reconnects the DRAM controller.

The application side consists of a set of Python scripts communicating with the FPGA using the LiteX EtherBone bridge.

Installing dependencies
-----------------------

Make sure you have Python 3 installed with the ``venv`` module, and the dependencies required to build
`verilator <https://github.com/verilator/verilator>`_ and `xc3sprog <https://github.com/matrix-io/xc3sprog>`_.
To install the dependencies on Ubuntu 18.04 LTS, run:

.. code-block:: sh

   apt install git build-essential autoconf cmake flex bison libftdi-dev libjson-c-dev libevent-dev libtinfo-dev uml-utilities python3 python3-venv python3-wheel protobuf-compiler

.. note::

   On some Debian-based systems there's a problem with a broken dependency:

   .. code-block::

      libc6-dev : Breaks: libgcc-9-dev (< 9.3.0-5~) but 9.2.1-19 is to be installed

   ``gcc-9-base`` package installation solves the problem.

OpenOCD
^^^^^^^

To flash QSPI flash module on LPDDR4 Test Board you'll need a patched version of ``openocd`` program. To install it, run:

.. code-block:: sh

   git clone https://github.com/antmicro/openocd.git -b add-jtagspi-command
   cd openocd
   ./bootstrap
   ./configure --enable-ftdi
   make -j `nproc`
   sudo make install

Row-hammer tester
^^^^^^^^^^^^^^^^^

Now clone the ``litex-rowhammer-tester`` repository and install the rest of the required dependecies:

.. code-block:: sh

   git clone --recursive https://github.com/antmicro/litex-rowhammer-tester.git
   cd litex-rowhammer-tester
   make deps

The last command will download and build all the dependencies (inlcuding a RISC-V GCC toolchain)
and will set up a `Python virtual environment <https://docs.python.org/3/library/venv.html>`_ under
the ``./venv`` directory with all the required packages installed.

The virtual environment allows you to use Python without installing the packages system-wide.
To enter the environment, you have to run ``source venv/bin/activate`` in each new shell.
You can also use the provided ``make env`` target, which will start a new Bash shell with the virtualenv already sourced.
You can install packages inside the virtual environment by entering the environment and then using ``pip``.

.. note::

   Some options to the scripts may require additional Python dependencies. To install them run ``pip install -r requirements-dev.txt`` inside the virtual environment.


To build the bitstream you will also need to have Vivado installed and the ``vivado`` command available in your ``PATH``.
To configure Vivado in the current shell, you need to ``source /PATH/TO/Vivado/VERSION/settings64.sh``.
This can be put in your ``.bashrc`` or other shell init script.

To make the process automatic without hard-coding these things in shell init script,
tools like `direnv <https://github.com/direnv/direnv>`_ can be used. A sample ``.envrc`` file would then look like this:

.. code-block:: sh

   source venv/bin/activate
   source /PATH/TO/Vivado/VERSION/settings64.sh

All other commands assume that you run Python from the virtual environment with ``vivado`` in your ``PATH``.

Local documentation build
-------------------------

The gateware part of the documentation is auto-generated from source files.
Other files are static and are located in ``doc/`` directory.
To build the documentation, enter:

.. code-block:: sh

   source venv/bin/activate
   pip install -r requirements.txt
   python -m sphinx doc build/documentation

The documentation will be located in ``build/documentation/index.html``.

Tests
-----

To run project tests use:

.. code-block:: sh

   make test

Usage
-----

This tool can be run on real hardware (FPGAs) or in a simulation mode.
As the rowhammer attack exploits physical properties of cells in DRAM (draining charges), no bit flips can be observed in simulation mode.
However, the simulation mode is useful to test command sequences during the development.

The Makefile can be configured using environmental variables to modify the network configuration used and to select the target.
Currently, the Arty-A7 (xc7a35t) FPGA board (\ ``TARGET=arty``\ ) and the ZCU104 board (\ ``TARGET=zcu104``\ ) are both supported.
Keep in mind that Arty is targeting DDR3, while ZCU is targeting DDR4 (SO-DIMM modules).

For board-specific instructons refer to :ref:`arty-chapter` and :ref:`zcu104-chapter` chapters.
The rest of this chapter describes operations that are common for all supported boards.

Simulation
^^^^^^^^^^

Select ``TARGET``\ , generate intermediate files & run simulation:

.. code-block:: sh

   export TARGET=arty # (or zcu104)
   make sim

This command will generate intermediate files & simulate them with Verilator.
After simulation has finished, a signals dump can be investigated using `gtkwave <http://gtkwave.sourceforge.net/>`_\ :

.. code-block:: sh

   gtkwave build/$TARGET/gateware/sim.fst

WARNING: The repository contains a wrapper script around ``sudo`` which disallows LiteX to interfere with
the host network configuration. This forces the user to manually configure a TUN interface for valid
communication with the simulated device:


#.
   Create the TUN interface:

   .. code-block:: sh

      tunctl -u $USER -t litex-sim

#.
   Configure the IP address of the interface:

   .. code-block:: sh

      ifconfig litex-sim 192.168.100.1/24 up

#.
   Optionally allow network traffic on this interface:

   .. code-block:: sh

      iptables -A INPUT -i litex-sim -j ACCEPT
      iptables -A OUTPUT -o litex-sim -j ACCEPT

TIP: Typing ``make ARGS="--sim"`` will cause LiteX to generate only intermediate files and stop right after that.

.. _controlling-the-board:

Controlling the board
^^^^^^^^^^^^^^^^^^^^^

Board control is the same for both simulation and hardware runs.
In order to communicate with the board via EtherBone, the ``litex_server`` needs to be started with the following command:

.. code-block:: sh

   export IP_ADDRESS=192.168.100.50  # optional, should match the one used during build
   make srv

The build files (CSRs address list) must be up to date. It can be re-generated with ``make`` without arguments.

Then, in another terminal, you can use the Python scripts provided. *Remember to enter the Python virtual environment before running the scripts!* Also, the ``TARGET`` variable should be set to load configuration for the given target.
For example, to use the ``leds.py`` script, run the following:

.. code-block:: sh

   source ./venv/bin/activate
   export TARGET=arty  # (or zcu104) required to load target configuration
   cd rowhammer_tester/scripts/
   python leds.py  # stop with Ctrl-C


Provided scripts
^^^^^^^^^^^^^^^^

Some of the scripts are simple and do not take command line arguments, others will provide help via ``SCRIPT.PY --help`` or ``SCRIPT.PY -h``.
Some of the scripts accept ``--srv`` option.
With this option enabled, a program will start it's own instance of ``litex_server`` (the user doesn't need to run ``make srv`` from :ref:`controlling the board`)

leds.py
~~~~~~~

Displays a simple "bouncing" animation using the LEDs on Arty-A7 board, with the light moving from side to side.

``-t TIME_MS`` or ``--time-ms TIME_MS`` option can be used to adjust LED switching interval.

version.py
~~~~~~~~~~

Prints the data stored in the LiteX identification memory:

* hardware platform identifier
* source code git hash
* build date

Example output:

.. code-block:: sh

   (venv)
   LiteX Row Hammer Tester SoC on xc7a35ticsg324-1L, git: 7c22b0c5a22f2aa1b1ad0f134cda9c4d280c1ad5 2021-03-02 06:39:07

dump_regs.py
~~~~~~~~~~~~

Dumps values of all CSRs.
Example output of ``dump_regs.py``:

.. code-block:: sh

   0x82000000: 0x00000000 ctrl_reset
   0x82000004: 0x12345678 ctrl_scratch
   0x82000008: 0x00000000 ctrl_bus_errors
   0x82002000: 0x00000000 uart_rxtx
   0x82002004: 0x00000001 uart_txfull
   0x82002008: 0x00000001 uart_rxempty
   0x8200200c: 0x00000003 uart_ev_status
   0x82002010: 0x00000000 uart_ev_pending
   ...

.. note::

   Note that ctrl_scratch value is 0x12345678. This is the reset value of this register.
   If you are getting a different, this may indicate a problem.

mem.py
~~~~~~

Before the DRAM memory can be used, the initialization and leveling must be performed. The ``mem.py`` script serves this purpose.

Expected output:

.. code-block:: sh

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

rowhammer.py & hw_rowhammer.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Runs a rowhammer attack against a DRAM module.
For the complete list of modifiers, see ``--help``.

Different attack modes can be specified:

* ``sequential`` - list of attacked rows is a sequence from ``start-row`` to ``start-row + nrows``. For example, all rows from 10 to 90.
* ``const`` - two rows specified with the ``const-rows-pair`` parameter will be attacked
* ``random`` - random two rows from between ``start-row`` and ``start-row + nrows`` will be attacked

User can choose a pattern that memory will be initially filled with:

* ``all_0`` - all bits set to 0
* ``all_1`` - all bits set to 1
* ``01_in_row`` - alternating 0's and 1's in a row (``0xaaaaaaaa`` in hex)
* ``01_per_row`` - all 0's in odd-numbered rows, all 1's in even rows
* ``rand_per_row`` - random values for all rows

There are also two versions of a rowhammer script:

* ``rowhammer.py`` - this one uses regular memory access via EtherBone to fill/check the memory (slower)
* ``hw_rowhammer.py`` - BIST blocks will be used to fill/check the memory (much faster, but with some limitations regarding fill pattern)

BIST blocks are faster and are the intended way of running Row Hammer Tester.

.. warning:: Remember to initialize memory beforehand as explained in :ref:`mem.py`.

Example:

.. code-block:: sh

   (venv) $ python hw_rowhammer.py --nrows 512 --read_count 10e6 --pattern 01_in_row --row-pairs const --const-rows-pair 54 133 --no-refresh
   Preparing ...
   WARNING: only single word patterns supported, using: 0xaaaaaaaa
   Filling memory with data ...
   Progress: [========================================] 16777216 / 16777216
   Verifying written memory ...
   Progress: [========================================] 16777216 / 16777216 (Errors: 0)
   OK
   Disabling refresh ...
   Running row hammer attacks ...
   read_count: 10000000
     Iter 0 / 1 Rows = (54, 133), Count = 10.00M / 10.00M
   Reenabling refresh ...
   Verifying attacked memory ...
   Progress: [========================================] 16777216 / 16777216 (Errors: 30)
   Bit-flips for row    53: 5
   Bit-flips for row    55: 11
   Bit-flips for row   132: 12
   Bit-flips for row   134: 3

bios_console.py
~~~~~~~~~~~~~~~

Sometimes it may happen that memory initialization fails when running the ``mem.py`` script.
This is most likely due to using boards that allow to swap memory modules, such as ZCU104.

Memory initialization procedure is peformed by the CPU instantiated inside the FPGA fabric.
The CPU runs the LiteX BIOS.
In case of memory training failure it may be helpful to access the LiteX BIOS console.

If the script cannot find a serial terminal emulator program on the host system, it will fall back
to ``litex_term`` which is shipped with LiteX. It is however advised to install ``picocom``/``minicom``
as ``litex_term`` has worse performance.

In the BIOS console use the ``help`` command to get information about other available commands.
To re-run memory initialization and training type ``reboot``.

.. note:: To close picocom/minicom enter CTRL+A+X key combination.

Example:

.. code-block:: sh

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

mem_bist.py
~~~~~~~~~~~

A script written to test BIST block functionality. Two tests are available:

* ``test-modules`` - memory is initialized and then a series of errors is introduced (on purpose).
  Then BIST is used to check the content of the memory. If the number of errors detected is equal to the number
  of errors introduced, the test is passed.
* ``test-memory`` - simple test that writes a pattern in the memory, reads it, and checks if the content is correct.
  Both write and read operations are done via BIST.

benchmark.py
~~~~~~~~~~~~~~~~~

Benchmarks memory access performance. There are two subcommands available:

* ``etherbone`` - measure performance of the EtherBone bridge
* ``bist`` - measure performance of DMA DRAM access using the BIST modules

Example output:

.. code-block:: sh

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


analyzer.py
~~~~~~~~~~~

This script utilizes the Litescope functionality to gather debug information about
signals in the LiteX system. In-depth Litescope documentation `is here <https://github.com/enjoy-digital/litex/wiki/Use-LiteScope-To-Debug-A-SoC>`_.

As you can see in Litescope documentation, Litescope analyzer needs to be instantiated in your design. Example design with analyzer added was provided as ``arty_litescope`` TARGET.
As the name implies it can be run using Arty board. You can use ``rowhammer_tester/targets/arty_litescope.py`` as a reference for your own Litescope-enabled targets.

To build ``arty_litescope`` example and upload it to device, in root directory run:

.. code-block:: sh

   export TARGET=arty_litescope
   make build
   make upload

``analyzer.csv`` file will be created in root directory.
We need to copy it to target's build dir before using ``analyzer.py``.

.. code-block:: sh

   cp analyzer.csv build/arty_litescope/

Then start litex-server with:

.. code-block:: sh

   make srv

And execute analyzer script in a separate shell:

.. code-block:: sh

   export TARGET=arty_litescope
   python rowhammer_tester/scripts/analyzer.py

Results will be stored in ``dump.vcd`` file and can be viewed with gtkwave:

.. code-block:: sh

   gtkwave dump.vcd

utils.py
~~~~~~~~

Contains useful functions that are used by other scripts. Not to be executed on its own.
Some of the implemented features:

* wrapper functions for memory operations
* DRAM address convertion
* payload execution
* helper functions for accessing configuration files
* prettified console output

