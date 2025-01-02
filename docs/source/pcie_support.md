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
In order to make the RDIMM DDR5 Tetser compliant with DRAM Bender API it is required to to transpill [Bender API](https://docs.google.com/spreadsheets/d/18mPiKa1HBoO0OmzAbWRvo5OnIguL6A9tLEIwNeVfOe8/edit?pli=1&gid=94309906#gid=94309906) into Rowhammer Payload Executor command set via an intermediate software layer.
The software layer executed on PCIe host side can map the 3rd-party command set into Rowhammer Tester format with respect to the mapping specified below.

The table below presents mapping of PCIe transactions into commands used for controling the Payload Executor.
This mapping is common for all DRAM variants.

```{include} csv/payload-executor-bender.md
```

The table below presents DRAM-specific command mappings proposed for PCIe integration.

````{tab} DDR4
```{include} csv/dfi-ddr4-bender.md
```
````
````{tab} DDR5
```{include} csv/dfi-ddr5-bender.md
```
````
````{tab} LPDDR4
```{include} csv/dfi-lpddr4-bender.md
```
````
````{tab} LPDDR5
```{include} csv/dfi-lpddr5-bender.md
```
````
