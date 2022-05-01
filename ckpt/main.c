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

    // map cl text
    size_t cl_size = cl_end - cl_begin;
    size_t cl_map_size = ALIGN_PAGE(cl_size);
    void *cl_p = (void *)CL_BASE;
    cl_p = mmap(cl_p, cl_map_size, PROT_EXEC | PROT_READ | PROT_WRITE,
                MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
    if (cl_p == MAP_FAILED) {
        fprintf(stderr, "cannot map cl: %s\n", strerror(errno));
        return -1;
    }
    memcpy(cl_p, cl_begin, cl_size);
    asm volatile("fence.i");
    printf("map cl to %p-%p\n", cl_p, cl_p + cl_map_size - 1);

    // map cl data (including stack)
    int mc_num;
    if (fscanf(cfg_f, "%d", &mc_num) != 1) {
        fprintf(stderr, "expected mc_num\n");
        return -1;
    }
    size_t mc_size = mc_num * sizeof(mmap_cfg);
    size_t mc_map_size = ALIGN_PAGE(mc_size + CL_STACK_SIZE);
    void *mc_p = cl_p + cl_map_size;
    mc_p = mmap(mc_p, mc_map_size, PROT_READ | PROT_WRITE,
                MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
    if (mc_p == MAP_FAILED) {
        fprintf(stderr, "cannot map mc: %s\n", strerror(errno));
        return -1;
    }
    printf("map mc to %p-%p\n", mc_p, mc_p + mc_map_size - 1);

    // parse mmap_cfgs
    for (int i = 0; i < mc_num; i++) {
        mmap_cfg *mc_i = (mmap_cfg *)mc_p + i;
        if (fscanf(cfg_f, "%llx%llx%x%x",
                   &mc_i->addr, &mc_i->offset,
                   &mc_i->length, &mc_i->size) != 4) {
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

    // invoke cl (no return)
    printf("invoke cl\n");
    fflush(stdout);
    cl_proxy_entry(mc_p, mc_num, dump_f, pc,
                   cl_p, mc_p + mc_map_size);
}
