Playbook
========

`Playbook directory <https://github.com/antmicro/litex-rowhammer-tester/tree/master/rowhammer_tester/scripts/playbook>`_ contains a group of Python classes and scripts designed to ease the process of writing various rowhammer related tests. These tests can be executed against the hardware platform.

Payload
-------

Tests are generated as ``payload`` data. After generation, this data is transferred to a memory area in device reserved for this purpose - called ``payload memory``. Payload consists of instruction list that can be interpreted by ``payload executor`` module in hardware. Payload executor translates these instructions into DRAM commands. Payload executor connects directly to the DRAM PHY, bypassing DRAM controller as explained in :ref:`architecture`.

Changing payload memory size
****************************

Payload memory size can be changed. Of course it can't exceed memory available on a hardware platform used.
Currently payload memory size is defined in `common.py <https://github.com/antmicro/litex-rowhammer-tester/blob/master/rowhammer_tester/targets/common.py>`_, as an argument to LiteX:

.. code-block:: python

  add_argument("--payload-size", default="1024", help="Payload memory size in bytes")

Examples shown in this chapter don't require any changes. When writing your own :ref:`configurations` you may need to change the default value.

Row mapping
-----------

When dealing with DRAM modules the physical layout of memory rows in hardware can be different then logical numbers assigned to them. The nature of rowhammer attack is that only physically adjacent rows are affected by `aggresor row`. To deal with the problem of disparity between physical location and logical enumeration we implement different mapping strategies:

* ``TrivialRowMapping`` - logical address is the same as physical one
* ``TypeARowMapping`` - more complex mapping method, reverse-engineered as a part of `this research <https://download.vusec.net/papers/hammertime_raid18.pdf>`_
* ``TypeBRowMapping`` - logical address is the physical one multiplied by 2, taken from `this paper <https://arxiv.org/pdf/2005.13121.pdf>`_

Row Generator class
-------------------

Row Generator class is responsible for creating a list of row numbers used in a rowhammer attack.
Currently only one instance of this class is available.

EvenRowGenerator
****************

Generates a list of even numbered rows. Uses the row mapping specified by :ref:`payload generator class` used. Two configuration parameters are needed for EvenRowGenerator:

* ``nr_rows`` - number of rows to be generated
* ``max_row`` - maximal number to be used. The chosen numbers will be *modulo max_row*

Payload Generator class
-----------------------

Payload generator's purpose is to prepare a payload, and process the test outcome. It is a class that can be re-used in different tests :ref:`configurations`.
Payload generators are located in `payload_generators directory <https://github.com/antmicro/litex-rowhammer-tester/tree/master/rowhammer_tester/scripts/playbook/payload_generators>`_

Available Payload Generators
****************************

Row mapping and row generator settings are combined into a payload generator class.
Currently only two payload generators are available.

RowListPayloadGenerator
^^^^^^^^^^^^^^^^^^^^^^^

A simple payload generator that can use a RowGenerator class to generate rows, and then generate a payload that hammers that list of rows
(``hammering`` is a term used to describe multiple read operations on the same row).
It can also issue refresh commands to DRAM module.
Here are the configs that can be used in *payload_generator_config* for this payload generator:

* ``row_mapping`` - this is the :ref:`row mapping` used
* ``row_generator`` - this is the :ref:`row generator class` used to generate the rows
* ``row_generator_config`` - parameters for the row generator
* ``verbose`` - should verbose output be generated (true or false)
* ``fill_local`` - when enabled, permits shrinking the filled memory area to just the aggressors and the victim
* ``read_count`` - number of hammers (reads) per row
* ``refresh`` - should refresh be enabled (true or false)

Example :ref:`configurations` for this test were provided as ``configs/example_row_list_*.cfg`` files.
Some of them require a significant amount o memory declared as `payload memory`.
To execute a minimalistic example from within litex-rowhammer-tester repo enter:

.. code-block:: console

  source venv/bin/activate
  export TARGET=arty # change accordingly
  cd rowhammer_tester/scripts/playbook/
  python playbook.py configs/example_row_list_minimal.cfg

Expected output:

.. code-block:: console

  Progress: [========================================] 65536 / 65536
  Row sequence:
  [0, 2, 4, 6, 14, 12, 10, 8, 16, 18]
  Generating payload:
    tRAS = 5
    tRP = 3
    tREFI = 782
    tRFC = 32
    Repeatable unit: 930
    Repetitions: 93
    Payload size =  0.10KB /  1.00KB
    Payload per-row toggle count = 0.010K  x10 rows
    Payload refreshes (if enabled) = 10 (disabled)
    Expected execution time = 1903 cycles = 0.019 ms
  
  Transferring the payload ...
  
  Executing ...
  Time taken: 0.738 ms
  
  Progress: [==                                      ]  3338 / 65536 (Errors: 1287)
  ...

