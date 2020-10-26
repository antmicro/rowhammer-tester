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

from litedram.modules import MT41K128M16
from litedram.phy import s7ddrphy
from litedram.phy.model import SDRAMPHYModel
from litedram import modules as litedram_modules
#from litedram import phy as litedram_phys
from litedram.init import get_sdram_phy_py_header
from litedram.core.controller import ControllerSettings

from liteeth.phy.mii import LiteEthPHYMII

from liteeth.phy.model import LiteEthPHYModel
from liteeth.core import LiteEthUDPIPCore
from liteeth.frontend.etherbone import LiteEthEtherbone

from litex.soc.cores import uart

from rowhammer import RowHammerDMA

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
    def __init__(self, toolchain="vivado", sys_clk_freq=int(100e6), args=None, **kwargs):
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

        controller_settings = ControllerSettings()
        controller_settings.with_auto_precharge = False

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
                               ip_address="192.168.100.50",
                               mac_address=0x10e2d5000001)
        else:
            # Ethernet PHY (simulation)
            self.submodules.ethphy = LiteEthPHYModel(self.platform.request("eth", 0)) # FIXME
            self.add_csr("ethphy")

            # Ethernet Core
            ethcore = LiteEthUDPIPCore(self.ethphy,
                ip_address="192.168.100.50",
                mac_address=0x10e2d5000001,
                clk_freq    = sys_clk_freq)
            self.submodules.ethcore = ethcore
            # Etherbone
            self.submodules.etherbone = LiteEthEtherbone(self.ethcore.udp, 1234, mode="master")
            self.add_wb_master(self.etherbone.wishbone.bus)

        # Leds -------------------------------------------------------------------------------------
        self.submodules.leds = LedChaser(
            pads         = platform.request_all("user_led"),
            sys_clk_freq = sys_clk_freq)
        self.add_csr("leds")

        # Analyzer ---------------------------------------------------------------------------------
        # analyzer_signals = [
        #    self.bus.masters['master0'].stb,
        #    self.bus.masters['master0'].cyc,
        #    self.bus.masters['master0'].adr,
        #    self.bus.masters['master0'].we,
        #    self.bus.masters['master0'].ack,
        #    self.bus.masters['master0'].sel,
        #    self.bus.masters['master0'].dat_w,
        #    self.bus.masters['master0'].dat_r,
        # ]
        # from litescope import LiteScopeAnalyzer
        # self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals,
        #    depth        = 512,
        #    clock_domain = "sys",
        #    csr_csv      = "analyzer.csv")
        # self.add_csr("analyzer")

        if args.sim:
            self.comb += platform.trace.eq(1)

        # Bulk -------------------------------------------------------------------------------------
        from litedram.frontend.dma import LiteDRAMDMAReader, LiteDRAMDMAWriter

        self.submodules.rowhammer_dma = LiteDRAMDMAReader(self.sdram.crossbar.get_port())
        self.submodules.rowhammer = RowHammerDMA(self.rowhammer_dma)
        self.add_csr("rowhammer")

        class BulkWrite(Module, AutoCSR):
            def __init__(self, dma, bankbits, colbits):
                self.enabled  = CSRStorage()
                self.address  = CSRStorage(size=(32*1))
                self.dataword = CSRStorage(size=(32*4))
                self.count    = CSRStorage(size=(32*1))
                self.reset    = CSRStorage()
                self.done     = CSRStatus()

                cnt = Signal(32*1)
                self.sync += If(self.enabled.storage, If(cnt < self.count.storage, If(dma.sink.ready, cnt.eq(cnt + 1))))
                self.sync += If(self.reset.storage, cnt.eq(0))
                self.sync += self.done.status.eq(self.count.storage == cnt)

                self.comb += [
                    dma.sink.address.eq(self.address.storage + cnt),
                    dma.sink.data.eq(self.dataword.storage),
                    dma.sink.valid.eq(self.enabled.storage),
                ]

        port = self.sdram.crossbar.get_port()
        self.submodules.bulk_wr_dma   = LiteDRAMDMAWriter(port)
        self.submodules.bulk_wr       = BulkWrite(self.bulk_wr_dma,
                                                  bankbits=self.sdram.controller.settings.geom.bankbits,
                                                  colbits=self.sdram.controller.settings.geom.colbits)
        self.add_csr("bulk_wr")

        # Bist -------------------------------------------------------------------------------------
        if not args.no_memory_bist:
            from litedram.frontend.bist import LiteDRAMBISTGenerator, LiteDRAMBISTChecker

            def add_xram(self, name, origin, mem):
                from litex.soc.interconnect import wishbone
                from litex.soc.integration.soc import SoCRegion
                ram_bus = wishbone.Interface(data_width=self.bus.data_width)
                ram     = wishbone.SRAM(mem, bus=ram_bus)
                self.bus.add_slave(name, ram.bus, SoCRegion(origin=origin, size=mem.width * mem.depth, mode='rw'))
                self.check_if_exists(name)
                self.logger.info("RAM {} {} {}.".format(
                    colorer(name),
                    colorer("added", color="green"),
                    self.bus.regions[name]))
                setattr(self.submodules, name, ram)
                return

            # ------------------------------ writer ------------------------------------
            memory_w0  = Memory(32, 1024)
            memory_w1  = Memory(32, 1024)
            memory_w2  = Memory(32, 1024)
            memory_w3  = Memory(32, 1024)
            memory_adr = Memory(32, 1024)

            add_xram(self, name='pattern_w0',  mem=memory_w0, origin=0x20000000)
            add_xram(self, name='pattern_w1',  mem=memory_w1, origin=0x21000000)
            add_xram(self, name='pattern_w2',  mem=memory_w2, origin=0x22000000)
            add_xram(self, name='pattern_w3',  mem=memory_w3, origin=0x23000000)
            add_xram(self, name='pattern_adr', mem=memory_adr, origin=0x24000000)

            class Writer(Module, AutoCSR):
                def __init__(self, dram_port, w0_port, w1_port, w2_port, w3_port, adr_port):
                    self.reset        = CSRStorage()
                    self.start        = CSRStorage()
                    self.done         = CSRStatus()

                    self.count        = CSRStorage(size=(32*1))

                    self.mem_base     = CSRStorage(size=32)
                    self.mem_mask     = CSRStorage(size=32)
                    self.data_mask    = CSRStorage(size=32) # patterns

                    dma = LiteDRAMDMAWriter(dram_port, fifo_depth=1)
                    self.submodules += dma

                    cmd_counter = Signal(32)

                    self.comb += [
                        w0_port.adr.eq(cmd_counter & self.data_mask.storage),
                        w1_port.adr.eq(cmd_counter & self.data_mask.storage),
                        w2_port.adr.eq(cmd_counter & self.data_mask.storage),
                        w3_port.adr.eq(cmd_counter & self.data_mask.storage),
                        adr_port.adr.eq(cmd_counter & self.data_mask.storage),
                    ]

                    self.comb += [
                        dma.sink.address.eq(self.mem_base.storage + adr_port.dat_r + (cmd_counter & self.mem_mask.storage)),
                        dma.sink.data.eq(Cat(w0_port.dat_r, w1_port.dat_r, w2_port.dat_r, w3_port.dat_r)),
                    ]

                    fsm = FSM(reset_state="IDLE")
                    self.submodules += fsm
                    fsm.act("IDLE",
                        If(self.start.storage,
                            NextValue(cmd_counter, 0),
                            NextState("WAIT"),
                        )
                    )
                    fsm.act("WAIT",
                        If(cmd_counter >= self.count.storage,
                            NextState("DONE")
                        ).Else(
                            NextState("RUN")
                        )
                    )
                    fsm.act("RUN",
                        dma.sink.valid.eq(1),
                        If(dma.sink.ready,
                            NextValue(cmd_counter, cmd_counter + 1),
                            NextState("WAIT")
                        )
                    )
                    fsm.act("DONE",
                        self.done.status.eq(1),
                        If(self.reset.storage,
                            NextState("IDLE"))
                    )


            dram_port = self.sdram.crossbar.get_port()
            w0_port   = memory_w0.get_port()
            w1_port   = memory_w1.get_port()
            w2_port   = memory_w2.get_port()
            w3_port   = memory_w3.get_port()
            adr_port  = memory_adr.get_port()
            self.specials += w0_port, w1_port, w2_port, w3_port, adr_port
            self.submodules.writer = Writer(dram_port,
                                            w0_port, w1_port, w2_port, w3_port, adr_port)
            self.add_csr('writer')

            # ----------------------------- reader -------------------------------------
            memory_rd_w0  = Memory(32, 1024)
            memory_rd_w1  = Memory(32, 1024)
            memory_rd_w2  = Memory(32, 1024)
            memory_rd_w3  = Memory(32, 1024)
            memory_rd_adr = Memory(32, 1024)

            add_xram(self, name='pattern_rd_w0',  mem=memory_rd_w0,  origin=0x30000000)
            add_xram(self, name='pattern_rd_w1',  mem=memory_rd_w1,  origin=0x31000000)
            add_xram(self, name='pattern_rd_w2',  mem=memory_rd_w2,  origin=0x32000000)
            add_xram(self, name='pattern_rd_w3',  mem=memory_rd_w3,  origin=0x33000000)
            add_xram(self, name='pattern_rd_adr', mem=memory_rd_adr, origin=0x34000000)

            class Reader(Module, AutoCSR):
                def __init__(self, dram_port, w0_port, w1_port, w2_port, w3_port, adr_port):
                    self.reset        = CSRStorage()
                    self.start        = CSRStorage()
                    self.done         = CSRStatus()

                    self.count        = CSRStorage(size=32)
                    self.pointer      = CSRStatus(size=32)

                    self.mem_base     = CSRStorage(size=32)
                    self.mem_mask     = CSRStorage(size=32)
                    self.data_mask    = CSRStorage(size=32) # patterns

                    dma = LiteDRAMDMAReader(dram_port, fifo_depth=1, fifo_buffered=False)
                    self.submodules += dma

                    cmd_counter = Signal(32)

                    self.comb += [
                        w0_port.adr.eq(cmd_counter & self.data_mask.storage),
                        w1_port.adr.eq(cmd_counter & self.data_mask.storage),
                        w2_port.adr.eq(cmd_counter & self.data_mask.storage),
                        w3_port.adr.eq(cmd_counter & self.data_mask.storage),
                        adr_port.adr.eq(cmd_counter & self.data_mask.storage),
                    ]

                    data_pattern = Signal(32 * 4)
                    self.comb += [
                        dma.sink.address.eq(self.mem_base.storage + adr_port.dat_r + (cmd_counter & self.mem_mask.storage)),
                        data_pattern.eq(Cat(w0_port.dat_r, w1_port.dat_r, w2_port.dat_r, w3_port.dat_r)),
                    ]

                    fsm = FSM(reset_state="IDLE")
                    self.submodules += fsm
                    fsm.act("IDLE",
                        If(self.start.storage,
                            NextValue(cmd_counter, 0),
                            NextValue(self.pointer.status, 0xdeadbeef),
                            NextState("WAIT"),
                        )
                    )
                    fsm.act("WAIT",
                        If(cmd_counter >= self.count.storage,
                            NextState("DONE")
                        ).Else(
                            NextState("WR_ADR")
                        )
                    )
                    fsm.act("WR_ADR",
                        dma.sink.valid.eq(1),
                        If(dma.sink.ready,
                            NextState("RD_DATA")
                        )
                    )
                    fsm.act("RD_DATA",
                        dma.source.ready.eq(1),
                        If(dma.source.valid,
                            NextValue(cmd_counter, cmd_counter + 1),
                            If(dma.source.data != data_pattern,
                                NextValue(self.pointer.status, cmd_counter)
                            ),
                            NextState("WAIT")
                        )
                    )
                    fsm.act("DONE",
                        self.done.status.eq(1),
                        If(self.reset.storage,
                            NextState("IDLE"))
                    )


            dram_rd_port = self.sdram.crossbar.get_port()
            w0_port   = memory_rd_w0.get_port()
            w1_port   = memory_rd_w1.get_port()
            w2_port   = memory_rd_w2.get_port()
            w3_port   = memory_rd_w3.get_port()
            adr_port  = memory_rd_adr.get_port()
            self.specials += w0_port, w1_port, w2_port, w3_port, adr_port
            self.submodules.reader = Reader(dram_rd_port,
                                            w0_port, w1_port, w2_port, w3_port, adr_port)
            self.add_csr('reader')


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
    soc = BaseSoC(args.toolchain, args=args, sys_clk_freq=sys_clk_freq, **soc_kwargs)

    # FIXME: try to generate to build/ and make the scripts use that version?
    script_dir = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
    soc.generate_sdram_phy_py_header(os.path.join(script_dir, "..", "scripts", "sdram_init.py"))

    builder_kwargs = builder_argdict(args)
    builder_kwargs["csr_csv"] = os.path.join(script_dir, "..", "csr.csv")
    builder = Builder(soc, **builder_kwargs)
    build_kwargs = vivado_build_argdict(args)

    if not args.sim:
        builder.build(**build_kwargs, run=args.build)

    else:
        sim_config = SimConfig()
        sim_config.add_clocker("sys_clk", freq_hz=sys_clk_freq)
        sim_config.add_module("ethernet", "eth", args={"interface": "arty", "ip": "192.168.100.1"})

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
