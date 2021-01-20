class RowGenerator:
    subclasses = {}
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        RowGenerator.subclasses[cls.__name__] = cls()

    def get_by_name(name):
        return RowGenerator.subclasses[name]

    def initialize(self, config, row_mapping):
        pass
    def generate_rows(self, iteration):
        pass
