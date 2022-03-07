#!/usr/bin/python3

import argparse
from enum import Enum
import sys
import google.protobuf.text_format

from rowhammer_tester.payload import ddr3lib
from rowhammer_tester.payload import ddr4lib


class DRAM(Enum):
    DDR3 = 1
    DDR4 = 2


class State:

    def __init__(self, dramlib):
        self.ip = 0  # Instruction pointer
        self.tick = 0  # Elapsed cycles
        self.loop = 0  # Loop iterations
        self.executed = [0] * dramlib.Opcode.MAX  # Instructions executed
        self.dramlib = dramlib

    def __str__(self):
        string = 'ip: {}\ntick: {}\nloop: {}'.format(self.ip, self.tick, self.loop)
        for opcode, count in enumerate(self.executed):
            if count == 0:
                continue
            string += '\n{}: {}'.format(self.dramlib.Opcode.Name(opcode), count)
        return string


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('payload', type=argparse.FileType('r'))
    parser.add_argument(
        '--dram', type=str, choices=[d.name.lower() for d in DRAM], default=DRAM.DDR3.name.lower())
    args = parser.parse_args()
    if args.dram == DRAM.DDR3.name.lower():
        dramlib = ddr3lib
    elif args.dram == DRAM.DDR4.name.lower():
        dramlib = ddr4lib
    else:
        print('Unsupported DRAM protocol:', args.dram)
        return -1

    # Parse textproto.
    payload = dramlib.Payload()
    google.protobuf.text_format.Parse(args.payload.read(), payload)

    # Verify timing.
    for field in payload.timing.DESCRIPTOR.fields:
        t = getattr(payload.timing, field.name)
        if t <= 0:
            print('Timing parameter {} is not positive: {}'.format(field.name, t))
            return -1

    # Verify each instruction.
    for ip, instr in enumerate(payload.instr):
        if not dramlib.VerifyInstr(ip, instr):
            print('Illegal instruction ({}) at ip ({})'.format(' '.join(str(instr).split()), ip))
            return -1

    # Run through the payload.
    state = State(dramlib)
    rank = dramlib.Rank(payload.timing)
    while state.ip < len(payload.instr):
        instr = payload.instr[state.ip]
        if instr.HasField('mem'):
            if not rank.Execute(state.tick, instr.mem):
                print(
                    'Failed to execute ({}) at ip ({}) on tick ({})'.format(
                        ' '.join(str(instr).split()), state.ip, state.tick))
                return -1
            state.tick += instr.mem.timeslice
            state.ip += 1
            state.executed[instr.mem.opcode] += 1
        elif instr.HasField('nop'):
            state.tick += instr.nop.timeslice
            state.ip += 1
            state.executed[instr.nop.opcode] += 1
        elif instr.HasField('jmp'):
            state.tick += 1
            if state.loop < instr.jmp.count:
                state.ip -= instr.jmp.offset
                state.loop += 1
                state.executed[instr.jmp.opcode] += 1
                continue
            state.ip += 1
            state.loop = 0
            state.executed[instr.jmp.opcode] += 1
        else:
            print(
                'Illegal instruction ({}) at ip ({}) on tick ({})'.format(
                    ' '.join(str(instr).split()), state.ip, state.tick))
            return -1

    print(state)
    print('OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
