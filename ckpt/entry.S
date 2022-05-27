##
# Checkpoint Loader (CL)
#   A place-independent program to restore memory space
#   and registers for the process, and resume execution
#   from the checkpoint.
#
# Arguments
#   a0: pointer to the mmap_cfg array
#   a1: number of mmap_cfgs
#   a2: fd of the memory dump file
#   a3: pointer to the register file array
##
	.text
	.global	cl_entry
cl_entry:
	# map pages
	addi	sp, sp, -(8+NUM_CSR*8)
	sd	a3, 0(sp)
	jal	map_pages

	# set replay stack
	ld	a0, 0(sp)	# regfile
	addi	a1, a0, 512	# replay_sp
	sd	sp, 0(a1)
	lla	a2, replay	# replay_pc
	sd	a2, 8(a1)
	addi	a1, a1, 16	# replay_table
	sd	a1, 0(sp)

	# restore register file
	mv	sp, a0
	# 30 int regs except x0 and x2 (sp)
	ld	x1, 8(sp)
	ld	x3, 24(sp)
	ld	x4, 32(sp)
	ld	x5, 40(sp)
	ld	x6, 48(sp)
	ld	x7, 56(sp)
	ld	x8, 64(sp)
	ld	x9, 72(sp)
	ld	x10, 80(sp)
	ld	x11, 88(sp)
	ld	x12, 96(sp)
	ld	x13, 104(sp)
	ld	x14, 112(sp)
	ld	x15, 120(sp)
	ld	x16, 128(sp)
	ld	x17, 136(sp)
	ld	x18, 144(sp)
	ld	x19, 152(sp)
	ld	x20, 160(sp)
	ld	x21, 168(sp)
	ld	x22, 176(sp)
	ld	x23, 184(sp)
	ld	x24, 192(sp)
	ld	x25, 200(sp)
	ld	x26, 208(sp)
	ld	x27, 216(sp)
	ld	x28, 224(sp)
	ld	x29, 232(sp)
	ld	x30, 240(sp)
	ld	x31, 248(sp)
	# 32 fp regs
	fld	f0, 256(sp)
	fld	f1, 264(sp)
	fld	f2, 272(sp)
	fld	f3, 280(sp)
	fld	f4, 288(sp)
	fld	f5, 296(sp)
	fld	f6, 304(sp)
	fld	f7, 312(sp)
	fld	f8, 320(sp)
	fld	f9, 328(sp)
	fld	f10, 336(sp)
	fld	f11, 344(sp)
	fld	f12, 352(sp)
	fld	f13, 360(sp)
	fld	f14, 368(sp)
	fld	f15, 376(sp)
	fld	f16, 384(sp)
	fld	f17, 392(sp)
	fld	f18, 400(sp)
	fld	f19, 408(sp)
	fld	f20, 416(sp)
	fld	f21, 424(sp)
	fld	f22, 432(sp)
	fld	f23, 440(sp)
	fld	f24, 448(sp)
	fld	f25, 456(sp)
	fld	f26, 464(sp)
	fld	f27, 472(sp)
	fld	f28, 480(sp)
	fld	f29, 488(sp)
	fld	f30, 496(sp)
	fld	f31, 504(sp)

	# goto entrypoint
	ld	sp, 0(sp)
	jr	sp
	.size	cl_entry, .-cl_entry

#include "raw-syscall-impl.h"
	RAW_CLOSE
	RAW_LSEEK
	RAW_READ
	RAW_WRITE
	RAW_EXIT
	RAW_MMAP
