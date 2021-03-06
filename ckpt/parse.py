import os
import io
import re
import copy
import argparse
import hashlib
from subprocess import Popen, PIPE, DEVNULL
from typing import Union, List, Tuple

parser = argparse.ArgumentParser()
parser.add_argument('path')
parser.add_argument('--exec')
parser.add_argument('-j', '--jobs', type=int, default=1)
parser.add_argument('-r', '--rebuild', action='store_true')
parser.add_argument('-v', '--verify', action='store_true')

SRC_DIR = os.path.dirname(__file__)
WORK_DIR = os.getcwd()

PAGE_OFFS = 12
PAGE_SIZE = 1 << PAGE_OFFS
PAGE_OFFS_MASK = PAGE_SIZE - 1
FIRST_PN = 0x10
ECALL = '00000073'
J_MAX_OFFS = 1 << 20


class MakeHelper:
    identifier = b''

    @staticmethod
    def make(target: str, args: List[str]) -> bytes:
        # make output name unique
        sig = (target + '\t'.join(args)).encode('utf-8')
        sig += MakeHelper.identifier
        sig = hashlib.sha256(sig).hexdigest()[:8]
        base, ext = os.path.splitext(target)
        target = base + sig + ext

        os.chdir(SRC_DIR)
        cmd = ['make', target] + args
        p = Popen(cmd, stdout=DEVNULL)
        if p.wait():
            exit(p.returncode)
        with open(target, 'rb') as f:
            data = f.read()
        os.remove(target)
        os.chdir(WORK_DIR)
        return data

    @staticmethod
    def jump(offset: int, norvc: bool = True):
        assert offset < J_MAX_OFFS and offset >= -J_MAX_OFFS
        args = ['OFFSET=%d' % offset]
        if norvc:
            args += ['NORVC=1']
        return MakeHelper.make('jump.bin', args)

    @staticmethod
    def near(ret_pc: int, near_pc: int, near_buf: int,
             far_pc: int = None, alter_rd: int = None,
             norvc: bool = True) -> bytes:
        args = ['NEAR_BUF=0x%x' % near_buf]
        if far_pc is not None:
            args += ['FAR_CALL=0x%x' % far_pc]
        if alter_rd is not None and alter_rd != 10:
            if alter_rd == 2:
                args += ['ALTER_RD_IS_SP=1']
            else:
                args += ['ALTER_RD=x%d' % alter_rd]
        if norvc:
            args += ['NORVC=1']
        near = MakeHelper.make('near.bin', args)
        ret = MakeHelper.jump(ret_pc - near_pc - len(near))
        return near + ret

    @staticmethod
    def far(replay_sp: int, replay_pc: int):
        args = ['REPLAY_SP=0x%x' % replay_sp, 'REPLAY_PC=0x%x' % replay_pc]
        return MakeHelper.make('far.bin', args)


class BBVBase:
    LINE = re.compile(r'^\s+([0-9a-f]+):\s+[0-9a-f]+\s+(\S+)')
    CFIS = {
        'jal', 'jalr', 'beq', 'bne', 'blt', 'bge', 'bltu', 'bgeu',
        'c.j', 'c.jal', 'c.jr', 'c.jalr', 'c.beqz', 'c.bnez'}

    def __init__(self, path: str):
        print(path, 'disassembling')
        cmd = ['riscv64-unknown-linux-gnu-objdump', '-d',
               '-z', '-j', '.text', '-Mno-aliases', path]
        p = Popen(cmd, stdout=PIPE, encoding='utf-8')

        self.cfi_map = {}
        while True:
            line = p.stdout.readline()
            if not line:
                break
            m = BBVBase.LINE.match(line)
            if m is None:
                continue
            pc, inst = m.groups()
            if inst in BBVBase.CFIS:
                index = len(self.cfi_map) + 1
                self.cfi_map[int(pc, 16)] = index

        if p.wait():
            exit(p.returncode)
        print(path, 'done')

    def index(self, pc: int) -> int:
        return self.cfi_map.get(pc)


class Page:

    def __init__(self, bitmap: Union[int, bytes], data: bytes):
        if isinstance(bitmap, int):
            self.bitmap = bitmap
        else:
            self.bitmap = int.from_bytes(bitmap, 'little')
        self.data = io.BytesIO(data)
        self.exec_count = None

    def set_exec_count(self, data: bytes):
        self.exec_count = [None] * (PAGE_SIZE // 2)
        for i in range(PAGE_SIZE // 2):
            b, e = i * 4, (i + 1) * 4
            count = int.from_bytes(data[b:e], 'little')
            self.exec_count[i] = count

    def put(self, offs: int, data: bytes):
        assert offs + len(data) <= PAGE_SIZE
        self.data.seek(offs)
        self.data.write(data)
        self.bitmap |= ((1 << len(data)) - 1) << offs

    def is_free(self, offs: int) -> bool:
        return self.bitmap & (1 << offs) == 0

    def get(self) -> bytes:
        self.data.seek(0)
        data = self.data.read()
        assert len(data) == PAGE_SIZE
        return data


class PageMap:

    def __init__(self):
        self._map = {}  # pn: Page

    def __getitem__(self, pn: int) -> Page:
        if pn not in self._map:
            self._map[pn] = Page(0, b'\0' * PAGE_SIZE)
        return self._map[pn]

    def __setitem__(self, pn: int, page: Page):
        self._map[pn] = page

    def put(self, addr: int, data: bytes):
        begin_pn = addr >> PAGE_OFFS
        end_pn = (addr + len(data) + PAGE_SIZE - 1) >> PAGE_OFFS
        for pn in range(begin_pn, end_pn):
            begin_addr = max(addr, pn * PAGE_SIZE)
            end_addr = min(addr + len(data), (pn + 1) * PAGE_SIZE)
            offs = begin_addr & PAGE_OFFS_MASK
            part = data[begin_addr - addr: end_addr - addr]
            self[pn].put(offs, part)

    def make_free_list(self) -> List[Tuple[int, int]]:
        free_list = []
        page_list = sorted(self._map.items())
        cur = FIRST_PN * PAGE_SIZE

        for pn, page in page_list:
            pa = pn * PAGE_SIZE
            for i in range(PAGE_SIZE):
                free = page.is_free(i)
                if cur is None and free:  # begin a free range
                    cur = pa + i
                elif cur is not None and not free:  # end
                    # align boundaries to 2 as instructions are 2-aligned
                    begin = (cur + 1) & ~1
                    end = (pa + i) & ~1
                    if begin < end:
                        free_list.append((begin, end))
                    cur = None

        return free_list

    def reserve(self, free_list: List[Tuple[int, int]],
                base_addr: int, size: int) -> int:
        # get upper bound and lower bound of free range
        if base_addr < free_list[0][0]:
            s, e = -1, 0
        elif base_addr >= free_list[-1][1]:
            s, e = len(free_list) - 1, len(free_list)
        else:
            s, e = 0, len(free_list) - 1
            while s + 1 < e:  # binary search
                m = (s + e) // 2
                if free_list[m][1] <= base_addr:
                    s = m
                elif free_list[m][0] > base_addr:
                    e = m

        # search both upwards and downwards
        s_hit, e_hit = False, False
        while True:
            do_s = s >= 0 and not s_hit
            do_e = e < len(free_list) and not e_hit
            if not (do_s or do_e):
                break
            if do_s:
                if free_list[s][0] + size <= free_list[s][1]:
                    s_hit = True
                else:
                    s -= 1
            if do_e:
                if free_list[e][1] - size >= free_list[e][0]:
                    e_hit = True
                else:
                    e += 1

        # select the nearest free range
        if s_hit and e_hit:
            s_dist = base_addr - free_list[s][1]
            e_dist = free_list[e][0] - base_addr
            if s_dist < e_dist:
                use_i = s
            else:
                use_i = e
        elif s_hit:
            use_i = s
        elif e_hit:
            use_i = e
        else:
            raise Exception('failed to reserve')

        # update free_list and page map
        begin, end = free_list[use_i]
        if free_list[use_i][0] > base_addr:
            free_list[use_i] = (begin + size, end)
            near_addr = begin
        else:
            free_list[use_i] = (begin, end - size)
            near_addr = end - size
        self.put(near_addr, b'\0' * size)
        return near_addr

    def reserve_page(self, size: int) -> int:
        pages_needed = (size + PAGE_SIZE - 1) >> PAGE_OFFS
        cur = FIRST_PN
        pn_list = sorted(self._map.keys())
        for pn in pn_list:
            if pn - cur < pages_needed:
                cur = pn + 1
            else:
                break
        return cur

    def dump(self, dumpfile: io.BytesIO, cfgfile: io.StringIO):
        # merge successive pages
        page_list = sorted(self._map.items())
        last_pn = None
        cfgs = []  # (pn, count)
        for pn, _ in page_list:
            if last_pn is None or last_pn + 1 < pn:
                cfgs.append([pn, 1])
            else:
                cfgs[-1][1] += 1
            last_pn = pn

        # write configs
        cfgfile.write('%d\n' % len(cfgs))
        offs = 0
        for pn, count in cfgs:
            addr = pn * PAGE_SIZE
            size = count * PAGE_SIZE
            cfgfile.write('%x\t%x\t%x\t%x\n' % (addr, offs, size, size))
            offs += size

        # write pages
        for i, (pn, page) in enumerate(page_list):
            dumpfile.write(page.get())

    def dump_bbv(self, bbv: BBVBase, f: io.StringIO):
        page_list = sorted(self._map.items())
        f.write('T')
        for pn, page in page_list:
            if page.exec_count is None:
                continue
            for i, count in enumerate(page.exec_count):
                if not count:
                    continue
                pc = pn * PAGE_SIZE + i * 2
                index = bbv.index(pc)
                if index is not None:
                    f.write(':%d:%d ' % (index, count))
        f.write('\n')


class SysCall:
    RET = 0
    EXIT = 1
    ENTRY = 2
    RET_VERBOSE = 3

    def __init__(self, addr: int, retval: int = None,
                 alter_rd: int = None, is_break: bool = False,
                 waddr: int = None, wdata: bytes = None):
        self.addr = addr
        self.retval = retval
        self.alter_rd = alter_rd
        self.is_break = is_break
        self.waddr = waddr
        self.wdata = wdata

    def set_wdata(self, wdata: str):
        assert len(wdata) % 2 == 0
        wbuf = bytearray()
        for i in range(0, len(wdata), 2):
            wbuf.append(int(wdata[i:i + 2], 16))
        self.wdata = bytes(wbuf)

    def make_entry(self, verbose: bool) -> bytes:
        buf = []

        if self.waddr is not None:
            buf.append(self.waddr.to_bytes(8, 'little'))
            buf.append(len(self.wdata).to_bytes(8, 'little'))
            padded_size = (len(self.wdata) + 7) & ~7
            padding_size = padded_size - len(self.wdata)
            buf.append(self.wdata)
            buf.append(b'\0' * padding_size)

        if self.is_break:
            buf.append(self.EXIT.to_bytes(8, 'little'))
            buf.append((0).to_bytes(8, 'little'))
        else:
            ret = self.RET_VERBOSE if verbose else self.RET
            buf.append(ret.to_bytes(8, 'little'))
            buf.append(self.retval.to_bytes(8, 'little'))

        return b''.join(buf)


class Checkpoint:

    def __init__(self):
        self.entry_pc = None
        self.regs = []  # pc, 31 int, 32 fp
        self.syscalls = []
        self.breakpoint = None  # (pc, rd, repeat)
        self.pages = PageMap()
        self.path_prefix = None
        self.stores = []  # (addr, size, data)
        self.bbv = None
        self.clpath = None

    def process_once(self, verbose=False, suffix='.1'):
        # reserve space for near/entry/far calls
        for syscall in self.syscalls:
            # set all 4 bytes in case the latter 2 bytes of
            # an rvc instruction are considered free
            self.pages.put(syscall.addr, b'\0' * 4)
        free_list = self.pages.make_free_list()
        near_map = {}  # base_addr: near_addr

        for syscall in self.syscalls:
            if syscall.addr in near_map:
                continue
            size = len(MakeHelper.near(0, 0, 0, 0, syscall.alter_rd))
            near_addr = self.pages.reserve(free_list, syscall.addr, size)
            near_map[syscall.addr] = near_addr

        size = len(MakeHelper.near(0, 0, 0))
        entry_addr = self.pages.reserve(free_list, self.entry_pc, size)

        size = len(MakeHelper.far(0, 0))
        far_addr = self.pages.reserve(free_list, self.entry_pc, size)

        # reserve pages for replay stack
        '''
        struct replay_stack {
            uint64_t regfile[64];
            uint64_t replay_sp;
            uint64_t replay_pc;
            uint64_t replay_table[N];
            uint64_t near_buf; };
        '''
        replay_table = self.make_replay_table(verbose)
        replay_stack_size = 64 * 8 + 8 + 8 + len(replay_table) + 8
        replay_stack_pn = self.pages.reserve_page(replay_stack_size)

        regs_addr = replay_stack_pn * PAGE_SIZE
        replay_sp_addr = regs_addr + 64 * 8
        replay_pc_addr = replay_sp_addr + 8
        replay_table_addr = replay_pc_addr + 8
        near_buf = replay_table_addr + len(replay_table)

        # write near/entry/far calls
        for syscall in self.syscalls:
            if syscall.addr not in near_map:
                continue
            near_addr = near_map.pop(syscall.addr)
            trap = MakeHelper.jump(near_addr - syscall.addr)
            near_call = MakeHelper.near(
                syscall.addr + 4, near_addr, near_buf, far_addr,
                syscall.alter_rd)
            self.pages.put(syscall.addr, trap)
            self.pages.put(near_addr, near_call)

        entry_call = MakeHelper.near(self.entry_pc, entry_addr, near_buf)
        self.pages.put(entry_addr, entry_call)

        far_call = MakeHelper.far(replay_sp_addr, replay_pc_addr)
        self.pages.put(far_addr, far_call)

        # write replay stack
        regs = self.regs.copy()
        regs[0] = far_addr.to_bytes(8, 'little')
        regs[10] = entry_addr.to_bytes(8, 'little')
        self.pages.put(regs_addr, b''.join(regs))
        self.pages.put(replay_table_addr, replay_table)
        self.pages.put(near_buf, self.regs[2])

        # dump pages and cfg
        dumpfile = open(self.path_prefix + suffix + '.dump', 'wb')
        cfgfile = open(self.path_prefix + suffix + '.cfg', 'w')
        self.pages.dump(dumpfile, cfgfile)
        dumpfile.close()
        cfgfile.write('%x\n' % regs_addr)
        cfgfile.close()

    def process(self):
        # dump bbv
        if self.bbv is not None:
            bbvpath = self.path_prefix + '.bb'
            with open(bbvpath, 'w') as f:
                self.pages.dump_bbv(self.bbv, f)

        # break with ecall or first-executed instruction
        if self.breakpoint is None:
            print(self.path_prefix, 'single pass')
            self.process_once()
            self.verify()
            return

        # break with a repeating instruction
        print(self.path_prefix, 'first pass')
        pages = copy.deepcopy(self.pages)
        self.process_once(verbose=True)

        # run the checkpoint and trace the execution of
        # the breakpoint instruction
        print(self.path_prefix, 'rerunning')
        addr, rd, repeat = self.breakpoint
        cmd = ['rv-sim', '-M', hex(addr), '--',
               os.path.join(SRC_DIR, 'cl'),
               self.path_prefix + '.1.cfg',
               self.path_prefix + '.1.dump']
        p = Popen(cmd, bufsize=8, stdout=PIPE, encoding='utf-8')
        while True:
            line = p.stdout.readline()
            if not line:
                raise Exception('expected cl')
            if line == 'invoke cl\n':
                break

        # insert execution into the syscall sequence
        syscall_queue = list(reversed(self.syscalls))
        new_syscalls = []
        while True:
            line = p.stdout.readline()
            if not line:
                raise Exception('incomplete execution')
            if line.startswith('execute'):
                val = int(line.split()[1], 16)
                syscall = SysCall(addr, val, alter_rd=rd)
                new_syscalls.append(syscall)
                repeat -= 1
            elif line.startswith('syscall'):
                val = int(line.split()[1], 16)
                syscall = syscall_queue.pop()
                assert val == syscall.retval
                new_syscalls.append(syscall)
            # omit the last occurence of the breakpoint, since this
            # execution shouldn't happen, and may incur errors (e.g.
            # loading from a new page)
            if repeat == 1 and not syscall_queue:
                syscall = SysCall(addr, is_break=True)
                new_syscalls.append(syscall)
                p.kill()
                break

        # process again with the new syscall sequence
        print(self.path_prefix, 'second pass')
        self.syscalls = new_syscalls
        self.pages = pages
        self.process_once(suffix='.2')
        self.verify('.2')

    def verify(self, suffix='.1'):
        if self.clpath is not None:
            print(self.path_prefix, 'verifying')
            cmd = ['spike', 'pk', self.clpath,
                   self.path_prefix + suffix + '.cfg',
                   self.path_prefix + suffix + '.dump']
            p = Popen(cmd, stdin=DEVNULL, stdout=PIPE)
            cause = b'\n'
            while True:
                line = p.stdout.readline()
                if not line:
                    break
                cause = line
            if p.wait():
                cause = cause.decode('utf-8')[:-1]
                info = '[%d] %s' % (p.returncode, cause)
                print(self.path_prefix, info)
                return
        print(self.path_prefix, 'done')

    def make_replay_table(self, verbose: bool):
        buf = []

        # entrypoint
        buf.append((SysCall.ENTRY).to_bytes(8, 'little'))
        buf.append(self.regs[10])  # a0

        # syscalls
        # breakpoint is automatically encoded
        for syscall in self.syscalls:
            buf.append(syscall.make_entry(verbose))

        # store assertions
        for addr, size, data in sorted(self.stores):
            addr = addr.to_bytes(8, 'little')
            size = size.to_bytes(8, 'little')
            data = data.to_bytes(8, 'little')
            buf.append(addr + size + data)
        buf.append((0).to_bytes(8, 'little'))
        buf.append((0).to_bytes(8, 'little'))

        return b''.join(buf)

    def exists(self) -> bool:
        if self.bbv is not None:
            bbvpath = self.path_prefix + '.bb'
            if not os.path.exists(bbvpath):
                return False
        if self.breakpoint is None:
            cfgpath = self.path_prefix + '.1.cfg'
            dumppath = self.path_prefix + '.1.dump'
        else:
            cfgpath = self.path_prefix + '.2.cfg'
            dumppath = self.path_prefix + '.2.dump'
        return os.path.exists(cfgpath) and os.path.exists(dumppath)


def main(logpath, execpath, rebuild, verify):
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
        page <pn>
        exec <pn>
    '''
    f = open(logpath)
    dirname = os.path.dirname(logpath)
    cur = None
    dumpfile = None
    children = set()  # pid
    bbv = BBVBase(execpath) if execpath else None
    clpath = os.path.join(SRC_DIR, 'cl') if verify else None

    def submit_task():
        if cur is None:
            return
        dumpfile.close()  # close it as soon as possible

        # no multiprocessing
        if args.jobs < 2:
            cur.process()
            return

        # block main if parallel jobs reach limitation
        if len(children) == args.jobs:
            pid, status = os.wait()
            children.remove(pid)
            if status:
                while children:
                    children.remove(os.wait()[0])
                exit(-1)

        # do fork
        pid = os.fork()
        if pid != 0:
            children.add(pid)
            return
        f.close()
        MakeHelper.identifier = os.getpid().to_bytes(4, 'little')
        cur.process()
        exit(0)

    while True:
        line = f.readline()
        if not line:
            submit_task()
            break
        tokens = line.split()

        if tokens[0] == 'begin':
            submit_task()
            cur = Checkpoint()
            cur.entry_pc = int(tokens[1], 16)
            cur.bbv = bbv
            cur.clpath = clpath

        elif tokens[0] in {'ireg', 'freg'}:
            for val in tokens[1:]:
                reg = int(val, 16).to_bytes(8, 'little')
                cur.regs.append(reg)

        elif tokens[0] == 'syscall':
            addr = int(tokens[1], 16)
            if len(tokens) > 3 and tokens[3] == 'exit':
                syscall = SysCall(addr, is_break=True)
            else:
                syscall = SysCall(addr, int(tokens[2], 16))
                if len(tokens) > 3:
                    syscall.waddr = int(tokens[3], 16)
                    syscall.set_wdata(tokens[4])
            cur.syscalls.append(syscall)

        elif tokens[0] == 'break':
            addr = int(tokens[1], 16)
            if tokens[2] == 'repeat':
                repeat = int(tokens[3])
                rd = int(tokens[4])
                assert rd != 0
                cur.breakpoint = (addr, rd, repeat)
            else:
                syscal = SysCall(addr, is_break=True)
                cur.syscalls.append(syscal)

        elif tokens[0] == 'file':
            path = os.path.join(dirname, tokens[1])
            cur.path_prefix, _ = os.path.splitext(path)
            if rebuild or not cur.exists():
                dumpfile = open(path, 'rb')
            else:
                cur = None
        elif tokens[0] == 'page':
            if cur is not None:
                bitmap = dumpfile.read(PAGE_SIZE // 8)
                data = dumpfile.read(PAGE_SIZE)
                pn = int(tokens[1], 16)
                cur.pages[pn] = Page(bitmap, data)
        elif tokens[0] == 'exec':
            if cur is not None:
                data = dumpfile.read(PAGE_SIZE * 2)
                pn = int(tokens[1], 16)
                cur.pages[pn].set_exec_count(data)

        elif tokens[0] == 'store':
            if cur is not None:
                addr = int(tokens[1], 16)
                size = len(tokens[2]) // 2
                data = int(tokens[2], 16)
                cur.stores.append((addr, size, data))

        else:
            raise KeyError(tokens[0])

    f.close()
    while children:
        pid, status = os.wait()
        children.remove(pid)
        if status:
            while children:
                children.remove(os.wait()[0])
            exit(-1)


if __name__ == '__main__':
    args = parser.parse_args()
    try:
        main(args.path, args.exec, args.rebuild, args.verify)
    except KeyboardInterrupt:
        pass
