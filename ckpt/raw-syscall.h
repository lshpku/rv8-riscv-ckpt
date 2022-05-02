#ifndef __RAW_SYSCALL_H__
#define __RAW_SYSCALL_H__
#include <unistd.h>
#include <sys/mman.h>

int raw_close(int fd);

off_t raw_lseek(int fd, off_t offset, int whence);

ssize_t raw_read(int fd, void *buf, size_t count);

ssize_t raw_write(int fd, const void *buf, size_t count);

void *raw_mmap(void *addr, size_t length, int prot, int flags,
               int fd, off_t offset);

void raw_exit(int status) __attribute__((noreturn));

#define RAW_FPRINT(fd, msg)                    \
    do {                                       \
        const char buf[sizeof(msg) - 1] = msg; \
        raw_write(fd, buf, sizeof(buf));       \
    } while (0)

#define RAW_PRINT(msg) RAW_FPRINT(1, msg)

#define RAW_LOG(msg) RAW_PRINT(msg "\n")

#define RAW_PANIC(msg)       \
    RAW_FPRINT(2, msg "\n"); \
    raw_exit(-1)

#endif
