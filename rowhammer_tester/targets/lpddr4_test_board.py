#!/usr/bin/env python3

import math

from litedram.phy import lpddr4
from liteeth.phy import LiteEthS7PHYRGMII
from litex.build.xilinx.vivado import vivado_build_argdict, vivado_build_args
from litex.soc.cores.clock import S7IDELAYCTRL, S7PLL
from litex.soc.integration.builder import Builder
from litex_boards.platforms import antmicro_lpddr4_test_board
from migen import *

from rowhammer_tester.targets import common

# CRG ----------------------------------------------------------------------------------------------


class CRG(Module):
    def __init__(self, platform, sys_clk_freq, iodelay_clk_freq):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys2x = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys8x = ClockDomain(reset_less=True)
        self.clock_domains.cd_idelay = ClockDomain()

        # # #

        self.submodules.pll = pll = S7PLL(speedgrade=-1)
        pll.register_clkin(platform.request("clk100"), 100e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        pll.create_clkout(self.cd_sys2x, 2 * sys_clk_freq)
        pll.create_clkout(self.cd_sys8x, 8 * sys_clk_freq)
        pll.create_clkout(self.cd_idelay, iodelay_clk_freq)

        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_idelay)


# SoC ----------------------------------------------------------------------------------------------


class SoC(common.RowHammerSoC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_platform(self):
        return antmicro_lpddr4_test_board.Platform()

    def get_crg(self):
        return CRG(
            self.platform, self.sys_clk_freq, iodelay_clk_freq=float(self.args.iodelay_clk_freq)
        )

    def get_ddrphy(self):
        return lpddr4.K7LPDDR4PHY(
            self.platform.request("lpddr4"),
            iodelay_clk_freq=float(self.args.iodelay_clk_freq),
            sys_clk_freq=self.sys_clk_freq,
        )

    def get_sdram_ratio(self):
        return "1:8"


# Build --------------------------------------------------------------------------------------------


def main():
    parser = common.ArgumentParser(
        description="LiteX SoC on LPDDR4 Test Board", sys_clk_freq="50e6", module="MT53E256M16D1"
    )
    g = parser.add_argument_group(title="LPDDR4 Test Board")
    parser.add(g, "--eth-reset-time", default="10e-3", help="Duration of Ethernet PHY reset")
    parser.add(g, "--iodelay-clk-freq", default="200e6", help="IODELAY clock frequency")
    vivado_build_args(g)
    args = parser.parse_args()

    soc_kwargs = common.get_soc_kwargs(args)
    soc_kwargs["masked_write"] = True  # LPDDR4 always has masked writes
    soc = SoC(**soc_kwargs)

    target_name = "lpddr4_test_board"
    builder_kwargs = common.get_builder_kwargs(args, target_name=target_name)
    builder = Builder(soc, **builder_kwargs)
    build_kwargs = vivado_build_argdict(args) if not args.sim else {}

    common.run(args, builder, build_kwargs, target_name=target_name)


if __name__ == "__main__":
    main()
