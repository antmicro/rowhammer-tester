#!/usr/bin/env python3

import os
import math

from migen import *

from litex.build.xilinx.vivado import vivado_build_args, vivado_build_argdict
from litex.soc.integration.builder import Builder
from litex.soc.cores.clock import S7PLL, S7IDELAYCTRL

from litex_boards.platforms import antmicro_sodimm_ddr5_tester
from litedram.phy import lpddr5
from liteeth.phy import LiteEthS7PHYRGMII

from rowhammer_tester.targets import common

from litepcie.phy.s7pciephy import S7PCIEPHY
from litepcie.software import generate_litepcie_software

# CRG ----------------------------------------------------------------------------------------------

class CRG(Module):
    def __init__(self, platform, sys_clk_freq, iodelay_clk_freq):
        self.clock_domains.cd_sys    = ClockDomain()
        self.clock_domains.cd_sys2x  = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x  = ClockDomain(reset_less=True)
        self.clock_domains.cd_idelay = ClockDomain()

        # # #

        self.submodules.pll = pll = S7PLL(speedgrade=-1)
        pll.register_clkin(platform.request("clk100"), 100e6)
        pll.create_clkout(self.cd_sys,    sys_clk_freq)
        pll.create_clkout(self.cd_sys2x,  2 * sys_clk_freq)
        pll.create_clkout(self.cd_sys4x,  4 * sys_clk_freq)
        pll.create_clkout(self.cd_idelay, iodelay_clk_freq)

        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_idelay)

# SoC ----------------------------------------------------------------------------------------------

class SoC(common.RowHammerSoC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.pcie_phy = S7PCIEPHY(self.platform, self.platform.request("pcie_x4"),
                                  data_width = 128, bar0_size  = 0x20000)
        self.add_pcie(phy=self.pcie_phy, ndmas=1)

    def get_platform(self):
        return antmicro_sodimm_ddr5_tester.Platform()

    def get_crg(self):
        return CRG(self.platform, self.sys_clk_freq,
            iodelay_clk_freq=float(self.args.iodelay_clk_freq))

    def get_ddrphy(self):
        return lpddr5.K7UNILPDDR5PHY(self.platform.request("lpddr5"),
            iodelay_clk_freq  = float(self.args.iodelay_clk_freq),
            ck_freq           = self.sys_clk_freq,
            with_sub_channels = True)

    def get_sdram_ratio(self):
        return "1:8"

    def add_host_bridge(self):
        self.submodules.ethphy = LiteEthS7PHYRGMII(
            clock_pads       = self.platform.request("eth_clocks"),
            pads             = self.platform.request("eth"),
            hw_reset_cycles  = math.ceil(float(self.args.eth_reset_time) * self.sys_clk_freq),
            rx_delay         = 0.8e-9,
            iodelay_clk_freq = float(self.args.iodelay_clk_freq),
        )
        self.add_etherbone(
            phy          = self.ethphy,
            ip_address   = self.ip_address,
            mac_address  = self.mac_address,
            udp_port     = self.udp_port,
            buffer_depth = 256)

# Build --------------------------------------------------------------------------------------------

def main():
    parser = common.ArgumentParser(
        description  = "LiteX SoC on SO-DDIM DDR5 Tester Board",
        sys_clk_freq = '60e6',
        module       = 'MT62F1G32D4DR'
    )
    g = parser.add_argument_group(title="SO-DDIM DDR5 Tester Board")
    parser.add(g, "--eth-reset-time", default="10e-3", help="Duration of Ethernet PHY reset")
    parser.add(g, "--iodelay-clk-freq", default="200e6", help="IODELAY clock frequency")
    parser.add(g, "--pcie-driver", action="store_true", help="Generate PCIe driver.")
    vivado_build_args(g)
    args = parser.parse_args()

    soc_kwargs = common.get_soc_kwargs(args)
    soc_kwargs['with_sub_channels'] = True
    soc = SoC(**soc_kwargs)

    target_name = 'sodimm_ddr5_tester'
    builder_kwargs = common.get_builder_kwargs(args, target_name=target_name)
    builder = Builder(soc, **builder_kwargs)
    build_kwargs = vivado_build_argdict(args) if not args.sim else {}

    common.run(args, builder, build_kwargs, target_name=target_name)

    if args.pcie_driver:
        generate_litepcie_software(soc, os.path.join(builder.output_dir, "pcie_driver"))


if __name__ == "__main__":
    main()

