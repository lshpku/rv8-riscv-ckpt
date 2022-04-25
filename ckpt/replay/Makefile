
TOOLCHAIN ?= riscv64-unknown-linux-gnu-

CC      = $(TOOLCHAIN)gcc
LD      = $(TOOLCHAIN)ld
OBJCOPY = $(TOOLCHAIN)objcopy

all:

near.o: near.S
	$(CC) -DNEAR_BUF=$(NEAR_BUF) -DFAR_CALL=$(FAR_CALL) -c -o $@ $<
near.partial.o: near.o
	$(LD) -e 0x10000 -o $@ $^
near.bin: near.partial.o
	$(OBJCOPY) -O binary $< $@

far.o: far.S
	$(CC) -DFAR_STACK_TOP=$(FAR_STACK_TOP) -c -o $@ $<
replay.o: replay.c
	$(CC) -fPIC -O3 -c -o $@ $<
far.partial.o: far.o replay.o
	$(LD) -e 0x10000 -o $@ $^
far.bin: far.partial.o
	$(OBJCOPY) -O binary $< $@

jump.o: jump.S
	$(CC) -DOFFSET=$(OFFSET) -c -o $@ $<
jump.partial.o: jump.o
	$(LD) -e 0 -o $@ $^
jump.bin: jump.partial.o
	$(OBJCOPY) -O binary $< $@

clean:
	rm -f *.o *.bin

