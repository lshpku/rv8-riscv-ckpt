//
//  fmt.h
//

#ifndef rv_fmt_h
#define rv_fmt_h

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cassert>
#include <cmath>
#include <cctype>
#include <cwchar>
#include <climits>
#include <cfloat>
#include <cfenv>
#include <limits>
#include <array>
#include <string>
#include <vector>
#include <unordered_map>
#include <type_traits>

#include "args.h"

/*-
 * portions from freebsd/lib/libc/stdio/vfprintf.c
 * portions from freebsd/lib/libc/stdio/printfcommon.h
 *
 * Copyright (c) 1990, 1993
 *	The Regents of the University of California.  All rights reserved.
 *
 * Portions of this software were developed by David Chisnall
 * under sponsorship from the FreeBSD Foundation.
 *
 * Portions of this software were contributed to Berkeley by Chris Torek.
 *
 * Copyright (c) 2011 The FreeBSD Foundation
 * All rights reserved.
 * Portions of this software were developed by David Chisnall
 * under sponsorship from the FreeBSD Foundation.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 * 3. Neither the name of the University nor the names of its contributors
 *    may be used to endorse or promote products derived from this software
 *    without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE REGENTS OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 */

namespace riscv {

	/* fmt flags used during conversion */
	enum {
		ALT =           0x001,          /* alternate form */
		LADJUST =       0x004,          /* left adjustment */
		ZEROPAD =       0x080,          /* zero (as opposed to blank) pad */
		FPT =           0x100,          /* Floating point number */
	};

	/* fmt constants */
	enum {
		PADSIZE =      16,
		MAXEXPDIG =    6,
		DEFPREC =      6
	};

	/* dtoa constants */
	enum {
		Ebits =            11,
		Exp_shift =        20,
		Exp_msk1 =   0x100000,
		Exp_mask = 0x7ff00000,
		Exp_1 =    0x3ff00000,
		P =                53,
		Bias =           1023,
		Frac_mask =   0xfffff,
		Bndry_mask =  0xfffff,
		Ten_pmax =         22,
		Bletch =         0x10,
		LSB =               1,
		Log2P =             1,
		Quick_max =        14,
		Int_max =          14,
		kshift =            5,
		kmask =            31,
		n_bigtens =         5
	};

	/* Ten_pmax = floor(P*log(2)/log(5)) */
	/* Bletch = (highest power of 2 < DBL_MAX_10_EXP) / 16 */
	/* Quick_max = floor((P-1)*log(FLT_RADIX)/log(10) - 1) */
	/* Int_max = floor(P*log(FLT_RADIX)/log(10) - 1) */

	enum : unsigned {
		Sign_bit = 0x80000000
	};

	struct Bigint {
		int k, maxwds, sign, wds;
		unsigned int x[1];
	};

	/* constants */

	extern const double bigtens[];
	extern const double tens[];
	extern const char blanks[PADSIZE];
	extern const char zeroes[PADSIZE];

	/* bigint */

	Bigint* Balloc(int k);
	void Bcopy(Bigint *x, Bigint *y);
	void Bfree(Bigint *v);
	int lo0bits(unsigned int *y);
	Bigint* multadd(Bigint *b, int m, int a);
	int hi0bits(unsigned int x);
	Bigint* i2b(int i);
	Bigint* mult(Bigint *a, Bigint *b);
	Bigint* pow5mult(Bigint *b, int k);
	Bigint* lshift(Bigint *b, int k);
	int cmp(Bigint *a, Bigint *b);
	Bigint* diff(Bigint *a, Bigint *b);
	double b2d(Bigint *a, int *e);
	Bigint* d2b(double dd, int *e, int *bits);
	char* rv_alloc(int i);
	char* nrv_alloc(const char *s, char **rve, int n);
	void freedtoa(char *s);
	int quorem(Bigint *b, Bigint *S);

	/* fmt */
	constexpr int to_char(int n) { return '0' + n; }
	void io_print(std::string &buf, std::string str, ssize_t len);
	void io_print(std::string &buf, const char* str, ssize_t len);
	void io_pad(std::string &buf, ssize_t len, const char* with);
	void io_print_and_pad(std::string &buf, const char *p, const char *ep, ssize_t len, const char* with);
	void io_print_and_pad(std::string &buf, std::string str, ssize_t len, const char* with);
	int io_printf(std::string &buf, std::string &fmt,
		const arg_type *at, const type_holder *th, const int elem);

