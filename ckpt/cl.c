#include "cl.h"
#include "raw-syscall.h"
#include "FastLZ/fastlz.h"

void map_pages(void *mc_p, int mc_num, int md_fd)
{
    char buf[CL_BUF_SIZE];

    for (int i = 0; i < mc_num; i++) {
        mmap_cfg *mc_i = (mmap_cfg *)mc_p + i;
        if (mc_i->size == mc_i->length) {
            void *addr = (void *)mc_i->addr;
            addr = raw_mmap(addr, mc_i->size,
                            PROT_EXEC | PROT_READ | PROT_WRITE,
                            MAP_PRIVATE | MAP_FIXED,
                            md_fd, mc_i->offset);
            if ((long)addr < 0) {
                RAW_PANIC("mmap file failed");
            }
            // force OS to allocate private pages by reading and
            // writing one word of it, in case the copy-on-write
            // handling happens during execution
            for (uint64_t i = 0; i < mc_i->size; i += 4096) {
                volatile long *p = addr + i;
                *p = *p;
            }
        } else {
            void *addr = (void *)mc_i->addr;
            addr = raw_mmap(addr, mc_i->size,
                            PROT_EXEC | PROT_READ | PROT_WRITE,
                            MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED,
                            -1, 0);
            if ((long)addr < 0) {
                RAW_PANIC("mmap anonymous failed");
            }
            if (raw_lseek(md_fd, mc_i->offset, SEEK_SET) < 0) {
                RAW_PANIC("lseek failed");
            }
            if (raw_read(md_fd, buf, mc_i->length) != mc_i->length) {
                RAW_PANIC("read failed");
            }
            if (!fastlz_decompress(buf, mc_i->length, addr, mc_i->size)) {
                RAW_PANIC("decompress failed");
            }
        }
    }

    raw_close(md_fd);
    RAW_LOG("begin execution");
}
