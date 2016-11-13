.section .text
.globl _start
_start:

# RAM is at 0x8000_0000 - 0xc000_0000

# setup trap stack at top of memory
	li      sp, 0xbffffff8
	csrrw   zero, mscratch, sp

# setup stack 1MB below top of memory
	li      sp, 0xbfeffff8

# setup mtvec
1:	auipc   a0, %pcrel_hi(mtvec)       # load mtvec(hi)
	addi    a0, a0, %pcrel_lo(1b)      # load mtvec(lo)
	csrrw   zero, mtvec, a0

# trap test
	ecall
	li      a0, 0
	ebreak

# simple trap vector example
mtvec:
	csrrw   sp, mscratch, sp

	# save several registers
	sd      a0, 0(sp)
	sd      a1, -8(sp)
	sd      a2, -16(sp)
	sd      a3, -24(sp)
	sd      a4, -32(sp)
	sd      a5, -40(sp)

	# increment past the trapping instruction
	csrrsi  a2, mepc, 0
	addi    a2, a2, 4
	csrrw   zero, mepc, a2

	# restore several registers
	ld      a0, 0(sp)
	ld      a1, -8(sp)
	ld      a2, -16(sp)
	ld      a3, -24(sp)
	ld      a4, -32(sp)
	ld      a5, -40(sp)

	# return
	csrrw   sp, mscratch, sp
	mret

.section .rodata
.p2align 12
sv39_pte_0:
	# riscv-pte-util sv39 0x80000000 URWV
	.dword 0x20000017   # 0x0000 -> 0x8000_0000 - 0xC000_0000