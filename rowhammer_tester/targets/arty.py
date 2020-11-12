#!/usr/bin/env python3

#
# This file is based on litex/boards/arty.py
#

import os
import argparse

from migen import *

from litex.build.generic_platform import *
from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig

from litex.boards.platforms import arty
from litex.build.xilinx.vivado import vivado_build_args, vivado_build_argdict

from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import *
#from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *
from litex.soc.cores.led import LedChaser
from litex.soc import doc
from litex.soc.integration.doc import AutoDoc, ModuleDoc

from litedram.modules import MT41K128M16
from litedram.phy import s7ddrphy
from litedram.phy.model import SDRAMPHYModel
from litedram import modules as litedram_modules
#from litedram import phy as litedram_phys
from litedram.init import get_sdram_phy_py_header
from litedram.core.controller import ControllerSettings
from litedram.frontend.dma import LiteDRAMDMAReader, LiteDRAMDMAWriter

from liteeth.phy.mii import LiteEthPHYMII

from liteeth.phy.model import LiteEthPHYModel
from liteeth.core import LiteEthUDPIPCore
from liteeth.frontend.etherbone import LiteEthEtherbone

from litex.soc.cores import uart

from rowhammer_tester.gateware.writer import Writer
from rowhammer_tester.gateware.reader import Reader
from rowhammer_tester.gateware.rowhammer import RowHammerDMA
from rowhammer_tester.gateware.payload_executor import PayloadExecutor

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq, args):
        if not args.sim:
            self.submodules.pll = pll = S7PLL(speedgrade=-1)
            self.comb += pll.reset.eq(~platform.request("cpu_reset"))
            pll.register_clkin(platform.request("clk100"), 100e6)


        if not args.sim:
            self.clock_domains.cd_sys       = ClockDomain()
            pll.create_clkout(self.cd_sys,       sys_clk_freq)
        else:
            # copy-paste from litex/build/io.py
            # Power on Reset (vendor agnostic)
            clk = platform.request("sys_clk")
            rst = 0

            # create sys clock domain _AFTER_ platform.request("sys_clk")
            self.clock_domains.cd_sys= ClockDomain()
            self.clock_domains.cd_por = ClockDomain(reset_less=True)

            int_rst = Signal(reset=1)
            self.sync.por += int_rst.eq(rst)
            self.comb += [
                self.cd_sys.clk.eq(clk),
                self.cd_por.clk.eq(clk),
                self.cd_sys.rst.eq(int_rst)
            ]

        # Etherbone --------------------------------------------------------------------------------
        self.clock_domains.cd_eth = ClockDomain()
        pll.create_clkout(self.cd_eth,       25e6)
        self.comb += platform.request("eth_ref_clk").eq(self.cd_eth.clk)

        # DDRPHY -----------------------------------------------------------------------------------
        self.clock_domains.cd_sys4x     = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x_dqs = ClockDomain(reset_less=True)

        if not args.sim:
            pll.create_clkout(self.cd_sys4x,     4*sys_clk_freq)
            pll.create_clkout(self.cd_sys4x_dqs, 4*sys_clk_freq, phase=90)

            self.clock_domains.cd_clk200    = ClockDomain()
            pll.create_clkout(self.cd_clk200,    200e6)
            self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_clk200)

# IOs -- simulation --------------------------------------------------------------------------------

_io = [
    ("sys_clk", 0, Pins(1)),
    #("sys_rst", 0, Pins(1)),

    ("eth_clocks", 0,
        Subsignal("tx", Pins(1)),
        Subsignal("rx", Pins(1)),
    ),
    ("eth", 0,
        Subsignal("source_valid", Pins(1)),
        Subsignal("source_ready", Pins(1)),
        Subsignal("source_data",  Pins(8)),

        Subsignal("sink_valid",   Pins(1)),
        Subsignal("sink_ready",   Pins(1)),
        Subsignal("sink_data",    Pins(8)),
    ),

    ("user_led", 0, Pins(1)),
    ("user_led", 1, Pins(1)),
    ("user_led", 2, Pins(1)),
    ("user_led", 3, Pins(1)),
]

