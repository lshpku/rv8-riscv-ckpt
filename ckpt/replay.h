#ifndef __REPLAY_H__
#define __REPLAY_H__
#include <stdint.h>

#define REPLAY_RET 0
#define REPLAY_EXIT 1
#define REPLAY_STAT 2

typedef struct {
    uint64_t addr;
    uint64_t size;
    char data[0];
} replay_cfg;

#define DEFINE_CSRR(sym)              \
    inline uint64_t __csrr_##sym()    \
    {                                 \
        uint64_t value;               \
        asm volatile("csrr %0, " #sym \
                     : "=r"(value));  \
        return value;                 \
    }

DEFINE_CSRR(cycle)
DEFINE_CSRR(instret)

#endif
