class PayloadGenerator():
    subclasses = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        PayloadGenerator.subclasses[cls.__name__] = cls()

    def get_by_name(name):
        return PayloadGenerator.subclasses[name]

    def initialize(self, config):
        raise NotImplementedError("Initialize attributes from config")

    def get_payload(self, *, settings, bank, payload_mem_size, sys_clk_freq=None):
        raise NotImplementedError("Provide the payload to execute")

    def process_errors(self, settings, row_errors):
        raise NotImplementedError("Process errors detected during payload execution")

    def done(self):
        raise NotImplementedError("Provide the exit condition")

    def summarize(self):
        raise NotImplementedError("Summarize experiment results")

    def get_memtest_range(self, wb, settings):
        return 0x0, wb.mems.main_ram.size

    def get_memset_range(self, wb, settings):
        return 0x0, wb.mems.main_ram.size