	/* dtoa */
	inline unsigned int& word0(double_bits *x) { return x->w.d0; }
	inline unsigned int& word1(double_bits *x) { return x->w.d1; }
	inline double& dval(double_bits *x) { return x->f; }
	std::string dtoa(double d0, int mode, int ndigits, int *decpt, int *sign);

	/* hdtoa */
	std::string hdtoa(double d, const char *xdigs, int ndigits, int *decpt, int *sign);

	/* itoa */
	std::string itoa(unsigned long long val, int base, const char *xdigs);


	struct PageRec {
		uint8_t visited[512];
		uint8_t content[4096];

		template <typename T>
		int check(int offset) {
			int mask = (1 << sizeof(T)) - 1;
			return (visited[offset >> 3] >> (offset & 7)) & mask;
		}

		template <typename T>
		void set(int offset) {
			int mask = (1 << sizeof(T)) - 1;
			visited[offset >> 3] |= mask << (offset & 7);
		}

		template <typename T>
		void put(int offset, T data) {
			set<T>(offset);
			*(T *)(content + offset) = data;
		}

		PageRec() { memset(this, 0, sizeof(PageRec)); }
	};

	struct ExecRec {
		// instructions are 2-aligned
		uint32_t count[2048];

		uint32_t &get(int offs) {
			return count[(offs >> 1) & 0x7ff];
		}

		ExecRec() { memset(this, 0, sizeof(ExecRec)); }
	};

	struct StoreRec {
		uint64_t addr;
		unsigned size;

		StoreRec() { memset(this, 0, sizeof(StoreRec)); }
	};

	struct MemTrace {
		std::unordered_map<uint64_t, PageRec *> pages;
		std::unordered_map<uint64_t, ExecRec *> execs;
		enum { STREC_SIZE = 256 };
		StoreRec stores[STREC_SIZE];

		PageRec* get_page(uint64_t pn) {
			PageRec *&page = pages[pn];
			if (page == NULL) {
				page = new PageRec;
			}
			return page;
		}

		PageRec* get_page_init(uint64_t pn) {
			PageRec *&page = pages[pn];
			if (page == NULL) {
				page = new PageRec;
				memcpy(page->content, (void *)(pn << 12), 4096);
			}
			return page;
		}

		uint32_t &get_exec_counter(uint64_t addr) {
			ExecRec *&exec = execs[addr >> 12];
			if (exec == NULL) {
				exec = new ExecRec;
			}
			return exec->get(addr & 0xfff);
		}

		bool fetch(uint64_t addr, uint64_t inst, int length) {
			get_exec_counter(addr)++;
			// to accelerate fetch, page content is set on init
			PageRec *page = get_page_init(addr >> 12);
			int offset = addr & 0xfff;
			if (length == 2) {
				bool first = page->check<uint16_t>(offset) == 0;
				page->set<uint16_t>(offset);
				return first;
			}
			if ((addr & 3) < 6) {
				bool first = page->check<uint32_t>(offset) == 0;
				page->set<uint32_t>(offset);
				return first;
			}
			bool first1 = page->check<uint16_t>(offset) == 0;
			page->set<uint16_t>(offset);
			if (offset + 2 == 4096) {
				page = get_page_init((addr >> 12) + 1);
			}
			bool first2 = page->check<uint16_t>(offset + 2) == 0;
			page->set<uint16_t>(offset + 2);
			return first1 && first2;
		}

		bool prefetch(uint64_t addr, int length) {
			PageRec *page = get_page(addr >> 12);
			int offset = addr & 0xfff;
			switch (length) {
				case 2:
					return page->check<uint16_t>(offset) == 0;
			}
			return false;
		}

		template <typename T>
		void load(uint64_t addr, T data) {
			uint64_t pn = addr >> 12;
			PageRec *page = get_page(pn);
			int offset = addr & 0xfff;
			// perform a coalesced put if it's aligned and complete
			if ((offset & (sizeof(T) - 1)) == 0) {
				switch (page->check<T>(offset)) {
					case 0:
						page->put(offset, data);
						return;
					case (1 << sizeof(T)) - 1:
						return;
				}
			}
			// otherwise, put it byte by byte
			union { char b[8]; T t; } x = { .t = data };
			for (int i = 0; i < (int)sizeof(T); i++) {
				if (offset + i == 4096) {
					page = get_page(pn + 1);
					offset -= 4096;
				}
				if (page->check<char>(offset + i) == 0) {
					page->put(offset + i, x.b[i]);
				}
			}
			return;
		}

