#ifndef __CL_H__
#define __CL_H__
#include <stdint.h>
#include <stddef.h>

typedef struct {
    uint64_t addr;
    uint64_t offset;
    uint32_t size;
    uint32_t length;
} mmap_cfg;

#define CL_BASE 0x60000000
#define CL_STACK_SIZE 4096
#define CL_BUF_SIZE 2048

#define ALIGN_PAGE(a) (((a) + 0xfff) & ~0xfff)

#endif
