import os
import math
import ctypes
import argparse

dirname = os.path.dirname(__file__)
dirname = dirname if dirname else '.'
libpath = os.path.join(dirname, 'fastlz.so')
lib = ctypes.CDLL(libpath)
fastlz_compress_level = lib.fastlz_compress_level
fastlz_decompress = lib.fastlz_decompress


def compress(input: bytes) -> bytes:
    assert len(input) >= 16
    outlen = max(66, math.ceil(len(input) * 1.05))
    output = ctypes.create_string_buffer(outlen)
    outlen = fastlz_compress_level(2, input, len(input), output)
    return output.raw[:outlen]


def decompress(input: bytes, maxout: int) -> bytes:
    assert len(input) > 0
    output = ctypes.create_string_buffer(maxout)
    outlen = fastlz_decompress(input, len(input), output, maxout)
    assert outlen > 0
    return output.raw[:outlen]


parser = argparse.ArgumentParser()
parser.add_argument('cfg')
parser.add_argument('dump')
parser.add_argument('-r', '--max-ratio', type=float, default=0.3)
parser.add_argument('-l', '--max-length', type=int, default=2048)

if __name__ == '__main__':
    args = parser.parse_args()

    # read image
    cfgfile = open(args.cfg)
    dumpfile = open(args.dump, 'rb')

    page_map = {}

    mc_num = int(cfgfile.readline())
    for _ in range(mc_num):
        tokens = cfgfile.readline().split()
        assert len(tokens) == 4, 'Bad cfg format'
        addr = int(tokens[0], 16)
        offset = int(tokens[1], 16)
        size = int(tokens[2], 16)
        length = int(tokens[3], 16)
        assert size == length, 'Expected uncompressed data'

        dumpfile.seek(offset)
        data = dumpfile.read(length)
        assert len(data) == length, 'Unexpected EOF'

        # split dump into single pages
        for off in range(0, size, 4096):
            page_map[addr + off] = data[off:off + 4096]

    entry_pc = int(cfgfile.readline(), 16)
    cfgfile.close()
    dumpfile.close()

    # try compressing data
    comp = []  # addr, [data, ...]
    uncomp = []  # addr, [data, ...]
    comp_pages = 0
    for addr, data in sorted(page_map.items()):
        comp_data = compress(data)
        # compressed pages may be coalesced if each page fits
        # into the min compression ratio and the total length
        # is within the max length
        if len(comp_data) <= len(data) * args.max_ratio:
            if not comp:
                comp.append((addr, [data]))
            elif comp[-1][0] + len(comp[-1][1]) * 4096 < addr:
                comp.append((addr, [data]))
            elif len(compress(b''.join(comp[-1][1]) + data)) > args.max_length:
                comp.append((addr, [data]))
            else:
                comp[-1][1].append(data)
            comp_pages += 1
        # uncompressed pages can be freely coalesced
        else:
            if not uncomp:
                uncomp.append((addr, [data]))
            elif uncomp[-1][0] + len(uncomp[-1][1]) * 4096 < addr:
                uncomp.append((addr, [data]))
            else:
                uncomp[-1][1].append(data)

    # dump processed image
    cfgfile = open('.c'.join(os.path.splitext(args.cfg)), 'w')
    dumpfile = open('.c'.join(os.path.splitext(args.dump)), 'wb')
    offset = 0
    cfgfile.write('%d\n' % (len(comp) + len(uncomp)))

    # dump uncompressed pages first since they need to be
    # page-aligned
    for addr, data in uncomp:
        size = len(data) * 4096
        cfgfile.write('%x\t%x\t%x\t%x\n' % (addr, offset, size, size))
        dumpfile.write(b''.join(data))
        offset += size

    for addr, data in comp:
        size = len(data) * 4096
        comp_data = compress(b''.join(data))
        length = len(comp_data)
        cfgfile.write('%x\t%x\t%x\t%x\n' % (addr, offset, size, length))
        dumpfile.write(comp_data)
        offset += length

    cfgfile.write('%x\n' % entry_pc)
    cfgfile.close()
    dumpfile.close()

    print('compressed pages: %d/%d' % (comp_pages, len(page_map)))
    comp_ratio = 1 - offset / (len(page_map) * 4096)
    print('compression ratio: %.1f%%' % (comp_ratio * 100))
