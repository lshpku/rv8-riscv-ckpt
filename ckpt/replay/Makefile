
CC = riscv64-unknown-elf-gcc
LD = riscv64-unknown-elf-ld
OBJCOPY = riscv64-unknown-elf-objcopy


all:

near.o: near.S
	$(CC) -DNEAR_BUF=$(NEAR_BUF) -DFAR_CALL=$(FAR_CALL) -c -o $@ $<
near.bin: near.o
	$(OBJCOPY) -O binary $< $@

far.o: far.S
	$(CC) -DFAR_STACK_TOP=$(FAR_STACK_TOP) -c -o $@ $<
replay.o: replay.c
	$(CC) -fPIC -O3 -c -o $@ $<
partial.o: far.o replay.o
	$(LD) -e 0x10000 -o $@ $^
replay.bin: partial.o
	$(OBJCOPY) -O binary $< $@

jump.o: jump.S
	$(CC) -DOFFSET=$(OFFSET) -c -o $@ $<
jump.bin: jump.o
	$(OBJCOPY) -O binary $< $@

clean:
	rm -f *.o *.bin

