#!/usr/bin/env python3

import math

from migen import *
from litex.soc.interconnect.csr import AutoCSR, CSR, CSRStorage, CSRStatus

from litex.build.xilinx.vivado import vivado_build_args, vivado_build_argdict
from litex.soc.integration.builder import Builder
from litex.soc.cores.clock import S7PLL, S7MMCM, S7IDELAYCTRL

from litex_boards.platforms import antmicro_ddr5_test_board
from litedram.phy import ddr5
from litedram.phy.ddr5.s7phy import Xilinx7SeriesAsyncFIFOWrap
from liteeth.phy import LiteEthS7PHYRGMII

from rowhammer_tester.targets import common

# AsyncFIFO DUT ------------------------------------------------------------------------------------

class AsyncFIFOWithoutALMOSTEMPTYDUT(Module, AutoCSR):
    def __init__(self, i_cd_name, o_cd_name):
        self.start_csr = CSRStorage()
        self.rst_csr = CSRStorage()

        w_data = Signal(36)
        we     = Signal()
        rst    = Signal()

        r_data = Signal(36)
        r_data.attr.add("keep")
        re     = Signal()
        rd     = Signal()

        i_cd = getattr(self.sync, i_cd_name)
        o_cd = getattr(self.sync, o_cd_name)

        o_cd += [
            rst.eq(self.rst_csr.storage),
            If(rd & ~re,
                rd.eq(0),
            ).Elif(~rd,
                rd.eq(1),
            )
        ]

        i_cd += [
            If(self.start_csr.storage,
                w_data.eq(w_data+1),
            )
        ]
        self.comb += If(self.start_csr.storage, we.eq(1))

        self.specials += Instance(
            "FIFO18E1",
            p_ALMOST_EMPTY_OFFSET     = 5,
            p_DATA_WIDTH              = 36,
            p_DO_REG                  = 1,
            p_EN_SYN                  = "FALSE",
            p_FIFO_MODE               = "FIFO18_36",
            p_FIRST_WORD_FALL_THROUGH = "FALSE",
            o_DO                      = r_data[:32],
            o_DOP                     = r_data[32:],
            o_EMPTY                   = re,
            i_RDCLK                   = ClockSignal(o_cd_name),
            i_RDEN                    = (~re & rd),
            i_RST                     = rst,
            i_WRCLK                   = ClockSignal(i_cd_name),
            i_WREN                    = we,
            i_DI                      = w_data[:32],
            i_DIP                     = w_data[32:],
        )


class AsyncFIFOWraperDUT(Module, AutoCSR):
    def __init__(self, i_cd_name, o_cd_name):
        self.start_csr = CSRStorage()
        self.rst_csr = CSRStorage()

        w_data = Signal(36)
        we     = Signal()
        rst    = Signal()

        r_data = Signal(18)
        r_data.attr.add("keep")
        r_cnt  = Signal(6)
        r_cnt.attr.add("keep")
        re     = Signal()
        re.attr.add("keep")
        rd     = Signal()

        i_cd = getattr(self.sync, i_cd_name)
        i_cd += [
            If(self.start_csr.storage,
                w_data.eq(w_data+1),
            ).Else(
                w_data.eq(0),
            )
        ]
        o_cd = getattr(self.sync, o_cd_name)
        o_cd += [
            If(self.start_csr.storage,
                r_cnt.eq(r_cnt+1),
            ).Else(
                r_cnt.eq(0),
            )
        ]

        self.comb += [
            If(self.start_csr.storage,
                we.eq(1)
            ),
            rst.eq(self.rst_csr.storage),
        ]

        fifo = Xilinx7SeriesAsyncFIFOWrap(i_cd_name, o_cd_name, 36, 18)
        self.submodules += fifo
        self.comb += [
            fifo._rst.eq(rst),
            fifo.we.eq(we),
            fifo.re.eq(re),
            re.eq(fifo.readable),
            fifo.din.eq(w_data),
            r_data.eq(fifo.dout),
        ]

# CRG ----------------------------------------------------------------------------------------------

