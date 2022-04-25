	.text
	.option	norvc
	.global	near_call
near_call:
#ifndef RETURN_ONLY
	lui	a0, %hi(NEAR_BUF)
	sd	sp, %lo(NEAR_BUF)(a0)	# save sp
	lui	a0, %hi(FAR_CALL)
	jalr	a0, a0, %lo(FAR_CALL)	# call far_call
#endif
	lui	sp, %hi(NEAR_BUF)
	ld	sp, %lo(NEAR_BUF)(sp)	# restore sp
	.size	near_call, .-near_call