HammerTolerancePayloadGenerator
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Payload generator for measuring and characterizing rowhammer tolerance.
It can provide information about how many rows and bits are susceptible to rowhammer.
It can also provide information about where the susceptible bits are located.

A series of double-sided hammers against the available group of victim rows is performed.
The double-sided hammers increase in intensity based on ``read_count_step`` parameter.
Here are the parameters that can be specified in *payload_generator_config* for this payload generator:

* ``row_mapping`` - this is the :ref:`row mapping` used
* ``row_generator`` - this is the :ref:`row generator class` used to generate the rows
* ``row_generator_config`` - parameters for the row generator
* ``verbose`` - should verbose output be generated (true or false)
* ``fill_local`` - when enabled, permits shrinking the filled memory area to just the aggressors and the victim
* ``nr_rows`` - number of rows to conduct the experiment over. This is the number of aggressor rows.
  Victim rows will be 2 times fewer than this number. For example, to perform hammering for 32 victim rows, use 34 as the parameter value
* ``read_count_step`` - this is how much to increment the hammer count between multiple tests for the same row.
  This is the number of hammers on single side (total number of hammers on both sides is 2x this value)
* ``iters_per_row`` - number of times the hammer count is incremented for each row

The results are a series of histograms with appropriate labeling.

Example :ref:`configurations` for this test were provided as ``configs/example_hammer_*.cfg`` files.
Some of them require a significant amount o memory declared as `payload memory`.
To execute a minimalistic example from within litex-rowhammer-tester repo enter:

.. code-block:: console

  source venv/bin/activate
  export TARGET=arty # change accordingly
  cd rowhammer_tester/scripts/playbook/
  python playbook.py configs/example_hammer_minimal.cfg

Expected output:

.. code-block:: console

  Progress: [========================================] 3072 / 3072 
  Generating payload:
    tRAS = 5
    tRP = 3
    tREFI = 782
    tRFC = 32
    Repeatable unit: 186
    Repetitions: 93
    Payload size =  0.04KB /  1.00KB
    Payload per-row toggle count = 0.010K  x2 rows
    Payload refreshes (if enabled) = 10 (disabled)
    Expected execution time = 1263 cycles = 0.013 ms
  
  Transferring the payload ...
  
  Executing ...
  Time taken: 0.647 ms
  
  Progress: [============                            ]  323 / 1024 (Errors: 320) 
  ...

Configurations
--------------

Test configuration files are represented as JSON files. An example:

.. code-block:: python

    {
        "inversion_divisor" : 2,
        "inversion_mask" : "0b10",
        "payload_generator" : "RowListPayloadGenerator",
        "payload_generator_config" : {
            "row_mapping" : "TypeARowMapping",
            "row_generator" : "EvenRowGenerator",
            "read_count" : 27,
            "max_iteration" : 10,
            "verbose" : true,
            "refresh" : false,
            "fill_local" : true,
            "row_generator_config" : {
                "nr_rows" : 10,
                "max_row" : 64
            }
        }
    }

Different parameters are supported:

* ``payload_generator`` - name of the :ref:`payload generator class` to use
* ``row_pattern`` - pattern that will be stored in rows
* inversion_divisor and inversion_mask - controls which rows get the inverted pattern
  described in :ref:`inversion`
* ``payload_generator_config`` - these parameters are specific for :ref:`payload generator class` used

Inversion
*********

If needed, the data pattern used for some of the tested rows can be ``bitwise-inverted``.

Two parameters are used to specify which rows are to be inverted:

* ``inversion_divisor``
* ``inversion_mask``

An example. ``inversion_divisor = 8``, ``inversion_mask = 0b10010010`` (bits 1, 4 and 7 are "on").
We iterate through all row numbers 0,1,2,3,4,...,8,9,10,...
First a modulo ``inversion_divisor`` operation is performed on a row number. In our case it's ``mod 8``.
Next we check if bit in ``inversion_mask`` on position corresponding to our row number (after modulo) is "on" or "off".
If it's "on", this whole row will be inverted. The results for our example are shown in a table below.

.. list-table:: Inversion example
    :widths: 10 10 80
    :header-rows: 1

    * - Row number
      - Row number modulo divisor (8)
      - Value
    * - 0
      - 0
      - pattern
    * - 1
      - 1
      - inverted pattern
    * - 2
      - 2
      - pattern
    * - 3
      - 3
      - pattern
    * - 4
      - 4
      - inverted pattern
    * - 5
      - 5
      - pattern
    * - 6
      - 6
      - pattern
    * - 7
      - 7
      - inverted pattern
    * - 8
      - 0
      - pattern
    * - 9
      - 1
      - inverted pattern
    * - 10
      - 2
      - pattern
    * - 11
      - 3
      - pattern
    * - 12
      - 4
      - inverted pattern


