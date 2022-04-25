import os
import argparse
import subprocess
from typing import Union

parser = argparse.ArgumentParser()
parser.add_argument('path')

PAGE_OFFS = 12
PAGE_SIZE = 1 << PAGE_OFFS
FIRST_PN = 0x10


def page_align(a):
    return (a + (PAGE_SIZE - 1)) & ~(PAGE_SIZE - 1)


class chdir:
    def __init__(self, path):
        self.dpath = os.path.join(os.path.dirname(__file__), path)
        self.spath = os.getcwd()

    def __enter__(self):
        os.chdir(self.dpath)

    def __exit__(self, type, value, traceback):
        os.chdir(self.spath)


def make_clean():
    cmd = ['make', 'clean']
    with chdir('replay'):
        p = subprocess.Popen(cmd)
        if p.wait():
            exit(p.returncode)


def make_jump(offset):
    make_clean()
    cmd = ['make', 'jump.bin', 'OFFSET=%d' % offset]
    with chdir('replay'):
        p = subprocess.Popen(cmd)
        if p.wait():
            exit(p.returncode)
        with open('jump.bin', 'rb') as f:
            return f.read()


def make_near(trap_pc, near_pc, near_buf, far_call):
    trap_jump = make_jump(near_pc - trap_pc)

    make_clean()
    cmd = ['make', 'near.bin',
           'NEAR_BUF=%d' % near_buf, 'FAR_CALL=%d' % far_call]
    with chdir('replay'):
        p = subprocess.Popen(cmd)
        if p.wait():
            exit(p.returncode)
        with open('near.bin', 'rb') as f:
            near = f.read()

    ret_jump = make_jump(trap_pc + 4 - near_pc - len(near))
    return trap_jump, near + ret_jump


def make_far(far_stack_top):
    make_clean()
    cmd = ['make', 'far.bin', 'FAR_STACK_TOP=%d' % far_stack_top]
    with chdir('replay'):
        p = subprocess.Popen(cmd)
        if p.wait():
            exit(p.returncode)
        with open('far.bin', 'rb') as f:
            return f.read()


class PageSet:

    def __init__(self):
        self.page_map = {}

    def put(self, addr: int, data: Union[int, str, bytes], force: bool = False):
        if isinstance(data, int):
            data = b'\0' * data
        elif isinstance(data, str):
            data = int(data, 16).to_bytes(len(data) // 2, 'little')
        else:
            assert isinstance(data, bytes)
        for i, b in enumerate(data):
            pn = (addr + i) >> PAGE_OFFS
            offs = (addr + i) & (PAGE_SIZE - 1)
            if pn not in self.page_map:
                self.page_map[pn] = [None] * PAGE_SIZE
            page = self.page_map[pn]
            if force or page[offs] is None:
                page[offs] = b

    def get_free_list(self):
        free_list = []
        cur = FIRST_PN * PAGE_SIZE
        for pn, content in self.get_page_list():
            pa = pn * PAGE_SIZE
            for i, c in enumerate(content):
                if cur is None and c is None:
                    cur = pa + i
                elif cur is not None and c is not None:
                    begin = (cur + 1) & ~1
                    end = (pa + i) & ~1
                    if begin < end:  # align to 2
                        free_list.append((begin, end))
                    cur = None
        return free_list

    def get_page_list(self):
        return sorted(self.page_map.items())


def parse_log(f):
    regs = [None] * 64  # 30 ints, 32 fp, pc, sp
    pages = PageSet()
    syscalls = []  # [addr, retval, (addr, stream), ...]

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
            value = tokens[3]
            if value == '00000073':
                syscalls.append([addr])
            pages.put(addr, value)
            if regs[62] is None:
                regs[62] = addr.to_bytes(8, 'little')

        elif tokens[0] == 'load':
            pages.put(addr, tokens[3])
        elif tokens[0] == 'store':
            pages.put(addr, len(tokens[3]) // 2)
        elif tokens[0] == 'amo':
            pages.put(addr, tokens[3])

        elif tokens[0] == 'syscall':
            if tokens[2].startswith('0x'):
                syscalls[-1].append(int(tokens[2], 16))
            else:
                syscalls[-1].append(int(tokens[2]))
        elif tokens[0] == 'syswrite':
            value = []
            for i, b in enumerate(tokens[3:]):
                pages.put(addr + i, 1)
                value.append(int(b, 16).to_bytes(1, 'little'))
            syscalls[-1].append((addr, b''.join(value)))

        elif tokens[0] == 'ireg':
            regs[0] = int(tokens[3], 16).to_bytes(8, 'little')
            regs[63] = int(tokens[4], 16).to_bytes(8, 'little')
            for i in range(1, 30):
                regs[i] = int(tokens[i + 4], 16).to_bytes(8, 'little')
        elif tokens[0] == 'freg':
            for i in range(32):
                regs[i + 30] = int(tokens[i + 2], 16).to_bytes(8, 'little')
        else:
            raise ValueError('unknown type: %s' % tokens[0])

    return regs, pages, syscalls


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


if __name__ == '__main__':
    args = parser.parse_args()

    with open(args.path) as f:
        regs, pages, syscalls = parse_log(f)

    # find holes
    free_list = pages.get_free_list()

    # reserve places for near_calls
    make_clean()
    _, near_tmp = make_near(0, 0, 0, 0)
    near_size = len(near_tmp)
    near_map = {}  # syscall_addr: near_addr
    for syscall in syscalls:
        addr = syscall[0]
        if addr in near_map:
            continue
        use_free_i = None
        for i, (begin, end) in enumerate(free_list):
            if end - begin < near_size:
                continue
            if end <= addr:
                if addr - end + near_size < 0x1000000:
                    use_free_i = i
            elif begin > addr:
                if begin + near_size - addr >= 0x1000000:
                    continue
                if use_free_i is None:
                    use_free_i = i
                else:
                    _, last_end = free_list[use_free_i]
                    if addr - last_end > begin - addr:
                        use_free_i = i
                break
        if use_free_i is None:
            raise Exception('cannot find place for syscall')

        begin, end = free_list[use_free_i]
        if end <= addr:
            near_addr = end - near_size
            free_list[use_free_i] = (begin, end - near_size)
        else:
            near_addr = begin
            free_list[use_free_i] = (begin + near_size, end)
        near_map[addr] = near_addr

    # find a place to put supervisor
    replay_table = make_replay_table(syscalls)
    regs_bin = b''.join(regs[:63])

    ro_size = page_align(len(replay_table) + len(regs_bin))
    rx_size = PAGE_SIZE
    rw_size = PAGE_SIZE
    sv_size = ro_size + rx_size + rw_size + 4096

    sv_pn = 0x10
    for pn, content in pages.get_page_list():
        if pn - sv_pn < sv_size // PAGE_SIZE:
            sv_pn = pn + len(content) // PAGE_SIZE

    far_addr = sv_pn * PAGE_SIZE
    replay_table_addr = far_addr + rx_size
    regs_bin_addr = replay_table_addr + len(replay_table)
    far_stack_addr = replay_table_addr + ro_size

    # write near_calls
    for syscall in syscalls:
        addr = syscall[0]
        if addr not in near_map:
            continue
        near_addr = near_map.pop(addr)
        trap, near_call = make_near(addr, near_addr, far_stack_addr, far_addr)
        pages.put(addr, trap, force=True)
        pages.put(near_addr, near_call, force=True)
