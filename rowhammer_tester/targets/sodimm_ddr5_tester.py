#!/usr/bin/env python3

import math

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import MultiReg

from litex.build.xilinx.vivado import vivado_build_args, vivado_build_argdict
from litex.soc.integration.builder import Builder
from litex.soc.cores.bitbang import I2CMaster
from litex.soc.cores.clock import S7PLL, S7MMCM, S7IDELAYCTRL
from litex.soc.cores.gpio import GPIOIn, GPIOOut
from litex.soc.integration.doc import ModuleDoc

from litex_boards.platforms import antmicro_sodimm_ddr5_tester
from litedram.phy import ddr5
from liteeth.phy import LiteEthS7PHYRGMII

from rowhammer_tester.targets import common

# CRG ----------------------------------------------------------------------------------------------

class CRG(Module):
    def __init__(self, platform, sys_clk_freq, iodelay_clk_freq):
        self.clock_domains.cd_sys                  = ClockDomain()
        self.clock_domains.cd_sys2x                = ClockDomain(reset_less=True)
        self.clock_domains.cd_idelay               = ClockDomain()

        # BUFMR to BUFR and BUFIO, "raw" clocks
        self.clock_domains.cd_sys4x_raw    = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x_90_raw = ClockDomain(reset_less=True)
        # BUFMR reset domains
        self.clock_domains.cd_sys2x_rst = ClockDomain()
        self.clock_domains.cd_sys2x_90_rst = ClockDomain()

        # # #
        input_clk_freq = 100e6
        input_clk = platform.request("clk100")

        # MMCM
        self.submodules.mmcm = mmcm = S7MMCM(speedgrade=-3)
        mmcm.register_clkin(input_clk, input_clk_freq)

        mmcm.create_clkout(
            self.cd_sys4x_raw,
            4 * sys_clk_freq,
            buf=None,
            with_reset=False,
        )
        mmcm.create_clkout(
            self.cd_sys4x_90_raw,
            4 * sys_clk_freq,
            phase=90,
            with_reset=False,
            buf=None,
        )
        mmcm.create_clkout(
            self.cd_sys2x_rst,
            2 * sys_clk_freq,
            clock_out = 0,
            div       = 2,
            buf       = 'bufr',
        )
        mmcm.create_clkout(
            self.cd_sys2x_90_rst,
            2 * sys_clk_freq,
            clock_out = 1,
            div       = 2,
            phase     = 90,
            buf       = 'bufr',
        )

        mmcm.create_clkout(self.cd_sys,    sys_clk_freq)
        mmcm.create_clkout(self.cd_sys2x,  sys_clk_freq * 2)

        self.submodules.pll_iodly = pll_iodly = S7PLL(speedgrade=-3)
        pll_iodly.register_clkin(input_clk, input_clk_freq)
        pll_iodly.create_clkout(self.cd_idelay, iodelay_clk_freq)

        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_idelay)

def ddr5_tester_CRGDOC():
    return [
    ModuleDoc(title="S7CRGPHY", body="""\
This module contains 7 series specific clock and reset generation for S7DDR5 PHY.
It adds:

- BUFMRCE to control multi region PHYs (UDIMMs and/or RDIMMs),
- BUFMRCE/BUFRs reset sequence,
- ISERDES reset sequence correct with Xilinx documentation and design advisories,
- OSERDES reset sequence.
"""),
    ModuleDoc(title="DDR5 Tester Clock tree", body="""\
.. image:: ddr5_tester_CRG.png
"""),
]

# SoC ----------------------------------------------------------------------------------------------

