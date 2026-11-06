/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef RVV_AME_BENCHMARK_ROI_H
#define RVV_AME_BENCHMARK_ROI_H
#include <stdint.h>

extern volatile unsigned bench_repeat;
#ifndef BENCH_REPEATS
#define BENCH_REPEATS 3
#endif

/* Same encodings as util/m5/src/abi/riscv/m5op.S. These are measurement
 * markers, not AME instructions. Memory fences bracket completed stores. */
static inline void bench_begin(void)
{
#ifdef __riscv
    register uint64_t work __asm__("a0") = bench_repeat;
    register uint64_t thread __asm__("a1") = 0;
    __asm__ volatile("fence rw, rw\n\t.4byte 0xb400007b"
                     : "+r"(work), "+r"(thread) :: "memory");
#endif
}

static inline void bench_end(void)
{
#ifdef __riscv
    register uint64_t work __asm__("a0") = bench_repeat;
    register uint64_t thread __asm__("a1") = 0;
    __asm__ volatile("fence rw, rw\n\t.4byte 0xb600007b"
                     : "+r"(work), "+r"(thread) :: "memory");
#endif
}
#endif
