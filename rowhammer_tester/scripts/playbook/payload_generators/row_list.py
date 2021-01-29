from math import ceil
from collections import (OrderedDict, defaultdict)
from rowhammer_tester.gateware.payload_executor import Encoder, OpCode, Decoder
from rowhammer_tester.scripts.playbook.payload_generators import PayloadGenerator
from rowhammer_tester.scripts.utils import (get_expected_execution_cycles, validate_keys)

from rowhammer_tester.scripts.playbook.row_generators import RowGenerator
from rowhammer_tester.scripts.playbook.row_generators.even_rows import EvenRowGenerator
from rowhammer_tester.scripts.playbook.row_mappings import (
    RowMapping, TrivialRowMapping, TypeARowMapping, TypeBRowMapping)


# returns the number of refreshes issued
def encode_one_loop(*, unrolled, rolled, row_sequence, timings, encoder, bank, refresh_op, payload):
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
                        OpCode.ACT, timeslice=tras, address=encoder.address(bank=bank, row=row)),
                    encoder.I(OpCode.PRE, timeslice=trp,
                              address=encoder.address(col=1 << 10)),  # all
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
        payload_mem_size,
        refresh=False,
        verbose=True,
        sys_clk_freq=None):
    encoder = Encoder(bankbits=bankbits)

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
        refresh_op=refresh_op,
        payload=payload)
    refreshes += encode_long_loop(
        unrolled=1,
        rolled=read_count_remainder,
        row_sequence=row_sequence,
        timings=timings,
        encoder=encoder,
        bank=bank,
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

    assert len(payload) <= payload_mem_size // 4

    return encoder(payload)


#################################################################################


class RowListPayloadGenerator(PayloadGenerator):
    _valid_module_keys = set(
        [
            "row_generator", "read_count", "refresh", "verbose", "row_generator_config",
            "row_mapping", "max_iteration"
        ])

    def initialize(self, config):
        self.module_config = config["payload_generator_config"]
        assert validate_keys(self.module_config, self._valid_module_keys)

        row_mapping_name = self.module_config["row_mapping"]
        self.row_mapping = RowMapping.get_by_name(row_mapping_name)

        row_generator_name = self.module_config["row_generator"]
        self.row_generator = RowGenerator.get_by_name(row_generator_name)
        self.row_generator.initialize(config, self.row_mapping)

        self.max_iteration = self.module_config["max_iteration"]
        self.refresh = self.module_config["refresh"]
        self.verbose = self.module_config["verbose"]
        self.read_count = self.module_config["read_count"]
        self.iteration = 0

    def get_payload(self, *, settings, bank, payload_mem_size, sys_clk_freq=None):
        row_sequence = self.row_generator.generate_rows(self.iteration)
        print("Row sequence: ")
        print(row_sequence)

        return generate_payload_from_row_list(
            read_count=self.read_count,
            row_sequence=row_sequence,
            timings=settings.timing,
            bankbits=settings.geom.bankbits,
            bank=bank,
            payload_mem_size=payload_mem_size,
            refresh=self.refresh,
            verbose=self.verbose,
            sys_clk_freq=sys_clk_freq)

    @staticmethod
    def bitcount(x):
        return bin(x).count('1')  # seems faster than operations on integers

    @classmethod
    def bitflips(cls, val, ref):
        return cls.bitcount(val ^ ref)

    def process_errors(self, settings, row_errors):
        row_errors_logical = {}
        for row in row_errors:
            row_errors_logical[self.row_mapping.physical_to_logical(row)] = (row, row_errors[row])
        for logical_row in sorted(row_errors_logical.keys()):
            row, errors = row_errors_logical[logical_row]
            if len(errors) > 0:
                print(
                    "Bit-flips for row {:{n}}: {}".format(
                        logical_row,
                        sum(self.bitflips(value, expected) for addr, value, expected in errors),
                        n=len(str(2**settings.geom.rowbits - 1))))
        self.iteration += 1

    def done(self):
        return self.iteration >= self.max_iteration

    def summarize(self):
        return
