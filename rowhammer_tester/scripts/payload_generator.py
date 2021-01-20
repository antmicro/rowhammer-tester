class PayloadGenerator():
    subclasses = {}
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        PayloadGenerator.subclasses[cls.__name__] = cls()

    def get_by_name(name):
        return PayloadGenerator.subclasses[name]

    def initialize(self, config):
        pass

    def get_payload(self, *, settings, bank, payload_mem_size,
                    sys_clk_freq=None):
        pass

    def process_errors(self, settings, row_errors):
        pass

    def done(self):
        pass

    def summarize(self):
        pass
