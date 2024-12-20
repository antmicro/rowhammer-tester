#!/usr/bin/env python3

import math

from litedram.phy import ddr5
from liteeth.phy import LiteEthUSPHYRGMII
from litex.build.io import DifferentialInput
from litex.build.xilinx.vivado import vivado_build_argdict, vivado_build_args
from litex.soc.cores.bitbang import I2CMaster
from litex.soc.cores.clock import USPIDELAYCTRL, USPMMCM
from litex.soc.integration.builder import Builder

# from litex.soc.integration.doc import ModuleDoc
from litex_boards.platforms import antmicro_ddr5_tester_usp
from migen import ClockDomain, Instance, Module, Signal

from rowhammer_tester.targets import common

# CRG ----------------------------------------------------------------------------------------------


class CRG(Module):
    def __init__(self, platform, sys_clk_freq, riu_clk_freq, iodelay_clk_freq):
        if iodelay_clk_freq < 300e6 or iodelay_clk_freq > 800e6:
            raise AssertionError(
                "IDELAYCTRL reference frequency must be between 300Mhz and 800MHz"
                f". Selected value {iodelay_clk_freq} doesn't fall it this range."
            )
        if riu_clk_freq > 250e6:
            raise AssertionError(
                f"RIU clock frequency {riu_clk_freq} is beyond safe value of 250 MHz"
            )
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_riu = ClockDomain()
        self.clock_domains.cd_idelay = ClockDomain()

        # # #
        input_clk_freq = 100e6
        input_clk_pads = platform.request("clk100")
        input_clk_unbuf = Signal()
        self.bufg_o = input_clk = Signal()
        self.specials += DifferentialInput(input_clk_pads.p, input_clk_pads.n, input_clk_unbuf)
        self.specials += Instance(
            "BUFG",
            i_I=input_clk_unbuf,
            o_O=input_clk,
        )

        # MMCM
        self.submodules.mmcm = mmcm = USPMMCM(speedgrade=-2)
        mmcm.register_clkin(input_clk, input_clk_freq)
        mmcm.create_clkout(self.cd_sys, sys_clk_freq, with_reset=False)
        mmcm.create_clkout(self.cd_riu, riu_clk_freq, with_reset=False)
        mmcm.params["name"] = "MMCM_IO"

        self.submodules.mmcm_idlyctrl = mmcm_idlyctrl = USPMMCM(speedgrade=-2)
        mmcm_idlyctrl.register_clkin(input_clk, input_clk_freq)
        mmcm_idlyctrl.create_clkout(self.cd_idelay, iodelay_clk_freq)

        self.submodules.idelayctrl = USPIDELAYCTRL(self.cd_idelay, self.cd_sys)


# SoC ----------------------------------------------------------------------------------------------


