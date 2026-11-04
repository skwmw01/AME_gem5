/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef RVV_KERNELS_H
#define RVV_KERNELS_H

#include <stddef.h>
#include <stdint.h>

/* Row-major C = (accumulate ? C : 0) + A B; B may be transposed. */
void rvv_gemm_f32(const float *a, const float *b, float *c,
                  size_t m, size_t k, size_t n, int transpose_b,
                  int accumulate);
void rvv_gemm_i8(const int8_t *a, const int8_t *b, int32_t *c, size_t n);
void rvv_i32_i64_roundtrip(int32_t *values, size_t count);
/* These examples follow example/: base-2, integer-exponent activation. */
void rvv_gelu(const float *input, float *output, size_t count);
void rvv_softmax(const float *input, float *output, size_t rows, size_t cols);
void rvv_rmsnorm(const float *input, float *output, size_t rows, size_t cols);
/* Even count; both lanes of each interleaved pair have the same angle.
 * Angles must be in the example's [0, 3] radian domain. */
void rvv_rope(const float *input, const float *angles, float *output,
              size_t count);

#endif
