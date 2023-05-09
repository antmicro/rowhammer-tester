# Rowhammer Tester

Copyright (c) 2020-2023 [Antmicro](https://www.antmicro.com)

The aim of this project is to provide a platform for testing the [DRAM "Row Hammer" vulnerability](https://users.ece.cmu.edu/~yoonguk/papers/kim-isca14.pdf).

The repository includes:

* `rowhammer_tester/` - Core part of the project, a Python module including:

  * gateware for Rowhammer Tester platform
  * userspace scripts used for running tests
* `docs/` - Sphinx-based documentation for the project
* `.github/` - Directory with CI configuration

