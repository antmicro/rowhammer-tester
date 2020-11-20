#!/usr/bin/env python3

import argparse

from migen import *

from litex_boards.platforms import zcu104
from litex.build.xilinx.vivado import vivado_build_args, vivado_build_argdict
from litex.soc.integration.builder import Builder
from litex.soc.cores.clock import USMMCM, USIDELAYCTRL, AsyncResetSynchronizer

from litedram.modules import MTA4ATF51264HZ
from litedram.phy import usddrphy

from liteeth.phy.usrgmii import LiteEthPHYRGMII

from rowhammer_tester.targets import common

# CRG ----------------------------------------------------------------------------------------------

class CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.rst = Signal()
        self.clock_domains.cd_sys    = ClockDomain()
        self.clock_domains.cd_sys4x  = ClockDomain(reset_less=True)
        self.clock_domains.cd_pll4x  = ClockDomain(reset_less=True)
        self.clock_domains.cd_idelay = ClockDomain()
        self.clock_domains.cd_uart   = ClockDomain()

        # # #

        self.submodules.pll = pll = USMMCM(speedgrade=-2)
        self.comb += pll.reset.eq(self.rst)
        pll.register_clkin(platform.request("clk125"), 125e6)
        pll.create_clkout(self.cd_pll4x, sys_clk_freq*4, buf=None, with_reset=False)
        pll.create_clkout(self.cd_idelay, 500e6, with_reset=False)
        pll.create_clkout(self.cd_uart, sys_clk_freq, with_reset=False)

        self.specials += [
            Instance("BUFGCE_DIV", name="main_bufgce_div",
                p_BUFGCE_DIVIDE=4,
                i_CE=1, i_I=self.cd_pll4x.clk, o_O=self.cd_sys.clk),
            Instance("BUFGCE", name="main_bufgce",
                i_CE=1, i_I=self.cd_pll4x.clk, o_O=self.cd_sys4x.clk),
            AsyncResetSynchronizer(self.cd_idelay, ~pll.locked),
        ]

        self.submodules.idelayctrl = USIDELAYCTRL(cd_ref=self.cd_idelay, cd_sys=self.cd_sys)

# SoC ----------------------------------------------------------------------------------------------

class SoC(common.RowHammerSoC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_platform(self):
        return zcu104.Platform()

    def get_crg(self):
        return CRG(self.platform, self.sys_clk_freq)

    def get_ddrphy(self):
        return usddrphy.USPDDRPHY(
            pads             = self.platform.request("ddram"),
            memtype          = "DDR4",
            sys_clk_freq     = self.sys_clk_freq,
            iodelay_clk_freq = 500e6)

    def get_sdram_module(self):
        return MTA4ATF51264HZ(self.sys_clk_freq, "1:4")

    def add_host_bridge(self):
        self.add_uartbone(name="serial", clk_freq=self.sys_clk_freq, baudrate=1e6, cd="uart")

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on ZCU104")

    common.parser_args(parser, sys_clk_freq='125e6')
    vivado_build_args(parser)
    args = parser.parse_args()

    soc_kwargs = common.get_soc_kwargs(args)
    soc = SoC(**soc_kwargs)

    target_name = 'zcu104'
    builder_kwargs = common.get_builder_kwargs(args, target_name=target_name)
    builder = Builder(soc, **builder_kwargs)
    build_kwargs = vivado_build_argdict(args) if not args.sim else {}

    common.run(args, builder, build_kwargs, target_name=target_name)

if __name__ == "__main__":
    main()
