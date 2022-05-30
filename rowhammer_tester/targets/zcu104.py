#!/usr/bin/env python3

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex_boards.platforms import xilinx_zcu104
from litex.build.xilinx.vivado import vivado_build_args, vivado_build_argdict
from litex.soc.integration.builder import Builder
from litex.soc.integration.soc_core import colorer
from litex.soc.cores.clock import USMMCM, USIDELAYCTRL
from litex.soc.interconnect import axi, wishbone
from litex.soc.cores.bitbang import I2CMaster

from litedram.phy import usddrphy

from liteeth.phy.usrgmii import LiteEthPHYRGMII

from rowhammer_tester.targets import common

# CRG ----------------------------------------------------------------------------------------------

class CRG(Module):
    IODELAYCTRL_REFCLK_RANGE = (300e6, 800e6)  # according to Zynq US+ MPSoC datasheet

    def __init__(self, platform, sys_clk_freq, iodelay_clk_freq):
        self.rst = Signal()
        self.clock_domains.cd_sys    = ClockDomain()
        self.clock_domains.cd_sys4x  = ClockDomain(reset_less=True)
        self.clock_domains.cd_pll4x  = ClockDomain(reset_less=True)
        self.clock_domains.cd_idelay = ClockDomain()
        self.clock_domains.cd_uart   = ClockDomain()

        # # #

        self.submodules.pll = pll = USMMCM(speedgrade=-2)
        self.comb += pll.reset.eq(self.rst)
        pll.register_clkin(platform.request("clk125"), 125e6)
        pll.create_clkout(self.cd_pll4x, sys_clk_freq*4, buf=None, with_reset=False)
        pll.create_clkout(self.cd_idelay, iodelay_clk_freq)
        pll.create_clkout(self.cd_uart, sys_clk_freq, with_reset=False)
        platform.add_false_path_constraints(self.cd_sys.clk, pll.clkin) # Ignore sys_clk to pll.clkin path created by SoC's rst.

        self.specials += [
            Instance("BUFGCE_DIV", name="main_bufgce_div",
                p_BUFGCE_DIVIDE=4,
                i_CE=1, i_I=self.cd_pll4x.clk, o_O=self.cd_sys.clk),
            Instance("BUFGCE", name="main_bufgce",
                i_CE=1, i_I=self.cd_pll4x.clk, o_O=self.cd_sys4x.clk),
        ]

        fmin, fmax = self.IODELAYCTRL_REFCLK_RANGE
        assert fmin <= iodelay_clk_freq <= fmax, \
            f"IDELAYCTRL refclk must be in range ({fmin/1e6}, {fmax/1e6}) MHz, got {iodelay_clk_freq/1e6} MHz"
        self.submodules.idelayctrl = USIDELAYCTRL(cd_ref=self.cd_idelay, cd_sys=self.cd_sys)

    @classmethod
    def find_iodelay_clk_freq(cls, sys_clk_freq):
        # try to find IODELAYCTRL refclk as a multiple of sysclk so that a PLL config almost always is found
        fmin, fmax = cls.IODELAYCTRL_REFCLK_RANGE
        mul = 4
        while sys_clk_freq * mul < fmin:
            mul *= 2
        while sys_clk_freq * mul > fmax and mul >= 1:
            mul //= 2
        return sys_clk_freq * mul

# SoC ----------------------------------------------------------------------------------------------