class SoC(common.RowHammerSoC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # SPD EEPROM I2C ---------------------------------------------------------------------------
        self.submodules.i2c = I2CMaster(self.platform.request("i2c_ddr"), True)
        self.add_csr("i2c")
        self.submodules.platform_i2c = I2CMaster(self.platform.request("i2c_platform"))
        self.add_csr("platform_i2c")
        # GPIO -------------------------------------------------------------------------------------
        in_pads = [
            self.platform.request("pwr_good"),
            self.platform.request("tb_detect"),
            self.platform.request("ddr_presence_n"),
        ]
        _in = Signal(3)
        self.comb += [_in[i].eq(pad) for i, pad in enumerate(in_pads)]
        self.submodules.GPIO_in = GPIOIn(_in)
        self.add_csr("GPIO_in")

        out_pads = [
            self.platform.request("pwr_en"),
            self.platform.request("LED_yellow"),
            self.platform.request("LED_red"),
            self.platform.request("LED_green"),
        ]
        _out = Signal(4)
        self.comb += [pad.eq(_out[i]) for i, pad in enumerate(out_pads)]
        self.submodules.GPIO_out = GPIOOut(_out)
        self.add_csr("GPIO_out")

        with self.create_early_init() as early_init:
            early_init += """printf("Early Init\\n");
	uint32_t board_state = 0;
	uint32_t i2c_count;
	uint32_t GPIO_state;
	uint32_t default_i2c;
	int i;
	// Disable PWR_EN
	GPIO_out_out_write(0);
	busy_wait(5000);

	// Wait for DIMM to show up
	do {
		busy_wait(500);
		board_state = GPIO_in_in_read();
		printf("Board state:%"PRId32"\\n", board_state);
		leds_out_write(board_state);
	} while (board_state&0x4);

	// Testbed detected but SO-DIMM expected
	if (board_state&0x2) {
		printf("Incorrect module detected! Power-off and replace with DDR5 SO-DIMM\\n");
		GPIO_state = GPIO_out_out_read();
		GPIO_state |= 0x4;
		GPIO_out_out_write(GPIO_state);
		while (1) {
			busy_wait(500);
			leds_out_write(-1);
			busy_wait(500);
			leds_out_write(0);
			busy_wait(2000);
		}
	}

	GPIO_state = GPIO_out_out_read();
	GPIO_state |= 0x8;
	GPIO_out_out_write(GPIO_state);
	// Setup Vref values
	i2c_count = get_i2c_devs_count();
	default_i2c = get_i2c_active_dev();
	for(i=0; i < i2c_count; ++i) {
		set_i2c_active_dev(i);
		printf("%d:%s\\n", i, get_i2c_devs()[i].name);
		if (strcmp(get_i2c_devs()[i].name, "platform_i2c") == 0) {
			unsigned char command[2] = {0x80, 0x00};
			i2c_write(0x60, 0x70, command, 2, 1);
			set_i2c_active_dev(default_i2c);
			break;
		}
	}

	// Set PWR_EN
	GPIO_state = GPIO_out_out_read();
	GPIO_state |= 0x1;
	GPIO_out_out_write(GPIO_state);
	// Wait for PWR_GOOD
	do {
		busy_wait(50);
		board_state = GPIO_in_in_read();
	} while(!(board_state&1));
	leds_out_write(-1);
"""

    def get_platform(self):
        return antmicro_sodimm_ddr5_tester.Platform()

    def get_crg(self):
        crg = CRG(self.platform, self.sys_clk_freq,
            iodelay_clk_freq=float(self.args.iodelay_clk_freq))
        return crg

    def get_ddr_pin_domains(self):
        return dict(
            A_ck_t=(("sys2x_io", "sys4x_io"), None),
            A_ck_c=(("sys2x_io", "sys4x_io"), None),
            B_ck_t=(("sys2x_io", "sys4x_io"), None),
            B_ck_c=(("sys2x_io", "sys4x_io"), None),
            A_ca=(("sys2x_io", "sys4x_io"), None),
            A_cs_n=(("sys2x_io", "sys4x_io"), None),
            B_ca=(("sys2x_io", "sys4x_io"), None),
            B_cs_n=(("sys2x_io", "sys4x_io"), None),
            reset_n=(("sys2x_io", "sys4x_io"), None),
            alert_n=(None, ("sys_io", "sys4x_io")),
            A_dq=(("sys2x_90_io", "sys4x_90_io"), ("sys_io", "sys4x_io")),
            A_dm_n=(("sys2x_90_io", "sys4x_90_io"), ("sys_io", "sys4x_io")),
            A_dqs_t=(("sys2x_io", "sys4x_io"), ("sys_io", "sys4x_io")),
            A_dqs_c=(("sys2x_io", "sys4x_io"), ("sys_io", "sys4x_io")),
            B_dq=(("sys2x_90_io", "sys4x_90_io"), ("sys_io", "sys4x_io")),
            B_dm_n=(("sys2x_90_io", "sys4x_90_io"), ("sys_io", "sys4x_io")),
            B_dqs_t=(("sys2x_io", "sys4x_io"), ("sys_io", "sys4x_io")),
            B_dqs_c=(("sys2x_io", "sys4x_io"), ("sys_io", "sys4x_io")),
        )

    def get_ddrphy(self):
        PHYCRG = ddr5.S7PHYCRG(
            reset_clock_domain = "sys2x_rst",
            reset_clock_90_domain = "sys2x_90_rst",
            source_4x          = ClockSignal("sys4x_raw"),
            source_4x_90       = ClockSignal("sys4x_90_raw"),
        )
        self.submodules.PHYCRG = PHYCRG
        PHYCRG.create_clock_domains(
            clock_domains = ["sys_io", "sys2x_io", "sys2x_90_io", "sys4x_io", "sys4x_90_io"],
            io_banks      = ["bank32", "bank33", "bank34"],
        )
        setattr(PHYCRG, "get_module_documentation", ddr5_tester_CRGDOC)
        return ddr5.K7DDR5PHY(self.platform.request("ddr5"),
            crg               = PHYCRG,
            iodelay_clk_freq  = float(self.args.iodelay_clk_freq),
            sys_clk_freq      = self.sys_clk_freq,
            with_sub_channels = True,
            direct_control    = False,
            with_per_dq_idelay= True,
            pin_domains       = self.get_ddr_pin_domains(),
            pin_banks         = self.platform.pin_bank_mapping()["ddr5"],
        )

    def get_sdram_ratio(self):
        return "1:4"

    def add_host_bridge(self):
        self.submodules.ethphy = LiteEthS7PHYRGMII(
            clock_pads         = self.platform.request("eth_clocks"),
            pads               = self.platform.request("eth"),
            hw_reset_cycles    = math.ceil(float(self.args.eth_reset_time) * self.sys_clk_freq),
            rx_delay           = 0.8e-9,
            iodelay_clk_freq   = float(self.args.iodelay_clk_freq),
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
        description  = "LiteX SoC on DDR5 Tester Board",
        sys_clk_freq = '200e6',
        module       = 'MTC8C1084S1SC48BA1_BC'
    )
    g = parser.add_argument_group(title="DDR5 Tester Board")
    parser.add(g, "--eth-reset-time", default="10e-3", help="Duration of Ethernet PHY reset")
    parser.add(g, "--iodelay-clk-freq", default="200e6", help="IODELAY clock frequency")
    vivado_build_args(g)
    args = parser.parse_args()

    soc_kwargs = common.get_soc_kwargs(args)
    soc = SoC(**soc_kwargs)
    soc.get_ddr_pin_domains()
    soc.platform.add_platform_command("set_property CLOCK_BUFFER_TYPE BUFG [get_nets sys_rst]")
    soc.platform.add_platform_command("set_disable_timing -from WRCLK -to RST "
        "[get_cells -filter {{(REF_NAME == FIFO18E1 || REF_NAME == FIFO36E1) && EN_SYN == FALSE}}]")
    soc.platform.add_platform_command("set_max_delay -quiet "
        "-to [get_pins -hierarchical -regexp BUFR.*/CLR] 10.0")
    soc.platform.add_platform_command("set_max_delay -quiet "
        "-from [get_clocks -of_objects [get_pins rst_domain/O]] "
        "-to [list [get_pins -hierarchical -regexp .*CLR.*] [get_pins -hierarchical -regexp .*PRE.*]] 10.0")

    soc.platform.toolchain.pre_synthesis_commands.append("set_property strategy Congestion_SpreadLogic_high [get_runs impl_1]")
#    soc.platform.toolchain.pre_synthesis_commands.append("set_property -name {{STEPS.OPT_DESIGN.ARGS.MORE OPTIONS}} -value {{-merge_equivalent_drivers -hier_fanout_limit 1000}} -objects [get_runs impl_1]")

    target_name = 'sodimm_ddr5_tester'
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

