#!/usr/bin/env python3
import math

import ddr5_tester
import common

from migen import *

from litex.build.xilinx.vivado import vivado_build_args, vivado_build_argdict
from litex.soc.integration.builder import Builder
from litex.soc.cores.cpu.vexriscv_smp.core import VexRiscvSMP

from liteeth.phy import LiteEthS7PHYRGMII


# SoC ----------------------------------------------------------------------------------------------
class SoC(ddr5_tester.SoC):
    def __init__(self, **kwargs):
        print(kwargs)
        ddr5_tester.SoC.__init__(self, **kwargs)

    def add_host_bridge(self):
        if self.args.with_ethernet:
            self.submodules.ethphy = LiteEthS7PHYRGMII(
                clock_pads=self.platform.request("eth_clocks"),
                pads=self.platform.request("eth"),
                hw_reset_cycles=math.ceil(float(self.args.eth_reset_time) * self.sys_clk_freq),
                rx_delay=0.8e-9,
                iodelay_clk_freq=float(self.args.iodelay_clk_freq))

            self.add_ethernet(phy=self.ethphy)
        elif self.args.with_etherbone:
            ddr5_tester.SoC.add_host_bridge(self)

    def configure_ethernet(self, local_ip, remote_ip):
        local_ip = local_ip.split(".")
        remote_ip = remote_ip.split(".")

        self.add_constant("LOCALIP1", int(local_ip[0]))
        self.add_constant("LOCALIP2", int(local_ip[1]))
        self.add_constant("LOCALIP3", int(local_ip[2]))
        self.add_constant("LOCALIP4", int(local_ip[3]))

        self.add_constant("REMOTEIP1", int(remote_ip[0]))
        self.add_constant("REMOTEIP2", int(remote_ip[1]))
        self.add_constant("REMOTEIP3", int(remote_ip[2]))
        self.add_constant("REMOTEIP4", int(remote_ip[3]))

    def add_ddr5_tester_platform_commands(self):
        self.platform.add_platform_command("set_property CLOCK_BUFFER_TYPE BUFG [get_nets sys_rst]")
        self.platform.add_platform_command("set_disable_timing -from WRCLK -to RST "
                                           "[get_cells -filter {{(REF_NAME == FIFO18E1 || REF_NAME == FIFO36E1) && EN_SYN == FALSE}}]")
        self.platform.add_platform_command("set_max_delay -quiet -to [get_pins -hierarchical -regexp BUFR.*/CLR] 10.0")
        self.platform.add_platform_command("set_max_delay -quiet -from [get_clocks -of_objects [get_pins rst_domain/O]] "
                                           "-to [list [get_pins -hierarchical -regexp .*CLR.*] [get_pins -hierarchical -regexp .*PRE.*]] 10.0")
        self.platform.toolchain.pre_synthesis_commands.append(
            "set_property strategy Congestion_SpreadLogic_high [get_runs impl_1]")

# Build --------------------------------------------------------------------------------------------
def get_bare_ddr5_tester_kwargs(args):
    soc_kwargs = common.get_soc_kwargs(args)

    soc_kwargs.update(dict(
        cpu_type="vexriscv_smp",
        cpu_variant="linux",
        uart_name="serial",
        with_ethernet=args.with_ethernet,
        with_etherbone=args.with_etherbone
    ))

    return soc_kwargs


def ddr5_tester_args(parser):
    parser.add_argument("--local-ip-address",    default="10.0.2.10",      help="Local IP address")
    parser.add_argument("--remote-ip-address",   default="10.0.2.20",      help="IP address of the TFTP server.")
    parser.add_argument("--eth-reset-time",      default="10e-3",          help="Duration of Ethernet PHY reset")
    parser.add_argument("--iodelay-clk-freq",    default="400e6",          help="IODELAY clock frequency")

    # Ethernet / Etherbone
    eth = parser.add_mutually_exclusive_group()
    parser.add(eth, "--with-etherbone", action='store_true', help="Set up etherbone.")
    parser.add(eth, "--with-ethernet",  action='store_true', help="Set up ethernet.")

    vivado_build_args(parser)


def main():
    parser = common.ArgumentParser(
        description="Linux capable SoC on DDR5 Tester Board",
        sys_clk_freq='200e6',
        module='M329R8GA0BB0'
    )
    ddr5_tester_args(parser)
    VexRiscvSMP.args_fill(parser)

    # Overide defaults; don't generate memory bist or payload executor by default
    parser.set_defaults(no_memory_bist=True, no_payload_executor=True)

    args = parser.parse_args()

    VexRiscvSMP.args_read(args)

    soc_kwargs = get_bare_ddr5_tester_kwargs(args)
    soc = SoC(**soc_kwargs)

    if soc_kwargs['with_ethernet']:
        soc.configure_ethernet(local_ip=args.local_ip_address, remote_ip=args.remote_ip_address)

    soc.get_ddr_pin_domains()
    soc.add_ddr5_tester_platform_commands()

    target_name = 'ddr5_tester_linux'
    builder_kwargs = common.get_builder_kwargs(args, target_name=target_name)
    builder = Builder(soc, **builder_kwargs)

    common.configure_generated_files(builder, args, target_name)

    build_kwargs = vivado_build_argdict(args)
    build_kwargs.update({"vivado_place_directive":               "AltSpreadLogic_high",
                         "vivado_post_place_phys_opt_directive": "AggressiveExplore",
                         "vivado_route_directive":               "AggressiveExplore",
                         "vivado_post_route_phys_opt_directive": "AggressiveExplore"})
    if args.build:
        builder.build(**build_kwargs, run=args.build)


if __name__ == "__main__":
    main()