class ZynqUSPS(Module):
    # For full address map see UG1085, ZynqUS+ TRM, Table 10-1
    _KB = 2**10
    _MB = 2**10 * _KB
    _GB = 2**10 * _MB
    PS_MEMORY_MAP = {
        'gp_lpd_master': [[
            # M_AXI_HPM0_LPD
            # (base, size)
            (0x8000_0000, 512*_MB),
        ]],
        'gp_fpd_master': [
            [  # M_AXI_HPM0_FPD regions
                (     0xa400_0000, 192*_MB),  # (32-bit), may be different (see TRM notes)
                (0x0004_0000_0000,   4*_GB),  # (36-bit)
                (0x0010_0000_0000, 224*_GB),  # (40-bit)
            ],
            [  # M_AXI_HPM1_FPD regions
                (     0xb000_0000, 256*_MB),  # (32-bit)
                (0x0005_0000_0000,   4*_GB),  # (36-bit)
                (0x0048_0000_0000, 224*_GB),  # (40-bit)
            ],
        ],
    }

    def __init__(self):
        self.params = {}
        # fpd/lpd = full/low power domain
        self.axi_gp_fpd_masters = []
        self.axi_gp_lpd_masters = []
        self.axi_gp_fpd_slaves  = []
        self.axi_gp_lpd_slaves  = []
        self.axi_acp_fpd_slaves  = []

    def add_axi_gp_fpd_master(self, **kwargs):  # MAXIGP0 - MAXIGP1
        return self._append_axi(attr='axi_gp_fpd_masters', maxn=2, name='MAXIGP{n}', **kwargs)

    def add_axi_gp_lpd_master(self, **kwargs):  # MAXIGP2
        return self._append_axi(attr='axi_gp_lpd_masters', maxn=1, name='MAXIGP2', **kwargs)

    def add_axi_gp_fpd_slave(self, **kwargs):  # SAXIGP0 - SAXIGP5
        return self._append_axi(attr='axi_gp_fpd_slaves', maxn=6, name='SAXIGP{n}', **kwargs)

    def add_axi_gp_lpd_slave(self, **kwargs):  # SAXIGP6
        return self._append_axi(attr='axi_gp_lpd_slaves', maxn=1, name='SAXIGP6', **kwargs)

    def add_axi_acp_fpd_slave(self, **kwargs):  # SAXIACP
        return self._append_axi(attr='axi_acp_fpd_slaves', maxn=1, name='SAXIACP', **kwargs)

    def _append_axi(self, attr, maxn, name, **kwargs):
        axis = getattr(self, attr)
        n = len(axis)
        assert n < maxn, 'Maximum number of AXIs for {} is {}'.format(attr, maxn)
        ax = self._add_axi(name=name.format(n=n), **kwargs)
        axis.append(ax)
        return ax

    def _add_axi(self, name, data_width=128, address_width=40, id_width=16):
        assert data_width <= 128
        assert address_width <= 40
        assert id_width <= 16
        ax = axi.AXIInterface(data_width=data_width, address_width=address_width, id_width=id_width)
        self.params.update({
            f'o_{name}ACLK':     ClockSignal(),
            # aw
            f'o_{name}AWVALID': ax.aw.valid,
            f'i_{name}AWREADY': ax.aw.ready,
            f'o_{name}AWADDR':  ax.aw.addr,
            f'o_{name}AWBURST': ax.aw.burst,
            f'o_{name}AWLEN':   ax.aw.len,
            f'o_{name}AWSIZE':  ax.aw.size[:3],  # need to match size exactly
            f'o_{name}AWID':    ax.aw.id,
            f'o_{name}AWLOCK':  ax.aw.lock[:1],  # need to match size exactly
            f'o_{name}AWPROT':  ax.aw.prot,
            f'o_{name}AWCACHE': ax.aw.cache,
            f'o_{name}AWQOS':   ax.aw.qos,
            # w
            f'o_{name}WVALID':  ax.w.valid,
            f'o_{name}WLAST':   ax.w.last,
            f'i_{name}WREADY':  ax.w.ready,
            # f'o_{name}WID':     ax.w.id,  # does not exist
            f'o_{name}WDATA':   ax.w.data,
            f'o_{name}WSTRB':   ax.w.strb,
            # b
            f'i_{name}BVALID':  ax.b.valid,
            f'o_{name}BREADY':  ax.b.ready,
            f'i_{name}BID':     ax.b.id,
            f'i_{name}BRESP':   ax.b.resp,
            # ar
            f'o_{name}ARVALID': ax.ar.valid,
            f'i_{name}ARREADY': ax.ar.ready,
            f'o_{name}ARADDR':  ax.ar.addr,
            f'o_{name}ARBURST': ax.ar.burst,
            f'o_{name}ARLEN':   ax.ar.len,
            f'o_{name}ARID':    ax.ar.id,
            f'o_{name}ARLOCK':  ax.ar.lock[:1],
            f'o_{name}ARSIZE':  ax.ar.size[:3],
            f'o_{name}ARPROT':  ax.ar.prot,
            f'o_{name}ARCACHE': ax.ar.cache,
            f'o_{name}ARQOS':   ax.ar.qos,
            # r
            f'i_{name}RVALID':  ax.r.valid,
            f'o_{name}RREADY':  ax.r.ready,
            f'i_{name}RLAST':   ax.r.last,
            f'i_{name}RID':     ax.r.id,
            f'i_{name}RRESP':   ax.r.resp,
            f'i_{name}RDATA':   ax.r.data,
        })
        return ax

    def do_finalize(self):
        self.specials += Instance('PS8', **self.params)

