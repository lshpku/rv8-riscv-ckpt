#define HEAD_SIZE 8
#define CSRV_SIZE 16
#define CALLER_SAVE_SIZE 128
#define HEAD_OFFSET (CSRV_SIZE+CALLER_SAVE_SIZE)
#define STACK_SIZE (HEAD_OFFSET+HEAD_SIZE)

	.text
	.global	far_call
far_call:
	la	sp, FAR_STACK_TOP-STACK_SIZE
	sd	ra, 0(sp)
	sd	t0, 8(sp)
	sd	t1, 16(sp)
	sd	t2, 24(sp)
	sd	a0, 32(sp)	# return address
	sd	a1, 40(sp)
	sd	a2, 48(sp)
	sd	a3, 56(sp)
	sd	a4, 64(sp)
	sd	a5, 72(sp)
	sd	a6, 80(sp)
	sd	a7, 88(sp)
	sd	t3, 96(sp)
	sd	t4, 104(sp)
	sd	t5, 112(sp)
	sd	t6, 120(sp)

	ld	a0, HEAD_OFFSET(sp)	# current table offset
	addi	a1, sp, CALLER_SAVE_SIZE	# csr vector address
	call	replay
	sd	a0, HEAD_OFFSET(sp)	# next table offset
	ld	a0, -8(a0)	# return value

	ld	ra, 0(sp)
	ld	t0, 8(sp)
	ld	t1, 16(sp)
	ld	t2, 24(sp)
	ld	a1, 40(sp)
	ld	a2, 48(sp)
	ld	a3, 56(sp)
	ld	a4, 64(sp)
	ld	a5, 72(sp)
	ld	a6, 80(sp)
	ld	a7, 88(sp)
	ld	t3, 96(sp)
	ld	t4, 104(sp)
	ld	t5, 112(sp)
	ld	t6, 120(sp)
	ld	sp, 32(sp)	# return address
	jr	sp
	.size	far_call, .-far_call

	.global	raw_exit
raw_exit:
	li	a7, 93	# exit
	ecall
	unimp
	.size	raw_exit, .-raw_exit

	.global raw_write
raw_write:
	li	a7, 64	# write
	ecall
	ret
	.size	raw_write, .-raw_write
