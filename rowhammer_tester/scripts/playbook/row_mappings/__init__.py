class RowMapping:
    subclasses = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        RowMapping.subclasses[cls.__name__] = cls()

    def get_by_name(name):
        return RowMapping.subclasses[name]

    def logical_to_physical(self, logical):
        raise NotImplementedError("Convert logical row number to physical row number")

    def physical_to_logical(self, physical):
        raise NotImplementedError("Convert physical row number to logical row number")


class TrivialRowMapping(RowMapping):

    def logical_to_physical(self, logical):
        return logical

    def physical_to_logical(self, physical):
        return physical


class TypeARowMapping(RowMapping):

    def logical_to_physical(self, logical):
        bit3 = (logical & 8) >> 3
        return logical ^ (bit3 << 1) ^ (bit3 << 2)

    def physical_to_logical(self, physical):
        bit3 = (physical & 8) >> 3
        return physical ^ (bit3 << 1) ^ (bit3 << 2)


class TypeBRowMapping(RowMapping):

    def logical_to_physical(self, logical):
        return logical * 2

    def physical_to_logical(self, physical):
        return physical // 2
