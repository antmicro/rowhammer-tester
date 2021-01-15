import os
import csv
import json
import argparse

from migen import *

from litex.soc import doc
from litex.soc.cores.led import LedChaser
from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import AutoCSR, CSRStorage
from litex.soc.integration.doc import AutoDoc, ModuleDoc
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.soc_core import soc_core_argdict, soc_core_args, SoCCore, colorer
from litex.soc.integration.builder import builder_argdict, builder_args
from litex.build.generic_platform import *
from litex.build.sim.config import SimConfig
from litex.build.sim import SimPlatform as _SimPlatform
from litex.tools.litex_sim import get_sdram_phy_settings

from litedram.gen import get_dram_ios, LiteDRAMCoreControl
from litedram.core.controller import ControllerSettings
from litedram.frontend.dma import LiteDRAMDMAReader
from litedram.init import get_sdram_phy_py_header
from litedram.phy.model import SDRAMPHYModel
from litedram.common import PhySettings, GeomSettings, TimingSettings
import litedram.modules as litedram_modules

from liteeth.phy.model import LiteEthPHYModel
from liteeth.core import LiteEthUDPIPCore
from liteeth.frontend.etherbone import LiteEthEtherbone

from rowhammer_tester.gateware.bist import Reader, Writer, PatternMemory
from rowhammer_tester.gateware.rowhammer import RowHammerDMA
from rowhammer_tester.gateware.payload_executor import PayloadExecutor

# SoC ----------------------------------------------------------------------------------------------

