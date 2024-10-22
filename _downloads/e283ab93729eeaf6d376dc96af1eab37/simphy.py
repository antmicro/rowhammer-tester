#
# This file is part of LiteDRAM.
#
# Copyright (c) 2021 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import PulseSynchronizer

from litex.soc.interconnect.csr import CSR

from litedram.phy.utils import delayed, Serializer, Deserializer, Latency
from litedram.phy.sim_utils import (SimPad, SimulationPads, SimSerDesMixin,
    SimpleCDC, SimpleCDCr, SimpleCDCWrap, SimpleCDCrWrap, AsyncFIFOXilinx7Wrap)
from litedram.phy.ddr5.basephy import DDR5PHY
from litedram.phy.ddr5.BasePHYOutput import BasePHYOutput


class DDR5SimulationPads(SimulationPads):
    def layout(self, databits=8, nranks=1, dq_dqs_ratio=8, with_sub_channels=False):
        common = [
            SimPad("ck_t", 1),
            SimPad("ck_c", 1),
            SimPad("reset_n", 1),
            SimPad("alert_n", 1),
        ]
        per_channel = [
            ('cs_n', nranks, False, -1),
            ('ca', 14, False, -1),
            ('par', 1, False, -1),
            ('dq', databits, True, dq_dqs_ratio),
            ('dm_n',  databits // dq_dqs_ratio, True, 1),
            ('dqs_t',  databits // dq_dqs_ratio, True, 1),
            ('dqs_c',  databits // dq_dqs_ratio, True, 1),
        ]
        channels_prefix = [""] if not with_sub_channels else ["A_", "B_"]
        return common + \
                [SimPad(prefix+name, size, io, gran) for prefix in channels_prefix for name, size, io, gran in per_channel]


class DDR5SimPHY(SimSerDesMixin, DDR5PHY):
    """DDR5 simulation PHY with direct 16:1 serializers

    For simulation purpose two additional "DDR" clock domains are requires.
    """
    def __init__(self, aligned_reset_zero=False, dq_dqs_ratio=8, nranks=1, with_sub_channels=False, databits=8, **kwargs):
        if dq_dqs_ratio == 8:
            pads = DDR5SimulationPads(databits=databits,
                                      nranks=nranks,
                                      dq_dqs_ratio=8,
                                      with_sub_channels=with_sub_channels)
        elif dq_dqs_ratio == 4:
            # databits length taken from DDR5 Tester
            pads = DDR5SimulationPads(databits=databits,
                                      nranks=nranks,
                                      dq_dqs_ratio=4,
                                      with_sub_channels=with_sub_channels)
        else:
            raise NotImplementedError(f"Unspupported DQ:DQS ratio: {dq_dqs_ratio}")

        self.submodules += pads
        SimpleCDC.set_register()
        SimpleCDCWrap.reset_latency()
        Serializer.set_xilinx()
        prefixes = [""] if not with_sub_channels else ["A_", "B_"]

        def cdc_any(target):
            def new_cdc(i):
                o = Signal()
                psync = PulseSynchronizer("sys", target)
                self.submodules += psync
                self.comb += [
                    psync.i.eq(i),
                    o.eq(psync.o),
                ]
                return o
            return new_cdc

        super().__init__(pads,
            ser_latency       = Latency(sys2x=Serializer.LATENCY+1),
            des_latency       = Latency(sys=(Deserializer.LATENCY-1 if aligned_reset_zero else Deserializer.LATENCY)),
            phytype           = "DDR5SimPHY",
            with_sub_channels = with_sub_channels,
            ca_domain         = "sys2x",
            dq_domain         = {prefix:"sys2x_90" for prefix in prefixes},
            wr_dqs_domain     = {prefix:"sys2x" for prefix in prefixes},
            per_pin_ca_domain = None,

            csr_ca_cdc        = cdc_any("sys2x"),
            csr_dq_rd_cdc     = {prefix: cdc_any("sys") for prefix in prefixes},
            csr_dq_wr_cdc     = {prefix: cdc_any("sys2x_90") for prefix in prefixes},
            csr_dqs_cdc       = {prefix: cdc_any("sys2x") for prefix in prefixes},

            out_CDC_CA_primitive_cls = AsyncFIFOXilinx7Wrap,
            ca_cdc_min_max_delay =
                (Latency(sys2x=AsyncFIFOXilinx7Wrap.LATENCY), Latency(sys2x=(AsyncFIFOXilinx7Wrap.WCL_LATENCY))),

            out_CDC_primitive_cls = AsyncFIFOXilinx7Wrap,
            wr_cdc_min_max_delay =
                (Latency(sys2x=AsyncFIFOXilinx7Wrap.LATENCY), Latency(sys2x=(AsyncFIFOXilinx7Wrap.LATENCY))),

            rd_extra_delay    = Latency(sys2x=2),
            **kwargs)

        # fake delays (make no sense in simulation, but sdram.c expects them)
        self.settings.read_leveling = True
        self.settings.delays = 1

        delay = lambda sig, cycles: delayed(self, sig, cycles=cycles)

        cs          = dict(clkdiv="sys2x", clk="sys4x_ddr")
        cmd         = dict(clkdiv="sys2x", clk="sys4x_ddr")
        ddr         = dict(clkdiv="sys2x", clk="sys4x_ddr")
        recv_ddr_90 = dict(clkdiv="sys", clk="sys4x_90_ddr")
        ddr_90      = dict(clkdiv="sys2x_90", clk="sys4x_90_ddr")

        # This configuration mimics Xilinx 7-series serdes behavior
        if aligned_reset_zero:
            ddr["reset_cnt"] = 0
            ddr["aligned"] = True
            cs["reset_cnt"] = 0
            cs["aligned"] = True
            cmd["reset_cnt"] = 0
            cmd["aligned"] = True

        # Clock is shifted 180 degrees to get rising edge in the middle of SDR signals.
        # To achieve that we send negated clock on clk (clk_p).
        cdc_ck_t = Signal(4)
        self.comb += cdc_ck_t.eq(self.clk_pattern&0xF)
        self.ser(i=cdc_ck_t, o=self.pads.ck_t, name='ck_t', **ddr)

        cdc_ck_c = Signal(4)
        self.comb += cdc_ck_c.eq(~(self.clk_pattern&0xF))
        self.ser(i=cdc_ck_c, o=self.pads.ck_c, name='ck_c', **ddr)

        reset_n = self.out.reset_n[:4]
        self.ser(i=reset_n, o=self.pads.reset_n, name='reset_n', **ddr)

        self.des(i=self.pads.alert_n, o=self.out.alert_n, name='alert_n', **ddr_90)

        for prefix in prefixes:

            # Command/address
            for it, (basephy_cs, pad) in enumerate(zip(getattr(self.out, prefix+'cs_n'),
                                                       getattr(self.pads, prefix+'cs_n'))):
                self.ser(i=basephy_cs[:4], o=pad, name=f'{prefix}cs_n_{it}', **cs)

            for it, (basephy_ca, pad) in enumerate(zip(getattr(self.out, prefix+'ca'),
                                                       getattr(self.pads, prefix+'ca'))):
                self.ser(i=basephy_ca[:4], o=pad, name=f'{prefix}ca{it}', **cmd)

            basephy_par = getattr(self.out, prefix+'par')
            pad = getattr(self.pads, prefix+'par')
            self.ser(i=basephy_par[:4], o=pad, name=f'{prefix}par', **cmd)

            # nibble to output mapping
            mult = dq_dqs_ratio//4
            # Tristate I/O (separate for simulation)
            for it in range(self.databits//dq_dqs_ratio):
                dqs_t_o = getattr(self.out, prefix+'dqs_t_o')[it*mult]
                self.ser(i=dqs_t_o[:4],
                         o=getattr(self.pads, prefix+'dqs_t_o')[it],
                         name=f'{prefix}dqs_t_o{it}', **ddr)
                self.des(o=getattr(self.out, prefix+'dqs_t_i')[it*mult],
                         i=getattr(self.pads, prefix+'dqs_t')[it],
                         name=f'{prefix}dqs_t_i{it}', reset_cnt=0, **recv_ddr_90)

                dqs_c_o = getattr(self.out, prefix+'dqs_c_o')[it*mult]
                self.ser(i=dqs_c_o[:4],
                         o=getattr(self.pads, prefix+'dqs_c_o')[it],
                         name=f'{prefix}dqs_c_o{it}', **ddr)
                self.des(o=getattr(self.out, prefix+'dqs_c_i')[it*mult],
                         i=getattr(self.pads, prefix+'dqs_c')[it],
                         name=f'{prefix}dqs_c_i{it}', reset_cnt=0, **recv_ddr_90)

                basephy_dm = getattr(self.out, prefix+'dm_n_o')[it*mult]
                delay_dm = Signal.like(basephy_dm)
                out_dm = Signal.like(basephy_dm)
                dq_domain = getattr(self.sync, "sys2x_90")
                dq_domain += delay_dm.eq(basephy_dm[1:4])
                dq_domain += out_dm.eq(Cat(delay_dm[:3], basephy_dm[0]))
                self.ser(i=out_dm[:4], o=getattr(self.pads, prefix+'dm_n_o')[it],
                         name=f'{prefix}dm_n_o{it}', **ddr_90)

                basephy_dm_i =  getattr(self.out, prefix+'dm_n_i')[it*mult]
                in_dm = Signal.like(basephy_dm_i)
                self.des(o=in_dm, i=getattr(self.pads, prefix+'dm_n')[it],
                         name=f'{prefix}dm_n_i{it}', **recv_ddr_90)
                delay_dm_i = Signal(2)
                self.sync += delay_dm_i.eq(in_dm[-2:])
                self.comb += basephy_dm_i.eq(Cat(delay_dm_i, in_dm[:-2]))

            for it in range(self.databits):
                basephy_dq = getattr(self.out, prefix+'dq_o')[it]
                delay_dq = Signal.like(basephy_dq)
                out_dq = Signal.like(basephy_dq)
                dq_domain = getattr(self.sync, "sys2x_90")
                dq_domain += delay_dq.eq(basephy_dq[1:4])
                dq_domain += out_dq.eq(Cat(delay_dq[:3], basephy_dq[0]))
                self.ser(i=out_dq[:4], o=getattr(self.pads, prefix+'dq_o')[it],
                         name=f'{prefix}dq_o{it}', **ddr_90)

                basephy_dq_i =  getattr(self.out, prefix+'dq_i')[it]
                self.des(o=basephy_dq_i, i=getattr(self.pads, prefix+'dq')[it],
                         name=f'{prefix}dq_i{it}', reset_cnt=0, **recv_ddr_90)

            # Output enable signals can be and should be serialized as well
            for strobe in range(databits//dq_dqs_ratio):
                out_dqs_t_oe = getattr(self.out, prefix+'dqs_oe')[strobe*mult]
                self.ser(i=out_dqs_t_oe[:4],
                         o=getattr(self.pads, prefix+'dqs_t_oe')[strobe],
                         name=f'{prefix}dqs_t_oe', **ddr)

                out_dqs_c_oe = getattr(self.out, prefix+'dqs_oe')[strobe*mult]
                self.ser(i=out_dqs_c_oe[:4],
                         o=getattr(self.pads, prefix+'dqs_c_oe')[strobe],
                         name=f'{prefix}dqs_c_oe', **ddr)

                basephy_dq_oe = getattr(self.out, prefix+'dq_oe')[strobe*mult]
                delay_dq_oe = Signal.like(basephy_dq_oe)
                out_dq_oe = Signal.like(basephy_dq_oe)
                dq_domain = getattr(self.sync, "sys2x_90")
                dq_domain += delay_dq_oe.eq(basephy_dq_oe[1:4])
                dq_domain += out_dq_oe.eq(Cat(delay_dq_oe[:3], basephy_dq_oe[0]))
                self.ser(i=out_dq_oe[:4],
                         o=getattr(self.pads, prefix+'dq_oe')[strobe],
                         name=f'{prefix}dq_oe', **ddr_90)

                self.ser(i=out_dq_oe[:4],
                         o=getattr(self.pads, prefix+'dm_n_oe')[strobe],
                         name=f'{prefix}dm_n_oe', **ddr_90)
