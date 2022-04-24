	.text
	.global	near_call
near_call:
	lui		a0, %hi(RT_BUF)
	sd		sp, %lo(RT_BUF)(a0)		# save sp
	lui		a0, %hi(FAR_CALL)
	jalr	a0, a0, %lo(FAR_CALL)	# call far_call
	lui		sp, %hi(RT_BUF)
	ld		sp, %lo(RT_BUF)(sp)		# restore sp
	.size	near_call, .-near_call
