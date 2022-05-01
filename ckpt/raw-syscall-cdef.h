#ifndef __RAW_SYSCALL_CDEF_H__
#define __RAW_SYSCALL_CDEF_H__
#include <unistd.h>
#include <sys/mman.h>

off_t raw_lseek(int fd, off_t offset, int whence);

ssize_t raw_read(int fd, void *buf, size_t count);

ssize_t raw_write(int fd, const void *buf, size_t count);

void *raw_mmap(void *addr, size_t length, int prot, int flags,
               int fd, off_t offset);

void raw_exit(int status) __attribute__((noreturn));

#endif
