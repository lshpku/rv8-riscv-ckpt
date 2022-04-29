#include <stdint.h>
#include <stddef.h>

#define REPLAY_RET 0
#define REPLAY_EXIT -1

typedef struct {
    uint64_t addr;
    uint64_t size;
    char value[0];
} replay_cfg;

void raw_exit(int status) __attribute__((noreturn));
void raw_write(int fd, const void *buf, size_t count);

replay_cfg *replay(replay_cfg *head)
{
    while (head->addr != REPLAY_RET) {
        // handle exit
        if (head->addr == REPLAY_EXIT) {
            const char *msg = "exit\n";
            raw_write(1, msg, sizeof(msg) - 1);
            raw_exit(head->size);
        }

        // handle copy
        size_t size = head->size;
        char *src = head->value;
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
