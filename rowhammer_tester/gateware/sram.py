from litex.soc.interconnect import wishbone
from migen import FSM, READ_FIRST, WRITE_FIRST, If, Memory, Module, NextState, NextValue, Signal

# Wishbone SRAM ------------------------------------------------------------------------------------


class SRAM(Module):
    def __init__(self, mem_or_size, read_only=None, init=None, bus=None, name=None, mode=None):
        if bus is None:
            bus = wishbone.Interface()
        self.bus = bus
        bus_data_width = len(self.bus.dat_r)
        if isinstance(mem_or_size, Memory):
            assert mem_or_size.width <= bus_data_width
            self.mem = mem_or_size
        else:
            self.mem = Memory(
                bus_data_width, mem_or_size // (bus_data_width // 8), init=init, name=name
            )

        if read_only is None:
            read_only = self.mem.bus_read_only if hasattr(self.mem, "bus_read_only") else False

        # Memory.
        # -------
        port = self.mem.get_port(
            write_capable=not read_only,
            we_granularity=8,
            mode=mode if mode is not None else READ_FIRST if read_only else WRITE_FIRST,
        )
        self.specials += self.mem, port

        self.read_only = Signal()
        self.comb += [self.read_only.eq(read_only)]

        self.submodules.fsm = FSM()
        self.fsm.act(
            "ADDR",
            If(
                self.bus.cyc & self.bus.stb,
                NextValue(port.adr, self.bus.adr),
                If(
                    self.bus.we & ~self.read_only,
                    [NextValue(port.we[i], self.bus.sel[i]) for i in range(bus_data_width // 8)],
                    NextValue(port.dat_w, self.bus.dat_w),
                ),
                NextState("GET_DATA"),
            ),
        )
        self.fsm.delayed_enter("GET_DATA", "DATA", 2)
        reg_dat_r = Signal.like(port.dat_r)
        self.sync += [
            reg_dat_r.eq(port.dat_r)
        ]
        self.fsm.act(
            "DATA",
            self.bus.dat_r.eq(reg_dat_r),
            self.bus.ack.eq(1),
            NextState("ADDR"),
        )
