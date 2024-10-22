#
# This file is part of LiteDRAM.
#
# Copyright (c) 2021 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import argparse
from random import randrange

from operator import or_, and_
from migen import *

from litex.build.generic_platform import Pins, Subsignal
from litex.build.sim.config import SimConfig

from litex.soc.interconnect.csr import CSR, CSRStorage
from litex.soc.integration.soc_core import SoCCore, soc_core_args, soc_core_argdict
from litex.soc.integration.soc import *
from litex.soc.integration.builder import builder_args, builder_argdict, Builder
from litex.soc.integration.common import get_mem_data
from litex.soc.cores.cpu import CPUS

from litedram.gen import LiteDRAMCoreControl
from litedram import modules as litedram_modules
from litedram.init import get_ddr5_phy_init_sequence as ddr5_seqs
from litedram.core.controller import ControllerSettings
from litedram.phy.model import DFITimingsChecker, _speedgrade_timings, _technology_timings

from litedram.phy.ddr5.simphy import DDR5SimPHY
from litedram.phy.ddr5.sdram_simulation_model import DDR5SDRAMSimulationModel
from litedram.phy.ddr5.commands import MPC, CMD

from litedram.phy.sim_utils import Clocks, CRG, Platform

from liteeth.phy.gmii import LiteEthPHYGMII
from liteeth.phy.xgmii import LiteEthPHYXGMII
from liteeth.phy.model import LiteEthPHYModel
from liteeth.mac import LiteEthMAC
from liteeth.core.arp import LiteEthARP
from liteeth.core.ip import LiteEthIP
from liteeth.core.udp import LiteEthUDP
from liteeth.core.icmp import LiteEthICMP
from liteeth.core import LiteEthUDPIPCore
from liteeth.common import *


from litex.soc.cores.cpu.vexriscv_smp.core import VexRiscvSMP
# Platform -----------------------------------------------------------------------------------------

