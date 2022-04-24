import os
import argparse
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('path')

PAGE_OFFS = 12
PAGE_SIZE = 1 << PAGE_OFFS

JAL_LENGTH = 1 << 20

dirname = os.path.dirname(__file__)


def make_jump(offset):
    cmd = ['make', 'jump.bin', '-DOFFSET=%d' % offset]
    p = subprocess.Popen(cmd)
    if p.wait():
        exit(p.returncode)
    with open('jump.bin', 'rb') as f:
        return f.read()


def make_near(trap_pc, near_pc, near_buf, far_call):
    trap_jump = make_jump(near_pc - trap_pc)

    cmd = ['make', 'near.bin',
           '-DNEAR_BUF=%d' % near_buf, '-DFAR_CALL=%d' % far_call]
    p = subprocess.Popen(cmd)
    if p.wait():
        exit(p.returncode)
    with open('near.bin', 'rb') as f:
        near = f.read()

    ret_jump = make_jump(trap_pc + 4 - near_pc - len(near))
    return trap_jump, near + ret_jump


def make_replay(far_stack_top):
    cmd = ['make', 'replay.bin', '-DFAR_STACK_TOP=%d' % far_stack_top]
    p = subprocess.Popen(cmd)
    if p.wait():
        exit(p.returncode)
    with open('replay.bin', 'rb') as f:
        return f.read()


def parse_log(f):
    syscalls = []  # [addr, retval, (addr, value), ...]
    page_map = {}

    def read(addr, size, value):
        for i in range(size):
            pn = (addr + i) >> PAGE_OFFS
            offs = (addr + i) & (PAGE_SIZE - 1)
            if pn not in page_map:
                page_map[pn] = [None] * PAGE_SIZE
            page = page_map[pn]
            if page[offs] is None:
                page[offs] = (value >> (i * 4)) & 0xff

    def write(addr, size):
        read(addr, size, 0)

    while True:
        line = f.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue

        tokens = line.split()
        if tokens[1] != '=':
            addr = int(tokens[1], 16)

        if tokens[0] == 'fetch':
            size = len(tokens[3]) // 2
            value = tokens[3]
            if value == '00000073':
                syscalls.append([addr])
            read(addr, size, int(value, 16))
        elif tokens[0] == 'load':
            size = len(tokens[3]) // 2
            read(addr, size, int(tokens[3], 16))
        elif tokens[0] == 'store':
            size = len(tokens[3]) // 2
            write(addr, size)
        elif tokens[0] == 'amo':
            size = len(tokens[3]) // 2
            read(addr, size, int(tokens[3], 16))
            write(addr, size)
        elif tokens[0] == 'syscall':
            if tokens[2].startswith('0x'):
                syscalls[-1].append(int(tokens[2], 16))
            else:
                syscalls[-1].append(int(tokens[2]))
        elif tokens[0] == 'syswrite':
            value = []
            for i, b in enumerate(tokens[3:]):
                write(addr + i, 1)
                value.append(int(b, 16).to_bytes(1, 'little'))
            syscalls[-1].append((addr, b''.join(value)))
        else:
            raise ValueError('unknown type: %s' % tokens[0])

    page_list = sorted(page_map.items())

    return page_list, syscalls


def make_replay_table(syscalls):
    replay_table = []
    for syscall in syscalls:
        retval = syscall[1]
        for waddr, value in syscall[2:]:
            if not value:
                continue
            replay_table.append(waddr.to_bytes(8, 'little'))
            if len(value) % 8 != 0:
                value += b'\0' * (8 - (len(value) % 8))
            replay_table.append((len(value) // 2).to_bytes(8, 'little'))
            replay_table.append(value)
        replay_table.append(b'\0' * 8)
        replay_table.append(retval.to_bytes(8, 'little'))
    return b''.join(replay_table)


def find_hole(page_list):
    pass


if __name__ == '__main__':
    args = parser.parse_args()

    with open(args.path) as f:
        page_list, syscalls = parse_log(f)

    for pn, _ in page_list:
        print(pn)
    for syscall in syscalls:
        print(syscall)

    rt = make_replay_table(syscalls)
    rt_alloc_size = (len(rt) + 0xfff) & ~(0xfff)
