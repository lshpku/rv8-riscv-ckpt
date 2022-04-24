
CC = riscv64-unknown-elf-gcc
LD = riscv64-unknown-elf-ld
OBJCOPY = riscv64-unknown-elf-objcopy

all: near.bin far.bin

near.bin: near.S
	$(CC) near.S -DRT_BUF=0x7ffe4000 -DFAR_CALL=0x62030 -c -o near.o
	$(OBJCOPY) -O binary near.o near.bin

far.bin: far.S replay.c
	$(CC) far.S -DFAR_STACK_TOP=0x7ffe4000 -c -o far.o
	$(CC) -fPIC -O3 -c replay.c -o replay.o
	$(LD) -e 0x10000 far.o replay.o -o partial.o
	$(OBJCOPY) -O binary partial.o far.bin

