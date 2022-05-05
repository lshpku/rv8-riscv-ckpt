##
# A short procedure to serve as a jump between syscall (jal)
# and syscall replay codes (far_call).
#
# Parameters:
#   ALTER_RD       : set when rd is not a0 nor sp.
#   ALTER_RD_IS_SP : set when rd is sp.
##
	.text
	.global	near_call
near_call:
#ifdef FAR_CALL
#ifdef ALTER_RD
	mv	ALTER_RD, a0
#endif
#ifdef ALTER_RD_IS_SP
	lui	sp, %hi(NEAR_BUF)
	sd	a0, %lo(NEAR_BUF)(sp)	# save a0
#else
	lui	a0, %hi(NEAR_BUF)
	sd	sp, %lo(NEAR_BUF)(a0)	# save sp
#endif
	lui	a0, %hi(FAR_CALL)
	jalr	a0, a0, %lo(FAR_CALL)	# call far_call
#endif
#ifdef ALTER_RD
	mv	sp, a0
	mv	a0, ALTER_RD
	mv	ALTER_RD, sp
#endif
#ifdef ALTER_RD_IS_SP
	mv	sp, a0
	lui	a0, %hi(NEAR_BUF)
	ld	a0, %lo(NEAR_BUF)(a0)	# restore a0
#else
	lui	sp, %hi(NEAR_BUF)
	ld	sp, %lo(NEAR_BUF)(sp)	# restore sp
#endif
	.size	near_call, .-near_call
