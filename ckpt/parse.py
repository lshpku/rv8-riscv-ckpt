import os
import io
import copy
import argparse
import hashlib
from subprocess import Popen, PIPE, DEVNULL
from typing import Union, List, Tuple

parser = argparse.ArgumentParser()
parser.add_argument('path')
parser.add_argument('-j', '--jobs', type=int, default=1)

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
            args += ['ALTER_RD=x%d' % alter_rd]
        if norvc:
            args += ['NORVC=1']
        near = MakeHelper.make('near.bin', args)
        ret = MakeHelper.jump(ret_pc - near_pc - len(near))
        return near + ret

    @staticmethod
    def far(far_stack_top: int, verbose: bool = False):
        args = ['FAR_STACK_TOP=0x%x' % far_stack_top]
        if verbose:
            args += ['VERBOSE=1']
        return MakeHelper.make('far.bin', args)


class Page:

    def __init__(self, bitmap: Union[int, bytes], data: bytes):
        if isinstance(bitmap, int):
            self.bitmap = bitmap
        else:
            self.bitmap = int.from_bytes(bitmap, 'little')
        self.data = io.BytesIO(data)

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
            cfgfile.write('%x\t%x\t%x\n' % (addr, offs, size))
            offs += size

        # write pages
        for i, (pn, page) in enumerate(page_list):
            dumpfile.write(page.get())


class SysCall:

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

    def make_entry(self) -> bytes:
        buf = []

        if self.waddr is not None:
            buf.append(self.waddr.to_bytes(8, 'little'))

            padded_size = (len(self.wdata) + 7) & ~7
            buf.append(padded_size.to_bytes(8, 'little'))

            padding_size = padded_size - len(self.wdata)
            buf.append(self.wdata)
            buf.append(b'\0' * padding_size)

        if not self.is_break:
            buf.append((0).to_bytes(8, 'little'))
            buf.append(self.retval.to_bytes(8, 'little'))
        else:
            buf.append((-1).to_bytes(8, 'little', signed=True))
            buf.append((0).to_bytes(8, 'little'))

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

    def process_once(self, verbose=False, suffix='.1'):
        # reserve space for near_calls
        for syscall in self.syscalls:
            # set all 4 bytes in case the latter 2 bytes of
            # an rvc instruction are considered free
            self.pages.put(syscall.addr, b'\0' * 4)
        free_list = self.pages.make_free_list()
        near_map = {}  # base_addr: near_addr

        size1 = len(MakeHelper.near(0, 0, 0, 0))
        size2 = len(MakeHelper.near(0, 0, 0, 0, 0))
        for syscall in self.syscalls:
            if syscall.addr in near_map:
                continue
            size = size1 if syscall.alter_rd is None else size2
            near_addr = self.pages.reserve(free_list, syscall.addr, size)
            near_map[syscall.addr] = near_addr

        size = len(MakeHelper.near(0, 0, 0))
        entry_addr = self.pages.reserve(free_list, self.entry_pc, size)

        # reserve pages for supervisor
        '''
        Supervisor (SV) structure:
                +--------------+
                |              | replay_table_head
            rw  |  far_stack   |  4K
                |              | near_buf
                +--------------+
                |   regfile    |
                | ------------ |
            ro  |              |  4K * N
                | replay_table |
                |              |
                +--------------+
            rx  |   far_call   |  4K
                +--------------+
        '''
        replay_table = self.make_replay_table()
        rw_size = PAGE_SIZE
        ro_size = len(replay_table) + 8 * len(self.regs)
        ro_size = (ro_size + PAGE_OFFS_MASK) & ~PAGE_OFFS_MASK
        rx_size = PAGE_SIZE
        sv_size = rx_size + ro_size + rw_size

        sv_pn = self.pages.reserve_page(sv_size)

        far_addr = sv_pn * PAGE_SIZE
        replay_table_addr = far_addr + rx_size
        regs_addr = replay_table_addr + len(replay_table)
        near_buf = replay_table_addr + ro_size
        far_stack_top = near_buf + rw_size

        # write near_calls
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
        self.regs[0] = entry_addr.to_bytes(8, 'little')

        # write supervisor
        far_call = MakeHelper.far(far_stack_top, verbose)
        self.pages.put(far_addr, far_call)
        self.pages.put(replay_table_addr, replay_table)
        self.pages.put(regs_addr, b''.join(self.regs))
        self.pages.put(near_buf, self.regs[2])
        self.pages.put(far_stack_top - 8,
                       replay_table_addr.to_bytes(8, 'little'))

        # dump pages and cfg
        dumpfile = open(self.path_prefix + suffix + '.dump', 'wb')
        cfgfile = open(self.path_prefix + suffix + '.cfg', 'w')
        self.pages.dump(dumpfile, cfgfile)
        dumpfile.close()
        cfgfile.write('%x\n' % regs_addr)
        cfgfile.close()

    def process(self):
        # break with ecall or first-executed instruction
        if self.breakpoint is None:
            print(self.path_prefix, 'single pass')
            self.process_once()
            print(self.path_prefix, 'done')
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
        syscall_iter = iter(self.syscalls)
        syscalls = []
        while True:
            line = p.stdout.readline()
            if not line:
                raise Exception('incomplete execution')
            if line.startswith('execute'):
                val = int(line.split()[1], 16)
                repeat -= 1
                if repeat > 0:
                    syscall = SysCall(addr, val, alter_rd=rd)
                    syscalls.append(syscall)
                else:
                    syscall = SysCall(addr, is_break=True)
                    syscalls.append(syscall)
                    p.kill()
                    break
            elif line.startswith('syscall'):
                val = int(line.split()[1], 16)
                syscall = next(syscall_iter)
                assert val == syscall.retval
                syscalls.append(syscall)

        # process again with the new syscall sequence
        print(self.path_prefix, 'second pass')
        self.syscalls = syscalls
        self.pages = pages
        self.process_once(suffix='.2')
        print(self.path_prefix, 'done')

    def make_replay_table(self):
        buf = []

        # syscalls
        # breakpoint is automatically encoded
        for syscall in self.syscalls:
            buf.append(syscall.make_entry())

        # store assertions
        for addr, size, data in self.stores:
            addr = addr.to_bytes(8, 'little')
            size = size.to_bytes(8, 'little')
            data = data.to_bytes(8, 'little')
            buf.append(addr + size + data)
        buf.append((0).to_bytes(8, 'little'))
        buf.append((0).to_bytes(8, 'little'))

        return b''.join(buf)


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
    children = set()  # pid

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
            if status:
                while children:
                    children.remove(os.wait()[0])
                exit(-1)
            children.remove(pid)

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

        elif tokens[0] == 'store':
            addr = int(tokens[1], 16)
            size = len(tokens[2]) // 2
            data = int(tokens[2], 16)
            cur.stores.append((addr, size, data))

        elif tokens[0] == 'file':
            path = os.path.join(dirname, tokens[1])
            dumpfile = open(path, 'rb')
            cur.path_prefix, _ = os.path.splitext(path)
        elif tokens[0] == 'dump':
            bitmap = dumpfile.read(PAGE_SIZE // 8)
            data = dumpfile.read(PAGE_SIZE)
            pn = int(tokens[1], 16)
            cur.pages[pn] = Page(bitmap, data)

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
        parse_log(args.path)
    except KeyboardInterrupt:
        pass