class Platform(SimPlatform):
    def __init__(self):
        SimPlatform.__init__(self, "SIM", _io)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def __init__(self, toolchain="vivado", sys_clk_freq=int(100e6), args=None,
                 ip_address="192.168.100.50", mac_address=0x10e2d5000001, udp_port=1234, **kwargs):
        if not args.sim:
            platform = arty.Platform(toolchain=toolchain)
        else:
            platform = Platform()

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, sys_clk_freq,
            ident          = "LiteX SoC on Arty A7",
            ident_version  = True,
            **kwargs)

        # CRG --------------------------------------------------------------------------------------
        if not args.sim:
            self.submodules.crg = _CRG(platform, sys_clk_freq, args)
        else:
            self.submodules.crg = CRG(platform.request("sys_clk"))

        # DDR3 SDRAM -------------------------------------------------------------------------------
        if not args.sim:
            self.submodules.ddrphy = s7ddrphy.A7DDRPHY(platform.request("ddram"),
                memtype        = "DDR3",
                nphases        = 4,
                sys_clk_freq   = sys_clk_freq)
        else:
            from litedram.gen import get_dram_ios
            core_config = dict()
            core_config["sdram_module_nb"] = 2             # Number of byte groups
            core_config["sdram_rank_nb"]   = 1             # Number of ranks
            core_config['sdram_module']    = getattr(litedram_modules, 'MT41K128M16')
            core_config["memtype"]         = "DDR3"      # DRAM type

            platform.add_extension(get_dram_ios(core_config))
            sdram_module = core_config["sdram_module"](sys_clk_freq, rate={
                "DDR2": "1:2",
                "DDR3": "1:4",
                "DDR4": "1:4"}[core_config["memtype"]])

            from litex.tools.litex_sim import get_sdram_phy_settings
            sdram_clk_freq   = int(100e6) # FIXME: use 100MHz timings
            phy_settings   = get_sdram_phy_settings(
                memtype    = sdram_module.memtype,
                data_width = core_config["sdram_module_nb"]*8,
                clk_freq   = sdram_clk_freq)

            self.submodules.ddrphy = SDRAMPHYModel(
                module    = sdram_module,
                settings  = phy_settings,
                clk_freq  = sdram_clk_freq,
                verbosity = 3,
            )

        class ControllerDynamicSettings(Module, AutoCSR, AutoDoc):
            """Allows to change LiteDRAMController behaviour at runtime"""
            def __init__(self):
                self.refresh = CSRStorage(reset=1, description="Enable/disable Refresh commands sending")

        self.submodules.controller_settings = ControllerDynamicSettings()
        self.add_csr("controller_settings")
        controller_settings = ControllerSettings()
        controller_settings.with_auto_precharge = True
        controller_settings.with_refresh = self.controller_settings.refresh.storage

        self.add_csr("ddrphy")
        self.add_sdram("sdram",
            phy                     = self.ddrphy,
            module                  = MT41K128M16(sys_clk_freq, "1:4"),
            origin                  = self.mem_map["main_ram"],
            size                    = kwargs.get("max_sdram_size", 0x40000000),
            l2_cache_size           = 0,
            l2_cache_min_data_width = 0, #128
            l2_cache_reverse        = True,
            controller_settings     = controller_settings
        )

        # Ethernet / Etherbone ---------------------------------------------------------------------
        if not args.sim:
            # Ethernet PHY (arty)
            self.submodules.ethphy = LiteEthPHYMII(
                clock_pads = self.platform.request("eth_clocks"),
                pads       = self.platform.request("eth"))
            self.add_csr("ethphy")

            self.add_etherbone(phy=self.ethphy,
                               ip_address=ip_address, mac_address=mac_address, udp_port=udp_port)
        else:
            # Ethernet PHY (simulation)
            self.submodules.ethphy = LiteEthPHYModel(self.platform.request("eth", 0)) # FIXME
            self.add_csr("ethphy")

            # Ethernet Core
            ethcore = LiteEthUDPIPCore(self.ethphy,
                ip_address  = ip_address,
                mac_address = mac_address,
                clk_freq    = sys_clk_freq)
            self.submodules.ethcore = ethcore
            # Etherbone
            self.submodules.etherbone = LiteEthEtherbone(self.ethcore.udp, udp_port, mode="master")
            self.add_wb_master(self.etherbone.wishbone.bus)

        # Leds -------------------------------------------------------------------------------------
        self.submodules.leds = LedChaser(
            pads         = platform.request_all("user_led"),
            sys_clk_freq = sys_clk_freq)
        self.add_csr("leds")

        if args.sim:
            self.comb += platform.trace.eq(1)

        # Rowhammer --------------------------------------------------------------------------------
        self.submodules.rowhammer_dma = LiteDRAMDMAReader(self.sdram.crossbar.get_port())
        self.submodules.rowhammer = RowHammerDMA(self.rowhammer_dma)
        self.add_csr("rowhammer")

        def add_xram(self, name, origin, mem, mode='rw'):
            from litex.soc.interconnect import wishbone
            from litex.soc.integration.soc import SoCRegion
            ram     = wishbone.SRAM(mem, bus=wishbone.Interface(data_width=mem.width),
                                    read_only='w' not in mode)
            ram_bus = wishbone.Interface(data_width=self.bus.data_width)
            self.submodules += wishbone.Converter(ram_bus, ram.bus)
            region = SoCRegion(origin=origin, size=mem.width//8 * mem.depth, mode=mode)
            self.bus.add_slave(name, ram_bus, region)
            self.check_if_exists(name)
            self.logger.info("RAM {} {} {}.".format(
                colorer(name),
                colorer("added", color="green"),
                self.bus.regions[name]))
            setattr(self.submodules, name, ram)

        # Bist -------------------------------------------------------------------------------------
        if not args.no_memory_bist:
            # ------------------------------ writer ------------------------------------
            dram_wr_port = self.sdram.crossbar.get_port()
            self.submodules.writer = Writer(dram_wr_port)
            self.add_csr('writer')

            # TODO: Rename as 'pattern_wr_w?'
            add_xram(self, name='pattern_w0',  mem=self.writer.memory_w0, origin=0x20000000)
            add_xram(self, name='pattern_w1',  mem=self.writer.memory_w1, origin=0x21000000)
            add_xram(self, name='pattern_w2',  mem=self.writer.memory_w2, origin=0x22000000)
            add_xram(self, name='pattern_w3',  mem=self.writer.memory_w3, origin=0x23000000)
            add_xram(self, name='pattern_adr', mem=self.writer.memory_adr, origin=0x24000000)

            # ----------------------------- reader -------------------------------------
            dram_rd_port = self.sdram.crossbar.get_port()
            self.submodules.reader = Reader(dram_rd_port)
            self.add_csr('reader')

            add_xram(self, name='pattern_rd_w0',  mem=self.reader.memory_w0,  origin=0x30000000)
            add_xram(self, name='pattern_rd_w1',  mem=self.reader.memory_w1,  origin=0x31000000)
            add_xram(self, name='pattern_rd_w2',  mem=self.reader.memory_w2,  origin=0x32000000)
            add_xram(self, name='pattern_rd_w3',  mem=self.reader.memory_w3,  origin=0x33000000)
            add_xram(self, name='pattern_rd_adr', mem=self.reader.memory_adr, origin=0x34000000)


        # Payload executor -------------------------------------------------------------------------
        if not args.no_payload_executor:
            # TODO: disconnect bus during payload execution

            phy_settings = self.sdram.controller.settings.phy
            scratchpad_width = phy_settings.dfi_databits * phy_settings.nphases
            scratchpad_size  = 2**10

            payload_mem    = Memory(32, 2**10)
            scratchpad_mem = Memory(scratchpad_width, scratchpad_size // (scratchpad_width//8))
            self.specials += payload_mem, scratchpad_mem

            add_xram(self, name='payload', mem=payload_mem, origin=0x35000000)
            add_xram(self, name='scratchpad', mem=scratchpad_mem, origin=0x36000000, mode='r')

            self.submodules.payload_executor = PayloadExecutor(
                mem_payload    = payload_mem,
                mem_scratchpad = scratchpad_mem,
                dfi            = self.sdram.dfii.ext_dfi,
                dfi_sel        = self.sdram.dfii.ext_dfi_sel,
                nranks         = self.sdram.controller.settings.phy.nranks,
                bankbits       = self.sdram.controller.settings.geom.bankbits,
                rowbits        = self.sdram.controller.settings.geom.rowbits,
                colbits        = self.sdram.controller.settings.geom.colbits,
                rdphase        = self.sdram.controller.settings.phy.rdphase,
            )
            self.payload_executor.add_csrs()
            self.add_csr('payload_executor')

        # # Analyzer ---------------------------------------------------------------------------------
        # analyzer_signals = [
        #     self.sdram.dfii.ext_dfi_sel,
        #     *[p.rddata for p in self.ddrphy.dfi.phases],
        #     *[p.rddata_valid for p in self.ddrphy.dfi.phases],
        #     *[p.rddata_en for p in self.ddrphy.dfi.phases],
        # ]
        # from litescope import LiteScopeAnalyzer
        # self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals,
        #    depth        = 512,
        #    clock_domain = "sys",
        #    csr_csv      = "analyzer.csv")
        # self.add_csr("analyzer")

    def generate_sdram_phy_py_header(self, output_file):
        f = open(output_file, "w")
        f.write(get_sdram_phy_py_header(
            self.sdram.controller.settings.phy,
            self.sdram.controller.settings.timing))
        f.close()

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on Arty A7")
    parser.add_argument("--build", action="store_true", help="Build bitstream")
    parser.add_argument("--load",  action="store_true", help="Load bitstream")
    parser.add_argument("--docs",  action="store_true", help="Generate documentation")
    parser.add_argument("--toolchain", default="vivado", help="Gateware toolchain to use, vivado (default) or symbiflow")
    parser.add_argument("--sim", action="store_true", help="Build and run in simulation mode")
    parser.add_argument("--sys-clk-freq", default="100e6", help="TODO")
    parser.add_argument("--no-memory-bist", action="store_true", help="Enable memory BIST module")
    parser.add_argument("--ip-address", default="192.168.100.50", help="Use given IP address")
    parser.add_argument("--mac-address", default="0x10e2d5000001", help="Use given MAC address")
    parser.add_argument("--udp-port", default="1234", help="Use given UDP port")
    parser.add_argument("--no-payload-executor", action="store_true", help="Disable Payload Executor module")

    builder_args(parser)
    soc_core_args(parser)
    vivado_build_args(parser)
    args = parser.parse_args()

    # Force defaults to no CPU
    soc_kwargs = soc_core_argdict(args)
    soc_kwargs.update(dict(
        cpu_type                 = None,
        no_timer                 = True,
        no_ctrl                  = True,
        no_uart                  = True,
        uart_name                = "stub",
        integrated_rom_size      = 0,
        integrated_sram_size     = 0,
        integrated_main_ram_size = 0,
    ))

    sys_clk_freq = int(float(args.sys_clk_freq))
    soc = BaseSoC(
        toolchain    = args.toolchain,
        args         = args,
        sys_clk_freq = sys_clk_freq,
        ip_address   = args.ip_address,
        mac_address  = int(args.mac_address, 0),
        udp_port     = int(args.udp_port, 0),
        **soc_kwargs)

    # FIXME: try to generate to build/ and make the scripts use that version?
    script_dir = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
    soc.generate_sdram_phy_py_header(os.path.join(script_dir, "..", "scripts", "sdram_init.py"))

    builder_kwargs = builder_argdict(args)
    builder_kwargs["csr_csv"] = os.path.join(script_dir, "..", "scripts", "csr.csv")
    builder = Builder(soc, **builder_kwargs)
    build_kwargs = vivado_build_argdict(args)

    if not args.sim:
        builder.build(**build_kwargs, run=args.build)

    else:
        sim_config = SimConfig()
        sim_config.add_clocker("sys_clk", freq_hz=sys_clk_freq)
        sim_config.add_module("ethernet", "eth", args={"interface": "arty", "ip": args.ip_address})

        del build_kwargs['synth_mode']
        builder.build(**build_kwargs, run=args.build, sim_config=sim_config, trace=True, trace_fst=False)

    if args.docs:
        doc.generate_docs(soc,
            base_dir     = "build/documentation",
            project_name = "LiteX Row Hammer Tester",
            author       = "Antmicro"
        )

    if args.load:
       prog = soc.platform.create_programmer()
       prog.load_bitstream(os.path.join(builder.gateware_dir, soc.build_name + ".bit"))

if __name__ == "__main__":
    main()
