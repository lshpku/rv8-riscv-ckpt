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
parser.add_argument('-r', '--threshold', type=float, default=0.3)

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
    uncomp, comp = [], []
    orig_size, shrink_size = 0, 0
    for addr, data in sorted(page_map.items()):
        orig_size += len(data)
        comp_data = compress(data)
        if len(comp_data) <= len(data) * args.threshold:
            comp.append((addr, comp_data))
            shrink_size += len(data) - len(comp_data)
        else:
            uncomp.append((addr, data))
    print('compressed pages: %d/%d' % (len(comp), len(page_map)))
    print('compression ratio: %.1f%%' % (shrink_size / orig_size * 100))

    # dump processed image
    cfgfile = open('.c'.join(os.path.splitext(args.cfg)), 'w')
    dumpfile = open('.c'.join(os.path.splitext(args.dump)), 'wb')
    cfgs = []  # addr, offset, size, length
    offset = 0

    # dump uncompressed pages first since they need to be
    # page-aligned. Uncompressed pages may be coalesced
    for addr, data in uncomp:
        if cfgs and cfgs[-1][0] + cfgs[-1][2] == addr:
            cfgs[-1][2] += 4096
            cfgs[-1][3] = cfgs[-1][2]
        else:
            cfgs.append([addr, offset, 4096, 4096])
        offset += 4096
        dumpfile.write(data)

    # compressed pages are currently seperated. This is due
    # to the limited size of the decompressor buffer
    for addr, data in comp:
        cfgs.append([addr, offset, 4096, len(data)])
        dumpfile.write(data)
        offset += len(data)

    cfgfile.write('%d\n' % len(cfgs))
    for addr, offset, size, length in cfgs:
        cfgfile.write('%x\t%x\t%x\t%x\n' % (
            addr, offset, size, length))
    cfgfile.write('%x\n' % entry_pc)

    cfgfile.close()
    dumpfile.close()
