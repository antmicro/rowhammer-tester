import unittest
from collections import namedtuple
from enum import IntEnum

from litedram.common import PhySettings
from litedram.core import LiteDRAMCore
from litedram.core.controller import ControllerSettings
from litedram.modules import MT60B2G8HB48B
from litedram.phy import dfi
from litex.gen.sim import passive, run_simulation
from litex.soc.integration.doc import AutoDoc, ModuleDoc
from litex.soc.interconnect.csr import AutoCSR, CSRStorage
from migen import Module, Signal

from rowhammer_tester.gateware.payload_executor import DFISwitch, SyncableRefresher


class OpCode(IntEnum):
    NOOP = 0
    ACT = 1
    READ = 2
    WRITE = 3
    PRE_ALL = 4
    PRE = 5
    REF = 6


DDR5_DFI_COMMANDS = {
    OpCode.NOOP: dict(cmd_length=5, cmd=0x1F, phase_count=1),
    OpCode.ACT: dict(cmd_length=2, cmd=0x0, phase_count=2),
    OpCode.READ: dict(cmd_length=5, cmd=0x1D, phase_count=2),
    OpCode.WRITE: dict(cmd_length=5, cmd=0xD, phase_count=2),
    OpCode.PRE_ALL: dict(cmd_length=5, cmd=0xB, phase_count=1),
    OpCode.PRE: dict(cmd_length=5, cmd=0x1B, phase_count=1),
    OpCode.REF: dict(cmd_length=5, cmd=0x13, phase_count=1),
}


class DDR5DFICmd(namedtuple("Cmd", ["cs", "phase_cnt", "phase_adr"])):
    @property
    def op_code(self):
        if self.cs == 0:
            return OpCode.NOOP
        for op, desc in DDR5_DFI_COMMANDS.items():
            mask = 2 ** desc["cmd_length"] - 1
            if self.phase_cnt == desc["phase_count"] and (self.phase_adr & mask) == desc["cmd"]:
                return op
        assert False


HistoryEntry = namedtuple("HistoryEntry", ["time", "phase", "cmd"])


class PayloadExecutorDDR5DUT(Module):
    def __init__(self, with_refresh=True):
        class _PhyStub:
            def __init__(self):
                # Values taken from S7PHY
                self.bankbits = 8
                self.addressbits = 18
                self.settings = PhySettings(
                    address_lines=14,
                    bitslips=0,
                    cl=22,
                    cmd_delay=None,
                    cmd_latency=2,
                    cwl=20,
                    databits=8,
                    delays=0,
                    dfi_databits=16,
                    direct_control=False,
                    masked_write=False,
                    memtype="DDR5",
                    min_read_latency=2,
                    min_write_latency=0,
                    nibbles=2,
                    nphases=4,
                    nranks=1,
                    phytype="PHY_STUB",
                    rdphase=0,
                    read_latency=29,
                    read_leveling=False,
                    soc_freq=200000000,
                    strobes=1,
                    t_cmd_lat=0,
                    t_ctrl_delay=10,
                    t_parin_lat=0,
                    t_phy_rdcsgap=0,
                    t_phy_rdcslat=0,
                    t_phy_rdlat=0,
                    t_phy_wrcsgap=0,
                    t_phy_wrcslat=0,
                    t_phy_wrdata=0,
                    t_phy_wrlat=0,
                    t_rddata_en=0,
                    with_address_odelay=False,
                    with_alert=False,
                    with_clock_odelay=False,
                    with_idelay=False,
                    with_odelay=False,
                    with_per_dq_idelay=False,
                    with_sub_channels=False,
                    write_dq_dqs_training=False,
                    write_latency=0,
                    write_latency_calibration=False,
                    write_leveling=False,
                    wrphase=0,
                )
                self.dfi = dfi.Interface(14, 1, 1, 16, nphases=4, with_sub_channels=False)

        phy_stub = _PhyStub()
        module = MT60B2G8HB48B(clk_freq=int(100e6), rate="1:4")

        self.refresher_reset = Signal()

        class ControllerDynamicSettings(Module, AutoCSR, AutoDoc, ModuleDoc):
            """Allows to change LiteDRAMController behaviour at runtime"""

            def __init__(self):
                self.refresh = CSRStorage(
                    reset=1, description="Enable/disable Refresh commands sending"
                )

        self.submodules.controller_settings = ControllerDynamicSettings()
        controller_settings = ControllerSettings()
        controller_settings.with_auto_precharge = True
        controller_settings.with_refresh = self.controller_settings.refresh.storage
        controller_settings.refresh_cls = SyncableRefresher
        controller_settings.cmd_buffer_buffered = True
        self.submodules.mc = LiteDRAMCore(
            phy=phy_stub,
            module=module,
            clk_freq=int(100e6),
            controller_settings=controller_settings,
        )
        self.mc_port = self.mc.crossbar.get_port()
        self.submodules.dfi_switch = DFISwitch(
            with_refresh=with_refresh,
            dfii=self.mc.dfii,
            refresher_reset=self.refresher_reset,
            memtype="DDR5",
        )

        self.dfi_history: list[HistoryEntry] = []
        self.runtime_cycles = 0  # time when memory controller is disconnected
        self.execution_cycles = 0  # time when actually executing the payload

    def get_generators(self):
        return [self.dfi_monitor()]

    @passive
    def dfi_monitor(self, dfi=None):
        if dfi is None:
            dfi = self.mc.dfii.master
        time = 0
        while True:
            for i, phase in enumerate(dfi.phases):
                entry = None
                addr = yield phase.address
                cs = 1 - (yield phase.cs_n[0])
                for _op, desc in DDR5_DFI_COMMANDS.items():
                    mask = 2 ** desc["cmd_length"] - 1
                    if cs == 1 and (addr & mask) == desc["cmd"]:
                        cmd = DDR5DFICmd(cs=cs, phase_cnt=desc["phase_count"], phase_adr=addr)
                        entry = HistoryEntry(time=time, phase=i, cmd=cmd)
                        break
                else:
                    cmd = DDR5DFICmd(cs=cs, phase_cnt=desc["phase_count"], phase_adr=addr)
                    entry = HistoryEntry(time=time, phase=i, cmd=cmd)

                assert entry is not None, f"Unknown DFI command: address={addr}, cs={cs}"
                if entry.cmd.op_code != OpCode.NOOP:  # omit NOOPs
                    self.dfi_history.append(entry)
            yield
            time += 1


