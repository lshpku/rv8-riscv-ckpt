##
# A short procedure to serve as a jump between syscall (jal)
# and syscall replay codes (far_call). 
##
#ifdef NORVC
	.option	norvc
#endif
	.text
	.global	near_call
near_call:
#ifdef FAR_CALL
#ifdef ALTER_RD
	mv	ALTER_RD, a0
#endif
	lui	a0, %hi(NEAR_BUF)
	sd	sp, %lo(NEAR_BUF)(a0)	# save sp
	lui	a0, %hi(FAR_CALL)
	jalr	a0, a0, %lo(FAR_CALL)	# call far_call
#endif
#ifdef ALTER_RD
	mv	sp, a0
	mv	a0, ALTER_RD
	mv	ALTER_RD, sp
#endif
	lui	sp, %hi(NEAR_BUF)
	ld	sp, %lo(NEAR_BUF)(sp)	# restore sp
	.size	near_call, .-near_call
