from rowhammer_tester.scripts.row_generator import RowGenerator
from rowhammer_tester.scripts.row_mapping import (RowMapping, TrivialRowMapping, TypeARowMapping, TypeBRowMapping)
from rowhammer_tester.scripts.utils import validate_keys

class EvenRowGenerator(RowGenerator):
    _valid_module_keys = set(["nr_rows", "max_row"])
    def initialize(self, config, row_mapping):
        self.row_generator_config = config["payload_generator_config"]["row_generator_config"]
        assert validate_keys(self.row_generator_config, self._valid_module_keys)
        self.nr_rows = self.row_generator_config["nr_rows"]
        self.max_row = self.row_generator_config["max_row"]
        self.row_mapping = row_mapping

    def generate_rows(self, iteration):
        row_list = []
        for i in range(0, self.nr_rows):
            row_list.append(self.row_mapping.logical_to_physical((iteration + 2 * i) % self.max_row))

        return row_list
