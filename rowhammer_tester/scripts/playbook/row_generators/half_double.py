from collections import defaultdict
from rowhammer_tester.scripts.playbook.row_generators import RowGenerator
from rowhammer_tester.scripts.playbook.row_mappings import (
    RowMapping, TrivialRowMapping, TypeARowMapping, TypeBRowMapping)
from rowhammer_tester.scripts.utils import validate_keys


class HalfDoubleRowGenerator(RowGenerator):
    _valid_module_keys = set(
        [
            "nr_rows", "distance_one", "double_sided", "distance_two", "attack_rows_start",
            "max_attack_row_idx", "decoy_rows_start"
        ])
    _updateable_module_keys = set(["nr_rows", "distance_one", "double_sided", "distance_two"])

    def load_params(self):
        self.nr_rows = self.row_generator_config["nr_rows"]
        self.distance_one = self.row_generator_config["distance_one"]
        self.double_sided = self.row_generator_config["double_sided"]
        self.distance_two = self.row_generator_config["distance_two"]
        self.attack_rows_start = self.row_generator_config["attack_rows_start"]
        self.max_attack_row_idx = self.row_generator_config["max_attack_row_idx"]
        self.decoy_rows_start = self.row_generator_config["decoy_rows_start"]

    def initialize(self, config, row_mapping):
        self.row_generator_config = config["payload_generator_config"]["row_generator_config"]
        assert validate_keys(self.row_generator_config, self._valid_module_keys)
        self.load_params()
        self.row_mapping = row_mapping

    def update_param(self, param, value):
        assert param in self._updateable_module_keys
        self.row_generator_config[param] = value
        self.load_params()

    def get_logical_victim(self, iteration):
        return self.attack_rows_start + (iteration + 2) % (self.max_attack_row_idx - 2)

    def generate_rows(self, iteration):
        row_list = []
        distance_two_rows = self.nr_rows
        if self.double_sided:
            distance_two_rows -= 2
        else:
            distance_two_rows -= 1

        for i in range(distance_two_rows):
            if not self.double_sided and i % 2 == 0:
                row_list.append(self.decoy_row_start)
            elif self.distance_two:
                if i % 2 != 0 and self.double_sided:
                    row_list.append(
                        self.attack_rows_start + (iteration + 4) % self.max_attack_row_idx)
                else:
                    row_list.append(
                        self.attack_rows_start + iteration % (self.max_attack_row_idx - 4))
            else:
                if not self.double_sided or i % 2 == 0:
                    row_list.append(self.decoy_rows_start + 1)
                else:
                    row_list.append(self.decoy_rows_start + 2)

        if self.distance_one:
            row_list.append(
                self.attack_rows_start + (iteration + 1) % (self.max_attack_row_idx - 3))
            if self.double_sided:
                row_list.append(
                    self.attack_rows_start + (iteration + 3) % (self.max_attack_row_idx - 1))

        def default_zero():
            return 0

        row_dict = defaultdict(default_zero)
        for row in row_list:
            row_dict[row] += 1

        print('Constructed:')
        for row in sorted(row_dict.keys()):
            print('\tRow {} x {}'.format(row, row_dict[row]))

        return list(map(self.row_mapping.logical_to_physical, row_list))
