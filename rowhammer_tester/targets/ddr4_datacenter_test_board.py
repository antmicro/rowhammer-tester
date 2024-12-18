#!/usr/bin/env python3

from litedram.phy import k7ddrphy
from litex.build.xilinx.vivado import vivado_build_argdict, vivado_build_args
from litex.soc.cores.bitbang import I2CMaster, I2CMasterSim
from litex.soc.cores.clock import S7IDELAYCTRL, S7PLL
from litex.soc.integration.builder import Builder
from litex_boards.platforms import antmicro_datacenter_ddr4_test_board
from migen import ClockDomain, Module

from rowhammer_tester.targets import common

# CRG ----------------------------------------------------------------------------------------------


class CRG(Module):
    def __init__(self, platform, sys_clk_freq, iodelay_clk_freq):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys2x = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x_dqs = ClockDomain(reset_less=True)
        self.clock_domains.cd_idelay = ClockDomain()

        # # #

        self.submodules.pll = pll = S7PLL(speedgrade=-1)
        pll.register_clkin(platform.request("clk100"), 100e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        pll.create_clkout(self.cd_sys2x, 2 * sys_clk_freq)
        pll.create_clkout(self.cd_sys4x, 4 * sys_clk_freq)
        pll.create_clkout(self.cd_sys4x_dqs, 4 * sys_clk_freq, phase=90)
        pll.create_clkout(self.cd_idelay, iodelay_clk_freq)

        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_idelay)


# SoC ----------------------------------------------------------------------------------------------


class SoC(common.RowHammerSoC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # SPD EEPROM I2C ---------------------------------------------------------------------------
        pads = self.platform.request("i2c")
        if self.args.sim:
            self.submodules.i2c = I2CMasterSim(pads)

            # As we don't simulate communication with SPD or RCD via I2C,
            # we need to set SDA high, so the I2C controller gets NACK.
            self.comb += pads.sda_in.eq(1)
        else:
            self.submodules.i2c = I2CMaster(
                pads, sys_freq=self.sys_clk_freq, bus_freq=400e3, fifo_depth=192
            )

        self.add_csr("i2c")

    def get_platform(self):
        return antmicro_datacenter_ddr4_test_board.Platform()

    def get_crg(self):
        return CRG(
            self.platform, self.sys_clk_freq, iodelay_clk_freq=float(self.args.iodelay_clk_freq)
        )

    def get_ddrphy(self):
        return k7ddrphy.K7DDRPHY(
            self.platform.request("ddr4"),
            write_latency_calibration=True,
            iodelay_clk_freq=float(self.args.iodelay_clk_freq),
            sys_clk_freq=self.sys_clk_freq,
            memtype="DDR4",
            is_rdimm=True,
        )

    def get_sdram_ratio(self):
        return "1:4"


# Build --------------------------------------------------------------------------------------------


def main():
    parser = common.ArgumentParser(
        description="LiteX SoC on DDR4 Datacenter Test Board",
        sys_clk_freq="100e6",
        module="MTA18ASF2G72PZ",
    )
    g = parser.add_argument_group(title="DDR4 Datacenter Test Board")
    parser.add(g, "--eth-reset-time", default="10e-3", help="Duration of Ethernet PHY reset")
    parser.add(g, "--iodelay-clk-freq", default="200e6", help="IODELAY clock frequency")
    vivado_build_args(g)
    args = parser.parse_args()

    soc_kwargs = common.get_soc_kwargs(args)
    soc = SoC(**soc_kwargs)

    target_name = "ddr4_datacenter_test_board"
    builder_kwargs = common.get_builder_kwargs(args, target_name=target_name)
    builder = Builder(soc, **builder_kwargs)
    build_kwargs = vivado_build_argdict(args) if not args.sim else {}

    common.run(args, builder, build_kwargs, target_name=target_name)


if __name__ == "__main__":
    main()
