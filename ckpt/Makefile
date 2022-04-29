
TOOLCHAIN ?= riscv64-unknown-linux-gnu-

CC      = $(TOOLCHAIN)gcc
LD      = $(TOOLCHAIN)ld
OBJCOPY = $(TOOLCHAIN)objcopy

all:

ifdef FAR_CALL
$(eval CFLAGS += -DFAR_CALL=$(FAR_CALL))
endif
ifdef ALTER_RD
$(eval CFLAGS += -DALTER_RD=$(ALTER_RD))
endif
ifdef NORVC
$(eval CFLAGS += -DNORVC=1)
endif
ifdef VERBOSE
$(eval CFLAGS += -DVERBOSE=1)
endif

near%.o: near.S
	$(CC) $(CFLAGS) -DNEAR_BUF=$(NEAR_BUF) -c -o $@ $<
near%.partial: near%.o
	$(LD) -e 0 -o $@ $^
near%.bin: near%.partial
	$(OBJCOPY) -O binary $< $@

far%.o: far.S
	$(CC) -DFAR_STACK_TOP=$(FAR_STACK_TOP) -c -o $@ $<
replay%.o: replay.c
	$(CC) $(CFLAGS) -fPIC -O3 -c -o $@ $<
far%.partial: far%.o replay%.o
	$(LD) -e 0 -o $@ $^
far%.bin: far%.partial
	$(OBJCOPY) -O binary $< $@

jump%.o: jump.S
	$(CC) $(CFLAGS) -DOFFSET=$(OFFSET) -c -o $@ $<
jump%.partial: jump%.o
	$(LD) -e 0 -o $@ $^
jump%.bin: jump%.partial
	$(OBJCOPY) -O binary $< $@

cl: main.c cl.S
	$(CC) -O3 -static -o $@ $^

clean:
	rm -f cl *.o *.partial *.bin

