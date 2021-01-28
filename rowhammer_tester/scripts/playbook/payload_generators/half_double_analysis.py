from collections import defaultdict
from enum import Enum
import math
from collections import (OrderedDict, defaultdict)
from rowhammer_tester.gateware.payload_executor import Encoder, OpCode, Decoder
from rowhammer_tester.scripts.playbook.payload_generators import PayloadGenerator
from rowhammer_tester.scripts.playbook.lib import (
    generate_payload_from_row_list, get_range_from_rows)
from rowhammer_tester.scripts.utils import (get_expected_execution_cycles, validate_keys)

from rowhammer_tester.scripts.playbook.row_generators import RowGenerator
from rowhammer_tester.scripts.playbook.row_generators.half_double import HalfDoubleRowGenerator
from rowhammer_tester.scripts.playbook.row_mappings import (
    RowMapping, TrivialRowMapping, TypeARowMapping, TypeBRowMapping)


class HalfDoubleAnalysisState(Enum):
    NOFLIP_DISTANCE_ONE = 1
    NOFLIP_DISTANCE_TWO = 2
    HAMMER_TOLERANCE = 3
    MAX_DILUTION = 4


class HalfDoubleAnalysisPayloadGenerator(PayloadGenerator):
    _valid_module_keys = set(
        [
            "max_total_read_count", "read_count_steps", "initial_dilution", "dilution_multiplier",
            "verbose", "row_mapping", "attack_rows_start", "max_attack_row_idx", "decoy_rows_start",
            "max_dilution", "fill_local"
        ])

    def initialize(self, config):
        self.module_config = config["payload_generator_config"]
        assert validate_keys(self.module_config, self._valid_module_keys)

        row_mapping_name = self.module_config["row_mapping"]
        self.row_mapping = RowMapping.get_by_name(row_mapping_name)

        self.max_total_read_count = self.module_config["max_total_read_count"]
        self.read_count_steps = self.module_config["read_count_steps"]
        self.initial_dilution = self.module_config["initial_dilution"]
        self.dilution_multiplier = self.module_config["dilution_multiplier"]
        self.max_dilution = self.module_config["max_dilution"]
        self.verbose = self.module_config["verbose"]
        self.attack_rows_start = self.module_config["attack_rows_start"]
        self.max_attack_row_idx = self.module_config["max_attack_row_idx"]
        self.decoy_rows_start = self.module_config["decoy_rows_start"]
        self.fill_local = self.module_config.get("fill_local", False)

        self.row_generator = HalfDoubleRowGenerator()
        self.module_config["row_generator_config"] = {}
        self.module_config["row_generator_config"]["nr_rows"] = self.initial_dilution
        self.module_config["row_generator_config"]["distance_one"] = True
        self.module_config["row_generator_config"]["double_sided"] = True
        self.module_config["row_generator_config"]["distance_two"] = False
        self.module_config["row_generator_config"]["attack_rows_start"] = self.attack_rows_start
        self.module_config["row_generator_config"]["max_attack_row_idx"] = self.max_attack_row_idx
        self.module_config["row_generator_config"]["decoy_rows_start"] = self.decoy_rows_start
        self.row_generator.initialize(config, self.row_mapping)

        self.iteration = 0
        self.total_read_count = self.max_total_read_count
        self.dilution = self.initial_dilution
        self.read_count = self.total_read_count // self.dilution
        self.state = HalfDoubleAnalysisState.NOFLIP_DISTANCE_ONE

        def zero_func():
            return 0

        def empty_list_func():
            return []

        self.row_count = defaultdict(zero_func)
        self.bit_count = defaultdict(zero_func)

        self.victim_list = defaultdict(empty_list_func)

    def get_memset_range(self, wb, settings):
        # Keep the default behaviour the same as it may have subtle consequences
        # in terms of bit flip counts.
        if not self.fill_local:
            return PayloadGenerator.get_memset_range(self, wb, settings)
        row_sequence = self.row_generator.generate_rows(self.iteration)
        logical_victim = self.row_generator.get_logical_victim(self.iteration)
        victim = self.row_mapping.logical_to_physical(logical_victim)
        row_sequence.append(victim)

        return get_range_from_rows(wb, settings, row_sequence)

    def get_memtest_range(self, wb, settings):
        logical_victim = self.row_generator.get_logical_victim(self.iteration)
        victim = self.row_mapping.logical_to_physical(logical_victim)
        row_sequence = [victim]

        return get_range_from_rows(wb, settings, row_sequence)

    def get_payload(self, *, settings, bank, payload_mem_size, sys_clk_freq=None):
        row_sequence = self.row_generator.generate_rows(self.iteration)

        return generate_payload_from_row_list(
            read_count=self.read_count,
            row_sequence=row_sequence,
            timings=settings.timing,
            bankbits=settings.geom.bankbits,
            bank=bank,
            payload_mem_size=payload_mem_size,
            refresh=False,
            verbose=self.verbose,
            sys_clk_freq=sys_clk_freq)

    @staticmethod
    def bitcount(x):
        return bin(x).count('1')  # seems faster than operations on integers

    @classmethod
    def bitflips(cls, val, ref):
        return cls.bitcount(val ^ ref)

    # State machine functions begin ---------------------------------
    def noflip_distance_one(self, victim_flipped):
        if not victim_flipped:
            self.state = HalfDoubleAnalysisState.NOFLIP_DISTANCE_TWO
            self.row_generator.update_param("distance_two", True)
            self.row_generator.update_param("distance_one", False)
        else:
            # we must have too many hammers.  inflate dilution more
            self.dilution *= self.dilution_multiplier
            if self.dilution > self.max_dilution:
                self.next_row()
            else:
                self.row_generator.update_param("nr_rows", self.dilution)
                self.read_count = self.total_read_count // self.dilution

    def noflip_distance_two(self, victim_flipped):
        if not victim_flipped:
            self.state = HalfDoubleAnalysisState.HAMMER_TOLERANCE
            self.row_generator.update_param("distance_one", True)
        else:
            self.next_row()

    def find_hammer_tolerance(self, victim_flipped):
        if not victim_flipped or self.total_read_count <= self.max_total_read_count // self.read_count_steps:
            self.next_row()
        else:
            self.dilution *= self.dilution_multiplier
            self.row_generator.update_param("nr_rows", self.dilution)
            self.read_count = self.total_read_count // self.dilution
            self.state = HalfDoubleAnalysisState.MAX_DILUTION

    def find_max_dilution(self, victim_flipped):
        if not victim_flipped or self.dilution * self.dilution_multiplier > self.max_dilution:
            self.dilution = self.initial_dilution
            self.total_read_count -= self.max_total_read_count // self.read_count_steps
            if self.total_read_count > 0:
                self.row_generator.update_param("nr_rows", self.dilution)
                self.read_count = self.total_read_count // self.dilution
                self.state = HalfDoubleAnalysisState.HAMMER_TOLERANCE
            else:
                self.next_row()
        else:
            self.dilution *= self.dilution_multiplier
            self.row_generator.update_param("nr_rows", self.dilution)
            self.read_count = self.total_read_count // self.dilution

    # State machine functions end ------------------------------------------

    def next_row(self):
        self.state = HalfDoubleAnalysisState.NOFLIP_DISTANCE_ONE
        self.dilution = self.initial_dilution
        self.total_read_count = self.max_total_read_count
        self.read_count = self.total_read_count // self.dilution
        self.row_generator.update_param("distance_two", False)
        self.row_generator.update_param("nr_rows", self.dilution)
        self.iteration += 1

    def process_errors(self, settings, row_errors):
        logical_victim = self.row_generator.get_logical_victim(self.iteration)
        row_errors_logical = {}
        for row in row_errors:
            row_errors_logical[self.row_mapping.physical_to_logical(row)] = (row, row_errors[row])
        victim_flipped = False
        victim_errors = 0

        for logical_row in sorted(row_errors_logical.keys()):
            row, errors = row_errors_logical[logical_row]
            if logical_row == logical_victim:
                victim_flipped = True
                if self.state != HalfDoubleAnalysisState.NOFLIP_DISTANCE_ONE:
                    if self.state == HalfDoubleAnalysisState.NOFLIP_DISTANCE_TWO:
                        dilution = math.inf
                    else:
                        dilution = self.dilution
                    self.row_count[(dilution, self.total_read_count)] += 1
                    victim_errors += sum(
                        self.bitflips(value, expected) for addr, value, expected in errors)
                    self.bit_count[(dilution, self.total_read_count)] += victim_errors
                    self.victim_list[(dilution, self.total_read_count)].append(logical_victim)
            if len(errors) > 0:
                print(
                    "Bit-flips for row {:{n}}: {}".format(
                        logical_row,
                        sum(self.bitflips(value, expected) for addr, value, expected in errors),
                        n=len(str(2**settings.geom.rowbits - 1))))
        if self.state == HalfDoubleAnalysisState.NOFLIP_DISTANCE_ONE:
            self.noflip_distance_one(victim_flipped)
        elif self.state == HalfDoubleAnalysisState.NOFLIP_DISTANCE_TWO:
            self.noflip_distance_two(victim_flipped)
        elif self.state == HalfDoubleAnalysisState.HAMMER_TOLERANCE:
            self.find_hammer_tolerance(victim_flipped)
        elif self.state == HalfDoubleAnalysisState.MAX_DILUTION:
            self.find_max_dilution(victim_flipped)

    def done(self):
        return self.iteration >= self.max_attack_row_idx - 4

    def print_pair_histogram(self, histo):
        dilution_set = set()
        hammers_set = set()
        for key in histo.keys():
            dilution_set.add(key[0])
            hammers_set.add(key[1])

        print("dilution\\hammer count", end=",")
        for hammers in sorted(hammers_set):
            print(hammers, end=",")
        print()

        for dilution in sorted(dilution_set):
            # Divide dilutions by two to get the single-sided value
            # This is easier for a human being to reason about.
            print(dilution // 2, end=",")
            for hammers in sorted(hammers_set):
                print(histo[(dilution, hammers)], end=",")
            print()

    def summarize(self):
        print("Bit histogram:")
        self.print_pair_histogram(self.bit_count)
        print("Row histogram:")
        self.print_pair_histogram(self.row_count)
        print("Victim list:")
        self.print_pair_histogram(self.victim_list)
