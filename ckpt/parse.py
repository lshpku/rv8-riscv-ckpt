import os
import argparse
from subprocess import Popen, DEVNULL
from typing import Union

parser = argparse.ArgumentParser()
parser.add_argument('path')

basedir = os.path.dirname(__file__)

PAGE_OFFS = 12
PAGE_SIZE = 1 << PAGE_OFFS
FIRST_PN = 0x10
ECALL = '00000073'


def page_align(a):
    return (a + (PAGE_SIZE - 1)) & ~(PAGE_SIZE - 1)


class chdir:
    def __init__(self, path):
        self.dpath = path
        self.spath = os.getcwd()

    def __enter__(self):
        os.chdir(self.dpath)

    def __exit__(self, type, value, traceback):
        os.chdir(self.spath)


def make_clean():
    cmd = ['make', 'clean']
    with chdir(basedir):
        p = Popen(cmd, stdout=DEVNULL)
        if p.wait():
            exit(p.returncode)


def make_jump(offset):
    make_clean()
    cmd = ['make', 'jump.bin', 'OFFSET=%d' % offset]
    with chdir(basedir):
        p = Popen(cmd, stdout=DEVNULL)
        if p.wait():
            exit(p.returncode)
        with open('jump.bin', 'rb') as f:
            return f.read()


def make_near(ret_pc: int, near_pc: int, near_buf: int,
              far_pc: int = None) -> bytes:
    make_clean()
    cmd = ['make', 'near.bin', 'NEAR_BUF=%d' % near_buf]
    if far_pc is None:
        cmd += ['RETURN_ONLY=1']
    else:
        cmd += ['FAR_CALL=%d' % far_pc]
    with chdir(basedir):
        p = Popen(cmd, stdout=DEVNULL)
        if p.wait():
            exit(p.returncode)
        with open('near.bin', 'rb') as f:
            near = f.read()

    ret_jump = make_jump(ret_pc - near_pc - len(near))
    return near + ret_jump


def make_far(far_stack_top):
    make_clean()
    cmd = ['make', 'far.bin', 'FAR_STACK_TOP=%d' % far_stack_top]
    with chdir(basedir):
        p = Popen(cmd, stdout=DEVNULL)
        if p.wait():
            exit(p.returncode)
        with open('far.bin', 'rb') as f:
            return f.read()


