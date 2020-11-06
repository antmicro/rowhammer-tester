import os
import sys
import time
import itertools

from rowhammer_tester.gateware.payload_executor import Encoder, OpCode, Decoder
from rowhammer_tester.scripts.utils import memdump, memread, memwrite, DRAMAddressConverter, RemoteClient

# Sample program
encoder = Encoder(bankbits=3)
PAYLOAD = [
    encoder(OpCode.NOOP, timeslice=50),

    encoder(OpCode.ACT,  timeslice=10, address=encoder.address(bank=1, row=100)),
    encoder(OpCode.READ, timeslice=10, address=encoder.address(bank=1, col=13)),
    encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=1, col=20)),
    encoder(OpCode.PRE,  timeslice=10, address=encoder.address(bank=1)),

    encoder(OpCode.ACT,  timeslice=10, address=encoder.address(bank=0, row=100)),
    encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=200)),
    encoder(OpCode.LOOP, count=8 - 1, jump=1),  # to READ col=200
    encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=208)),
    encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=216)),
    encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=224)),
    encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=232)),
    encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=240)),
    encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=248)),
    encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=256)),
    encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=264)),
    encoder(OpCode.READ, timeslice=30, address=encoder.address(bank=0, col=300 | (1 << 10))),  # auto precharge

    encoder(OpCode.ACT,  timeslice=60, address=encoder.address(bank=2, row=150)),

    encoder(OpCode.PRE,  timeslice=10, address=encoder.address(col=1 << 10)),  # all
    encoder(OpCode.REF,  timeslice=50),
    encoder(OpCode.REF,  timeslice=50),

    encoder(OpCode.NOOP, timeslice=50),
]

def byte_gen():
    while True:
        for i in range(16):
            yield 16*i + i  # 0x00, 0x11, 0x22, ...

def word_gen(offset):
    gen = byte_gen()
    while True:
        for _ in range(4):
            bytes = [next(gen) for _ in range(4)]
            word = 0
            for byte in reversed(bytes):
                word <<= 8
                word |= byte
            yield word  # 0x33221100, 0x77665544, ...
        for _ in range(offset):
            next(gen)

def execute(wb):
    depth = wb.mems.payload.size // 4  # bytes to 32-bit instructions

    program = [w for w in PAYLOAD]
    program += [0] * (wb.mems.payload.size//4 - len(program))  # fill with NOOPs

    # Write some data to the column we are reading to check that scratchpad gets filled
    converter = DRAMAddressConverter()
    data = list(itertools.islice(word_gen(3), 128))
    memwrite(wb, data, base=converter.encode_bus(bank=0, row=100, col=200))

    print('\nTransferring the payload ...')
    memwrite(wb, program, base=wb.mems.payload.base)

    def ready():
        status = wb.regs.payload_executor_status.read()
        return (status & 1) != 0

    print('\nExecuting ...')
    assert ready()
    wb.regs.payload_executor_start.write(1)
    while not ready():
        time.sleep(0.001)

    print('Finished')

    print('\nScratchpad contents:')
    scratchpad = memread(wb, n=512//4, base=wb.mems.scratchpad.base)
    memdump(scratchpad, base=0)

if __name__ == "__main__":
    wb = RemoteClient()
    wb.open()

    execute(wb)

    wb.close()
