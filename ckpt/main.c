#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <string.h>
#include <fcntl.h>
#include <sys/mman.h>

typedef struct {
    uint64_t addr;
    uint64_t offs;
    uint64_t size;
    int prot;
    int flags;
} mmap_cfg;

typedef void (*cl_func)(mmap_cfg *, size_t, int, uint64_t);

void cl_begin();
void cl_end();

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

    // decide cl core size
    int mc_num;
    if (fscanf(cfg_f, "%d", &mc_num) != 1) {
        fprintf(stderr, "expected mc_num\n");
        return -1;
    }

    size_t cl_size = cl_end - cl_begin;
    size_t mc_size = mc_num * sizeof(mmap_cfg);
    size_t total_size = cl_size + mc_size;
    size_t alloc_size = (total_size + 0xfff) & ~0xfff;

    printf("cl_size    = %ld\n", cl_size);
    printf("mc_size    = %ld\n", mc_size);
    printf("total_size = %ld\n", total_size);
    printf("alloc_size = %ld\n", alloc_size);

    // find a place to map cl
    void *cl_p = (void *)0x60000000;
    cl_p = mmap(cl_p, alloc_size, PROT_EXEC | PROT_READ | PROT_WRITE,
                MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
    if (cl_p == MAP_FAILED) {
        fprintf(stderr, "cannot map cl: %s\n", strerror(errno));
        return -1;
    }
    memcpy(cl_p, cl_begin, cl_size);
    asm volatile("fence.i");
    printf("map cl to %p\n", cl_p);

    // parse mmap_cfgs
    mmap_cfg *mc_p = cl_p + cl_size;
    for (int i = 0; i < mc_num; i++) {
        if (fscanf(cfg_f, "%llx%llx%llx",
                   &mc_p[i].addr, &mc_p[i].offs, &mc_p[i].size) != 3) {
            fprintf(stderr, "expected mmap_cfg\n");
            return -1;
        }
        mc_p[i].prot = PROT_EXEC | PROT_READ | PROT_WRITE;
        mc_p[i].flags = MAP_PRIVATE | MAP_FIXED;
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
    ((cl_func)cl_p)(mc_p, mc_num, dump_f, pc);
}
