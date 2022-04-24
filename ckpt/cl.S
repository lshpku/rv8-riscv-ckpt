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
#   a3: entrypoint pc
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

	# goto entrypoint
	jr	sp

.fail:
	li	a0, -1
	li	a7, 93	# exit
	ecall
	unimp
cl_end:
