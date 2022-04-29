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
    cmd = ['make', 'jump.bin', 'OFFSET=%d' % offset, 'NORVC=1']
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
    if far_pc is not None:
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


class Page:

    def __init__(self, bitmap: bytes, data: bytes):
        self.bitmap = int.from_bytes(bitmap, 'little')
        self.data = bytearray(data)

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


class SysCall:

    def __init__(self):
        self.addr = None
        self.retval = None
        self.waddr = None
        self.wdata = None

    def set_wdata(self, wdata: str):
        assert len(wdata) % 2 == 0
        wbuf = bytearray()
        for i in range(0, len(wdata), 2):
            wbuf.append(int(wdata[i:i + 2], 16))
        self.wdata = bytes(wbuf)

    def make_entry(self) -> bytes:
        '''
        Replay table entry types:
            VALID: copy data
            RET  : return from syscall
            EXIT : handle exit
        '''
        buf = []

        if self.waddr is not None:
            buf.append(self.addr.to_bytes(8, 'little'))

            padded_size = (len(self.wdata) + 7) & ~7
            buf.append(padded_size.to_bytes(8, 'little'))

            padding_size = padded_size - len(self.wdata)
            buf.append(self.wdata)
            buf.append(b'\0' * padding_size)

        buf.append(b'\0' * 8)
        buf.append(self.retval.to_bytes(8, 'little'))

        return b''.join(buf)


class Breakpoint(SysCall):

    def __init__(self, addr: int):
        super().__init__()
        self.addr = addr
        self.repeat_rd = None

    def make_entry(self) -> bytes:
        addr = (-1).to_bytes(8, 'little')
        retval = self.retval.to_bytes(8, 'little')
        return addr + retval


class Checkpoint:

    def __init__(self):
        self.begin = None
        self.regs = []  # pc, 31 int, 32 fp
        self.syscalls = []
        self.breakpoint = None
        self.page_map = {}  # pn: Page

    def process(self):
        pass


def parse_log(path):
    '''
    Log types:
        begin <addr>
        ireg <val0> ... <val31>
        freg <val0> ... <val31>
        syscall <addr> <retval> [<waddr> <wdata>]
        syscall <addr> <retval> exit
        break <addr> {ecall|first|firstrvc}
        break <addr> repeat <times> <rd>
        file <path>
        dump <pn>
    '''
    f = open(path)
    dirname = os.path.dirname(path)
    cur = None
    dumpfile = None

    while True:
        line = f.readline()
        if not line:
            break
        tokens = line.split()

        if tokens[0] == 'begin':
            if cur is not None:
                cur.process()
            if dumpfile is not None:
                dumpfile.close()
                dumpfile = None
            cur = Checkpoint()
            cur.begin = int(tokens[1], 16)

        elif tokens[0] in {'ireg', 'freg'}:
            for val in tokens[1:]:
                cur.regs.append(int(val, 16))

        elif tokens[0] == 'syscall':
            addr = int(tokens[1], 16)
            if len(tokens) > 3 and tokens[3] == 'exit':
                cur.breakpoint = Breakpoint(addr)
            else:
                syscall = SysCall()
                syscall.addr = addr
                syscall.retval = int(tokens[2], 16)
                if len(tokens) > 3:
                    syscall.waddr = int(tokens[3], 16)
                    syscall.set_wdata(tokens[4])
                cur.syscalls.append(syscall)

        elif tokens[0] == 'break':
            cur.breakpoint = Breakpoint(int(tokens[1], 16))
            if tokens[2] == 'repeat':
                cur.breakpoint.repeat_rd = int(tokens[4])

        elif tokens[0] == 'file':
            path = os.path.join(dirname, tokens[1])
            dumpfile = open(path, 'rb')
        elif tokens[0] == 'dump':
            bitmap = dumpfile.read(PAGE_SIZE // 8)
            data = dumpfile.read(PAGE_SIZE)
            pn = int(tokens[1], 16)
            cur.page_map[pn] = Page(bitmap, data)

    if cur is not None:
        cur.process()
    if dumpfile is not None:
        dumpfile.close()
    f.close()


if __name__ == '__main__':
    args = parser.parse_args()

    parse_log(args.path)
    exit()

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
