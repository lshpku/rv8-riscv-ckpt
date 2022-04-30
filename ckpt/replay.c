#include <stdint.h>
#include <stddef.h>

#define REPLAY_RET 0
#define REPLAY_EXIT -1

#define MSG_SUCCESS "finish\n"
#define MSG_ST_FAIL "store assertion failed\n"

typedef struct {
    uint64_t addr;
    uint64_t size;
    char data[0];
} replay_cfg;

void raw_exit(int status) __attribute__((noreturn));
void raw_write(int fd, const void *buf, size_t count);

void do_exit(replay_cfg *head) __attribute__((noreturn));

replay_cfg *replay(replay_cfg *head)
{
    while (head->addr != REPLAY_RET) {
        // handle exit
        if (head->addr == REPLAY_EXIT) {
            do_exit(head + 1);
        }

        // handle copy
        size_t size = head->size;
        char *src = head->data;
        char *dst = (void *)head->addr;
        while (size--)
            *(dst++) = *(src++);
        head = (void *)(head + 1) + ((head->size + 7) & ~7);
    }

#ifdef VERBOSE
    char msg[] = "syscall 0000000000000000\n";
    uint64_t rc = head->size;
    for (int i = 0; i < 16; i++) {
        int b = rc & 0xf;
        char c = b < 10 ? '0' + b : 'a' + b - 10;
        msg[sizeof(msg) - 3 - i] = c;
        rc >>= 4;
    }
    raw_write(1, msg, sizeof(msg) - 1);
#endif

    // return with the address of next entry
    return head + 1;
}

#define COMPARE_WIDTH(w)                        \
    if (*(w *)head->addr != *(w *)head->data) { \
        goto fail;                              \
    }                                           \
    break

void do_exit(replay_cfg *head)
{
    // check memory
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

    raw_write(1, MSG_SUCCESS, sizeof(MSG_SUCCESS) - 1);
    raw_exit(0);

fail:
    raw_write(1, MSG_ST_FAIL, sizeof(MSG_ST_FAIL) - 1);
    raw_exit(-1);
}
