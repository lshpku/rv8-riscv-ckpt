##
# An uncompressed jal that can be used to replace ecall/sc
# or return from near_call.
##
#ifdef NORVC
	.option	norvc
#endif
	.text
	.global	rel_jump
rel_jump:
	j	.+OFFSET
	.size	rel_jump, .-rel_jump
