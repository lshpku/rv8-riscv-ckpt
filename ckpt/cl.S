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
	.global	cl_begin, cl_end
cl_begin:
	mv	t2, a2
	mv	sp, a3

	# map pages
	beqz	a1, .end
	mv	t0, a0
	slli	t1, a1, 5
	add	t1, t1, t0
.loop:
	ld	a0, 0(t0)	# addr
	ld	a5, 8(t0)	# offset
	ld	a1, 16(t0)	# size
	lwu	a2, 24(t0)	# prot
	lwu	a3, 28(t0)	# flags
	mv	a4, s4	# fd
	li	a7, 222	# mmap
	ecall
	beqz	a0, .fail
	addi	t0, t0, 32
	bltu	t0, t1, .loop
.end:
	mv	a0, t2	# fd
	li	a7, 57	# close
	ecall
	j	.fail

	# restore register file
	# 30 int regs except x0 and x2 (sp)
	ld	x1, 0(sp)
	ld	x3, 8(sp)
	ld	x4, 16(sp)
	ld	x5, 24(sp)
	ld	x6, 32(sp)
	ld	x7, 40(sp)
	ld	x8, 48(sp)
	ld	x9, 56(sp)
	ld	x10, 64(sp)
	ld	x11, 72(sp)
	ld	x12, 80(sp)
	ld	x13, 88(sp)
	ld	x14, 96(sp)
	ld	x15, 104(sp)
	ld	x16, 112(sp)
	ld	x17, 120(sp)
	ld	x18, 128(sp)
	ld	x19, 136(sp)
	ld	x20, 144(sp)
	ld	x21, 152(sp)
	ld	x22, 160(sp)
	ld	x23, 168(sp)
	ld	x24, 176(sp)
	ld	x25, 184(sp)
	ld	x26, 192(sp)
	ld	x27, 200(sp)
	ld	x28, 208(sp)
	ld	x29, 216(sp)
	ld	x30, 224(sp)
	ld	x31, 232(sp)
	# 32 fp regs
	fld	f0, 240(sp)
	fld	f1, 248(sp)
	fld	f2, 256(sp)
	fld	f3, 264(sp)
	fld	f4, 272(sp)
	fld	f5, 280(sp)
	fld	f6, 288(sp)
	fld	f7, 296(sp)
	fld	f8, 304(sp)
	fld	f9, 312(sp)
	fld	f10, 320(sp)
	fld	f11, 328(sp)
	fld	f12, 336(sp)
	fld	f13, 344(sp)
	fld	f14, 352(sp)
	fld	f15, 360(sp)
	fld	f16, 368(sp)
	fld	f17, 376(sp)
	fld	f18, 384(sp)
	fld	f19, 392(sp)
	fld	f20, 400(sp)
	fld	f21, 408(sp)
	fld	f22, 416(sp)
	fld	f23, 424(sp)
	fld	f24, 432(sp)
	fld	f25, 440(sp)
	fld	f26, 448(sp)
	fld	f27, 456(sp)
	fld	f28, 464(sp)
	fld	f29, 472(sp)
	fld	f30, 480(sp)
	fld	f31, 488(sp)

	# goto entrypoint
	ld	sp, 496(sp)
	jr	sp

.fail:
	li	a0, -1
	li	a7, 93	# exit
	ecall
	unimp
cl_end:
