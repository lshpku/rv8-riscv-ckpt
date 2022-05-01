##
# cl_proxy_entry
#     An intermediate procedure that sets sp
#     for cl and invoke it.
##
	.text
	.global cl_proxy_entry
cl_proxy_entry:
	mv	sp, a5
	jr	a4
	.size	cl_proxy_entry, .-cl_proxy_entry

##
# cl.bin - The real cl program.
##
	.text
	.global	cl_begin, cl_end
cl_begin:
	.incbin "cl.bin"
cl_end:
