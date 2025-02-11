#!/usr/bin/env python3

import math

from litedram.phy import ddr5
from liteeth.phy import LiteEthUSPHYRGMII
from litex.build.generic_platform import Pins
from litex.build.io import DifferentialInput
from litex.build.xilinx.vivado import vivado_build_argdict, vivado_build_args
from litex.soc.cores.bitbang import I2CMaster
from litex.soc.cores.clock import USPIDELAYCTRL, USPMMCM
from litex.soc.cores.gpio import GPIOOut
from litex.soc.integration.builder import Builder

# from litex.soc.integration.doc import ModuleDoc
from litex_boards.platforms import antmicro_ddr5_tester_usp
from migen import ClockDomain, ClockSignal, Instance, Module, Signal

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
        # Fast clocks to the component mode PHYCRG
        self.clock_domains.cd_sys4x_raw = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x_90_raw = ClockDomain(reset_less=True)
        # BUFGCE/BUFGECE_DIV enable and reset domains
        self.clock_domains.cd_sys2x_rst = ClockDomain()
        self.clock_domains.cd_sys2x_90_rst = ClockDomain()

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
        mmcm.create_clkout(self.cd_sys4x_raw, 4 * sys_clk_freq, buf=None, with_reset=False)
        mmcm.create_clkout(self.cd_sys2x_rst, 2 * sys_clk_freq)
        mmcm.create_clkout(
            self.cd_sys4x_90_raw, 4 * sys_clk_freq, phase=90, buf=None, with_reset=False
        )
        mmcm.create_clkout(self.cd_sys2x_90_rst, 2 * sys_clk_freq, phase=45)
        mmcm.create_clkout(self.cd_sys, sys_clk_freq, with_reset=False)
        mmcm.create_clkout(self.cd_riu, riu_clk_freq, with_reset=False)
        mmcm.params["name"] = "MMCM_IO"

        self.submodules.mmcm_idlyctrl = mmcm_idlyctrl = USPMMCM(speedgrade=-2)
        mmcm_idlyctrl.register_clkin(input_clk, input_clk_freq)
        mmcm_idlyctrl.create_clkout(self.cd_idelay, iodelay_clk_freq)

        self.submodules.idelayctrl = USPIDELAYCTRL(self.cd_idelay, self.cd_sys)


# SoC ----------------------------------------------------------------------------------------------


class SoC(common.RowHammerSoC):
    def __init__(self, build_sim=False, **kwargs):
        self.skip_MC = False
        if build_sim:
            kwargs["uart_name"] = "serial"
            kwargs["uart_baudrate"] = 10000000
        super().__init__(**kwargs)

        # SPD EEPROM I2C ---------------------------------------------------------------------------
        self.submodules.i2c = I2CMaster(self.platform.request("i2c"))
        self.add_csr("i2c")
        if build_sim:
            self.platform.add_extension([("finish", 0, Pins(1))])
            self.add_constant("CONFIG_BIOS_NO_CRC")
            self.add_constant("CONFIG_BIOS_NO_PROMPT")
            self.add_constant("MAIN_RAM_BASE")
            self.add_constant("CONFIG_MAIN_RAM_INIT")
            self.submodules.sim_finisher = GPIOOut(self.platform.request("finish"))
            with self.create_early_init() as early_init:
                early_init += """printf("Sim PHY init\\n");
    ddrphy_phy_reset_write(0);
    do {
        busy_wait_us(50);
    } while (!ddrphy_init_status_init_done_read());

    sim_finisher_out_write(1);
"""
            breakpoint()

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

    def get_ddr_pin_domains(self):
        return dict(
            ck_t=(("sys2x_io", "sys4x_io"), None),
            ck_c=(("sys2x_io", "sys4x_io"), None),
            A_ca=(("sys2x_io", "sys4x_io"), None),
            A_par=(("sys2x_io", "sys4x_io"), None),
            A_cs_n=(("sys2x_io", "sys4x_io"), None),
            B_ca=(("sys2x_io", "sys4x_io"), None),
            B_par=(("sys2x_io", "sys4x_io"), None),
            B_cs_n=(("sys2x_io", "sys4x_io"), None),
            reset_n=(("sys2x_io", "sys4x_io"), None),
            alert_n=(None, ("sys_io", "sys4x_io")),
            A_dq=(("sys2x_90_io", "sys4x_90_io"), ("sys2x_90_io", "sys4x_90_io")),
            A_dqs_t=(("sys2x_io", "sys4x_io"), ("sys2x_io", "sys4x_io")),
            A_dqs_c=(("sys2x_io", "sys4x_io"), ("sys2x_io", "sys4x_io")),
            B_dq=(("sys2x_90_io", "sys4x_90_io"), ("sys2x_90_io", "sys4x_90_io")),
            B_dqs_t=(("sys2x_io", "sys4x_io"), ("sys2x_io", "sys4x_io")),
            B_dqs_c=(("sys2x_io", "sys4x_io"), ("sys2x_io", "sys4x_io")),
        )

    def get_ddrphy(self):
        phycrg = ddr5.USPPHYCRG(
            reset_clock_domain="sys2x_rst",
            reset_clock_90_domain="sys2x_90_rst",
            source_4x=ClockSignal("sys4x_raw"),
            source_4x_90=ClockSignal("sys4x_90_raw"),
        )
        self.submodules.PHYCRG = phycrg
        phycrg.create_clock_domains(
            clock_domains=["sys_io", "sys2x_io", "sys2x_90_io", "sys4x_io", "sys4x_90_io"],
        )

        pin_vref_mapping = {}
        for key, mappings in self.platform.pin_bank_byte_nibble_bitslice_mapping()["ddr5"].items():
            for (bank, byte, _, _) in mappings:
                if key not in pin_vref_mapping:
                    pin_vref_mapping[key] = []
                pin_vref_mapping[key].append((bank, byte))

        return ddr5.USPCompoDDR5PHY(
            iodelay_clk_freq=float(self.args.sys_clk_freq)*4,
            sys_clk_freq=self.sys_clk_freq,
            direct_control=False,
            pads=self.platform.request("ddr5"),
            crg=phycrg,
            with_sub_channels=True,
            pin_domains=self.get_ddr_pin_domains(),
            pin_vref_mapping = pin_vref_mapping
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
        sys_clk_freq="125e6",
        module="M329R8GA0BB0",
    )
    g = parser.add_argument_group(title="UltraScale+ DDR5 Tester Board")

    parser.add(g, "--eth-reset-time", default="10e-3", help="Duration of Ethernet PHY reset")
    parser.add(g, "--iodelay-clk-freq", default="300e6", help="IODELAY clock frequency")
    parser.add(g, "--riu-clk-freq", default="200e6", help="XIPHY RIU clock frequency")
    parser.add(
        g, "--build-for-simulation", action="store_true", help="Build verilog and SW for simulation"
    )
    vivado_build_args(g)
    args = parser.parse_args()
    if args.build_for_simulation:
        args.no_compile_gateware = True

    soc_kwargs = common.get_soc_kwargs(args)
    soc_kwargs.update(dict(riu_clk_freq=args.riu_clk_freq))
    soc = SoC(build_sim=args.build_for_simulation, **soc_kwargs)
    #    soc.platform.add_platform_command(
    #        "set_property USER_CLOCK_ROOT X0Y1 ["
    #        'get_nets -filter {{NAME=="{riu_clk}" || NAME=="{div_clk}"}}]',
    #        riu_clk=soc.crg.cd_riu.clk,
    #        div_clk=soc.crg.cd_sys.clk,
    #    )
    #    soc.platform.add_platform_command(
    #        "set_property CLOCK_DELAY_GROUP RIU_DIV_group ["
    #        'get_nets -filter {{NAME=="{riu_clk}" || NAME=~"*xiphy*pll_clk"}}]',
    #        riu_clk=soc.crg.cd_riu.clk,
    #    )
    #    soc.platform.add_platform_command(
    #        'set_property LOC MMCM_X0Y1 [get_cells -filter (NAME=="MMCM_IO")]'
    #    )
    soc.platform.add_platform_command(
        "set_property CLOCK_DEDICATED_ROUTE SAME_CMT_COLUMN "
        '[get_nets -filter (NAME=="{clkin}")]',
        clkin=soc.crg.bufg_o,
    )
    soc.platform.add_platform_command(
        "set_property UNAVAILABLE_DURING_CALIBRATION TRUE [get_ports ddr5_dlbdq]"
    )
    soc.platform.add_platform_command(
        "set_property UNAVAILABLE_DURING_CALIBRATION TRUE [get_ports ddr5_B_dqsb_t[0]]"
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
