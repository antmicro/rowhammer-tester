from collections import defaultdict
from rowhammer_tester.scripts.playbook.payload_generators import PayloadGenerator
from rowhammer_tester.scripts.playbook.lib import (
    generate_payload_from_row_list, get_range_from_rows)
from rowhammer_tester.scripts.playbook.row_mappings import (
    RowMapping, TrivialRowMapping, TypeARowMapping, TypeBRowMapping)
from rowhammer_tester.scripts.utils import validate_keys


class HammerTolerancePayloadGenerator(PayloadGenerator):
    _valid_module_keys = set(
        [
            "verbose", "row_mapping", "nr_rows", "read_count_step", "iters_per_row",
            "max_iteration", "nr_chips", "fill_local", "initial_read_count", "distance", "baseline",
            "first_dummy_row"
        ])

    def initialize(self, config):
        self.module_config = config["payload_generator_config"]
        assert validate_keys(self.module_config, self._valid_module_keys)

        row_mapping_name = self.module_config["row_mapping"]
        self.row_mapping = RowMapping.get_by_name(row_mapping_name)

        self.max_iteration = self.module_config["max_iteration"]
        self.verbose = self.module_config["verbose"]
        # victim rows is one fewer than the row span
        self.nr_rows = self.module_config["nr_rows"]
        self.read_count_step = self.module_config["read_count_step"]
        self.iters_per_row = self.module_config["iters_per_row"]
        self.nr_chips = self.module_config["nr_chips"]
        self.fill_local = self.module_config.get("fill_local", False)
        self.initial_read_count = self.module_config.get("initial_read_count", self.read_count_step)
        self.distance = self.module_config.get("distance", 1)
        self.baseline = self.module_config.get("baseline", False)
        self.run_baseline = False
        if self.baseline:
            self.first_dummy_row = self.module_config["first_dummy_row"]
            self.run_baseline = True

        def def_value_zero():
            return 0

        def def_value_defdict():
            return defaultdict(def_value_zero)

        def def_value_defdict_2():
            return defaultdict(def_value_defdict)

        self.row_errors = defaultdict(def_value_zero)
        self.bit_errors = defaultdict(def_value_zero)
        self.beat_errors = defaultdict(def_value_defdict)
        self.chip_errors_per_read = defaultdict(def_value_defdict_2)
        self.chip_errors_per_beat = defaultdict(def_value_defdict_2)
        self.chips_with_errors_per_beat = defaultdict(def_value_defdict)
        self.iteration = 0

    def get_payload(self, *, settings, bank, payload_mem_size, sys_clk_freq=None):
        if not self.run_baseline:
            logical_row_num, _ = self.get_row_for_iter(0)
        else:
            logical_row_num = self.first_dummy_row
        step = self.iteration % self.iters_per_row
        row_sequence = [
            self.row_mapping.logical_to_physical(logical_row_num),
            self.row_mapping.logical_to_physical(logical_row_num + 2 * self.distance)
        ]
        print("Rows: {}".format(row_sequence))
        return generate_payload_from_row_list(
            read_count=self.initial_read_count + self.read_count_step * step,
            row_sequence=row_sequence,
            timings=settings.timing,
            bankbits=settings.geom.bankbits,
            bank=bank,
            payload_mem_size=payload_mem_size,
            refresh=False,
            verbose=self.verbose,
            sys_clk_freq=sys_clk_freq)

    def extract_bits(self, bit_string, first_bit, group_stride, group_size, nr_groups):
        idx = first_bit
        bits = ""
        for group in range(nr_groups):
            bits += bit_string[idx:(idx + group_size)]
            idx += group_stride

        return bits

    # Returns logical and physical row number for row_idx from the point of view of the
    # current iteration.
    def get_row_for_iter(self, row_idx):
        assert row_idx < 1 + 2 * self.distance
        logical_row_num = ((self.iteration // self.iters_per_row) + row_idx) % (
            self.nr_rows - row_idx)
        row_num = self.row_mapping.logical_to_physical(logical_row_num)
        return logical_row_num, row_num

    # We'd like to only fill the three rows that we are interested in, but the
    # DRAM's internal layout might not allow us to do that with a single contiguous operation.
    # To keep things simple, let's find the span of the three rows and fill that
    # instead.  The row layouts that we have encountered so far allow us to do this
    # in a reasonably sized operation.
    def get_memset_range(self, wb, settings):
        # Keep the default behaviour the same as it may have subtle consequences
        # in terms of bit flip counts.
        if not self.fill_local:
            return PayloadGenerator.get_memset_range(self, wb, settings)
        row_nums = []
        for i in range(1 + 2 * self.distance):
            logical_row_num, row_num = self.get_row_for_iter(i)
            row_nums.append(row_num)
        return get_range_from_rows(wb, settings, row_nums)

    # This payload generator is only looking at flips in the intended victim row
    # of a double sided hammer.  Don't bother testing anything else.
    def get_memtest_range(self, wb, settings):
        logical_row_num, row_num = self.get_row_for_iter(self.distance)
        return get_range_from_rows(wb, settings, [row_num])

    @staticmethod
    def bitcount(x):
        return bin(x).count('1')  # seems faster than operations on integers

    @classmethod
    def bitflips(cls, val, ref):
        return cls.bitcount(val ^ ref)

    def gather_full_stats(self, step, errors):
        dq_bits = 64 // self.nr_chips
        for addr, value, expected in errors:
            flips = value ^ expected
            flips_bin = format(flips, "512b")[::-1]
            assert len(flips_bin) == 512
            total_flip_count = 0
            for bits in range(8):
                beat_flips = flips_bin[bits * 64:(bits + 1) * 64]
                flip_count = beat_flips.count('1')
                assert flip_count < 64
                if flip_count == 0:
                    continue
                total_flip_count += flip_count
                self.beat_errors[step][flip_count] += 1
                chip_count = 0
                for chip in range(self.nr_chips):
                    chip_flips_count = beat_flips[chip * dq_bits:(chip + 1) * dq_bits].count('1')
                    if chip_flips_count != 0:
                        self.chip_errors_per_beat[step][chip][chip_flips_count] += 1
                    chip_count += 1

                if chip_count > 0:
                    self.chips_with_errors_per_beat[step][chip_count] += 1

            for chip in range(self.nr_chips):
                chip_flips = self.extract_bits(flips_bin, chip * dq_bits, 64, dq_bits, 8)
                chip_flips_count = chip_flips.count('1')
                if chip_flips_count != 0:
                    self.chip_errors_per_read[step][chip][chip_flips_count] += 1
            self.bit_errors[step] += total_flip_count

    def process_errors(self, settings, row_errors):
        step = ((self.iteration % self.iters_per_row) + 1) * self.read_count_step
        logical_row_num, row_num = self.get_row_for_iter(self.distance)

        run_baseline = self.run_baseline
        if not self.run_baseline:
            self.iteration += 1
        else:
            self.baseline_flips = 0

        if self.baseline:
            self.run_baseline = not self.run_baseline
        if not row_num in row_errors.keys():
            return

        errors = row_errors[row_num]
        row_has_error = False
        if len(errors) > 0:
            if not self.baseline:
                self.gather_full_stats(step, errors)
                row_has_error = True
            elif run_baseline:
                total_flip_count = sum(
                    self.bitflips(value, expected) for addr, value, expected in errors)
                self.baseline_flips += total_flip_count
            else:
                total_flip_count = sum(
                    self.bitflips(value, expected) for addr, value, expected in errors)

                flipped_bits = max(total_flip_count - self.baseline_flips, 0)
                self.bit_errors[step] += flipped_bits
                if flipped_bits > 0:
                    row_has_error = True
        if row_has_error:
            self.row_errors[step] += 1

    def summarize(self):
        print("Row error summary:\n")
        for step in sorted(self.row_errors.keys()):
            print('{} : {}'.format(step, self.row_errors[step]))
        print("\nBit error summary:\n")
        for step in sorted(self.bit_errors.keys()):
            print('{} : {}'.format(step, self.bit_errors[step]))

        if self.baseline:
            return

        print("\nBeat error summary:\n")
        for step in sorted(self.beat_errors.keys()):
            print('Bit errors/beat histogram for {} hammers:'.format(step))
            for bits in sorted(self.beat_errors[step].keys()):
                print('\t{} : {}'.format(bits, self.beat_errors[step][bits]))

        for step in sorted(self.chip_errors_per_read.keys()):
            print("\nPer-chip bit errors / read command histograms for {} hammers:".format(step))
            for chip in sorted(self.chip_errors_per_read[step].keys()):
                print("\tChip {}:".format(chip))
                for count in sorted(self.chip_errors_per_read[step][chip].keys()):
                    print("\t\t{} : {}".format(count, self.chip_errors_per_read[step][chip][count]))

        for step in sorted(self.chip_errors_per_beat.keys()):
            print("\nPer-chip bit errors / beat histograms for {} hammers:".format(step))
            for chip in sorted(self.chip_errors_per_beat[step].keys()):
                print("\tChip {}:".format(chip))
                for count in sorted(self.chip_errors_per_beat[step][chip].keys()):
                    print("\t\t{} : {}".format(count, self.chip_errors_per_beat[step][chip][count]))

        for step in sorted(self.chips_with_errors_per_beat.keys()):
            print('Chips w/ errors/beat histogram for {} hammers:'.format(step))
            for chips in sorted(self.chips_with_errors_per_beat[step].keys()):
                print('\t{} : {}'.format(chips, self.chips_with_errors_per_beat[step][chips]))

    def done(self):
        return self.iteration >= self.max_iteration
