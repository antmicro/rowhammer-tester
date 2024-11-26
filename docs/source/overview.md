# Project overview

The aim of this project is to provide a platform for testing [DRAM vulnerability to rowhammer attacks](https://users.ece.cmu.edu/~yoonguk/papers/kim-isca14.pdf).

This suite can be run on real hardware (FPGAs) or in a simulation mode.

Read more about particular aspects of the framework in dedicated blog articles:

* [Rowhammer Tester platform overview](https://antmicro.com/blog/2021/08/open-source-ddr-test-framework-for-rowhammer/)
* [LPDDR4 Test Board](https://antmicro.com/blog/2021/04/lpddr4-test-platform/)
* [Data Center RDIMM DDR4 Tester](https://antmicro.com/blog/2021/12/open-source-data-center-rowhammer-tester/)
* [Data Center RDIMM DDR5 Tester](https://antmicro.com/blog/2023/07/open-source-data-center-rdimm-ddr5-tester-for-memory-vulnerability-research/)
* [SO-DIMM DDR5 Tester](https://antmicro.com/blog/2024/02/versatile-so-dimm-lpddr5-rowhammer-testing-platform/)

## Tester suite architecture

This section provides an overview of the Rowhammer Tester suite architecture.

System architecture is presented in {numref}`tester-architecture` below:

:::{figure-md} tester-architecture
![Rowhammer Tester architecture](images/rowhammer_tester_architecture.png)

Rowhammer Tester suite architecture
:::

The DRAM is connected to [LiteDRAM](https://github.com/enjoy-digital/litedram), which provides swappable PHYs and a DRAM controller implementation.

In the default bulk transfer mode, the LiteDRAM controller is connected to PHY and ensures correct DRAM traffic.
Bulk transfers can be controlled using dedicated Control & Status Registers (CSRs) and use LiteDRAM DMA to ensure fast operation.

The Payload Executor allows executing a user-provided sequence of commands.
It temporarily disconnects the DRAM controller from PHY; executes the instructions stored in the SRAM memory, translating them into DFI commands and finally reconnects the DRAM controller.

The application side consists of a set of Python scripts communicating with the FPGA using the LiteX EtherBone bridge.

