Development
===========

Adding new DRAM modules
-----------------------

When building one of the targets in `rowhammer_tester/targets <https://github.com/antmicro/litex-rowhammer-tester/tree/master/rowhammer_tester/targets>`_, a custom DRAM module can be specified using the ``--module`` argument. To find the default modules for each target, check the output of ``--help``.

`LiteDRAM <https://github.com/enjoy-digital/litedram>`_ controller provides out-of-the-box support for many DRAM modules.
Supported modules can be found in `litedram/modules.py <https://github.com/enjoy-digital/litedram/blob/master/litedram/modules.py>`_.
If a module is not listed there, you can add a new definition.

To make developement more convenient, modules can be added in litex-rowhammer-tester repository directly in file `rowhammer_tester/targets/modules.py <https://github.com/antmicro/litex-rowhammer-tester/blob/master/rowhammer_tester/targets/modules.py>`_. These definitions will be used before definitions in LiteDRAM.

.. note::

   After ensuring that the module works correctly, a Pull Request to LiteDRAM should be created to add support for the module.

To add a new module definition, use the existing ones as a reference. New module class should derive from ``SDRAMModule`` (or the helper classes, e.g. ``DDR4Module``\ ). Timing/geometry values for a module have to be obtained from the revelant DRAM module's datasheet. The timings in classes deriving from ``SDRAMModule`` are specified in nanoseconds. The timing value can also be specified as a 2-element tuple ``(ck, ns)``\ , in which case ``ck`` is the number of clock cycles and ``ns`` is the number of nanoseconds (and can be ``None``\ ). The highest of the resulting timing values will be used.
