#include "cl.h"
#include "raw-syscall.h"
#include "FastLZ/fastlz.h"

#define LOG(fd, msg) \
    raw_write(fd, msg "\n", sizeof(msg))

#define PANIC(msg) \
    LOG(2, msg); \
    raw_exit(-1)

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
                PANIC("mmap file failed");
            }
        } else {
            void *addr = (void *)mc_i->addr;
            addr = raw_mmap(addr, mc_i->size,
                            PROT_EXEC | PROT_READ | PROT_WRITE,
                            MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED,
                            -1, 0);
            if ((long)addr < 0) {
                PANIC("mmap anonymous failed");
            }
            if (raw_lseek(md_fd, mc_i->offset, SEEK_SET) < 0) {
                PANIC("lseek failed");
            }
            if (raw_read(md_fd, buf, mc_i->length) != mc_i->length) {
                PANIC("read failed");
            }
            if (!fastlz_decompress(addr, mc_i->length, addr, mc_i->size)) {
                PANIC("decompress failed");
            }
        }
    }

    raw_close(md_fd);
    LOG(1, "begin execution");
}
