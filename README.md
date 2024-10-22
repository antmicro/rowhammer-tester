# Rowhammer Tester

Copyright (c) 2020-2024 [Antmicro](https://www.antmicro.com)

The aim of this project is to provide a platform for testing the [DRAM "Row Hammer" vulnerability](https://users.ece.cmu.edu/~yoonguk/papers/kim-isca14.pdf).

The repository includes:

* `.github/` - Directory with CI configuration
* `docs/` - Sphinx-based documentation for the project
* `firmware/` - contains [Buildroot](https://github.com/buildroot/buildroot) configurations for Linux on DDR5 Tester and ZCU104 as well as custom configurations and board-specific firmware
* `openocd_scripts/` - [OpenOCD](https://github.com/openocd-org/openocd) helper scripts
* `rowhammer_tester/` - Core part of the project, a Python module including:
  * gateware for Rowhammer Tester platform
  * userspace scripts used for running tests
* `tests/` - Rowhammer Tester's block tests (e.g. PayloadExecutor, BIST)
* `third_party/` - Third party Rowhammer Tester sources

