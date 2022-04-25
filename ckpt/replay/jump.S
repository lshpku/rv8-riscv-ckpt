##
# An uncompressed jal that can be used to replace ecall/sc
# or serve as the return from near_call.
##
	.option	norvc
	.text
	.global	rel_jump
rel_jump:
	j	.+OFFSET
	.size	rel_jump, .-rel_jump