class SoC(common.RowHammerSoC):
    def __init__(self, **kwargs):
        min_rom = 0x9000
        if kwargs["integrated_rom_size"] < min_rom:
            kwargs["integrated_rom_size"] = min_rom

        super().__init__(**kwargs)

        if self.args.sim:
            return

        # SPD EEPROM I2C ---------------------------------------------------------------------------
        self.submodules.i2c = I2CMaster(self.platform.request("i2c"))
        self.add_csr("i2c")

        # ZynqUS+ PS -------------------------------------------------------------------------------
        self.submodules.ps = ZynqUSPS()

        # Configure PS->PL AXI
        # AXI(32) -> AXILite(32) -> WishBone(32) -> SoC Interconnect
        axi_ps = self.ps.add_axi_gp_fpd_master(data_width=32)

        axi_lite_ps = axi.AXILiteInterface(data_width=32, address_width=40)
        self.submodules += axi.AXI2AXILite(axi_ps, axi_lite_ps)

        # Use M_AXI_HPM0_FPD base address thaht will fit our whole address space (0x0004_0000_0000)
        base_address = None
        for base, size in self.ps.PS_MEMORY_MAP['gp_fpd_master'][0]:
            if size >= 2**30-1:
                base_address = base
                break
        assert base_address is not None

        def chunks(lst, n):
            for i in range(0, len(lst), n):
                yield lst[i:i + n]

        addr_str = '_'.join(chunks('{:012x}'.format(base_address), 4))
        self.logger.info("Connecting PS AXI master from PS address {}.".format(colorer('0x' + addr_str)))

        wb_ps = wishbone.Interface(adr_width=40-2)  # AXILite2Wishbone requires the same address widths
        self.submodules += axi.AXILite2Wishbone(axi_lite_ps, wb_ps, base_address=base_address)
        # silently ignores address bits above 30
        self.bus.add_master(name='ps_axi', master=wb_ps)

    def get_platform(self):
        return xilinx_zcu104.Platform()

    def get_crg(self):
        return CRG(self.platform, self.sys_clk_freq, iodelay_clk_freq=self.iodelay_clk_freq)

    def get_ddrphy(self):
        return usddrphy.USPDDRPHY(
            pads             = self.platform.request("ddram"),
            memtype          = "DDR4",
            sys_clk_freq     = self.sys_clk_freq,
            iodelay_clk_freq = self.iodelay_clk_freq)

    def get_sdram_ratio(self):
        return "1:4"

    def add_host_bridge(self):
        self.add_uartbone(name="serial", clk_freq=self.sys_clk_freq, baudrate=1e6, cd="uart")

    @property
    def iodelay_clk_freq(self):
        if not hasattr(self, '_iodelay_clk_freq'):
            if self.args.iodelay_clk_freq is None:
                self._iodelay_clk_freq = CRG.find_iodelay_clk_freq(float(self.args.sys_clk_freq))
            else:
                self._iodelay_clk_freq = self.args.iodelay_clk_freq
        return self._iodelay_clk_freq

# Build --------------------------------------------------------------------------------------------

def main():
    parser = common.ArgumentParser(
        description  = "LiteX SoC on ZCU104",
        sys_clk_freq = '125e6',
        module       = 'MTA4ATF51264HZ'
    )
    g = parser.add_argument_group(title="ZCU104")
    g.add_argument("--iodelay-clk-freq", type=float, help="Use given exact IODELAYCTRL reference clock frequency")
    vivado_build_args(g)
    args = parser.parse_args()

    soc_kwargs = common.get_soc_kwargs(args)
    soc = SoC(**soc_kwargs)

    target_name = 'zcu104'
    builder_kwargs = common.get_builder_kwargs(args, target_name=target_name)
    builder = Builder(soc, **builder_kwargs)
    build_kwargs = vivado_build_argdict(args) if not args.sim else {}

    common.run(args, builder, build_kwargs, target_name=target_name)

if __name__ == "__main__":
    main()
