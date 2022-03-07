import math
import collections

import payload_ddr4_pb2

Timing = payload_ddr4_pb2.Timing
Opcode = payload_ddr4_pb2.Opcode
Instr = payload_ddr4_pb2.Instr
Payload = payload_ddr4_pb2.Payload


def VerifyInstr(ip: int, instr: Instr) -> bool:
    if instr.HasField('mem'):
        mem = instr.mem
        if mem.opcode not in {Opcode.RD, Opcode.ACT, Opcode.PRE, Opcode.REF}:
            return False
        if not (0 < mem.timeslice < (1 << Instr.MemInstr.Bits.TIMESLICE)):
            return False
        if mem.rank != 0:  # TODO: Add multi-rank support.
            return False
        if mem.stack != 0:  # TODO: Add die-stack support.
            return False
        if mem.bank_group >= 1 << Instr.MemInstr.Bits.BANK_GROUP:
            return False
        if mem.bank >= 1 << Instr.MemInstr.Bits.BANK:
            return False
        if mem.addr >= 1 << Instr.MemInstr.Bits.ADDR:
            return False
        if mem.opcode == Opcode.RD and mem.addr % 8 != 0:
            # We only ever want sequential (non-permuted) bursts.
            return False
        return True
    if instr.HasField('nop'):
        nop = instr.nop
        if nop.opcode != Opcode.NOP:
            return False
        if not (0 < nop.timeslice < (1 << Instr.NopInstr.Bits.TIMESLICE)):
            return False
        return True
    if instr.HasField('jmp'):
        jmp = instr.jmp
        if jmp.opcode != Opcode.JMP:
            return False
        if not (0 < jmp.offset < (1 << Instr.JmpInstr.Bits.OFFSET)):
            return False
        if ip < jmp.offset:
            return False
        if not (0 < jmp.count < (1 << Instr.JmpInstr.Bits.COUNT)):
            return False
        return True
    return False


class Rank:

    def __init__(self, timing: Timing):
        self.parameters = {
            Opcode.ACT: {
                Opcode.REF: math.inf,
            },
            Opcode.PRE: {
                Opcode.REF: timing.rp,
            },
            Opcode.REF: {
                Opcode.ACT: timing.rfc,
                Opcode.PRE: timing.rfc,
                Opcode.REF: timing.rfc,
            },
        }
        self.next_tick = {Opcode.RD: 0, Opcode.ACT: 0, Opcode.PRE: 0, Opcode.REF: 0}

        # Special-case handling for tFAW.
        self.prev_acts = collections.deque(maxlen=4)
        self.faw = timing.faw

        self.bank_groups = [BankGroup(timing) for _ in range(1 << Instr.MemInstr.Bits.BANK_GROUP)]

    def Execute(self, tick: int, instr: Instr.MemInstr) -> bool:
        if tick < self.next_tick.get(instr.opcode, 0):
            print(
                'Rank timing violation for {}: {} < {}'.format(
                    Opcode.Name(instr.opcode), tick, self.next_tick[instr.opcode]))
            return False

        # Special-case handling for tFAW.
        if instr.opcode == Opcode.ACT:
            if len(self.prev_acts) == self.prev_acts.maxlen:
                if tick - self.prev_acts[0] < self.faw:
                    print(
                        'tFAW timing violation for {}: {} < {}'.format(
                            Opcode.Name(instr.opcode), tick - self.prev_acts[0], self.faw))
                    return False
            self.prev_acts.append(tick)

        if not self.bank_groups[instr.bank_group].Execute(tick, instr):
            return False
        for i, bank_group in enumerate(self.bank_groups):
            if i == instr.bank_group:
                continue
            # Update all other bank groups.
            bank_group.Update(tick, instr)

        for opcode, parameter in self.parameters.get(instr.opcode, {}).items():
            if self.next_tick[opcode] == math.inf:
                self.next_tick[opcode] = tick + parameter
            elif self.next_tick[opcode] < tick + parameter:
                self.next_tick[opcode] = tick + parameter
        return True


class BankGroup:

    def __init__(self, timing: Timing):
        self.parameters = {
            Opcode.RD: {
                Opcode.RD: [timing.ccd_l, timing.ccd_s]
            },
            Opcode.ACT: {
                Opcode.ACT: [timing.rrd_l, timing.rrd_s]
            },
        }
        self.next_tick = {Opcode.RD: 0, Opcode.ACT: 0}

        self.banks = [Bank(timing) for _ in range(1 << Instr.MemInstr.Bits.BANK)]

    def Execute(self, tick: int, instr: Instr.MemInstr) -> bool:
        if tick < self.next_tick.get(instr.opcode, 0):
            print(
                'Bank group timing violation for {}: {} < {}'.format(
                    Opcode.Name(instr.opcode), tick, self.next_tick[instr.opcode]))
            return False

        if not self.banks[instr.bank].Execute(tick, instr):
            return False

        for opcode, parameter in self.parameters.get(instr.opcode, {}).items():
            self.next_tick[opcode] = tick + parameter[0]
        return True

    def Update(self, tick: int, instr: Instr.MemInstr):
        for opcode, parameter in self.parameters.get(instr.opcode, {}).items():
            self.next_tick[opcode] = tick + parameter[1]


class Bank:

    def __init__(self, timing: Timing):
        self.parameters = {
            Opcode.RD: {
                Opcode.PRE: timing.rtp,
            },
            Opcode.ACT: {
                Opcode.RD: timing.rcd,
                Opcode.ACT: math.inf,
                Opcode.PRE: timing.ras,
            },
            Opcode.PRE: {
                Opcode.RD: math.inf,
                Opcode.ACT: timing.rp
            }
        }
        self.next_tick = {Opcode.RD: math.inf, Opcode.ACT: 0, Opcode.PRE: 0, Opcode.REF: 0}

    def Execute(self, tick: int, instr: Instr.MemInstr) -> bool:
        if tick < self.next_tick.get(instr.opcode, 0):
            print(
                'Bank timing violation for {}: {} < {}'.format(
                    Opcode.Name(instr.opcode), tick, self.next_tick[instr.opcode]))
            return False

        for opcode, parameter in self.parameters.get(instr.opcode, {}).items():
            if self.next_tick[opcode] == math.inf:
                self.next_tick[opcode] = tick + parameter
            elif self.next_tick[opcode] < tick + parameter:
                self.next_tick[opcode] = tick + parameter
        return True