_io = {
    "4": [
        ("ddr5", 0,
         Subsignal("ck_t",    Pins(1)),
         Subsignal("ck_c",    Pins(1)),
         Subsignal("reset_n", Pins(1)),
         Subsignal("alert_n", Pins(1)),

         Subsignal("cs_n",    Pins(1)),
         Subsignal("ca",      Pins(14)),
         Subsignal("par",     Pins(1)),

         # DQ and DQS are taken from DDR5 Tester board
         Subsignal("dq",      Pins(4)),
         # dmi is not supported on x4 device, I decided to keep it to make model simpler
         Subsignal("dm_n",    Pins(1)),
         Subsignal("dqs_t",   Pins(1)),
         Subsignal("dqs_c",   Pins(1)),
        ),
    ],
    "8": [
        ("ddr5", 0,
         Subsignal("ck_t",    Pins(1)),
         Subsignal("ck_c",    Pins(1)),
         Subsignal("reset_n", Pins(1)),
         Subsignal("alert_n", Pins(1)),

         Subsignal("cs_n",    Pins(1)),
         Subsignal("ca",      Pins(14)),
         Subsignal("par",     Pins(1)),

         Subsignal("dq",      Pins(8)),
         Subsignal("dm_n",    Pins(1)),
         Subsignal("dqs_t",   Pins(1)),
         Subsignal("dqs_c",   Pins(1)),
        ),
    ],
    "4x2": [
        ("ddr5", 0,
         Subsignal("ck_t",    Pins(1)),
         Subsignal("ck_c",    Pins(1)),
         Subsignal("reset_n", Pins(1)),
         Subsignal("alert_n", Pins(1)),

         Subsignal("cs_n",    Pins(1)),
         Subsignal("ca",      Pins(14)),
         Subsignal("par",     Pins(1)),

         # DQ and DQS are taken from DDR5 Tester board
         Subsignal("dq",      Pins(8)),
         # dmi is not supported on x4 device, I decided to keep it to make model simpler
         Subsignal("dm_n",    Pins(2)),
         Subsignal("dqs_t",   Pins(2)),
         Subsignal("dqs_c",   Pins(2)),
        ),
    ],
    "8x2": [
        ("ddr5", 0,
         Subsignal("ck_t",    Pins(1)),
         Subsignal("ck_c",    Pins(1)),
         Subsignal("reset_n", Pins(1)),
         Subsignal("alert_n", Pins(1)),

         Subsignal("cs_n",    Pins(1)),
         Subsignal("ca",      Pins(14)),
         Subsignal("par",     Pins(1)),

         Subsignal("dq",      Pins(16)),
         Subsignal("dm_n",    Pins(2)),
         Subsignal("dqs_t",   Pins(2)),
         Subsignal("dqs_c",   Pins(2)),
        ),
    ],
    "sub4": [
        ("ddr5", 0,
         Subsignal("ck_t",    Pins(1)),
         Subsignal("ck_c",    Pins(1)),
         Subsignal("reset_n", Pins(1)),
         Subsignal("alert_n", Pins(1)),

         Subsignal("A_cs_n",  Pins(1)),
         Subsignal("A_ca",    Pins(14)),
         Subsignal("A_par",   Pins(1)),

         # DQ and DQS are taken from DDR5 Tester board
         Subsignal("A_dq",    Pins(4)),
         # dmi is not supported on x4 device, I decided to keep it to make model simpler
         Subsignal("A_dm_n",  Pins(1)),
         Subsignal("A_dqs_t", Pins(1)),
         Subsignal("A_dqs_c", Pins(1)),

         Subsignal("B_cs_n",  Pins(1)),
         Subsignal("B_ca",    Pins(14)),
         Subsignal("B_par",   Pins(1)),

         # DQ and DQS are taken from DDR5 Tester board
         Subsignal("B_dq",    Pins(4)),
         # dmi is not supported on x4 device, I decided to keep it to make model simpler
         Subsignal("B_dm_n",  Pins(1)),
         Subsignal("B_dqs_t", Pins(1)),
         Subsignal("B_dqs_c", Pins(1)),
        ),
        ("i2c", 0,
         Subsignal("scl", Pins(1)),
         Subsignal("sda", Pins(1)),
        ),
    ],
    "sub8": [
        ("ddr5", 0,
         Subsignal("ck_t",    Pins(1)),
         Subsignal("ck_c",    Pins(1)),
         Subsignal("reset_n", Pins(1)),
         Subsignal("alert_n", Pins(1)),

         Subsignal("A_cs_n",  Pins(1)),
         # dmi is not supported on x4 device, I decided to keep it to make model simpler
         Subsignal("A_dm_n",  Pins(1)),

         Subsignal("A_ca",    Pins(14)),
         Subsignal("A_par",   Pins(1)),
         # DQ and DQS are taken from DDR5 Tester board
         Subsignal("A_dq",    Pins(8)),
         Subsignal("A_dqs_t", Pins(1)),
         Subsignal("A_dqs_c", Pins(1)),

         Subsignal("B_cs_n",  Pins(1)),
         # dmi is not supported on x4 device, I decided to keep it to make model simpler
         Subsignal("B_dm_n",  Pins(1)),

         Subsignal("B_ca",    Pins(14)),
         Subsignal("B_par",   Pins(1)),
         # DQ and DQS are taken from DDR5 Tester board
         Subsignal("B_dq",    Pins(8)),
         Subsignal("B_dqs_t", Pins(1)),
         Subsignal("B_dqs_c", Pins(1)),
        ),
        ("i2c", 0,
         Subsignal("scl", Pins(1)),
         Subsignal("sda", Pins(1)),
        ),
    ],
    "sub4x2": [
        ("ddr5", 0,
         Subsignal("ck_t",    Pins(1)),
         Subsignal("ck_c",    Pins(1)),
         Subsignal("reset_n", Pins(1)),
         Subsignal("alert_n", Pins(1)),

         Subsignal("A_cs_n",  Pins(1)),
         Subsignal("A_ca",    Pins(14)),
         Subsignal("A_par",   Pins(1)),

         # DQ and DQS are taken from DDR5 Tester board
         Subsignal("A_dq",    Pins(8)),
         # dmi is not supported on x4 device, I decided to keep it to make model simpler
         Subsignal("A_dm_n",  Pins(2)),
         Subsignal("A_dqs_t", Pins(2)),
         Subsignal("A_dqs_c", Pins(2)),

         Subsignal("B_cs_n",  Pins(1)),
         Subsignal("B_ca",    Pins(14)),
         Subsignal("B_par",   Pins(1)),

         # DQ and DQS are taken from DDR5 Tester board
         Subsignal("B_dq",    Pins(8)),
         # dmi is not supported on x4 device, I decided to keep it to make model simpler
         Subsignal("B_dm_n",  Pins(2)),
         Subsignal("B_dqs_t", Pins(2)),
         Subsignal("B_dqs_c", Pins(2)),
        ),
        ("i2c", 0,
         Subsignal("scl", Pins(1)),
         Subsignal("sda", Pins(1)),
        ),
    ],
    "sub8x2": [
        ("ddr5", 0,
         Subsignal("ck_t",    Pins(1)),
         Subsignal("ck_c",    Pins(1)),
         Subsignal("reset_n", Pins(1)),
         Subsignal("alert_n", Pins(1)),

         Subsignal("A_cs_n",  Pins(1)),
         # dmi is not supported on x4 device, I decided to keep it to make model simpler
         Subsignal("A_dm_n",  Pins(1)),

         Subsignal("A_ca",    Pins(14)),
         Subsignal("A_par",   Pins(1)),
         # DQ and DQS are taken from DDR5 Tester board
         Subsignal("A_dq",    Pins(16)),
         Subsignal("A_dqs_t", Pins(2)),
         Subsignal("A_dqs_c", Pins(2)),

         Subsignal("B_cs_n",  Pins(1)),
         # dmi is not supported on x4 device, I decided to keep it to make model simpler
         Subsignal("B_dm_n",  Pins(1)),

         Subsignal("B_ca",    Pins(14)),
         Subsignal("B_par",   Pins(1)),
         # DQ and DQS are taken from DDR5 Tester board
         Subsignal("B_dq",    Pins(16)),
         Subsignal("B_dqs_t", Pins(2)),
         Subsignal("B_dqs_c", Pins(2)),
        ),
        ("i2c", 0,
         Subsignal("scl", Pins(1)),
         Subsignal("sda", Pins(1)),
        ),
    ],
}

