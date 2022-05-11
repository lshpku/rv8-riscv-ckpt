#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <string.h>
#include <fcntl.h>
#include <sys/mman.h>
#include "cl.h"

void cl_begin();
void cl_end();

void cl_proxy_entry(mmap_cfg *mc_p, int mc_num, int md_fd, uint64_t pc,
                    void *cl_p, void *sp) __attribute__((noreturn));

#define COMPARE(a, b) ((a) == (b) ? 0 : ((a) < (b) ? -1 : 1))
static int less_addr(const mmap_cfg *a, const mmap_cfg *b)
{
    return COMPARE(a->addr, b->addr);
}
static int less_offset(const mmap_cfg *a, const mmap_cfg *b)
{
    return COMPARE(a->offset, b->offset);
}

typedef int (*f_cmp)(const void *, const void *, void *);
extern void _quicksort(void *, size_t, size_t, f_cmp, void *);
inline void _qsort(void *b, size_t n, size_t s, void *cmp)
{
    // glibc qsort selects the sorting algorithm dynamically
    // between quicksort and mergesort by making the sysinfo
    // syscall, which is unsupported on some platforms. Here
    // I force it to use quicksort
    _quicksort(b, n, s, (f_cmp)cmp, NULL);
}

int main(int argc, char *argv[])
{
    // parse arguments
    if (argc != 3) {
        fprintf(stderr, "usage: %s cfg_path dump_path\n", argv[0]);
        return -1;
    }
    FILE *cfg_f = fopen(argv[1], "r");
    if (!cfg_f) {
        fprintf(stderr, "%s: %s\n", argv[1], strerror(errno));
        return -1;
    }
    int dump_f = open(argv[2], O_RDONLY);
    if (dump_f == -1) {
        fprintf(stderr, "%s: %s\n", argv[2], strerror(errno));
        return -1;
    }

    // parse mmap_cfgs
    int mc_num;
    if (fscanf(cfg_f, "%d", &mc_num) != 1) {
        fprintf(stderr, "expected mc_num\n");
        return -1;
    }
    size_t mc_size = mc_num * sizeof(mmap_cfg);
    size_t mc_map_size = ALIGN_PAGE(mc_size + CL_STACK_SIZE);
    mmap_cfg *mc_buf = (mmap_cfg *)malloc(mc_size);
    if (!mc_buf) {
        fprintf(stderr, "cannot allocate mc_buf\n");
        return -1;
    }
    for (int i = 0; i < mc_num; i++) {
        if (fscanf(cfg_f, "%llx%llx%x%x",
                   &mc_buf[i].addr, &mc_buf[i].offset,
                   &mc_buf[i].size, &mc_buf[i].length) != 4) {
            fprintf(stderr, "expected mmap_cfg\n");
            return -1;
        }
    }

    // parse entrypoint pc
    uint64_t pc;
    if (fscanf(cfg_f, "%llx", &pc) != 1) {
        fprintf(stderr, "expected pc\n");
        return -1;
    }
    fclose(cfg_f);

    // find a place to map cl
    size_t cl_size = cl_end - cl_begin;
    size_t cl_map_size = ALIGN_PAGE(cl_size);
    size_t total_size = cl_map_size + mc_map_size;
    _qsort(mc_buf, mc_num, sizeof(mmap_cfg), less_addr);
    uint64_t found_base = CL_BASE;
    for (int i = 0; i < mc_num; i++) {
        if (found_base + total_size > mc_buf[i].addr &&
            found_base < mc_buf[i].addr + mc_buf[i].size) {
            found_base = mc_buf[i].addr + mc_buf[i].size;
        }
    }
    if (found_base + total_size > CL_TOP) {
        fprintf(stderr, "cannot find a place to map cl\n");
        return -1;
    }

    // map cl
    void *cl_p = (void *)found_base;
    cl_p = mmap(cl_p, cl_map_size, PROT_EXEC | PROT_READ | PROT_WRITE,
                MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
    if (cl_p == MAP_FAILED) {
        fprintf(stderr, "cannot map cl: %s\n", strerror(errno));
        return -1;
    }
    memcpy(cl_p, cl_begin, cl_size);
    asm volatile("fence.i");
    printf("map cl to %p-%p\n", cl_p, cl_p + cl_map_size - 1);

    // map mmap_cfgs
    void *mc_p = cl_p + cl_map_size;
    mc_p = mmap(mc_p, mc_map_size, PROT_READ | PROT_WRITE,
                MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
    if (mc_p == MAP_FAILED) {
        fprintf(stderr, "cannot map mc: %s\n", strerror(errno));
        return -1;
    }
    _qsort(mc_buf, mc_num, sizeof(mmap_cfg), less_offset);
    memcpy(mc_p, mc_buf, mc_size);
    printf("map mc to %p-%p\n", mc_p, mc_p + mc_map_size - 1);

    // invoke cl (no return)
    printf("invoke cl\n");
    fflush(stdout);
    cl_proxy_entry(mc_p, mc_num, dump_f, pc, cl_p, mc_p + mc_map_size);
}
