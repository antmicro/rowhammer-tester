from math import ceil
from rowhammer_tester.gateware.payload_executor import Encoder, OpCode, Decoder
from rowhammer_tester.scripts.utils import (get_expected_execution_cycles, DRAMAddressConverter)
import sys


# returns the number of refreshes issued
def encode_one_loop(
        *, unrolled, rolled, row_sequence, timings, encoder, bank, rank, refresh_op, payload):
    tras = timings.tRAS
    trp = timings.tRP
    trefi = timings.tREFI
    trfc = timings.tRFC
    local_refreshes = 1
    payload.append(encoder.I(refresh_op, timeslice=trfc))
    # Accumulate an extra cycle for the jump at the end to be conservative
    accum = trfc + 1
    for idx in range(unrolled):
        for row in row_sequence:
            if accum + tras + trp > trefi:
                payload.append(encoder.I(refresh_op, timeslice=trfc))
                # Invariant: time between the beginning of two refreshes
                # is is less than tREFI.
                accum = trfc
                local_refreshes += 1
            accum += tras + trp
            payload.extend(
                [
                    encoder.I(
                        OpCode.ACT,
                        timeslice=tras,
                        address=encoder.address(bank=bank, row=row, rank=rank)),
                    encoder.I(
                        OpCode.PRE, timeslice=trp, address=encoder.address(col=1 << 10,
                                                                           rank=rank)),  # all
                ])
    jump_target = 2 * unrolled * len(row_sequence) + local_refreshes
    assert jump_target < 2**Decoder.LOOP_JUMP
    payload.append(encoder.I(OpCode.LOOP, count=rolled, jump=jump_target))

    return local_refreshes * (rolled + 1)


def encode_long_loop(*, unrolled, rolled, **kwargs):
    refreshes = 0
    # fill payload so that we have >= desired read_count
    count_max = 2**Decoder.LOOP_COUNT - 1
    n_loops = ceil(rolled / (count_max + 1))

    for outer_idx in range(n_loops):
        if outer_idx == 0:
            loop_count = ceil(rolled) % (count_max + 1)
            if loop_count == 0:
                loop_count = count_max
            else:
                loop_count -= 1
        else:
            loop_count = count_max

        refreshes += encode_one_loop(unrolled=unrolled, rolled=loop_count, **kwargs)

    return refreshes


def least_common_multiple(x, y):
    gcd = x
    rem = y
    while (rem):
        gcd, rem = rem, gcd % rem

    return (x * y) // gcd


def generate_payload_from_row_list(
        *,
        read_count,
        row_sequence,
        timings,
        bankbits,
        bank,
        nranks,
        rank,
        payload_mem_size,
        refresh=False,
        verbose=False,
        sys_clk_freq=None):
    encoder = Encoder(bankbits=bankbits, nranks=nranks)

    tras = timings.tRAS
    trp = timings.tRP
    trefi = timings.tREFI
    trfc = timings.tRFC
    if verbose:
        print('Generating payload:')
        for t in ['tRAS', 'tRP', 'tREFI', 'tRFC']:
            print('  {} = {}'.format(t, getattr(timings, t)))

    acts_per_interval = (trefi - trfc) // (trp + tras)
    max_acts_in_loop = (2**Decoder.LOOP_JUMP - 1) // 2
    repeatable_unit = min(
        least_common_multiple(acts_per_interval, len(row_sequence)), max_acts_in_loop)
    assert repeatable_unit >= len(row_sequence)
    repetitions = repeatable_unit // len(row_sequence)
    print("  Repeatable unit: {}".format(repeatable_unit))
    print("  Repetitions: {}".format(repetitions))
    read_count_quotient = read_count // repetitions
    read_count_remainder = read_count % repetitions

    refresh_op = OpCode.REF if refresh else OpCode.NOOP

    # First instruction after mode transition should be a NOOP that waits until tRFC is satisfied
    # As we include REF as first instruction we actually wait tREFI here
    payload = [encoder.I(OpCode.NOOP, timeslice=max(1, trfc - 2, trefi - 2))]

    refreshes = encode_long_loop(
        unrolled=repetitions,
        rolled=read_count_quotient,
        row_sequence=row_sequence,
        timings=timings,
        encoder=encoder,
        bank=bank,
        rank=rank,
        refresh_op=refresh_op,
        payload=payload)
    refreshes += encode_long_loop(
        unrolled=1,
        rolled=read_count_remainder,
        row_sequence=row_sequence,
        timings=timings,
        encoder=encoder,
        bank=bank,
        rank=rank,
        refresh_op=refresh_op,
        payload=payload)

    # MC refresh timer is reset on mode transition, so issue REF now, this way it will be in sync with MC
    payload.append(encoder.I(refresh_op, timeslice=1))
    payload.append(encoder.I(OpCode.NOOP, timeslice=0))  # STOP

    if verbose:
        expected_cycles = get_expected_execution_cycles(payload)
        print(
            '  Payload size = {:5.2f}KB / {:5.2f}KB'.format(
                4 * len(payload) / 2**10, payload_mem_size / 2**10))
        count = '{:.3f}M'.format(read_count /
                                 1e6) if read_count > 1e6 else '{:.3f}K'.format(read_count / 1e3)
        print('  Payload per-row toggle count = {}  x{} rows'.format(count, len(row_sequence)))
        print(
            '  Payload refreshes (if enabled) = {} ({})'.format(
                refreshes, 'enabled' if refresh else 'disabled'))
        time = ''
        if sys_clk_freq is not None:
            time = ' = {:.3f} ms'.format(1 / sys_clk_freq * expected_cycles * 1e3)
        print('  Expected execution time = {} cycles'.format(expected_cycles) + time)

        for instruction in payload:
            op, *args = map(lambda p: p[1], instruction._parts)
            print(op, *map(hex, args), sep="\t")

    if len(payload) > payload_mem_size // 4:
        print(
            'Memory required for payload executor instructions ({} bytes) exceeds available payload memory ({} bytes)'
            .format(len(payload) * 4, payload_mem_size))
        print('The payload memory size can be changed with \'--payload-size \' option.')
        sys.exit(1)

    return encoder(payload)


def get_range_from_rows(wb, settings, row_nums):
    conv = DRAMAddressConverter.load()
    min_row = min(row_nums)
    max_row = max(row_nums) + 1
    start = conv.encode_bus(bank=0, row=min_row, col=0)
    if max_row < 2**settings.geom.rowbits:
        end = conv.encode_bus(bank=0, row=max_row, col=0)
    else:
        end = wb.mems.main_ram.base + wb.mems.main_ram.size

    return start - wb.mems.main_ram.base, end - start
