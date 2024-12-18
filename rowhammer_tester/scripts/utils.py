#!/usr/bin/env python3

import csv
import glob
import json
import os
import sys
import time
from collections import namedtuple
from functools import reduce
from operator import or_

from migen import log2_int

from rowhammer_tester.gateware.payload_executor import OpCode

# ###########################################################################


def discover_generated_files_dir():
    # Search for defs.csv file that should have been generated in build directory.
    # Assume that we are building in repo root.
    script_dir = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
    build_dir = os.path.normpath(os.path.join(script_dir, "..", "..", "build"))
    candidates = os.path.join(build_dir, "*", "defs.csv")
    results = glob.glob(candidates)
    if not results:
        raise ImportError(
            'Could not find "defs.csv". Make sure to run target generator (from'
            " rowhammer_tester/targets/) in the root directory of this repository."
        )
    elif len(results) > 1:
        if "TARGET" not in os.environ:
            raise ImportError(
                'More than one "defs.csv" file found. Set environmental variable'
                " TARGET to the name of the target to use (e.g. `export TARGET=arty`)."
            )
        gen_dir = os.path.join(build_dir, os.environ["TARGET"])
    else:
        gen_dir = os.path.dirname(results[0])

    sys.path.append(gen_dir)
    return gen_dir


GENERATED_DIR = discover_generated_files_dir()
print(f"Using generated target files in: {os.path.relpath(GENERATED_DIR)}")

# Import sdram_init.py
sys.path.append(GENERATED_DIR)
try:
    import sdram_init as sdram_init_defs
    from sdram_init import *  # noqa F403
except ModuleNotFoundError:
    print("WARNING: sdram_init not loaded")


def get_generated_file(name):
    # For getting csr.csv/analyzer.csv
    filename = os.path.join(GENERATED_DIR, name)
    if not os.path.isfile(filename):
        raise ImportError(f'Generated file "{name}" not found in directory "{GENERATED_DIR}"')
    return filename


def get_generated_defs():
    with open(get_generated_file("defs.csv"), newline="") as f:
        reader = csv.reader(f)
        return {name: value for name, value in reader}


class ReadonlySettings:
    def __init__(self, s):
        self._settings = s

    def __getattr__(self, name):
        val = self.__dict__["_settings"][name]
        if isinstance(val, dict):
            return ReadonlySettings(val)
        return val


def get_litedram_settings():
    with open(get_generated_file("litedram_settings.json")) as f:
        return ReadonlySettings(json.load(f))


def RemoteClient(*args, **kwargs):
    from litex import RemoteClient as _RemoteClient

    return _RemoteClient(csr_csv=get_generated_file("csr.csv"), *args, **kwargs)  # noqa B026


def litex_server():
    from litex.tools.litex_server import RemoteServer
    from litex.tools.remote.comm_udp import CommUDP

    defs = get_generated_defs()
    comm = CommUDP(server=defs["IP_ADDRESS"], port=int(defs["UDP_PORT"]))
    server = RemoteServer(comm, "127.0.0.1", 1234)
    server.open()
    server.start(4)


# ###########################################################################


def sdram_software_control(wb):
    reg_value = wb.regs.sdram_dfii_control.read()
    wb.regs.sdram_dfii_control.write(reg_value & (~dfii_control_sel))  # noqa F405
    if hasattr(wb.regs, "ddrphy_en_vtc"):
        wb.regs.ddrphy_en_vtc.write(0)


def sdram_hardware_control(wb):
    reg_value = wb.regs.sdram_dfii_control.read()
    wb.regs.sdram_dfii_control.write(reg_value | dfii_control_sel)  # noqa F405
    if hasattr(wb.regs, "ddrphy_en_vtc"):
        wb.regs.ddrphy_en_vtc.write(1)


