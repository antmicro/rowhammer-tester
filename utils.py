import time

from sdram_init import *

# ###########################################################################

def sdram_software_control(wb):
    wb.regs.sdram_dfii_control.write(dfii_control_cke|dfii_control_odt|dfii_control_reset_n)

def sdram_hardware_control(wb):
    wb.regs.sdram_dfii_control.write(dfii_control_sel)

def sdram_init(wb):
    sdram_software_control(wb)

    # we cannot check for the string "DFII_CONTROL" as done when generating C code,
    # so this is hardcoded for now
    # update: Hacky but works
    control_cmds = []
    with open('sdram_init.py', 'r') as f:
        n = 0
        while True:
            line = f.readline()
            if not line: break
            line = line.strip().replace(' ', '')
            if len(line) and line[0] == '(':
                if line.find('_control_') > 0:
                    control_cmds.append(n)
                n = n + 1

    print('control_cmds: ' + str(control_cmds))
    for i, (comment, a, ba, cmd, delay) in enumerate(init_sequence):
        wb.regs.sdram_dfii_pi0_address.write(a)
        wb.regs.sdram_dfii_pi0_baddress.write(ba)
        if i in control_cmds:
            print(comment + ' (ctrl)')
            wb.regs.sdram_dfii_control.write(cmd)
        else:
            print(comment + ' (cmd)')
            wb.regs.sdram_dfii_pi0_command.write(cmd)
            wb.regs.sdram_dfii_pi0_command_issue.write(1)
        time.sleep(0.001)

    sdram_hardware_control(wb)

# ###########################################################################

def memwrite(wb, data, base=0x40000000, burst=16):
    for i in range(0, len(data), burst):
        wb.write(base + 4*i, data[i:i+burst])

def memread(wb, n, base=0x40000000, burst=16):
    data = []
    for i in range(0, n, burst):
        data += wb.read(base + 4*i, burst)
    return data

def memfill(wb, n, pattern=0xaaaaaaaa, **kwargs):
    memwrite(wb, [pattern] * n, **kwargs)

def memcheck(wb, n, pattern=0xaaaaaaaa, **kwargs):
    data = memread(wb, n, **kwargs)
    errors = [(i, w) for i, w in enumerate(data) if w != pattern]
    return errors

def memspeed(wb, n, **kwargs):
    def measure(fun, name):
        start = time.time()
        fun(wb, n, **kwargs)
        elapsed = time.time() - start
        print('{:5} speed: {:6.2f} KB/s ({:.1f} sec)'.format(name, (n//4)/elapsed / 1e3, elapsed))

    def memcheck_assert(*args, **kwargs):
        errors = memcheck(*args, **kwargs)
        assert len(errors) == 0

    measure(memfill, 'Write')
    measure(memcheck_assert, 'Read')

def memdump(data, base=0x40000000, chunk_len=16):
    def tochar(val):
        return chr(val) if 0x20 <= val <= 0x7e else '.'

    def chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    def word2byte(words):
        for w in words:
            for i in range(4):
                yield (w & (0xff << 8*i)) >> 8*i

    data_bytes = list(word2byte(data))
    for i, chunk in enumerate(chunks(data_bytes, chunk_len)):
        b = " ".join("{:02x}".format(chunk[i] if i < len(chunk) else 0) for i in range(chunk_len))
        c = "".join(tochar(chunk[i] if i < len(chunk) else 0) for i in range(chunk_len))
        print("0x{addr:08x}:  {bytes}  {chars}".format(addr=base + chunk_len*i, bytes=b, chars=c))

# Open a remote connection in an interactive session (e.g. when sourced as `ipython -i <thisfile>`)
if __name__ == "__main__":
    import sys

    if bool(getattr(sys, 'ps1', sys.flags.interactive)):
        from litex import RemoteClient

        wb = RemoteClient()
        wb.open()