class SoC(common.RowHammerSoC):
    def __init__(self, **kwargs):
        self.skip_MC = True
        super().__init__(**kwargs)

        # SPD EEPROM I2C ---------------------------------------------------------------------------
        self.submodules.i2c = I2CMaster(self.platform.request("i2c"))
        self.add_csr("i2c")

    def get_platform(self):
        return antmicro_ddr5_tester_usp.Platform()

    def get_crg(self):
        crg = CRG(
            self.platform,
            self.sys_clk_freq,
            riu_clk_freq=float(self.args.riu_clk_freq),
            iodelay_clk_freq=float(self.args.iodelay_clk_freq),
        )
        return crg

    def get_ddrphy(self):
        return ddr5.USPDDR5PHY(
            pads=self.platform.request("ddr5"),
            sys_freq=self.sys_clk_freq,
            riu_freq=float(self.args.riu_clk_freq),
            with_sub_channels=True,
            pin_bank_byte_nibble_bitslice_mapping=self.platform.pin_bank_byte_nibble_bitslice_mapping()[
                "ddr5"
            ],
        )

    def add_host_bridge(self):
        clock_pads = self.platform.request("eth_clocks")
        self.submodules.ethphy = phy = LiteEthUSPHYRGMII(
            clock_pads=clock_pads,
            pads=self.platform.request("eth"),
            hw_reset_cycles=math.ceil(float(self.args.eth_reset_time) * self.sys_clk_freq),
            rx_delay=0.8e-9,
            iodelay_clk_freq=float(self.args.iodelay_clk_freq),
            usp=True,
        )
        self.add_etherbone(
            phy=phy,
            ip_address=self.ip_address,
            mac_address=self.mac_address,
            udp_port=self.udp_port,
            buffer_depth=256,
            with_timing_constraints=False,
        )

        eth_rx_clk = getattr(phy, "crg", phy).cd_eth_rx.clk
        eth_tx_clk = getattr(phy, "crg", phy).cd_eth_tx.clk
        eth_rx_clk.attr.add("keep")
        eth_tx_clk.attr.add("keep")
        # Period constraint is specified in ns
        self.platform.add_period_constraint(clock_pads.rx, 1e9 / phy.rx_clk_freq)
        self.platform.add_false_path_constraints(self.crg.cd_sys.clk, eth_rx_clk)
        self.platform.add_false_path_constraints(self.crg.cd_sys.clk, eth_tx_clk)

    def get_sdram_ratio(self):
        return "1:4"


# Build --------------------------------------------------------------------------------------------


def main():
    parser = common.ArgumentParser(
        description="LiteX SoC on UltraScale+ DDR5 Tester Board",
        sys_clk_freq="333.333333e6",
        module="M329R8GA0BB0",
    )
    g = parser.add_argument_group(title="UltraScale+ DDR5 Tester Board")

    parser.add(g, "--eth-reset-time", default="10e-3", help="Duration of Ethernet PHY reset")
    parser.add(g, "--iodelay-clk-freq", default="300e6", help="IODELAY clock frequency")
    parser.add(g, "--riu-clk-freq", default="200e6", help="XIPHY RIU clock frequency")
    vivado_build_args(g)
    args = parser.parse_args()

    soc_kwargs = common.get_soc_kwargs(args)
    soc_kwargs.update(dict(riu_clk_freq=args.riu_clk_freq))
    soc = SoC(**soc_kwargs)
    soc.platform.add_platform_command(
        "set_property USER_CLOCK_ROOT X0Y1 ["
        'get_nets -filter {{NAME=="{riu_clk}" || NAME=="{div_clk}"}}]',
        riu_clk=soc.crg.cd_riu.clk,
        div_clk=soc.crg.cd_sys.clk,
    )
    soc.platform.add_platform_command(
        "set_property CLOCK_DELAY_GROUP RIU_DIV_group ["
        'get_nets -filter {{NAME=="{riu_clk}" || NAME=~"*xiphy*pll_clk"}}]',
        riu_clk=soc.crg.cd_riu.clk,
    )
    soc.platform.add_platform_command(
        'set_property LOC MMCM_X0Y1 [get_cells -filter (NAME=="MMCM_IO")]'
    )
    soc.platform.add_platform_command(
        "set_property CLOCK_DEDICATED_ROUTE SAME_CMT_COLUMN "
        '[get_nets -filter (NAME=="{clkin}")]',
        clkin=soc.crg.bufg_o,
    )

    target_name = "ddr5_tester_usp"
    builder_kwargs = common.get_builder_kwargs(args, target_name=target_name)
    builder = Builder(soc, **builder_kwargs)
    build_kwargs = vivado_build_argdict(args) if not args.sim else {}
    if not args.sim:
        build_kwargs["vivado_place_directive"] = "AltSpreadLogic_high"
        build_kwargs["vivado_post_place_phys_opt_directive"] = "AggressiveExplore"
        build_kwargs["vivado_route_directive"] = "AggressiveExplore"
        build_kwargs["vivado_post_route_phys_opt_directive"] = "AggressiveExplore"

    common.run(args, builder, build_kwargs, target_name=target_name)


if __name__ == "__main__":
    main()