def sdram_init(wb):
    sdram_software_control(wb)

    # we cannot check for the string "DFII_CONTROL" as done when generating C code,
    # so this is hardcoded for now
    # update: Hacky but works
    control_cmds = []
    with open(sdram_init_defs.__file__) as f:
        n = 0
        while True:
            line = f.readline()
            if not line:
                break
            line = line.strip().replace(" ", "")
            if len(line) and line[0] == "(":
                if line.find("_control_") > 0:
                    control_cmds.append(n)
                n = n + 1

    for i, (comment, a, ba, cmd, delay) in enumerate(init_sequence):  # noqa F405
        wb.regs.sdram_dfii_pi0_address.write(a)
        wb.regs.sdram_dfii_pi0_baddress.write(ba)
        if i in control_cmds:
            print("(ctl) " + comment)
            wb.regs.sdram_dfii_control.write(cmd)
        else:
            print("(cmd) " + comment)
            wb.regs.sdram_dfii_pi0_command.write(cmd)
            wb.regs.sdram_dfii_pi0_command_issue.write(1)
        time.sleep(0.01 + delay * 1e-5)

    sdram_hardware_control(wb)


# ###########################################################################


def compare(val, ref, fmt, nbytes=4):
    assert fmt in ["bin", "hex"]
    if fmt == "hex":
        n = nbytes * 2
        cmp = "==" if val == ref else "!="
        print(f"0x{val:0{n}x} {cmp} 0x{ref:0{n}x}")
    if fmt == "bin":
        n = nbytes * 8
        print(f"{val:0{n}b} xor {ref:0{n}b} = {val ^ ref:0{n}b}")


def memwrite(wb, data, base=0x40000000, burst=0xFF):
    for i in range(0, len(data), burst):
        wb.write(base + 4 * i, data[i : min(i + burst, len(data))])


def memread(wb, n, base=0x40000000, burst=0xFF):
    data = []
    for i in range(0, n, burst):
        data += wb.read(base + 4 * i, min(burst, n - i))
    return data


def memfill(wb, n, pattern=0xAAAAAAAA, **kwargs):
    memwrite(wb, [pattern] * n, **kwargs)


def memcheck(wb, n, pattern=0xAAAAAAAA, **kwargs):
    data = memread(wb, n, **kwargs)
    errors = [(i, w) for i, w in enumerate(data) if w != pattern]
    return errors


def memspeed(wb, n, **kwargs):
    def measure(fun, name):
        start = time.time()
        ret = fun(wb, n, **kwargs)
        elapsed = time.time() - start
        print(f"{name:5} speed: {(n * 4) / elapsed / 1e3:6.2f} KB/s ({elapsed:.1f} sec)")
        return ret

    measure(memfill, "Write")
    data = measure(memread, "Read")
    errors = [(i, w) for i, w in enumerate(data) if w != kwargs.get("pattern", 0xAAAAAAAA)]
    assert len(errors) == 0, len(errors)


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def word2byte(words, word_size=4):
    for w in words:
        for i in range(word_size):
            yield (w & (0xFF << 8 * i)) >> 8 * i


def memdump(data, base=0x40000000, chunk_len=16):
    def tochar(val):
        return chr(val) if 0x20 <= val <= 0x7E else "."

    data_bytes = list(word2byte(data))
    for i, chunk in enumerate(chunks(data_bytes, chunk_len)):
        b = " ".join(
            "{:2}".format(f"{chunk[i]:02x}" if i < len(chunk) else "") for i in range(chunk_len)
        )
        c = "".join(tochar(chunk[i]) if i < len(chunk) else " " for i in range(chunk_len))
        print(f"0x{base + chunk_len * i:08x}:  {b}  {c}")


def read_ident(wb) -> str:
    # Maximal identification info size is 256
    buildinfo = memread(wb, 256, wb.bases.identifier_mem)

    # Info is stored as a \0 terminated string
    # truncate it
    string_term_idx = buildinfo.index(0)
    buildinfo = buildinfo[:string_term_idx]

    # Decode ASCII characters
    return bytes(buildinfo).decode("ascii")


################################################################################


