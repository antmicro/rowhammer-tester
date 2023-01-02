# DRAM modules

When building one of the targets in [rowhammer_tester/targets](https://github.com/antmicro/rowhammer-tester/tree/master/rowhammer_tester/targets), a custom DRAM module can be specified using the `--module` argument. To find the default modules for each target, check the output of `--help`.

```{note}
Specifying different DRAM module makes most sense on boards that allow to easily replace the DRAM module,
such as on ZCU104. On other boards it would be necessary to desolder the DRAM chip and solder a new one.
```

(adding-new-modules)=

## Adding new modules

[LiteDRAM](https://github.com/enjoy-digital/litedram) controller provides out-of-the-box support for many DRAM modules.
Supported modules can be found in [litedram/modules.py](https://github.com/enjoy-digital/litedram/blob/master/litedram/modules.py).
If a module is not listed there, you can add a new definition.

To make development more convenient, modules can be added in the rowhammer-tester repository directly in file [rowhammer_tester/targets/modules.py](https://github.com/antmicro/rowhammer-tester/blob/master/rowhammer_tester/targets/modules.py). These definitions will be used before definitions in LiteDRAM.

```{note}
After ensuring that the module works correctly, a Pull Request to LiteDRAM should be created to add support for the module.
```

To add a new module definition, use the existing ones as a reference. New module class should derive from `SDRAMModule` (or the helper classes, e.g. `DDR4Module`). Timing/geometry values for a module have to be obtained from the relevant DRAM module's datasheet. The timings in classes deriving from `SDRAMModule` are specified in nanoseconds. The timing value can also be specified as a 2-element tuple `(ck, ns)`, in which case `ck` is the number of clock cycles and `ns` is the number of nanoseconds (and can be `None`). The highest of the resulting timing values will be used.

## SPD EEPROM

On boards that use DIMM/SO-DIMM modules (e.g. ZCU104) it is possible to read the contents of the DRAM modules's [SPD EEPROM memory](https://en.wikipedia.org/wiki/Serial_presence_detect).
SPD contains several essential module parameters that the memory controller needs in order to use the DRAM module.
SPD EEPROM can be read over I2C bus.

### Reading SPD EEPROM

To read the SPD memory use the script `rowhammer_tester/scripts/spd_eeprom.py`.
First prepare the environment as described in {ref}`controlling-the-board`.
Then use the following command to read the contents of SPD EEPROM and save it to a file, for example:

```sh
python rowhammer_tester/scripts/spd_eeprom.py read MTA4ATF51264HZ-3G2J1.bin
```

The contents of the file can then be used to get DRAM module parameters.
Use the following command to examine the parameters:

```sh
python rowhammer_tester/scripts/spd_eeprom.py show MTA4ATF51264HZ-3G2J1.bin 125e6
```

Note that system clock frequency must be passed as an argument to determine timing values in controller clock cycles.

### Using SPD data

The memory controller is able to set the timings read from an SPD EEPROM during system boot.
The only requirement here is that the SoC is built with I2C controller, and I2C pins are routed to the (R)DIMM module.
There is no additional action required from system user.
The timings will be set automatically.