class PageSet:

    def __init__(self):
        self.page_map = {}
        self.free_list = []

    def put(self, addr: int, data: Union[int, str, bytes],
            force: bool = False) -> int:
        if isinstance(data, int):
            data = b'\0' * data
        elif isinstance(data, str):
            data = int(data, 16).to_bytes(len(data) // 2, 'little')
        else:
            assert isinstance(data, bytes)

        put = 0
        for i, b in enumerate(data):
            pn = (addr + i) >> PAGE_OFFS
            offs = (addr + i) & (PAGE_SIZE - 1)
            if pn not in self.page_map:
                self.page_map[pn] = [None] * PAGE_SIZE
            page = self.page_map[pn]
            if force or page[offs] is None:
                page[offs] = b
                put += 1
        return put

    def init_reserve(self):
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
                        self.free_list.append((begin, end))
                    cur = None

    def reserve(self, base: int, size: int) -> int:
        free_i = None
        for i, (begin, end) in enumerate(self.free_list):
            if end - begin < size:
                continue
            if end <= base:
                if base - end + size < 0x1000000:
                    free_i = i
            elif begin > base:
                if begin + size - base >= 0x1000000:
                    continue
                if free_i is None:
                    free_i = i
                else:
                    _, last_end = self.free_list[free_i]
                    if base - last_end > begin - base:
                        free_i = i
                break
        if free_i is None:
            raise Exception('cannot reserve for %x (%d)' % (base, size))

        begin, end = self.free_list[free_i]
        if end <= base:
            addr = end - size
            self.free_list[free_i] = (begin, end - size)
        else:
            addr = begin
            self.free_list[free_i] = (begin + size, end)
        return addr

    def get_page_list(self):
        return sorted(self.page_map.items())


def parse_log(f):
    regs = [None] * 64  # pc, 31 int, 32 fp
    pages = PageSet()
    syscalls = []  # [addr, retval, (addr, stream), ...]

    insts = 0
    expected_insts = 1000000
    last_syscall_insts = 0
    last_syscall_pages = PageSet()

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
            if regs[0] is None:
                regs[0] = addr.to_bytes(8, 'little')
            if value == ECALL:
                syscalls.append([addr])
                last_syscall_pages = PageSet()
                last_syscall_insts = insts
            n = pages.put(addr, value)
            new_since_begin = (n == len(value) // 2)
            n = last_syscall_pages.put(addr, value)
            new_since_last_syscall = (n == len(value) // 2)
            insts += 1
            if insts >= expected_insts:
                if new_since_last_syscall:
                    if syscalls:
                        print('last syscall %d: 0x%x' % (last_syscall_insts, syscalls[-1][0]))
                    print('find new inst %d: %s at 0x%x' % (insts, value, addr))
                    if new_since_begin:
                        print('new since begin')
                    break
                elif value == ECALL:
                    print('first syscall %d: 0x%x' % (insts, addr))
                    break

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
            for i in range(1, 32):
                regs[i] = int(tokens[i + 2], 16).to_bytes(8, 'little')
        elif tokens[0] == 'freg':
            for i in range(32):
                regs[i + 32] = int(tokens[i + 2], 16).to_bytes(8, 'little')
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
            replay_table.append(len(value).to_bytes(8, 'little'))
            replay_table.append(value)
        replay_table.append(b'\0' * 8)
        replay_table.append(retval.to_bytes(8, 'little'))
    return b''.join(replay_table)


if __name__ == '__main__':
    args = parser.parse_args()

    with open(args.path) as f:
        regs, pages, syscalls = parse_log(f)

    # reserve places for near_calls
    make_clean()
    near_size = len(make_near(0, 0, 0, 0))
    near_map = {}  # syscall_addr: near_addr
    pages.init_reserve()
    for syscall in syscalls:
        addr = syscall[0]
        if addr in near_map:
            continue
        near_map[addr] = pages.reserve(addr, near_size)

    entry_pc = int.from_bytes(regs[0], 'little')
    entry_size = len(make_near(0, 0, 0))
    entry_near_addr = pages.reserve(entry_pc, entry_size)

    # find a place to put supervisor
    replay_table = make_replay_table(syscalls)

    ro_size = page_align(len(replay_table) + 8 * len(regs))
    rx_size = PAGE_SIZE
    rw_size = PAGE_SIZE
    sv_size = ro_size + rx_size + rw_size + 4096

    sv_pn = 0x10
    for pn, content in pages.get_page_list():
        if pn - sv_pn < sv_size // PAGE_SIZE:
            sv_pn = pn + len(content) // PAGE_SIZE

    far_addr = sv_pn * PAGE_SIZE
    replay_table_addr = far_addr + rx_size
    regs_addr = replay_table_addr + len(replay_table)
    far_stack_base = replay_table_addr + ro_size
    far_stack_top = far_stack_base + rw_size

    # write near_calls
    for syscall in syscalls:
        addr = syscall[0]
        if addr not in near_map:
            continue
        near_addr = near_map.pop(addr)
        trap = make_jump(near_addr - addr)
        near_call = make_near(addr + 4, near_addr, far_stack_base, far_addr)
        pages.put(addr, trap, force=True)
        pages.put(near_addr, near_call)

    entry_call = make_near(entry_pc, entry_near_addr, far_stack_base)
    pages.put(entry_near_addr, entry_call)
    regs[0] = entry_near_addr.to_bytes(8, 'little')

    # write supervisor
    far_bin = make_far(far_stack_base + rw_size)
    pages.put(far_addr, far_bin)
    pages.put(replay_table_addr, replay_table)
    pages.put(regs_addr, b''.join(regs))
    pages.put(far_stack_base, regs[2])
    pages.put(far_stack_top - 8, replay_table_addr.to_bytes(8, 'little'))

    # dump pages and cfg
    cfgs = []
    with open('test.dump', 'wb') as f:
        for i, (pn, content) in enumerate(pages.get_page_list()):
            for c in content:
                if c is None:
                    f.write(b'\0')
                else:
                    f.write(c.to_bytes(1, 'little'))
            cfgs.append((pn * PAGE_SIZE, i * PAGE_SIZE, PAGE_SIZE))
    with open('test.cfg', 'w') as f:
        f.write('%d\n' % len(cfgs))
        for addr, offs, size in cfgs:
            f.write('%x %x %x\n' % (addr, offs, size))
        f.write('%x\n' % regs_addr)
