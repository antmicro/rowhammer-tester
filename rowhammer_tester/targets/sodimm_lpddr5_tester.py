#!/usr/bin/env python3

import os
import math

from migen import *

from litex.build.xilinx.vivado import vivado_build_args, vivado_build_argdict
from litex.soc.integration.builder import Builder
from litex.soc.cores.bitbang import I2CMaster
from litex.soc.cores.clock import S7PLL, S7IDELAYCTRL
from litex.soc.cores.gpio import GPIOIn, GPIOOut

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
    if (!(board_state&0x2)) {
        printf("Incorrect module detected! Power-off and replace with LPDDR5 testbed\\n");
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
            unsigned char command[2] = {0x44, 0x00};
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
        return CRG(self.platform, self.sys_clk_freq,
            iodelay_clk_freq=float(self.args.iodelay_clk_freq))

    def get_ddrphy(self):
        return lpddr5.K7LPDDR5PHY(self.platform.request("lpddr5"),
            iodelay_clk_freq  = float(self.args.iodelay_clk_freq),
            ck_freq           = self.sys_clk_freq,
            wck_ck_ratio      = 4)

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
    g = parser.add_argument_group(title="SO-DDIM LPDDR5 Tester Board")
    parser.add(g, "--eth-reset-time", default="10e-3", help="Duration of Ethernet PHY reset")
    parser.add(g, "--iodelay-clk-freq", default="200e6", help="IODELAY clock frequency")
    vivado_build_args(g)
    args = parser.parse_args()

    soc_kwargs = common.get_soc_kwargs(args)
    soc_kwargs['with_sub_channels'] = True
    soc = SoC(**soc_kwargs)

    target_name = 'sodimm_lpddr5_tester'
    builder_kwargs = common.get_builder_kwargs(args, target_name=target_name)
    builder = Builder(soc, **builder_kwargs)
    build_kwargs = vivado_build_argdict(args) if not args.sim else {}

    common.run(args, builder, build_kwargs, target_name=target_name)


if __name__ == "__main__":
    main()