		template <typename T>
		void store(uint64_t addr, T data) {
			load(addr, (T)0);

			int hash = 0;
			uint64_t shift = addr;
			for (unsigned i = 0; i < sizeof(addr); i++) {
				hash ^= shift & (STREC_SIZE - 1);
				shift /= STREC_SIZE;
			}
			stores[hash].addr = addr;
			stores[hash].size = sizeof(T);
		}

		void dump(FILE *dump_file, FILE *cfg_file);

		~MemTrace() {
			for (auto &page : pages) {
				delete page.second;
			}
			for (auto &exec : execs) {
				delete exec.second;
			}
		}
	};

	struct CheckpointManager {
		FILE *out;
		char *dirname;
		uint64_t period;
		uint64_t begin_instret;
		MemTrace *mem;
		uint64_t monitor_pc;

		enum {
			ECALL = 0x00000073
		};

		template <typename P, typename T>
		void fetch(P &proc, T &dec, uint64_t addr, uint64_t inst, int length) {
			if (out) {
				// begin new checkpoint
				if (!mem) {
					mem = new MemTrace;
					begin_instret = proc.instret;
					fprintf(out, "begin 0x%lx\n", addr);
					fprintf(out, "ireg");
					for (int i = 0; i < 32; i++) {
						fprintf(out, " %lx", (uint64_t)proc.ireg[i]);
					}
					fprintf(out, "\nfreg");
					for (int i = 0; i < 32; i++) {
						fprintf(out, " %llx", proc.freg[i].r.xu.val);
					}
					fprintf(out, "\n");
				}

				bool first_visit = mem->fetch(addr, inst ,length);

				// look for breakpoint
				// The breakpoint instruction is not executed between
				// two consecutive checkpoints, but is saved in the 
				// former one, which enables checkpoint concatenating.
				if (proc.instret - begin_instret > period) {
					// ecall
					if (inst == ECALL) {
						fprintf(out, "break 0x%lx ecall\n", addr);
						break_here(proc.instret);
						return;
					}
					// first met instruction
					if (first_visit && length == 4) {
						fprintf(out, "break 0x%lx first\n", addr);
						break_here(proc.instret);
						return;
					}
					// first met instruction (rvc)
					if (first_visit && length == 2 &&
						mem->prefetch(addr + 2, 2)) {
						fprintf(out, "break 0x%lx firstrvc\n", addr);
						break_here(proc.instret);
						return;
					}
					// any instruction that can be replaced by ecall
					int rd;
					if (length == 4 && (rd = proc.get_rd(dec)) > 0) {
						uint32_t exec_count = mem->get_exec_counter(addr);
						uint64_t total_exec = proc.instret - begin_instret;
						if (exec_count < (total_exec >> 18)) {
							fprintf(out, "break 0x%lx repeat %u %d\n",
								addr, exec_count, rd);
							break_here(proc.instret);
							return;
						}
					}
				}

				// mark syscall
				// This output line is expected to be completed with
				// a return value
				if (inst == ECALL) {
					fprintf(out, "syscall 0x%lx", addr);
				}
			}
		}

		void break_here(uint64_t instret);

		template <typename P, typename T>
		void execute(P &proc, T &dec, uint64_t addr) {
			if (addr == monitor_pc) {
				printf("execute %lx\n", (uint64_t)proc.ireg[dec.rd]);
				fflush(stdout);
			}
		}

		template <typename T>
		void load(uint64_t addr, T data) {
			if (mem) {
				mem->load(addr, data);
			}
		}

		template <typename T>
		void store(uint64_t addr, T data) {
			if (mem) {
				mem->store(addr, data);
			}
		}

		void syscall(uint64_t retval) { syscall(retval, NULL, 0); }
		void syscall(uint64_t retval, void *addr, size_t size);

		template <typename P>
		void exit(P &proc, int rc) {
			if (mem) {
				fprintf(out, " %x exit\n", rc);
				break_here(proc.instret);
				fclose(out);
			}
		}
	};
	extern CheckpointManager checkpoint;
}

#endif