class DRAMAddressConverter:
    def __init__(
        self,
        *,
        colbits,
        rowbits,
        bankbits,
        address_align,
        dram_port_width,
        address_mapping="ROW_BANK_COL",
    ):
        self.colbits = colbits
        self.rowbits = rowbits
        self.bankbits = bankbits
        self.address_align = address_align
        self.address_mapping = address_mapping
        self.dram_port_width = dram_port_width
        assert self.address_mapping == "ROW_BANK_COL"

    @classmethod
    def load(cls):
        settings = get_litedram_settings()
        if settings.phy.memtype == "SDR":
            burst_length = settings.phy.nphases
        else:
            from litedram.common import burst_lengths

            burst_length = burst_lengths[settings.phy.memtype]
        address_align = log2_int(burst_length)
        return cls(
            colbits=settings.geom.colbits,
            rowbits=settings.geom.rowbits,
            bankbits=settings.geom.bankbits,
            address_align=address_align,
            address_mapping=settings.address_mapping,
            dram_port_width=settings.phy.nphases * settings.phy.dfi_databits,
        )

    def _encode(self, bank, row, col):
        assert bank < 2**self.bankbits
        assert col < 2**self.colbits
        assert row < 2**self.rowbits

        def masked(value, width, offset):
            masked = value & (2**width - 1)
            assert masked == value, "Value larger than value bit-width"
            return masked << offset

        return reduce(
            or_,
            [
                masked(row, self.rowbits, self.bankbits + self.colbits),
                masked(bank, self.bankbits, self.colbits),
                masked(col, self.colbits, 0),
            ],
        )

    def _get_bus_shift(self, bus_width):
        addr_shift = log2_int(self.dram_port_width // bus_width)
        bus_shift = log2_int(bus_width // 8)
        shift = addr_shift + bus_shift - self.address_align
        return shift

    def encode_bus(self, *, bank, row, col, base=0x40000000, bus_width=32):
        shift = self._get_bus_shift(bus_width)
        address = self._encode(bank, row, col)
        if shift > 0:
            address <<= shift
        else:
            address >>= -shift
        return base + address

    def encode_dma(self, *, bank, row, col):
        address = self._encode(bank, row, col)
        return address >> self.address_align

    def _decode(self, address):
        def extract(value, width, offset):
            mask = 2**width - 1
            return (value & (mask << offset)) >> offset

        row = extract(address, self.rowbits, self.bankbits + self.colbits)
        bank = extract(address, self.bankbits, self.colbits)
        col = extract(address, self.colbits, 0)

        return bank, row, col

    def decode_bus(self, address, base=0x40000000, bus_width=32):
        address -= base
        shift = -1 * self._get_bus_shift(bus_width)
        if shift > 0:
            address <<= shift
        else:
            address >>= -shift
        return self._decode(address)

    def decode_dma(self, address):
        return self._decode(address << self.address_align)


# ######################### HW (accel) memory utils #############################


def _progress(current, max_count, bar_w=40, last=False, name="Progress", opt=None):
    s = "{name}: [{bar:{bw}}] {cur:{n}} / {max:{n}}{opt}".format(
        name=name,
        cur=current,
        max=max_count,
        n=len(str(max_count)),
        bar="=" * int(current / max_count * bar_w),
        bw=bar_w,
        opt="" if opt is None else f" ({opt})",
    )
    print(s + " ", end="\n" if last else "\r")


#
# wb - remote handle
# offset - memory offset in bytes (modulo 16)
# size - memory size in bytes (modulo 16)
# patterns - pattern to fill memory
def hw_memset(wb, offset, size, patterns, dbg=False):
    # we are limited to multiples of DMA data width
    settings = get_litedram_settings()
    dma_data_width = settings.phy.dfi_databits * settings.phy.nphases
    nbytes = dma_data_width // 8

    assert size % nbytes == 0, f"DMA data width is {dma_data_width} bits"
    assert len(patterns) == 1  # FIXME: Support more patterns

    pattern = patterns[0] & 0xFFFFFFFF

    if dbg:
        print(f"hw_memset: offset: 0x{offset:08x}, size: 0x{size:08x}, pattern: 0x{pattern:08x}")

    assert wb.regs.writer_ready.read() == 1

    # Unmask whole address space. TODO: Unmask only part of it?
    wb.regs.writer_mem_mask.write(0xFFFFFFFF)

    # FIXME: Support more patterns
    wb.write(wb.mems.writer_pattern_data.base, [pattern] * (nbytes // 4))  # pattern is 32-bit
    wb.write(wb.mems.writer_pattern_addr.base, offset // nbytes)
    wb.write(wb.mems.reader_pattern_data.base, [pattern] * (nbytes // 4))  # pattern is 32-bit
    wb.write(wb.mems.reader_pattern_addr.base, offset // nbytes)
    # Unmask just one pattern/offset (will always take data/addr from address 0)
    wb.regs.writer_data_mask.write(0x00000000)

    count = size // nbytes
    wb.regs.writer_count.write(count)

    # Start module
    wb.regs.writer_start.write(1)

    # FIXME: Support progress
    while True:
        if wb.regs.writer_ready.read():
            break
        _progress(wb.regs.writer_done.read(), count)
        time.sleep(10e-3)  # 10 ms
    _progress(wb.regs.writer_done.read(), count, last=True)


BISTError = namedtuple("BISTError", ["offset", "data", "expected"])


def hw_memtest(wb, offset, size, patterns, dbg=False):
    # we are limited to multiples of DMA data width
    settings = get_litedram_settings()
    dma_data_width = settings.phy.dfi_databits * settings.phy.nphases
    nbytes = dma_data_width // 8

    assert size % nbytes == 0, f"DMA data width is {dma_data_width} bits"
    assert len(patterns) == 1  # FIXME: Support more patterns

    pattern = patterns[0] & 0xFFFFFFFF

    if dbg:
        print(f"hw_memtest: offset: 0x{offset:08x}, size: 0x{size:08x}, pattern: 0x{pattern:08x}")

    # Flush error fifo
    wb.regs.reader_skip_fifo.write(1)
    time.sleep(0.1)
    # Enable error FIFO
    wb.regs.reader_skip_fifo.write(0)

    assert wb.regs.reader_ready.read() == 1

    # Unmask whole address space. TODO: Unmask only part of it?
    wb.regs.reader_mem_mask.write(0xFFFFFFFF)

    # FIXME: Support more patterns
    wb.write(wb.mems.writer_pattern_data.base, [pattern] * (nbytes // 4))  # pattern is 32-bit
    wb.write(wb.mems.writer_pattern_addr.base, offset // nbytes)
    wb.write(wb.mems.reader_pattern_data.base, [pattern] * (nbytes // 4))  # pattern is 32-bit
    wb.write(wb.mems.reader_pattern_addr.base, offset // nbytes)
    # Unmask just one pattern/offset (will always take data/addr from address 0)
    wb.regs.reader_data_mask.write(0x00000000)

    count = size // nbytes
    wb.regs.reader_count.write(count)

    wb.regs.reader_start.write(1)

    errors = []

    def progress(last=False):
        _progress(wb.regs.reader_done.read(), count, last=last, opt=f"Errors: {len(errors)}")

    # Read unmatched offset
    def append_errors(wb, err):
        while wb.regs.reader_error_ready.read():
            err.append(
                BISTError(
                    offset=wb.regs.reader_error_offset.read(),
                    data=wb.regs.reader_error_data.read(),
                    expected=wb.regs.reader_error_expected.read(),
                )
            )
            wb.regs.reader_error_continue.write(1)
            progress()

    # FIXME: Support progress
    while True:
        if wb.regs.reader_ready.read():
            break
        append_errors(wb, errors)
        _progress(wb.regs.reader_done.read(), count)
        progress()
        time.sleep(10e-3)  # !0 ms
    progress(last=True)

    # Make sure we read all errors
    append_errors(wb, errors)

    assert wb.regs.reader_ready.read() == 1
    assert wb.regs.reader_error_ready.read() == 0

    if dbg:
        print(f"hw_memtest: errors: {len(errors):d}")

    return errors


# Inversion_tuple has two elements: divisor and mask
def setup_inverters(wb, divisor, mask):
    assert (divisor & (divisor - 1)) == 0, "Divisor must be power of 2"
    wb.regs.writer_inverter_divisor_mask.write(divisor - 1)
    wb.regs.reader_inverter_divisor_mask.write(divisor - 1)
    wb.regs.writer_inverter_selection_mask.write(mask)
    wb.regs.reader_inverter_selection_mask.write(mask)


def get_expected_execution_cycles(payload):
    cycles = 0
    for i, instr in enumerate(payload):
        cycles += 1
        if instr.op_code == OpCode.NOOP and instr.timeslice == 0:  # STOP
            break
        elif instr.op_code == OpCode.LOOP:
            # there should be no STOP or LOOP instructions inside loop body
            body = payload[i - instr.jump : i]
            cycles += instr.count * sum(ii.timeslice for ii in body)
        else:
            # -1 because we've already included 1 cycle for this instruction
            cycles += instr.timeslice - 1
    return cycles


def execute_payload(wb, payload):
    print("\nTransferring the payload ...")
    memwrite(wb, payload, base=wb.mems.payload.base)

    def ready():
        status = wb.regs.payload_executor_status.read()
        return (status & 1) != 0

    # if refresh is enabled we will consider tracking progress of dfi_switch_at_refresh
    refresh_enabled = (
        hasattr(wb.regs, "controller_settings_refresh")
        and wb.regs.controller_settings_refresh.read()
    )

    def check_refresh_at(force=False):
        at = wb.regs.dfi_switch_at_refresh.read()
        # if at_refresh is not zero, then dfi switch will be blocked until refresh count is reached
        if at != 0:
            wb.regs.dfi_switch_refresh_update.write(1)
            now = wb.regs.dfi_switch_refresh_count.read()
            if force or at >= now:
                print(f"\rWaiting for refresh, remaining {at - now:10} ...", end=" ")
            if at < now:
                return True
        return False

    print("\nExecuting ...")
    assert ready()

    start = time.time()
    start_transition = None
    wb.regs.payload_executor_start.write(1)

    transitioned = False
    first = True

    while not ready():
        if refresh_enabled:
            # show progress of waiting for transition at concrete refresh command
            prev = transitioned
            transitioned = check_refresh_at()
            if not prev and transitioned:
                start_transition = time.time()
                check_refresh_at(force=True)
                print("Transition registered")
                if first:
                    print(
                        "WARNING: possibly switching refresh number set to value"
                        " smaller than current count"
                    )
        time.sleep(0.001)
        first = False

    finished = time.time()
    print(f"\nTotal elapsed time: {(finished - start) * 1e3:.3f} ms")
    if start_transition is not None:
        print(f"Registered execution time: {(finished - start_transition) * 1e3:.3f} ms\n")


def validate_keys(config_dict, valid_keys_set):
    for key in config_dict:
        if key not in valid_keys_set:
            print(f"Invalid key: {key}")
            return False
        return True


# ###############################################################################


def i2c_read(wb, slave_addr, reg_addr, length, send_stop=True, reg_addr_size=1):
    w_state = wb.regs.i2c_i2c_worker_write_fifo_state.read()
    w_depth = w_state & 0xFF
    if length + 3 + reg_addr_size > w_depth:
        error_msg = (
            f"Requested read length({length}) exceeds the number of available entries"
            f" in the I2C Worker FIFO({w_depth - 3 - reg_addr_size}"
        )
        raise ValueError(error_msg)
    wb.regs.i2c_i2c_worker_i2c_ctrl.write(0)
    wb.regs.i2c_worker.write(1)
    wb.regs.i2c_i2c_worker_fifos_access_port.write(
        slave_addr << 1 | 1 << 8 | 1 << 16 | 1 << 17 | 1 << 20
    )
    for i in range(reg_addr_size):
        wb.regs.i2c_i2c_worker_fifos_access_port.write(
            ((reg_addr >> (8 * i)) & 0xFF) | 1 << 8 | 1 << 17 | 1 << 20
        )
    if send_stop:
        wb.regs.i2c_i2c_worker_fifos_access_port.write(1 << 18 | 1 << 20)
    wb.regs.i2c_i2c_worker_fifos_access_port.write(
        slave_addr << 1 | 1 | 1 << 8 | 1 << 16 | 1 << 17 | 1 << 20
    )
    discard_reads = 2 + reg_addr_size
    w_state = wb.regs.i2c_i2c_worker_write_fifo_state.read()
    w_depth = w_state & 0xFF
    w_entries = w_state >> 8
    sent = 0
    for i in range(min(w_depth - w_entries, length)):
        flag = i == (length - 1)
        wb.regs.i2c_i2c_worker_fifos_access_port.write(
            0xFF | flag << 8 | 1 << 17 | flag << 18 | flag << 19 | (not flag) << 20
        )
        sent += 1
    wb.regs.i2c_i2c_worker_start.write(1)

    ret = []
    while len(ret) < length:
        fsm_state = wb.regs.i2c_i2c_worker_i2c_state.read() >> 8
        if fsm_state == I2CState.ABORT:
            print("Aborted")
            wb.regs.i2c_i2c_worker_i2c_ctrl.write(0x100)  # Reset FSM
            r_state = wb.regs.i2c_i2c_worker_read_fifo_state.read()
            r_entries = r_state >> 8
            for _ in range(r_entries):
                resp = wb.regs.i2c_i2c_worker_fifos_access_port.read()

            wb.regs.i2c_i2c_worker_i2c_ctrl.write(0x1)  # Setup for FIFO clear
            wb.regs.i2c_i2c_worker_start.write(1)  # Clear FIFOs
            while not (wb.regs.i2c_i2c_worker_i2c_state.read() & 1):
                time.sleep(0.001)
            ret = None
            break
        w_state = wb.regs.i2c_i2c_worker_write_fifo_state.read()
        w_depth = w_state & 0xFF
        w_entries = w_state >> 8
        for _ in range(min(length - sent, w_depth - w_entries)):
            flag = sent == (length - 1)
            wb.regs.i2c_i2c_worker_fifos_access_port.write(
                0xFF | flag << 8 | 1 << 17 | flag << 18 | flag << 19 | (not flag) << 20
            )
            sent += 1
        r_state = wb.regs.i2c_i2c_worker_read_fifo_state.read()
        r_entries = r_state >> 8
        i = 0
        while i < r_entries and discard_reads > 0:
            resp = wb.regs.i2c_i2c_worker_fifos_access_port.read()
            discard_reads -= 1
            i += 1
        if sent == length:
            for _ in range(r_entries - i):
                resp = wb.regs.i2c_i2c_worker_fifos_access_port.read()
                ret.append(resp & 0xFF)
        time.sleep(0.001)
    while not (wb.regs.i2c_i2c_worker_i2c_state.read() & 1):
        time.sleep(0.001)
    wb.regs.i2c_worker.write(0)
    return ret


def i2c_write(wb, slave_addr, reg_addr, data=None, reg_addr_size=1):
    if data is None:
        data = list()
    length = len(data)
    w_state = wb.regs.i2c_i2c_worker_write_fifo_state.read()
    w_depth = w_state & 0xFF
    if length + 1 + reg_addr_size > w_depth:
        error_msg = (
            f"Requested write length({length}) exceeds the number of available entries"
            f" in the I2C Worker FIFO({w_depth - 1 - reg_addr_size}"
        )
        raise ValueError(error_msg)
    wb.regs.i2c_i2c_worker_i2c_ctrl.write(0)
    wb.regs.i2c_worker.write(1)
    wb.regs.i2c_i2c_worker_fifos_access_port.write(
        slave_addr << 1 | 1 << 8 | 1 << 16 | 1 << 17 | 1 << 20
    )
    for i in range(reg_addr_size):
        wb.regs.i2c_i2c_worker_fifos_access_port.write(
            ((reg_addr >> (8 * i)) & 0xFF) | 1 << 8 | 1 << 17 | 1 << 20
        )
    discard_reads = 1 + reg_addr_size
    w_state = wb.regs.i2c_i2c_worker_write_fifo_state.read()
    w_depth = w_state & 0xFF
    w_entries = w_state >> 8
    sent = 0
    for _ in range(min(w_depth - w_entries, length)):
        flag = sent == (length - 1)
        wb.regs.i2c_i2c_worker_fifos_access_port.write(
            data[sent] | flag << 8 | 1 << 17 | flag << 18 | flag << 19 | (not flag) << 20
        )
        sent += 1
    wb.regs.i2c_i2c_worker_start.write(1)

    ret = []
    while len(ret) < length:
        fsm_state = wb.regs.i2c_i2c_worker_i2c_state.read() >> 8
        if fsm_state == I2CState.ABORT:
            print("Aborted")
            wb.regs.i2c_i2c_worker_i2c_ctrl.write(0x100)  # Reset FSM
            r_state = wb.regs.i2c_i2c_worker_read_fifo_state.read()
            r_entries = r_state >> 8
            for _ in range(r_entries):
                resp = wb.regs.i2c_i2c_worker_fifos_access_port.read()

            wb.regs.i2c_i2c_worker_i2c_ctrl.write(0x1)  # Setup for FIFO clear
            wb.regs.i2c_i2c_worker_start.write(1)  # Clear FIFOs
            while not (wb.regs.i2c_i2c_worker_i2c_state.read() & 1):
                time.sleep(0.001)
            break
        w_state = wb.regs.i2c_i2c_worker_write_fifo_state.read()
        w_depth = w_state & 0xFF
        w_entries = w_state >> 8
        for _ in range(min(length - sent, w_depth - w_entries)):
            flag = sent == (length - 1)
            wb.regs.i2c_i2c_worker_fifos_access_port.write(
                data[sent] | flag << 8 | 1 << 17 | flag << 18 | flag << 19 | (not flag) << 20
            )
            sent += 1
        r_state = wb.regs.i2c_i2c_worker_read_fifo_state.read()
        r_entries = r_state >> 8
        for _ in range(r_entries):
            resp = wb.regs.i2c_i2c_worker_fifos_access_port.read()
            if discard_reads > 0:
                discard_reads -= 1
                continue
            ret.append(resp & 0xFF)
        time.sleep(0.001)
    while not (wb.regs.i2c_i2c_worker_i2c_state.read() & 1):
        time.sleep(0.001)
    wb.regs.i2c_worker.write(0)
    return len(ret)


def i2c_poll(wb, slave_addr):
    wb.regs.i2c_i2c_worker_fifos_access_port.write(
        slave_addr << 1 | 1 << 8 | 1 << 16 | 1 << 17 | 1 << 18 | 1 << 19
    )
    wb.regs.i2c_worker.write(1)
    wb.regs.i2c_i2c_worker_start.write(1)
    wb.regs.i2c_worker.write(0)
    while not (wb.regs.i2c_i2c_worker_i2c_state.read() & 1):
        time.sleep(0.001)
    resp = wb.regs.i2c_i2c_worker_fifos_access_port.read()
    if (resp & 0x100) == 0:
        return True
    wb.regs.i2c_i2c_worker_fifos_access_port.write(slave_addr << 1 | 1 | 1 << 8 | 1 << 16 | 1 << 17)
    wb.regs.i2c_i2c_worker_fifos_access_port.write(0xFF | 1 << 8 | 1 << 17 | 1 << 18 | 1 << 19)
    wb.regs.i2c_worker.write(1)
    wb.regs.i2c_i2c_worker_start.write(1)
    wb.regs.i2c_worker.write(0)
    while not (wb.regs.i2c_i2c_worker_i2c_state.read() & 1):
        time.sleep(0.001)
    resp = wb.regs.i2c_i2c_worker_fifos_access_port.read()
    wb.regs.i2c_i2c_worker_fifos_access_port.read()
    if (resp & 0x100) == 0:
        return True
    return False


# ###############################################################################

# Open a remote connection in an interactive session (e.g. when sourced as `ipython -i <thisfile>`)
if __name__ == "__main__":
    if bool(getattr(sys, "ps1", sys.flags.interactive)):
        wb = RemoteClient()
        wb.open()
        print("Board info:", read_ident(wb))
