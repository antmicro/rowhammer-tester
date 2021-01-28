from collections import (OrderedDict, defaultdict)
from rowhammer_tester.scripts.playbook.payload_generators import PayloadGenerator
from rowhammer_tester.scripts.playbook.lib import generate_payload_from_row_list
from rowhammer_tester.scripts.utils import validate_keys
from rowhammer_tester.scripts.playbook.row_generators import RowGenerator
from rowhammer_tester.scripts.playbook.row_generators.even_rows import EvenRowGenerator
from rowhammer_tester.scripts.playbook.row_generators.half_double import HalfDoubleRowGenerator
from rowhammer_tester.scripts.playbook.row_mappings import (
    RowMapping, TrivialRowMapping, TypeARowMapping, TypeBRowMapping)


class RowListPayloadGenerator(PayloadGenerator):
    _valid_module_keys = set(
        [
            "row_generator", "read_count", "refresh", "verbose", "row_generator_config",
            "row_mapping", "max_iteration", "fill_local"
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
        self.fill_local = self.module_config.get("fill_local", False)
        self.iteration = 0

    def get_memtest_range(self, wb, settings):
        if not self.fill_local:
            return PayloadGenerator.get_memtest_range(self, wb, settings)
        return self.row_generator.get_memory_range(wb, settings)

    def get_memset_range(self, wb, settings):
        if not self.fill_local:
            return PayloadGenerator.get_memset_range(self, wb, settings)
        return self.row_generator.get_memory_range(wb, settings)

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