# Clocks -------------------------------------------------------------------------------------------

def get_clocks(sys_clk_freq):
    clk_dict = {
        "sys":             dict(freq_hz=sys_clk_freq),
        "sys2x":           dict(freq_hz=2*sys_clk_freq),
        "sys4x":           dict(freq_hz=4*sys_clk_freq),
        "sys4x_ddr":       dict(freq_hz=2*4*sys_clk_freq),                  # RCD cmd sample
        "sys4x_180":       dict(freq_hz=4*sys_clk_freq, phase_deg=180),     # phy cs
        "sys4x_180_ddr":   dict(freq_hz=2*4*sys_clk_freq),                  # phy ca
        "sys2x_90":        dict(freq_hz=2*sys_clk_freq, phase_deg=45),      # phy oe delay
        "sys4x_90":        dict(freq_hz=4*sys_clk_freq, phase_deg=90),      # phy oe delay
        "sys4x_90_ddr":    dict(freq_hz=2*4*sys_clk_freq, phase_deg=2*90),  # phy dq/dqs IO
        "sys8x_ddr":       dict(freq_hz=2*8*sys_clk_freq),
    }
    return Clocks(clk_dict)

# SoC ----------------------------------------------------------------------------------------------

class SimSoC(SoCCore):
    """Simulation of SoC with DDR5 DRAM

    This is a SoC used to run Verilator-based simulations of LiteDRAM with a simulated DDR5 chip.
    """
    def __init__(self, clocks, log_level,
            auto_precharge=False, with_refresh=True, trace_reset=0,
            masked_write=False, with_rcd=False, finish_after_memtest=False,
            dq_dqs_ratio=8, with_sub_channels=False, modules_in_rank=1, skip_csca=False,
            skip_mrs_seq=False, skip_reset_seq=False, ethernet_phy_model="sim", with_ethernet=False,
            with_prompt=False, **kwargs):

        io_type = str(dq_dqs_ratio) if not with_sub_channels else f"sub{dq_dqs_ratio}"
        io_type = io_type if modules_in_rank == 1 else io_type+f"x{modules_in_rank}"
        _io[io_type].append(
            ("gmii_eth", 0,
                Subsignal("rx_data",      Pins(8)),
                Subsignal("rx_dv",        Pins(1)),
                Subsignal("rx_er",        Pins(1)),
                Subsignal("tx_data",      Pins(8)),
                Subsignal("tx_en",        Pins(1)),
                Subsignal("tx_er",        Pins(1)),
            ),
        )
        platform     = Platform(_io[io_type], clocks)
        sys_clk_freq = clocks["sys"]["freq_hz"]

        # SoCCore ----------------------------------------------------------------------------------
        super().__init__(platform,
            clk_freq      = sys_clk_freq,
            ident         = "LiteX Simulation",
            cpu_variant   = "linux",
            **kwargs)

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = CRG(platform, clocks)

        # Debugging --------------------------------------------------------------------------------
        platform.add_debug(self, reset=trace_reset)

        # Ethernet / Etherbone PHY -----------------------------------------------------------------
        if with_ethernet:
            if ethernet_phy_model == "sim":
                self.ethphy = LiteEthPHYModel(self.platform.request("eth", 0))
            elif ethernet_phy_model == "xgmii":
                self.ethphy = LiteEthPHYXGMII(None, self.platform.request("xgmii_eth", 0), model=True)
            elif ethernet_phy_model == "gmii":
                self.ethphy = LiteEthPHYGMII(None, self.platform.request("gmii_eth", 0), model=True)
            else:
                raise ValueError("Unknown Ethernet PHY model:", ethernet_phy_model)

        # Ethernet ---------------------------------------------------------------------------------
        if with_ethernet:
            self.add_ethernet(phy=self.ethphy, dynamic_ip=False)

        # DDR5 -----------------------------------------------------------------------------------
        if dq_dqs_ratio == 8:
            sdram_module = litedram_modules.DDR5SimX8(sys_clk_freq, "1:4")
        elif dq_dqs_ratio == 4:
            sdram_module = litedram_modules.DDR5SimX4(sys_clk_freq, "1:4")
            if masked_write:
                masked_write = False
                print("Masked Write is unsupported for x4 device (JESD79-5A, section 4.8.1)")
        else:
            raise NotImplementedError(f"Unspupported DQ:DQS ratio: {dq_dqs_ratio}")

        pads = platform.request("ddr5")
        sim_phy_cls = DDR5SimPHY
        self.submodules.ddrphy = sim_phy_cls(
            sys_clk_freq       = sys_clk_freq,
            aligned_reset_zero = True,
            masked_write       = masked_write,
            dq_dqs_ratio       = dq_dqs_ratio,
            databits           = len(getattr(pads, "dq")) if not with_sub_channels else len(getattr(pads, "A_dq")),
            with_sub_channels  = with_sub_channels,
            direct_control     = True,
        )

        for p in _io[io_type][0][2:]:
            self.comb += getattr(pads, p.name).eq(getattr(self.ddrphy.pads, p.name))

        controller_settings = ControllerSettings()
        controller_settings.auto_precharge = auto_precharge
        controller_settings.with_refresh = with_refresh

        # CLK for sdram module, originates from phy
        setattr(self.clock_domains, "cd_sys4x_p_dimm",
            ClockDomain("sys4x_p_dimm"))
        setattr(self.clock_domains, "cd_sys4x_n_dimm",
            ClockDomain("sys4x_n_dimm"))
        self.comb += [
            ClockSignal("sys4x_p_dimm").eq(self.ddrphy.pads.ck_t),
            ResetSignal("sys4x_p_dimm").eq(~self.ddrphy.pads.reset_n),
            ClockSignal("sys4x_n_dimm").eq(self.ddrphy.pads.ck_c),
            ResetSignal("sys4x_n_dimm").eq(~self.ddrphy.pads.reset_n),
        ]

        self.add_sdram("sdram",
            phy                     = self.ddrphy,
            module                  = sdram_module,
            origin                  = self.mem_map["main_ram"],
            size                    = kwargs.get("max_sdram_size", 0x40000000),
            l2_cache_size           = kwargs.get("l2_size", 8192),
            l2_cache_min_data_width = kwargs.get("min_l2_data_width", 128),
            l2_cache_reverse        = False,
            controller_settings     = controller_settings
        )

        prefixes = [""] if not controller_settings.phy.with_sub_channels else ["A_", "B_"]
        for _, prefix in enumerate(prefixes):
            setattr(self, prefix+"DQ_remapping", CSRStorage(8*controller_settings.phy.nibbles*4, name=prefix+"DQ_remapping"))

        # Reduce memtest size for simulation speedup
        self.add_constant("MEMTEST_DATA_SIZE", 8*1024)
        self.add_constant("MEMTEST_ADDR_SIZE", 8*1024)
        self.add_constant("DDR5_TRAINING_SIM", 1)
        self.add_constant("CONFIG_BIOS_NO_CRC")

        n1_mode_select    = 0
        skip_fsm_to_stage = 0
        sdram_reg_setup = {}

        if skip_csca:
            self.add_constant("SKIP_CSCA_TRAINING")
            n1_mode_select    = 1
        if skip_reset_seq or skip_mrs_seq:
            self.add_constant("SKIP_RESET_SEQUENCE")
            skip_fsm_to_stage = 3
        if skip_mrs_seq:
            self.add_constant("SKIP_MRS_SEQUENCE")
            skip_fsm_to_stage = 7
            _, _, mrs, _, _ = ddr5_seqs(controller_settings.phy, sdram_module.timing_settings)
            for _, _, cs, cmd, _, _, _ in mrs:
                if isinstance(cs, str):
                    type_ = cmd & 0x1f
                    cmd >>= 5
                    if (type_ == CMD.MPC) and (cmd&0xf0) == MPC.DLL_SET:
                        if 13 not in sdram_reg_setup:
                            sdram_reg_setup[13] = 0
                        sdram_reg_setup[13] |= cmd & 0xf
                    if (type_ == CMD.MPC) and (cmd&0xf8) == 0x20:
                        if 32 not in sdram_reg_setup:
                            sdram_reg_setup[32] = 0
                        sdram_reg_setup[32] |= cmd & 0x7
                    if (type_ == CMD.MPC) and (cmd&0xf8) == 0x28:
                        pass
                    if (type_&CMD.MPC == CMD.MPC) and (cmd&0xf8) == 0x30:
                        if 32 not in sdram_reg_setup:
                            sdram_reg_setup[32] = 0
                        sdram_reg_setup[32] |= (cmd & 0x7) << 3
                    if (type_ == CMD.MPC) and (cmd&0xf8) == 0x38:
                        pass
                    if (type_ == CMD.MPC) and (cmd&0xf8) == 0x40:
                        if 33 not in sdram_reg_setup:
                            sdram_reg_setup[33] = 0
                        sdram_reg_setup[33] |= cmd & 0x7
                    if (type_ == CMD.MPC) and (cmd&0xf8) == 0x48:
                        pass
                    if (type_ == CMD.MPC) and (cmd&0xf8) == 0x50:
                        if 33 not in sdram_reg_setup:
                            sdram_reg_setup[33] = 0
                        sdram_reg_setup[33] |= (cmd & 0x7) << 3
                    if (type_ == CMD.MPC) and (cmd&0xf8) == 0x58:
                        if 34 not in sdram_reg_setup:
                            sdram_reg_setup[34] = 0
                        sdram_reg_setup[34] |= cmd & 0x7
                    if (type_ == CMD.VREF) and cmd & 0x80 == 0x80:
                        if 12 not in sdram_reg_setup:
                            sdram_reg_setup[12] = 0
                        sdram_reg_setup[12] |= cmd & 0x7f
                    if (type_ == CMD.VREF) and cmd & 0x80 == 0x00:
                        if 11 not in sdram_reg_setup:
                            sdram_reg_setup[11] = 0
                        sdram_reg_setup[11] |= cmd & 0x7f

        # DDR5 Module ------------------------------------------------------------------------------
        prefixes = [""] if not with_sub_channels else ["A_", "B_"]
        alerts = {}
        for prefix in prefixes:
            for i in range(modules_in_rank):
                module = DDR5SDRAMSimulationModel(
                    pads          = self.ddrphy.pads,
                    cl            = self.sdram.controller.settings.phy.cl,
                    cwl           = self.sdram.controller.settings.phy.cwl,
                    sys_clk_freq  = sys_clk_freq,
                    log_level     = log_level,
                    geom_settings = sdram_module.geom_settings,
                    prefix        = prefix,
                    module_num    = i,
                    dq_dqs_ratio  = dq_dqs_ratio,
                    n1_mode_select= n1_mode_select,
                    skip_fsm_to_stage = skip_fsm_to_stage,
                    sdram_reg_setup =  sdram_reg_setup,
                )
                setattr(self.submodules, prefix+'ddr5sim', module)
                alerts[prefix+f"alert_{i}"] = module.alert_n
        self.comb += self.ddrphy.pads.alert_n.eq(reduce(and_, alerts.values()))

        if not with_prompt:
            self.add_constant("CONFIG_SIM_DISABLE_BIOS_PROMPT")
        if finish_after_memtest:
            self.submodules.ddrctrl = LiteDRAMCoreControl()
            self.add_csr("ddrctrl")
            self.sync += If(self.ddrctrl.init_done.storage, Finish())

        # Reuse DFITimingsChecker from phy/model.py
        nphases = self.sdram.controller.settings.phy.nphases
        timings = {"tCK": (1e9 / sys_clk_freq) / nphases}
        for name in _speedgrade_timings + _technology_timings:
            timings[name] = sdram_module.get(name)

        # Debug info -------------------------------------------------------------------------------
        def dump(obj):
            print()
            print(" " + obj.__class__.__name__)
            print(" " + "-" * len(obj.__class__.__name__))
            d = obj if isinstance(obj, dict) else vars(obj)
            for var, val in d.items():
                if var == "self":
                    continue
                if isinstance(val, Signal):
                    val = "Signal(reset={})".format(val.reset.value)
                print("  {}: {}".format(var, val))

        print("=" * 80)
        dump(clocks)
        dump(self.ddrphy.settings)
        dump(sdram_module.geom_settings)
        dump(sdram_module.timing_settings)
        print()
        print("=" * 80)