class CRG(Module):
    def __init__(self, platform, sys_clk_freq, iodelay_clk_freq):
        self.clock_domains.cd_sys                = ClockDomain()
        self.clock_domains.cd_sys2x              = ClockDomain(reset_less=True)
        self.clock_domains.cd_idelay             = ClockDomain()

        # BUFMR to BUFR and BUFIO, "raw" clocks
        self.clock_domains.cd_sys4x_raw    = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x_90_raw = ClockDomain(reset_less=True)
        # BUFMR reset domains
        self.clock_domains.cd_sys2x_rst = ClockDomain()
        self.clock_domains.cd_sys2x_90_rst = ClockDomain()

        # # #
        input_clk_freq = 100e6
        input_clk = platform.request("clk100")

        self.submodules.mmcm = mmcm = S7MMCM(speedgrade=-3)
        mmcm.register_clkin(input_clk, input_clk_freq)

        mmcm.create_clkout(
            self.cd_sys4x_raw,
            4 * sys_clk_freq,
            buf=None,
            with_reset=False,
            platform=platform
        )
        mmcm.create_clkout(
            self.cd_sys4x_90_raw,
            4 * sys_clk_freq,
            phase=90,
            with_reset=False,
            buf=None,
            platform=platform
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

        mmcm.create_clkout(self.cd_sys,   sys_clk_freq)
        mmcm.create_clkout(self.cd_sys2x, sys_clk_freq * 2)

        self.submodules.pll_iodly = pll_iodly = S7PLL(speedgrade=-3)
        pll_iodly.register_clkin(input_clk, input_clk_freq)
        pll_iodly.create_clkout(self.cd_idelay, iodelay_clk_freq)

        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_idelay)

# SoC ----------------------------------------------------------------------------------------------

class SoC(common.RowHammerSoC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_platform(self):
        return antmicro_ddr5_test_board.Platform()

    def get_crg(self):
        return CRG(self.platform, self.sys_clk_freq,
            iodelay_clk_freq=float(self.args.iodelay_clk_freq))

    def get_ddr_pin_domains(self):
        return dict(
            ck_t=(("sys2x_io", "sys4x_io"), None),
            ck_c=(("sys2x_io", "sys4x_io"), None),
            ca=(("sys2x_io", "sys4x_io"), None),
            cs_n=(("sys2x_io", "sys4x_io"), None),
            reset_n=(("sys2x_io", "sys4x_io"), None),
            alert_n=(None, ("sys_io", "sys4x_io")),
            dq=(("sys2x_90_io", "sys4x_90_io"), ("sys_io", "sys4x_io")),
            dm_n=(("sys2x_90_io", "sys4x_90_io"), ("sys_io", "sys4x_io")),
            dqs_t=(("sys2x_io", "sys4x_io"), ("sys_io", "sys4x_io")),
            dqs_c=(("sys2x_io", "sys4x_io"), ("sys_io", "sys4x_io")),
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
            io_banks      = ["bank34"],
        )

        return ddr5.K7DDR5PHY(self.platform.request("ddr5"),
            crg                = PHYCRG,
            iodelay_clk_freq   = float(self.args.iodelay_clk_freq),
            sys_clk_freq       = self.sys_clk_freq,
            masked_write       = False,
            with_per_dq_idelay = True,
            with_sub_channels  = False,
            direct_control     = True,
            pin_domains        = self.get_ddr_pin_domains(),
            pin_banks          = self.platform.pin_bank_mapping()["ddr5"],
        )

    def get_sdram_ratio(self):
        return "1:4"

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
        description  = "LiteX SoC on DDR5 Test Board",
        sys_clk_freq = '200e6',
        module       = 'MT60B2G8HB48B'
    )
    g = parser.add_argument_group(title="DDR5 Test Board")
    parser.add(g, "--eth-reset-time", default="10e-3", help="Duration of Ethernet PHY reset")
    parser.add(g, "--iodelay-clk-freq", default="200e6", help="IODELAY clock frequency")
    vivado_build_args(g)
    args = parser.parse_args()

    soc_kwargs = common.get_soc_kwargs(args)
    soc = SoC(**soc_kwargs)
    soc.platform.add_platform_command("set_property CLOCK_BUFFER_TYPE BUFG [get_nets sys_rst]")
    # According to UG473 reset is synchronized internally, and must last 5 cycles
    soc.platform.add_platform_command("set_disable_timing -from WRCLK -to RST "
        "[get_cells -filter {{(REF_NAME == FIFO18E1 || REF_NAME == FIFO36E1) && EN_SYN == FALSE}}]")
    soc.platform.toolchain.pre_synthesis_commands.append("set_property strategy Congestion_SpreadLogic_high [get_runs impl_1]")
    soc.platform.toolchain.pre_synthesis_commands.append(
        "set_property -name ""{{STEPS.OPT_DESIGN.ARGS.MORE OPTIONS}} "
        "-value {{-merge_equivalent_drivers -hier_fanout_limit 1000}} -objects [get_runs impl_1]")

    target_name = 'ddr5_test_board'
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
