import io
import os
import re
import sys
import itertools
import subprocess
import statistics

def ng(name, regex):
    'Constructs python regex named group'
    return r'(?P<{}>{})'.format(name, regex)

class Command:
    PATTERN = re.compile(''.join([
        r'\[\s*{time}\s*ps\]',
        r'\s+{cmd}',
        r'\s+phase=\s*{phase}',
        r'(\s+bank=\s*{bank})?',
        r'(\s+row=\s*{row})?',
        r'(\s+col=\s*{col})?',
        r'(\s+apre=\s*{apre})?',
    ]).format(
        time  = ng('time', r'\d+'),
        cmd   = ng('cmd', r'[A-Z]+'),
        phase = ng('phase', r'\d+'),
        bank  = ng('bank', r'(\d+|all)'),
        row   = ng('row', r'\d+'),
        col   = ng('col', r'\d+'),
        apre  = ng('apre', r'[01]'),
    ))

    def __init__(self, *, time, name, phase, bank, row, column, auto_precharge):
        self.time = time
        self.name = name
        self.phase = phase
        self.bank = bank
        self.row = row
        self.column = column
        self.auto_precharge = auto_precharge

    @classmethod
    def parse_line(cls, line):
        match = cls.PATTERN.search(line)
        if not match:
            return None
        return cls(
            time = int(match['time']),
            name = match['cmd'],
            phase = int(match['phase']),
            bank = int(match['bank']) if match['bank'] != 'all' else 'all',
            row = int(match['row']) if match['row'] is not None else None,
            column = int(match['col']) if match['col'] is not None else None,
            auto_precharge = bool(match['apre']) if match['apre'] is not None else None,
        )

def parse_line(line):
    match = PATTERN.search(line)
    if not match:
        return None
    groups = match.groupdict()

def run(argv, **kwargs):
    commands = []
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE)

    try:
        for line in io.TextIOWrapper(proc.stdout, encoding='utf-8'):
            cmd = Command.parse_line(line)
            if cmd is not None:
                commands.append(cmd)
            if len(commands) % 100 == 0:
                s = 'Commands: {:6}  Time: {:14} ps'.format(len(commands), commands[-1].time if len(commands) else 0)
                print(s, end=4*' ' + '\r', flush=True)
    except KeyboardInterrupt:
        print('\nReceived KeyboardInterrupt, killing the simulation ...')
        proc.kill()

    return commands

def split(is_separator, iterable):
    'Split an iterable using the separator defined by `is_separator`'
    for is_sep, group in itertools.groupby(iterable, is_separator):
        if not is_sep:
            yield group

def act_counts_between_refs(commands):
    groups = split(lambda cmd: cmd.name == 'REF', commands)
    act_groups = (filter(lambda cmd: cmd.name == 'ACT', g) for g in groups)
    act_counts = (sum(1 for _ in g) for g in act_groups)
    return act_counts

def row_toggle_counts_between_refs(commands):
    groups = split(lambda cmd: cmd.name == 'REF', commands)
    for g in groups:
        last_row = None
        ntoggles = 0
        for cmd in g:
            assert cmd.name not in ['WR', 'REF']
            if cmd.name == 'ACT':
                if cmd.row != last_row:
                    ntoggles += 1
                    last_row = cmd.row
        yield ntoggles

def filter_counts(counts, min_len=2):
    # remove short groups (happen when dram just REFreshes periodically with REF+PRE)
    counts = filter(lambda c: c > min_len, counts)
    # remove first and last group
    counts = list(counts)
    counts.pop(0)
    counts.pop(-1)
    return counts

# ##############################################################################

def prepare_environ():
    # wrap sudo
    script_dir = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
    sudo_wrapper_dir = os.path.join(script_dir, 'bin')
    os.environ['PATH'] = ':'.join([sudo_wrapper_dir, os.getenv('PATH')])
    # set python path
    python_libs = ['migen', 'litex', 'liteeth', 'liteiclink', 'litescope', 'litedram']
    os.environ['PYTHONPATH'] = ':'.join(os.path.join(script_dir, lib) for lib in python_libs)

def print_stats(counts):
    counts = filter_counts(counts)
    print()
    print('### STATS ###')
    print('Data from {} REF periods'.format(len(counts)))
    print('Count of ACT between two REFs:')
    print('  mean   = {:.2f} +/- {:.2f}'.format(statistics.mean(counts), statistics.stdev(counts)))
    print('  median = {:.2f}'.format(statistics.median(counts)))

    # count number of commands per refresh period
    tREF = 64e-3
    nREF = 8192
    per_period = statistics.median(counts) * nREF
    freq = per_period / tREF
    print('ACTs per REF period = {:.3f} M'.format(per_period / 1e6))
    print('ACTs frequency = {:.2f} Mps'.format(freq / 1e6))
    print()

if __name__ == "__main__":
    prepare_environ()

    commands = run(sys.argv[1:])

    # both should be equivalent
    # print_stats(act_counts_between_refs(commands))
    print_stats(row_toggle_counts_between_refs(commands))
