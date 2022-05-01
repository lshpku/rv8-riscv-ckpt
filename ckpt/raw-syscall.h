#ifndef __RAW_SYSCALL_H__
#define __RAW_SYSCALL_H__

#define RAW_SYSCALL(name, number, end) \
    .global name;                      \
name:                                  \
    li a7, number;                     \
    ecall;                             \
    end;                               \
    .size name, .-name;

#define RAW_LSEEK RAW_SYSCALL(raw_lseek,  62, ret)
#define RAW_READ  RAW_SYSCALL(raw_read,   63, ret)
#define RAW_WRITE RAW_SYSCALL(raw_write,  64, ret)
#define RAW_EXIT  RAW_SYSCALL(raw_exit,   93, unimp)
#define RAW_MMAP  RAW_SYSCALL(raw_mmap,  222, ret)

#endif
