import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
sys.path.append(os.path.join(SCRIPT_DIR, '..', 'gateware'))

from payload_executor import Encoder, OpCode
from utils import memdump, memread
from rowhammer import DRAMAddressConverter

# Sample program
encoder = Encoder(bankbits=3)
PAYLOAD = [
    encoder(OpCode.NOOP, timeslice=50),

    encoder(OpCode.ACT,  timeslice=10, address=encoder.address(bank=1, row=100)),
    encoder(OpCode.READ, timeslice=10, address=encoder.address(bank=1, col=13)),
    encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=1, col=20)),
    encoder(OpCode.PRE,  timeslice=10, address=encoder.address(bank=1)),

    encoder(OpCode.ACT,  timeslice=10, address=encoder.address(bank=3, row=100)),
    encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=3, col=200)),
    encoder(OpCode.LOOP, count=100 - 1, jump=1),  # to READ, may overflow scratchpad
    encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=3, col=300 | (1 << 10))),  # auto precharge

    encoder(OpCode.ACT,  timeslice=60, address=encoder.address(bank=2, row=150)),

    encoder(OpCode.PRE,  timeslice=10, address=encoder.address(col=1 << 10)),  # all
    encoder(OpCode.REF,  timeslice=50),
    encoder(OpCode.REF,  timeslice=50),

    encoder(OpCode.NOOP, timeslice=50),
]

def execute(wb):
    base = wb.mems.payload.base
    depth = wb.mems.payload.size // 4  # bytes to 32-bit instructions

    program = [w for w in PAYLOAD]
    # # no need to fill with NOOPs as 0s are NOOPs
    # program += [encoder(OpCode.NOOP, timeslice=0)] * (depth - len(program))

    # Write some data to the column we are reading to check that scratchpad gets filled
    converter = DRAMAddressConverter()
    wb.write(converter.encode_bus(bank=3, row=100, col=200), [0xbaadc0de])

    print('Transferring the payload ...')
    # for i, instr in enumerate(program):
    #     wb.write(base + 4*i, instr)
    wb.write(base, program)

    def ready():
        status = wb.regs.payload_executor_status.read()
        return (status & 1) != 0

    print('Executing ...')
    assert ready()
    wb.regs.payload_executor_start.write(1)
    while not ready():
        time.sleep(0.001)

    print('Finished')

    print('Scratchpad contents:')
    scratchpad = memread(wb, n=wb.mems.scratchpad.size//4, base=wb.mems.scratchpad.base)
    memdump(scratchpad, base=0)

if __name__ == "__main__":
    from litex import RemoteClient

    wb = RemoteClient()
    wb.open()

    execute(wb)

    wb.close()