class TestRefreshCounterDDR5(unittest.TestCase):
    def run_payload(self, dut, test_generators, **kwargs):
        def generator(dut):
            yield dut.mc.dfii._control.fields.mode_2n.eq(0)
            yield dut.mc.dfii._control.fields.reset_n.eq(1)

        run_simulation(
            dut,
            [generator(dut), *dut.get_generators(), *test_generators],
            clocks={"sys": 10},
            **kwargs,
        )

    def assert_history(self, history, op_codes):
        history_ops = [entry.cmd.op_code for entry in history]
        self.assertEqual(history_ops, op_codes)

    def test_counter_no_traffic(self):
        dut = PayloadExecutorDDR5DUT()

        def idle_generator(dut):
            for _ in range(int(100e6 * 62.4e-6)):
                yield
            self.assertEqual((yield dut.dfi_switch.refresh_counter.counter), 0x10)

        self.run_payload(
            dut, test_generators=[idle_generator(dut)], vcd_name="test_counter_no_traffic.vcd"
        )
        op_codes = [OpCode.PRE_ALL, OpCode.REF] * 16
        self.assert_history(dut.dfi_history, op_codes)

    def test_counter_no_traffic_no_refresh(self):
        dut = PayloadExecutorDDR5DUT()

        def idle_generator(dut):
            yield from dut.controller_settings.refresh.write(0)
            for _ in range(int(100e6 * 62.4e-6) - 1):
                yield
            self.assertEqual((yield dut.dfi_switch.refresh_counter.counter), 0x0)

        self.run_payload(
            dut,
            test_generators=[idle_generator(dut)],
            vcd_name="test_counter_no_traffic_no_refresh.vcd",
        )
        op_codes = []
        self.assert_history(dut.dfi_history, op_codes)

    def test_counter_with_traffic(self):
        dut = PayloadExecutorDDR5DUT()

        def traffic_generator(dut):
            reduce_refs = 0
            # Wait some time before access
            for _ in range(100):
                reduce_refs += 1
                yield
            yield dut.mc_port.cmd.valid.eq(1)
            yield dut.mc_port.cmd.first.eq(1)
            yield dut.mc_port.cmd.last.eq(1)
            yield dut.mc_port.cmd.we.eq(0)
            yield dut.mc_port.cmd.addr.eq(0x130 << 12)
            reduce_refs += 1
            yield
            while (yield dut.mc_port.cmd.ready) == 0:
                reduce_refs += 1
                yield
            yield dut.mc_port.cmd.valid.eq(0)
            for _ in range(int(100e6 * 62.4e-6) - reduce_refs):
                yield
            self.assertEqual((yield dut.dfi_switch.refresh_counter.counter), 0x10)

        self.run_payload(
            dut, test_generators=[traffic_generator(dut)], vcd_name="test_counter_with_traffic.vcd"
        )
        op_codes = [OpCode.PRE_ALL, OpCode.REF, OpCode.ACT, OpCode.READ] + [
            OpCode.PRE_ALL,
            OpCode.REF,
        ] * 15
        self.assert_history(dut.dfi_history, op_codes)

    def test_counter_with_traffic_no_refresh(self):
        dut = PayloadExecutorDDR5DUT()

        def traffic_generator(dut):
            reduce_refs = 0
            reduce_refs += 1
            yield from dut.controller_settings.refresh.write(0)
            # Wait some time before access
            for _ in range(100):
                reduce_refs += 1
                yield
            yield dut.mc_port.cmd.valid.eq(1)
            yield dut.mc_port.cmd.first.eq(1)
            yield dut.mc_port.cmd.last.eq(1)
            yield dut.mc_port.cmd.we.eq(0)
            yield dut.mc_port.cmd.addr.eq(0x130 << 12)
            reduce_refs += 1
            yield
            while (yield dut.mc_port.cmd.ready) == 0:
                reduce_refs += 1
                yield
            yield dut.mc_port.cmd.valid.eq(0)
            for _ in range(int(100e6 * 62.4e-6) - reduce_refs):
                yield
            self.assertEqual((yield dut.dfi_switch.refresh_counter.counter), 0x0)

        self.run_payload(
            dut,
            test_generators=[traffic_generator(dut)],
            vcd_name="test_counter_with_traffic_no_refresh.vcd",
        )
        op_codes = [OpCode.ACT, OpCode.READ]
        self.assert_history(dut.dfi_history, op_codes)
