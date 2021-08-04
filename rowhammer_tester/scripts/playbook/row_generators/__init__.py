class RowGenerator:
    subclasses = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        RowGenerator.subclasses[cls.__name__] = cls()

    def get_by_name(name):
        return RowGenerator.subclasses[name]

    def initialize(self, config, row_mapping):
        raise NotImplementedError("Initialize attributes from config")

    def generate_rows(self, iteration):
        raise NotImplementedError("Return a list of rows based on the iteration count")

    def get_memory_range(self, wb, settings):
        return 0x0, wb.mems.main_ram.size

    def update_param(self, param, value):
        raise NotImplementedError("Update any updatable configuration parameters")