sim_io = [
    ("sys_clk", 0, Pins(1)),

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

class SimPlatform(_SimPlatform):
    def __init__(self):
        super().__init__('SIM', sim_io)


class RowHammerSoC(SoCCore):
    # Implementations for hardware backend ---------------------------------------------------------

    def get_platform(self):
        raise NotImplementedError()

    def get_crg(self):
        raise NotImplementedError()

    def get_ddrphy(self):
        raise NotImplementedError()

    def get_sdram_module(self):
        raise NotImplementedError()

    def add_host_bridge(self):
        raise NotImplementedError()

    # Common SoC configuration ---------------------------------------------------------------------

    def __init__(self, *, args, sys_clk_freq, sdram_module_cls,
            ip_address="192.168.100.50", mac_address=0x10e2d5000001, udp_port=1234, **kwargs):
        self.args = args
        self.sys_clk_freq = sys_clk_freq
        self.sdram_module_cls = sdram_module_cls
        self.ip_address = ip_address
        self.mac_address = mac_address
        self.udp_port = udp_port

        # Platform ---------------------------------------------------------------------------------
        if not args.sim:
            self.platform = self.get_platform()
        else:
            self.platform = SimPlatform()

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, self.platform, sys_clk_freq,
            ident          = "LiteX Row Hammer Tester SoC on {}".format(self.platform.device),
            ident_version  = True,
            **kwargs)

        # CRG --------------------------------------------------------------------------------------
        if not args.sim:
            self.submodules.crg = self.get_crg()
        else:
            self.submodules.crg = CRG(self.platform.request('sys_clk'))
            # Add dynamic simulation trace control, start enabled
            self.platform.add_debug(self, reset=1)

        # Leds -------------------------------------------------------------------------------------
        self.submodules.leds = LedChaser(
            pads         = self.platform.request_all("user_led"),
            sys_clk_freq = sys_clk_freq)
        self.add_csr("leds")

        # SDRAM PHY --------------------------------------------------------------------------------
        module = self.get_sdram_module()

        if args.sim:
            # Use the hardware platform to retrieve values for simulation
            hw_pads = self.get_platform().request('ddram')
            core_config = dict(
                sdram_module_nb = len(hw_pads.dq) // 8,  # number of byte groups
                sdram_rank_nb =   len(hw_pads.cs_n),     # number of ranks
                sdram_module =    module,
                memtype =         module.memtype,
            )
            # Add IO pins
            self.platform.add_extension(get_dram_ios(core_config))

            phy_settings   = get_sdram_phy_settings(
                memtype    = module.memtype,
                data_width = core_config["sdram_module_nb"]*8,
                clk_freq   = sys_clk_freq)

            self.submodules.ddrphy = SDRAMPHYModel(
                module    = module,
                settings  = phy_settings,
                clk_freq  = sys_clk_freq,
                verbosity = 3,
            )
        else:  # hardware
            self.submodules.ddrphy = self.get_ddrphy()
        self.add_csr("ddrphy")

        # SDRAM Controller--------------------------------------------------------------------------
        class ControllerDynamicSettings(Module, AutoCSR, AutoDoc, ModuleDoc):
            """Allows to change LiteDRAMController behaviour at runtime"""
            def __init__(self):
                self.refresh = CSRStorage(reset=1, description="Enable/disable Refresh commands sending")

        self.submodules.controller_settings = ControllerDynamicSettings()
        self.add_csr("controller_settings")
        controller_settings = ControllerSettings()
        controller_settings.with_auto_precharge = True
        controller_settings.with_refresh = self.controller_settings.refresh.storage

        self.add_sdram("sdram",
            phy                     = self.ddrphy,
            module                  = module,
            origin                  = self.mem_map["main_ram"],
            size                    = kwargs.get("max_sdram_size", 0x40000000),
            l2_cache_size           = 0,
            controller_settings     = controller_settings
        )

        # CPU will report that leveling finished by writing to ddrctrl CSRs
        self.submodules.ddrctrl = LiteDRAMCoreControl()
        self.add_csr("ddrctrl")

        # Ethernet / Etherbone ---------------------------------------------------------------------
        if not args.sim:
            self.add_host_bridge()
        else:  # simulation
            self.submodules.ethphy = LiteEthPHYModel(self.platform.request("eth"))
            self.add_csr("ethphy")

            # Ethernet Core
            ethcore = LiteEthUDPIPCore(self.ethphy,
                ip_address  = self.ip_address,
                mac_address = self.mac_address,
                clk_freq    = self.sys_clk_freq)
            self.submodules.ethcore = ethcore
            # Etherbone
            self.submodules.etherbone = LiteEthEtherbone(self.ethcore.udp, self.udp_port, mode="master")
            self.add_wb_master(self.etherbone.wishbone.bus)

        # Rowhammer --------------------------------------------------------------------------------
        self.submodules.rowhammer_dma = LiteDRAMDMAReader(self.sdram.crossbar.get_port())
        self.submodules.rowhammer = RowHammerDMA(self.rowhammer_dma)
        self.add_csr("rowhammer")

        # Bist -------------------------------------------------------------------------------------
        if not args.no_memory_bist:
            pattern_data_size  = int(args.pattern_data_size, 0)
            phy_settings       = self.sdram.controller.settings.phy
            pattern_data_width = phy_settings.dfi_databits * phy_settings.nphases
            pattern_length     = pattern_data_size//(pattern_data_width//8)

            assert pattern_data_size % (pattern_data_width//8) == 0, \
                'Pattern data memory size must be multiple of {} bytes'.format(pattern_data_width//8)

            self.submodules.pattern_mem = PatternMemory(
                data_width = pattern_data_width,
                mem_depth  = pattern_length)
            self.add_memory(self.pattern_mem.data, name='pattern_data', origin=0x20000000)
            self.add_memory(self.pattern_mem.addr, name='pattern_addr', origin=0x21000000)
            self.logger.info('{}: Length: {}, Data Width: {}-bit, Address width: {}-bit'.format(
                colorer('BIST pattern'), colorer(pattern_length), colorer(pattern_data_width), colorer(32)))

            # Writer
            dram_wr_port = self.sdram.crossbar.get_port()
            self.submodules.writer = Writer(dram_wr_port, self.pattern_mem)
            self.writer.add_csrs()
            self.add_csr('writer')

            # Reader
            dram_rd_port = self.sdram.crossbar.get_port()
            self.submodules.reader = Reader(dram_rd_port, self.pattern_mem)
            self.reader.add_csrs()
            self.add_csr('reader')

            assert pattern_data_width == dram_wr_port.data_width
            assert pattern_data_width == dram_rd_port.data_width

        # Payload executor -------------------------------------------------------------------------
        if not args.no_payload_executor:
            # TODO: disconnect bus during payload execution
            phy_settings = self.sdram.controller.settings.phy

            scratchpad_width = phy_settings.dfi_databits * phy_settings.nphases
            payload_size = int(args.payload_size, 0)
            scratchpad_size = int(args.scratchpad_size, 0)
            assert payload_size % 4 == 0, 'Payload memory size must be multiple of 4 bytes'
            assert scratchpad_size % (scratchpad_width//8) == 0, \
                'Scratchpad memory size must be multiple of {} bytes'.format(scratchpad_width//8)

            scratchpad_depth = scratchpad_size//(scratchpad_width//8)
            payload_mem    = Memory(32, payload_size//4)
            scratchpad_mem = Memory(scratchpad_width, scratchpad_depth)
            self.specials += payload_mem, scratchpad_mem

            self.add_memory(payload_mem,    name='payload',    origin=0x30000000)
            self.add_memory(scratchpad_mem, name='scratchpad', origin=0x31000000, mode='r')
            self.logger.info('{}: Length: {}, Data Width: {}-bit'.format(
                colorer('Instruction payload'), colorer(payload_size//4), colorer(32)))
            self.logger.info('{}: Length: {}, Data Width: {}-bit'.format(
                colorer('Scratchpad memory'), colorer(scratchpad_depth), colorer(scratchpad_width)))

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

    def add_memory(self, mem, *, name, origin, mode='rw'):
        ram = wishbone.SRAM(mem,
            bus       = wishbone.Interface(data_width=mem.width),
            read_only = 'w' not in mode)
        # Perform bus width conversion
        ram_bus = wishbone.Interface(data_width=self.bus.data_width)
        self.submodules += wishbone.Converter(ram_bus, ram.bus)
        # Add memory region
        region = SoCRegion(origin=origin, size=mem.width//8 * mem.depth, mode=mode)
        self.bus.add_slave(name, ram_bus, region)
        self.check_if_exists(name)
        self.logger.info("RAM {} {} {}.".format(
            colorer(name),
            colorer("added", color="green"),
            self.bus.regions[name]))
        setattr(self.submodules, name, ram)

    def generate_sdram_phy_py_header(self, output_file):
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        f = open(output_file, "w")
        f.write(get_sdram_phy_py_header(
            self.sdram.controller.settings.phy,
            self.sdram.controller.settings.timing))
        f.close()

# Build --------------------------------------------------------------------------------------------

def parser_args(parser, *, sys_clk_freq, module):
    # Print defaults only for the arguments added here, as Litex has defaults embedded in help messages
    class CustomArgumentDefaultHelpFormatter(argparse.HelpFormatter):
        ARG_NAMES = []

        def add_default(self, action):  # logic from argparse.ArgumentDefaultsHelpFormatter
            help = action.help
            if '%(default)' not in action.help:
                if action.default is not argparse.SUPPRESS:
                    defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
                    if action.option_strings or action.nargs in defaulting_nargs:
                        help += ' (default: %(default)s)'
            return help

        def _get_help_string(self, action):
            for s in action.option_strings:
                if s in self.ARG_NAMES:
                    return self.add_default(action)
            return action.help

    parser.formatter_class = CustomArgumentDefaultHelpFormatter

    def add_argument(*args, **kwargs):
        CustomArgumentDefaultHelpFormatter.ARG_NAMES.extend(args)
        parser.add_argument(*args, **kwargs)

    # Target args
    add_argument("--build", action="store_true", help="Build bitstream")
    add_argument("--load",  action="store_true", help="Load bitstream")
    add_argument("--docs",  action="store_true", help="Generate documentation")
    add_argument("--sim", action="store_true", help="Build and run in simulation mode")
    add_argument("--sys-clk-freq", default=sys_clk_freq, help="System clock frequency")
    add_argument("--module", default=module, help="DRAM module")
    add_argument("--no-memory-bist", action="store_true", help="Disable memory BIST module")
    add_argument("--pattern-data-size", default="1024", help="BIST pattern data memory size in bytes")
    add_argument("--no-payload-executor", action="store_true", help="Disable Payload Executor module")
    add_argument("--payload-size", default="1024", help="Payload memory size in bytes")
    add_argument("--scratchpad-size", default="1024", help="Scratchpad memory size in bytes")
    add_argument("--ip-address", default="192.168.100.50", help="Use given IP address")
    add_argument("--mac-address", default="0x10e2d5000001", help="Use given MAC address")
    add_argument("--udp-port", default="1234", help="Use given UDP port")

    # Litex args
    builder_args(parser)
    soc_core_args(parser)

def get_soc_kwargs(args):
    soc_kwargs = soc_core_argdict(args)
    # Set some defaults for SoC - no CPU, memory, etc.
    soc_kwargs.update(dict(
        cpu_type                 = "vexriscv",
        cpu_variant              = "minimal",
        no_timer                 = False,
        no_ctrl                  = False,
        no_uart                  = False,
        uart_name                = "crossover",
        integrated_rom_size      = 0x8000,
        integrated_sram_size     = 0x2000,
        integrated_main_ram_size = 0,
    ))
    # Common arguments to row hammer SoC
    soc_kwargs.update(dict(
        args             = args,
        sys_clk_freq     = int(float(args.sys_clk_freq)),
        sdram_module_cls = getattr(litedram_modules, args.module),
        ip_address       = args.ip_address,
        mac_address      = int(args.mac_address, 0),
        udp_port         = int(args.udp_port, 0),
    ))
    return soc_kwargs


def get_builder_kwargs(args, target_name):
    builder_kwargs = builder_argdict(args)
    builder_kwargs["output_dir"] = os.path.join('build', target_name)
    return builder_kwargs


def get_sim_kwargs(args, interface='litex-sim'):
    sim_config = SimConfig()
    sim_config.add_clocker("sys_clk", freq_hz=int(float(args.sys_clk_freq)))
    sim_config.add_module("ethernet", "eth", args={
        "interface": interface,
        "ip": args.ip_address,
    })
    return dict(sim_config=sim_config, trace=True, trace_fst=True)


class LiteDRAMSettingsEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (ControllerSettings, GeomSettings, PhySettings, TimingSettings)):
            ignored = ['self', 'refresh_cls']
            return {k: v for k, v in vars(o).items() if k not in ignored}
        elif isinstance(o, Signal) and isinstance(o.reset, Constant):
            return o.reset
        elif isinstance(o, Constant):
            return o.value
        print('o', end=' = '); __import__('pprint').pprint(o)
        return super().default(o)

def configure_generated_files(builder, args, target_name):
    # Generate target specific files in the build directory, for use by scripts
    # CSR location definitions
    builder.csr_csv = os.path.join(builder.output_dir, 'csr.csv')
    # DRAM initialization sequence
    builder.soc.generate_sdram_phy_py_header(os.path.join(builder.output_dir, "sdram_init.py"))
    # Target configuration
    with open(os.path.join(builder.output_dir, 'defs.csv'), 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows([
            ('TARGET',       target_name),
            ('IP_ADDRESS',   args.ip_address),
            ('MAC_ADDRESS',  args.mac_address),
            ('UDP_PORT',     args.udp_port),
            ('SYS_CLK_FREQ', args.sys_clk_freq),
        ])
    # LiteDRAM settings (controller, phy, geom, timing)
    with open(os.path.join(builder.output_dir, 'litedram_settings.json'), 'w') as f:
        json.dump(builder.soc.sdram.controller.settings, f, cls=LiteDRAMSettingsEncoder, indent=4)

def run(args, builder, build_kwargs, target_name):
    # Generate files in the build directory
    configure_generated_files(builder, args, target_name)

    # Build & run
    if not args.sim:  # hardware
        builder.build(**build_kwargs, run=args.build)

    else:  # simulation
        sim_kwargs = get_sim_kwargs(args)
        builder.build(**build_kwargs, run=args.build, **sim_kwargs)

    if args.docs:
        doc.generate_docs(builder.soc,
            base_dir     = "build/documentation",
            project_name = "LiteX Row Hammer Tester",
            author       = "Antmicro")

    if args.load:
        prog = builder.soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir, builder.soc.build_name + ".bit"))
