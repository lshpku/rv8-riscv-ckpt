#ifndef __RAW_SYSCALL_IMPL_H__
#define __RAW_SYSCALL_IMPL_H__

#define RAW_SYSCALL(name, number, end) \
    .global raw_##name;                \
raw_##name:                            \
    li a7, number;                     \
    ecall;                             \
    end;                               \
    .size raw_##name, .-raw_##name;

#define RAW_CLOSE RAW_SYSCALL(close,  57, ret)
#define RAW_LSEEK RAW_SYSCALL(lseek,  62, ret)
#define RAW_READ  RAW_SYSCALL(read,   63, ret)
#define RAW_WRITE RAW_SYSCALL(write,  64, ret)
#define RAW_EXIT  RAW_SYSCALL(exit,   93, unimp)
#define RAW_MMAP  RAW_SYSCALL(mmap,  222, ret)

#endif
