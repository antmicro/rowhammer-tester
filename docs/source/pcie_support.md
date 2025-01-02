# PCIe support

The selected hardware platforms used for DRAM testing include an optional PCIe interface break-routed from the on-board FPGA. 
These platforms are [SO-DIMM DDR5 Testers](so_dimm_ddr5_tester.md) supporting PCIe x4 and [RDIMM DDR5 Tester](rdimm_ddr5_tester.md) in Revision 2.0 supporting PCIe x8. 
The platforms were designed in the form factor of PCIe cards and are mechanically compliant with host platforms with a PCIe root complex.

:::{figure-md} rdimm-ddr5-tester-pcie-integration
![RDIMM DDR5 Tester PCIe integration](images/rdimm-ddr5-tester-pcie-integration.png)

RDIMM DDR5 Tester connected to Intel NUC-series host PC over PCIe x8.
:::

Enabling a PCIe interface in the digital design allows for fast data exchange between the host PC, the FPGA and the memory.

:::{note}

Enabling PCIe connectivity currently requires extending the existing the Rowhammer tester codebase with setup-specific features.
In particular, PCIe requires mapping the API/commands into a Rowhammer-specific API.

:::

## DRAM Bender integration

PCIe interface allows to integrate the RDIMM DDR5 Tester with third party DRAM testers. 
One of them is [DRAM Bender](https://github.com/CMU-SAFARI/DRAM-Bender) project.
In order to make the RDIMM DDR5 Tester compliant with DRAM Bender API it is required to transpile [Bender API](https://docs.google.com/spreadsheets/d/18mPiKa1HBoO0OmzAbWRvo5OnIguL6A9tLEIwNeVfOe8/edit?pli=1&gid=94309906#gid=94309906) into Rowhammer Payload Executor command set via an intermediate software layer.
The software layer executed on the PCIe host side can map the 3rd-party command set into Rowhammer Tester format with respect to the mapping specified below.

The table below presents encodings for the supported Payload Executor instructions.
The `NOOP`, `LOOP` and `STOP` instructions are used to control the flow of the Payload Executor module (are not propagated to the memory).
The DFI instruction is a sequence of the DDR commands and its length is determined by the number of preconfigured DDR phases. The example below presents single Rowhammer Tester instruction for the device working in 4 phases.

This mapping is common for all DRAM variants, the LSB distinguishes the Payload Executor control commands from the DFI commands.

After having transpilled the program, it is expected for the driver to transfer the the payload over the PCIe interface onto the Rowhammer Tester platform.

```{include} csv/payload-executor-bender.md
```

The table below represents the DDR-specific instructions encoding for the Rowhammer Tester platform.
A row of the table represents the DDR command (if one-cycle) or a `DFI PHASE` of the command.

Each of the DDR command in the DFI sequence can be prefixed with a `TIMESLICE` argument that determines the delay with which the next command in sequence is issued.

````{tab} DDR5
```{include} csv/dfi-ddr5-bender.md
```
````

````{tab} DDR4
```{include} csv/dfi-ddr4-bender.md
```
````

````{tab} LPDDR5
```{include} csv/dfi-lpddr5-bender.md
```
````

````{tab} LPDDR4
```{include} csv/dfi-lpddr4-bender.md
```
````

