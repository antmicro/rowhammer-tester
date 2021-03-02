General usage guide
===================

The aim of this project is to provide a platform for testing `DRAM vulnerability to Rowhammer attacks <https://users.ece.cmu.edu/~yoonguk/papers/kim-isca14.pdf>`_.

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

   apt install git build-essential autoconf cmake flex bison libftdi-dev libjson-c-dev libevent-dev libtinfo-dev uml-utilities python3 python3-venv python3-wheel protobuf-compiler gcc-riscv64-linux-gnu openocd

.. note::

   On some Debian-based systems there's a problem with a broken dependency:

   .. code-block::

      libc6-dev : Breaks: libgcc-9-dev (< 9.3.0-5~) but 9.2.1-19 is to be installed

   ``gcc-9-base`` package installation solves the problem.

Then run:

.. code-block:: sh

   git clone --recursive https://github.com/antmicro/litex-rowhammer-tester.git
   cd litex-rowhammer-tester
   make deps

The last command will download and build all the dependencies and will set up a `Python virtual environment <https://docs.python.org/3/library/venv.html>`_ under the ``./venv`` directory with all the required packages installed.

The virtual environment allows you to use Python without installing the packages system-wide.
To enter the environment, you have to run ``source venv/bin/activate`` in each new shell.
You can also use the provided ``make env`` target, which will start a new Bash shell with the virtualenv already sourced.
You can install packages inside the virtual environment by entering the environment and then using ``pip``.

..

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

Gateware documentation
----------------------

The gateware documentation was auto-generated from source files.
To build the gateware documentation manually, use:

.. code-block:: sh

   make doc

The documentation will be located in ``build/documentation/html/index.html``.

Tests
-----

To run project tests use:

.. code-block:: sh

   make test

Usage
-----

This tool can be run on real hardware (FPGAs) or in a simulation mode.
As the Rowhammer vulnerability exploits physical properties of cells in DRAM (draining charges), no bit flips can be observed in simulation mode.
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
   (Optionally) allow network traffic on this interface:

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

Some scripts are simple and do not take command line arguments, others will provide help via ``SCRIPT.PY --help``.

Examples
~~~~~~~~

Simple scripts:


* ``leds.py`` - Turns the LEDs on Arty-A7 board on, off, and on again
* ``dump_regs.py`` - Dumps the values of all CSRs

Example output of ``dump_regs.py``:

.. code-block::

   Using generated target files in: ../../build/arty
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
   If you get other value than 0x12345678, this may indicate a problem.

Before the DRAM memory can be used, the initialization and leveling must be performed. To do this run:

.. code-block:: sh

   python mem.py

.. note::

   When using a simulation target, running the read leveling will fail. To avoid it, use ``python mem.py --no-init``


To perform a Rowhammer attack sequence, use the ``rowhammer.py`` script (see ``--help``\ ), e.g:

.. code-block:: sh

   python rowhammer.py --nrows 512 --read_count 10e6 --pattern 01_in_row --row-pairs const --const-rows-pair 54 133 --no-refresh

To generate a plot (requires ``pip install -r requirements-dev.txt``\ ), you can use:

.. code-block:: sh

   python rowhammer.py --nrows 512 --read_count 10e6 --pattern 01_in_row --row-pairs const --const-rows-pair 54 133 --no-refresh --plot

To make use of BIST modules to fill/check the memory, you can use:

.. code-block:: sh

   python hw_rowhammer.py --nrows 512 --read_count 10e6 --pattern 01_in_row --row-pairs const --const-rows-pair 54 133 --no-refresh

Accessing LiteX BIOS console
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Sometimes it may happen that memory initialization fails when running the ``mem.py`` script.
This is most likely when using boards that allow to swap memory modules, such as ZCU104.

Memory initialization procedure is peformed by the CPU instantiated inside FPGA fabric.
The CPU runs the LiteX BIOS.
In case of memory training failure it may be helpful to access the LiteX BIOS console.
To do so use the following script (with ``litex_server`` running):

.. code-block:: sh

   python bios_console.py

If the script cannot find a serial terminal emulator program on the host system it will fall back
to ``litex_term`` which is shipped with LiteX. It is however advised to install ``picocom``/``minicom``
as ``litex_term`` has worse performance.

In the BIOS console use the ``help`` command to get information about other available commands.
To re-run memory initialization and training type ``reboot``.