# Build --------------------------------------------------------------------------------------------

def generate_gtkw_savefile(builder, vns, trace_fst):
    from litex.build.sim import gtkwave as gtkw

    dumpfile = os.path.join(builder.gateware_dir, "sim.{}".format("fst" if trace_fst else "vcd"))
    savefile = os.path.join(builder.gateware_dir, "sim.gtkw")
    soc = builder.soc
    wrphase = soc.sdram.controller.settings.phy.wrphase.reset.value

    with gtkw.GTKWSave(vns, savefile=savefile, dumpfile=dumpfile) as save:
        save.clocks()
        save.add(soc.bus.slaves["main_ram"], mappers=[gtkw.wishbone_sorter(), gtkw.wishbone_colorer()])
        save.fsm_states(soc)
        # all dfi signals
        save.add(soc.ddrphy.dfi, mappers=[gtkw.dfi_sorter(), gtkw.dfi_in_phase_colorer()])
        # each phase in separate group
        with save.gtkw.group("dfi phaseX", closed=True):
            for i, phase in enumerate(soc.ddrphy.dfi.phases):
                save.add(phase, group_name="dfi p{}".format(i), mappers=[
                    gtkw.dfi_sorter(phases=False),
                    gtkw.dfi_in_phase_colorer(),
                ])
        # only dfi command signals
        save.add(soc.ddrphy.dfi, group_name="dfi commands", mappers=[
            gtkw.regex_filter(gtkw.suffixes2re(["cas_n", "ras_n", "we_n"])),
            gtkw.dfi_sorter(),
            gtkw.dfi_per_phase_colorer(),
        ])
        # only dfi data signals
        save.add(soc.ddrphy.dfi, group_name="dfi wrdata", mappers=[
            gtkw.regex_filter(["wrdata$", "p{}.*wrdata_en$".format(wrphase)]),
            gtkw.dfi_sorter(),
            gtkw.dfi_per_phase_colorer(),
        ])
        save.add(soc.ddrphy.dfi, group_name="dfi wrdata_mask", mappers=[
            gtkw.regex_filter(gtkw.suffixes2re(["wrdata_mask"])),
            gtkw.dfi_sorter(),
            gtkw.dfi_per_phase_colorer(),
        ])
        save.add(soc.ddrphy.dfi, group_name="dfi rddata", mappers=[
            gtkw.regex_filter(gtkw.suffixes2re(["rddata", "p0.*rddata_valid"])),
            gtkw.dfi_sorter(),
            gtkw.dfi_per_phase_colorer(),
        ])
        # serialization
        with save.gtkw.group("serialization", closed=True):
            ser_groups = [("out", soc.ddrphy.out)]
            for name, out in ser_groups:
                save.group([out.dqs_t_o[0], out.dqs_t_oe, out.dm_n_o[0], out.dm_n_oe],
                    group_name = name,
                    mappers = [
                        gtkw.regex_colorer({
                            "yellow": gtkw.suffixes2re(["cs_n"]),
                            "orange": ["_o[^e]"],
                            "red": gtkw.suffixes2re(["oe"]),
                        })
                    ]
                )
        with save.gtkw.group("deserialization", closed=True):
            if isinstance(soc.ddrphy, DoubleRateDDR5SimPHY):
                ser_groups = [("in 1x", soc.ddrphy._out), ("in 2x", soc.ddrphy.out)]
            else:
                ser_groups = [("in", soc.ddrphy.out)]
            for name, out in ser_groups:
                save.group([out.dq_i[0], out.dq_oe, out.dqs_t_i[0], out.dqs_t_oe],
                    group_name = name,
                    mappers = [gtkw.regex_colorer({
                        "yellow": ["dqs"],
                        "orange": ["dq[^s]"],
                    })]
                )
        # dram pads
        save.group([s for s in vars(soc.ddrphy.pads).values() if isinstance(s, Signal)],
            group_name = "pads",
            mappers = [
                gtkw.regex_filter(["_[io]$"], negate=True),
                gtkw.regex_sorter(gtkw.suffixes2re(["clk", "mir", "cai", "ca_odt", "reset_n", "cs_n", "ca", "dq", "dqs", "dmi", "oe"])),
                gtkw.regex_colorer({
                    "yellow": gtkw.suffixes2re(["cs_n", "ca"]),
                    "orange": gtkw.suffixes2re(["dq", "dqs", "dmi"]),
                    "red": gtkw.suffixes2re(["oe"]),
                }),
            ],
        )

