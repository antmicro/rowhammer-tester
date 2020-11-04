import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
sys.path.append(os.path.join(SCRIPT_DIR, '..', 'gateware'))

from payload_executor import Encoder, OpCode

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
    encoder(OpCode.LOOP, count=20,     jump=1),  # to READ
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

    print('Transferring the payload ...')
    # for i, instr in enumerate(program):
    #     wb.write(base + 4*i, instr)
    wb.write(base, program)

    print('Executing ...')
    assert wb.regs.payload_executor_ready.read() == 1
    wb.regs.payload_executor_run.write(1)
    while wb.regs.payload_executor_ready.read() == 0:
        time.sleep(0.001)

    print('Finished')

if __name__ == "__main__":
    from litex import RemoteClient

    wb = RemoteClient()
    wb.open()

    execute(wb)

    wb.close()
