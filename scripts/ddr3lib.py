import math
import collections
import payload_ddr3_pb2

Timing = payload_ddr3_pb2.Timing
Opcode = payload_ddr3_pb2.Opcode
Instr = payload_ddr3_pb2.Instr
Payload = payload_ddr3_pb2.Payload

def VerifyInstr(ip: int, instr: Instr) -> bool:
  if instr.HasField('mem'):
    mem = instr.mem
    if mem.opcode not in {Opcode.RD, Opcode.ACT, Opcode.PRE, Opcode.REF}:
      return False
    if not (0 < mem.timeslice < (1 << Instr.MemInstr.Bits.TIMESLICE)):
      return False
    if mem.rank != 0:  # TODO: Add multi-rank support.
      return False
    if mem.bank >= 1 << Instr.MemInstr.Bits.BANK:
      return False
    if mem.addr >= 1 << Instr.MemInstr.Bits.ADDR:
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
    self.parameters = [[1] * Opcode.MAX for _ in range(Opcode.MAX)]
    self.parameters[Opcode.RD][Opcode.RD] = timing.ccd
    self.parameters[Opcode.RD][Opcode.ACT] = 1
    self.parameters[Opcode.RD][Opcode.PRE] = 1
    self.parameters[Opcode.RD][Opcode.REF] = math.inf
    self.parameters[Opcode.ACT][Opcode.RD] = 1
    self.parameters[Opcode.ACT][Opcode.ACT] = timing.rrd
    self.parameters[Opcode.ACT][Opcode.PRE] = 1
    self.parameters[Opcode.ACT][Opcode.REF] = math.inf
    self.parameters[Opcode.PRE][Opcode.RD] = 1
    self.parameters[Opcode.PRE][Opcode.ACT] = 1
    self.parameters[Opcode.PRE][Opcode.PRE] = 1
    self.parameters[Opcode.PRE][Opcode.REF] = timing.rp
    self.parameters[Opcode.REF][Opcode.RD] = math.inf
    self.parameters[Opcode.REF][Opcode.ACT] = timing.rfc
    self.parameters[Opcode.REF][Opcode.PRE] = timing.rfc
    self.parameters[Opcode.REF][Opcode.REF] = timing.rfc

    # Special-case handling for tFAW.
    self.prev_acts = collections.deque(maxlen = 4)
    self.faw = timing.faw

    self.next_tick = [math.inf] * Opcode.MAX
    self.next_tick[Opcode.ACT] = 0
    self.next_tick[Opcode.PRE] = 0
    self.next_tick[Opcode.REF] = 0

    self.banks = [
        Bank(timing) for _ in range(1 << Instr.MemInstr.Bits.BANK)
    ]

  def Execute(self, tick: int, instr: Instr.MemInstr) -> bool:
    if tick < self.next_tick[instr.opcode]:
      print('Rank timing violation for {}: {} < {}'.format(
          Opcode.Name(instr.opcode), tick, self.next_tick[instr.opcode]))
      return False

    # Special-case handling for tFAW.
    if instr.opcode == Opcode.ACT:
      if len(self.prev_acts) == self.prev_acts.maxlen:
        if tick - self.prev_acts[0] < self.faw:
          print('tFAW timing violation for {}: {} < {}'.format(
              Opcode.Name(instr.opcode), tick - self.prev_acts[0],
              self.faw))
          return False
      self.prev_acts.append(tick)

    # Recurse into banks.
    if not self.banks[instr.bank].Execute(tick, instr):
      return False

    for opcode, parameter in enumerate(self.parameters[instr.opcode]):
      if self.next_tick[opcode] == math.inf:
        self.next_tick[opcode] = tick + parameter
      elif self.next_tick[opcode] < tick + parameter:
        self.next_tick[opcode] = tick + parameter
    return True

class Bank:
  def __init__(self, timing: Timing):
    self.parameters = [[1] * Opcode.MAX for _ in range(Opcode.MAX)]
    self.parameters[Opcode.RD][Opcode.RD] = 1
    self.parameters[Opcode.RD][Opcode.ACT] = math.inf
    self.parameters[Opcode.RD][Opcode.PRE] = timing.rtp
    self.parameters[Opcode.ACT][Opcode.RD] = timing.rcd
    self.parameters[Opcode.ACT][Opcode.ACT] = math.inf
    self.parameters[Opcode.ACT][Opcode.PRE] = timing.ras
    self.parameters[Opcode.PRE][Opcode.RD] = math.inf
    self.parameters[Opcode.PRE][Opcode.ACT] = timing.rp
    self.parameters[Opcode.PRE][Opcode.PRE] = 1

    self.next_tick = [math.inf] * Opcode.MAX
    self.next_tick[Opcode.ACT] = 0
    self.next_tick[Opcode.PRE] = 0
    self.next_tick[Opcode.REF] = 0

  def Execute(self, tick: int, instr: Instr.MemInstr) -> bool:
    if tick < self.next_tick[instr.opcode]:
      print('Bank timing violation for {}: {} < {}'.format(
          Opcode.Name(instr.opcode), tick, self.next_tick[instr.opcode]))
      return False

    for opcode, parameter in enumerate(self.parameters[instr.opcode]):
      if self.next_tick[opcode] == math.inf:
        self.next_tick[opcode] = tick + parameter
      elif self.next_tick[opcode] < tick + parameter:
        self.next_tick[opcode] = tick + parameter
    return True
