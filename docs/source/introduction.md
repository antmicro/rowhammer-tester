# Introduction

The aim of this project is to provide a platform for testing [DRAM vulnerability to rowhammer attacks](https://users.ece.cmu.edu/~yoonguk/papers/kim-isca14.pdf).

Read more in dedicated blog articles:
* [General Rowhammer tester platform overview](https://antmicro.com/blog/2021/08/open-source-ddr-test-framework-for-rowhammer/)
* [LPDDR4 Test Board](https://antmicro.com/blog/2021/04/lpddr4-test-platform/)
* [Data Center RDIMM DDR4 Tester](https://antmicro.com/blog/2021/12/open-source-data-center-rowhammer-tester/)
* [Data Center RDIMM DDR5 Tester](https://antmicro.com/blog/2023/07/open-source-data-center-rdimm-ddr5-tester-for-memory-vulnerability-research/)
* [SO-DIMM DDR5 Tester](https://antmicro.com/blog/2024/02/versatile-so-dimm-lpddr5-rowhammer-testing-platform/)

# Tester suite architecture

This chapter provides an overview of the Rowhammer tester suite architecture.
The setup consists of FPGA gateware and application side software.

:::{figure-md} architecture
![Rowhammer tester architecture](images/architecture.png)

Rowhammer tester architecture
:::

TODO: replace with interactive system diagram when ready.

The DRAM is connected to [LiteDRAM](https://github.com/enjoy-digital/litedram), which provides swappable PHYs and a DRAM controller implementation.

In the default bulk transfer mode the LiteDRAM controller is connected to PHY and ensures correct DRAM traffic.
Bulk transfers can be controlled using dedicated Control & Status Registers (CSRs) and use LiteDRAM DMA to ensure fast operation.

The Payload Executor allows executing a user-provided sequence of commands.
It temporarily disconnects the DRAM controller from PHY, executes the instructions stored in the SRAM memory,
translating them into DFI commands and finally reconnects the DRAM controller.

The application side consists of a set of Python scripts communicating with the FPGA using the LiteX EtherBone bridge.

# Documentation structure

WIP: revise structure

* [General](general.md)
* [User guide](usage.md)
* [Visualization](visualization.md)
* [Playbook](playbook.md)
* [DRAM modules](dram_modules.md)
* Hardware
    * [Arty-A7 board](arty.md)
    * [ZCU104 board](zcu104.md)
    * [LPDDR4 Test Board](lpddr4_test_board.md)
    * [LPDDR4 Test Board with DDR5 Testbed](lpddr_test_board_with_ddr_testbed.md)
    * [Data Center RDIMM DDR4 Tester](data_center_rdimm_ddr4_tester.md)
    * [Data Center RDIMM DDR5 Tester](data_center_rdimm_ddr5_tester.md)
    * [SO-DIMM DDR5 Tester](so_dimm_ddr5_tester.md)
* Gateware documentation

