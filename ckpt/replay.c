#include "replay.h"
#include "raw-syscall.h"

#define COMPARE_WIDTH(w)                        \
    if (*(w *)head->addr != *(w *)head->data) { \
        return NULL;                            \
    }                                           \
    break

static replay_cfg *check_stores(replay_cfg *head)
{
    while (head->addr != REPLAY_RET) {
        switch (head->size) {
        case 1:
            COMPARE_WIDTH(uint8_t);
        case 2:
            COMPARE_WIDTH(uint16_t);
        case 4:
            COMPARE_WIDTH(uint32_t);
        case 8:
            COMPARE_WIDTH(uint64_t);
        }
        head = (void *)(head + 1) + 8;
    }
    return head;
}

static void fast_memcpy(char *dest, const char *src, size_t n)
{
    do {
        *dest++ = *src++;
    } while (--n);
}

static void raw_log_u64(uint64_t value)
{
    char buf[17];
    for (int i = 0; i < sizeof(buf) - 1; i++) {
        int b = value & 0xf;
        char c = b < 10 ? '0' + b : 'a' + b - 10;
        buf[sizeof(buf) - 2 - i] = c;
        value >>= 4;
    }
    buf[sizeof(buf) - 1] = '\n';
    raw_write(1, buf, sizeof(buf));
}

replay_cfg *replay(replay_cfg *head, uint64_t *csrv)
{
    while (1) {
        switch (head->addr) {
        case REPLAY_RET:
            goto end;
        case REPLAY_RET_VERBOSE:
            goto end_verbose;
        case REPLAY_EXIT: {
            uint64_t cycle = __csrr_cycle();
            uint64_t instret = __csrr_instret();
            if (!(head = check_stores(head + 1))) {
                RAW_PANIC("store assertion failed");
            }
            RAW_LOG("finish");
            RAW_PRINT("cycle ");
            raw_log_u64(cycle - csrv[0]);
            RAW_PRINT("instret ");
            raw_log_u64(instret - csrv[1]);
            raw_exit(0);
        }
        case REPLAY_ENTRY:
            csrv[0] = __csrr_cycle();
            csrv[1] = __csrr_instret();
            goto end;
        default:
            fast_memcpy((void *)head->addr, head->data, head->size);
            head = (void *)(head + 1) + ((head->size + 7) & ~7);
        }
    }

end_verbose:
    RAW_PRINT("syscall ");
    raw_log_u64(head->size);

end:
    // return with the address of next entry
    return head + 1;
}
