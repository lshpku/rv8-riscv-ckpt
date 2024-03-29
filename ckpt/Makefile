
TOOLCHAIN ?= riscv64-unknown-linux-gnu-

CC      = $(TOOLCHAIN)gcc
LD      = $(TOOLCHAIN)ld
OBJCOPY = $(TOOLCHAIN)objcopy

CFLAGS  = -O3

all:

ifdef FAR_CALL
$(eval CDEFS += -DFAR_CALL=$(FAR_CALL))
endif
ifdef ALTER_RD
$(eval CDEFS += -DALTER_RD=$(ALTER_RD))
endif
ifdef ALTER_RD_IS_SP
$(eval CDEFS += -DALTER_RD_IS_SP=1)
endif
ifdef NORVC
$(eval CDEFS += -DNORVC=1)
endif
ifndef NUM_CSR
NUM_CSR = 2
else
$(eval CDEFS += -DNUM_CSR=$(NUM_CSR))
endif

near%.o: near.S
	$(CC) $(CDEFS) -DNEAR_BUF=$(NEAR_BUF) -c -o $@ $<
near%.partial: near%.o
	$(LD) -e 0 -o $@ $^

far%.o: far.S
	$(CC) -DREPLAY_SP=$(REPLAY_SP) -DREPLAY_PC=$(REPLAY_PC) -c -o $@ $<
far%.partial: far%.o
	$(LD) -e 0 -o $@ $<

jump%.o: jump.S
	$(CC) $(CDEFS) -DOFFSET=$(OFFSET) -c -o $@ $<
jump%.partial: jump%.o
	$(LD) -e 0 -o $@ $^

FASTLZ_FLAGS = -fno-tree-loop-distribute-patterns -DFASTLZ_USE_MEMMOVE=0

cl.o: cl.c
	$(CC) $(CFLAGS) -fPIC -c -o $@ $<
entry.o: entry.S
	$(CC) -DNUM_CSR=$(NUM_CSR) -c -o $@ $<
replay.o: replay.c
	$(CC) $(CFLAGS) -fPIC $(CDEFS) -c -o $@ $<
fastlz.o: FastLZ/fastlz.c FastLZ/fastlz.h
	$(CC) $(CFLAGS) -fPIC $(FASTLZ_FLAGS) -c -o $@ $<
cl.partial: entry.o cl.o replay.o fastlz.o
	$(LD) -e 0 -o $@ $^
cl: main.c cl-wrapper.S cl.bin
	$(CC) $(CFLAGS) -static -o $@ $(filter %.c %.S, $^)

%.bin: %.partial
	$(OBJCOPY) -O binary $< $@

fastlz.so: FastLZ/fastlz.c
	gcc -O3 -shared -o $@ $<

clean:
	rm -f cl *.o *.partial *.bin