def main():
    parser = argparse.ArgumentParser(description="Generic LiteX SoC Simulation")
    builder_args(parser.add_argument_group(title="Builder"))
    soc_core_args(parser.add_argument_group(title="SoC Core"))

    parser.add_argument("--with-ethernet",        action="store_true",     help="Enable Ethernet support.")
    parser.add_argument("--ethernet-phy-model",   default="sim",           help="Ethernet PHY to simulate (sim, xgmii or gmii).")
    parser.add_argument("--local-ip",             default="192.168.10.50",  help="Local IP address of SoC.")
    parser.add_argument("--remote-ip",            default="192.168.10.100", help="Remote IP address of TFTP server.")

    group = parser.add_argument_group(title="DDR5 simulation")
    group.add_argument("--sdram-verbosity",      default=0,               help="Set SDRAM checker verbosity")
    group.add_argument("--trace",                action="store_true",     help="Enable Tracing")
    group.add_argument("--trace-fst",            action="store_true",     help="Enable FST tracing (default=VCD)")
    group.add_argument("--trace-start",          default=0,               help="Cycle to start tracing")
    group.add_argument("--trace-end",            default=-1,              help="Cycle to end tracing")
    group.add_argument("--trace-reset",          default=0,               help="Initial traceing state")
    group.add_argument("--sys-clk-freq",         default="250e6",          help="Core clock frequency")
    group.add_argument("--auto-precharge",       action="store_true",     help="Use DRAM auto precharge")
    group.add_argument("--no-refresh",           action="store_true",     help="Disable DRAM refresher")
    group.add_argument("--log-level",            default="all=INFO",      help="Set simulation logging level")
    group.add_argument("--disable-delay",        action="store_true",     help="Disable CPU delays")
    group.add_argument("--gtkw-savefile",        action="store_true",     help="Generate GTKWave savefile")
    group.add_argument("--no-masked-write",      action="store_true",     help="Use unmasked variant of WRITE command")
    group.add_argument("--no-run",               action="store_true",     help="Don't run the simulation, just generate files")
    group.add_argument("--with-sub-channels",    action="store_true",     help="Use sim PHY with sub chanels")
    group.add_argument("--finish-after-memtest", action="store_true",     help="Stop simulation after DRAM memory test")
    group.add_argument("--with-prompt",          action="store_true",     help="Run simulation to bios prompt")
    group.add_argument("--skip-reset-seq",       action="store_true",     help="Skip DDR5 reset seqence and check")
    group.add_argument("--skip-mrs-seq",         action="store_true",     help="Skip DDR5 initial MPC setup, it will skip reset as well")
    group.add_argument("--skip-csca",            action="store_true",     help="Skip CS and CA training, use 1N mode")
    group.add_argument("--dq-dqs-ratio",         default=8,               help="Set DQ:DQS ratio", type=int, choices={4, 8})
    group.add_argument("--modules-in-rank",      default=1,               help="Set DQ:DQS ratio", type=int, choices={1, 2})
    parser.add_argument("--ram-init",             default=None,            help="RAM init file (.bin or .json).")

    VexRiscvSMP.args_fill(parser)

    args = parser.parse_args()
    soc_kwargs     = soc_core_argdict(args)
    builder_kwargs = builder_argdict(args)

    VexRiscvSMP.args_read(args)

    sim_config = SimConfig()
    sys_clk_freq = int(float(args.sys_clk_freq))
    clocks = get_clocks(sys_clk_freq)
    clocks.add_clockers(sim_config)

    # Configuration --------------------------------------------------------------------------------
    if soc_kwargs["uart_name"] == "serial":
        soc_kwargs["uart_name"] = "sim"
        sim_config.add_module("serial2console", "serial")
    args.with_sdram = True
    soc_kwargs["integrated_main_ram_size"] = 0x0
    soc_kwargs["sdram_verbosity"]          = int(args.sdram_verbosity)

    # Ethernet.
    if args.with_ethernet:
        if args.ethernet_phy_model == "sim":
            sim_config.add_module("ethernet", "eth", args={"interface": "tap0", "ip": args.remote_ip})
        elif args.ethernet_phy_model == "xgmii":
            sim_config.add_module("xgmii_ethernet", "xgmii_eth", args={"interface": "tap0", "ip": args.remote_ip})
        elif args.ethernet_phy_model == "gmii":
            sim_config.add_module("gmii_ethernet", "gmii_eth", args={"interface": "tap0", "ip": args.remote_ip})
        else:
            raise ValueError("Unknown Ethernet PHY model: " + args.ethernet_phy_model)

    # SoC ------------------------------------------------------------------------------------------
    soc = SimSoC(
        clocks          = clocks,
        auto_precharge  = args.auto_precharge,
        with_refresh    = not args.no_refresh,
        trace_reset     = int(args.trace_reset),
        log_level       = args.log_level,
        masked_write    = not args.no_masked_write,
        finish_after_memtest = args.finish_after_memtest,
        dq_dqs_ratio    = args.dq_dqs_ratio,
        with_sub_channels = args.with_sub_channels,
        modules_in_rank = args.modules_in_rank,
        skip_csca       = args.skip_csca,
        skip_mrs_seq    = args.skip_mrs_seq,
        skip_reset_seq  = args.skip_reset_seq,
        with_prompt     = args.with_prompt,
        with_ethernet      = args.with_ethernet,
        ethernet_phy_model = args.ethernet_phy_model,
        **soc_kwargs)
    if args.ram_init is not None:
        init_data = get_mem_data(args.ram_init,
            data_width = 32,
            endianness = 'little',
        )
        soc.add_ram("images", origin = 0x30000000, size=0x10000000, contents=init_data)

    if args.with_ethernet:
        for i in range(4):
            soc.add_constant("LOCALIP{}".format(i+1), int(args.local_ip.split(".")[i]))
        for i in range(4):
            soc.add_constant("REMOTEIP{}".format(i+1), int(args.remote_ip.split(".")[i]))

    # Build/Run ------------------------------------------------------------------------------------
    def pre_run_callback(vns):
        if args.trace and args.gtkw_savefile:
            generate_gtkw_savefile(builder, vns, args.trace_fst)

    builder_kwargs["csr_csv"] = "csr.csv"
    builder = Builder(soc, **builder_kwargs)
    build_kwargs = dict(
        sim_config  = sim_config,
        trace       = args.trace,
        trace_fst   = args.trace_fst,
        trace_start = int(args.trace_start),
        trace_end   = int(args.trace_end),
        pre_run_callback = pre_run_callback,
        opt_level   = "O3",
        jobs="$(nproc)", # so CI doesn't get killed by OOM
    )
    builder.build(run=not args.no_run, **build_kwargs)

if __name__ == "__main__":
    main()
