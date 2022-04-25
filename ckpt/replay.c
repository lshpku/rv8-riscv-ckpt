#include <stdint.h>
#include <stddef.h>

typedef struct {
    uint64_t addr;
    uint64_t size;
    char value[0];
} replay_cfg;

replay_cfg *replay(replay_cfg *head)
{
    while (head->addr) {
        size_t size = head->size;
        char *src = head->value;
        char *dst = (void *)head->addr;
        while (size--)
            *(dst++) = *(src++);
        head = (void *)head + sizeof(replay_cfg) + ((head->size + 7) & ~7);
    }
    return head + sizeof(replay_cfg);
}
