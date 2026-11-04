/* SPDX-License-Identifier: BSD-3-Clause */
#include "rvv_kernels.h"

#if defined(__riscv)
#include <riscv_vector.h>

void
rvv_gemm_f32(const float *a, const float *b, float *c,
              size_t m, size_t k, size_t n, int transpose_b, int accumulate)
{
    for (size_t row = 0; row < m; ++row) {
        for (size_t col = 0; col < n;) {
            const size_t vl = __riscv_vsetvl_e32m1(n - col);
            vfloat32m1_t sum = accumulate
                ? __riscv_vle32_v_f32m1(c + row * n + col, vl)
                : __riscv_vfmv_v_f_f32m1(0.0f, vl);
            for (size_t depth = 0; depth < k; ++depth) {
                vfloat32m1_t rhs = transpose_b
                    ? __riscv_vlse32_v_f32m1(b + col * k + depth,
                                             k * sizeof(float), vl)
                    : __riscv_vle32_v_f32m1(b + depth * n + col, vl);
                /* Match the reference's separate FP32 multiply and add. */
                rhs = __riscv_vfmul_vf_f32m1(rhs, a[row * k + depth], vl);
                sum = __riscv_vfadd_vv_f32m1(sum, rhs, vl);
            }
            __riscv_vse32_v_f32m1(c + row * n + col, sum, vl);
            col += vl;
        }
    }
}

void
rvv_gemm_i8(const int8_t *a, const int8_t *b, int32_t *c, size_t n)
{
    for (size_t row = 0; row < n; ++row) {
        for (size_t col = 0; col < n;) {
            const size_t vl = __riscv_vsetvl_e32m1(n - col);
            vint32m1_t sum = __riscv_vle32_v_i32m1(c + row * n + col, vl);
            for (size_t depth = 0; depth < n; ++depth) {
                const vint8mf4_t bytes =
                    __riscv_vle8_v_i8mf4(b + depth * n + col, vl);
                const vint32m1_t rhs = __riscv_vsext_vf4_i32m1(bytes, vl);
                sum = __riscv_vmacc_vx_i32m1(sum, a[row * n + depth], rhs, vl);
            }
            __riscv_vse32_v_i32m1(c + row * n + col, sum, vl);
            col += vl;
        }
    }
}

void
rvv_i32_i64_roundtrip(int32_t *values, size_t count)
{
    for (size_t i = 0; i < count;) {
        const size_t vl = __riscv_vsetvl_e32m1(count - i);
        const vint32m1_t x = __riscv_vle32_v_i32m1(values + i, vl);
        const vint64m2_t wide = __riscv_vwcvt_x_x_v_i64m2(x, vl);
        const vint32m1_t narrow = __riscv_vncvt_x_x_w_i32m1(wide, vl);
        __riscv_vse32_v_i32m1(values + i, narrow, vl);
        i += vl;
    }
}

/* Exactly reproduce the integer-exponent helper in the original examples,
 * including its flush below -126. No RVV transcendental extension is used. */
static vfloat32m1_t
pow2_integer(vfloat32m1_t x, size_t vl)
{
    vint32m1_t exponent = __riscv_vfcvt_rtz_x_f_v_i32m1(x, vl);
    exponent = __riscv_vmax_vx_i32m1(exponent, -127, vl);
    exponent = __riscv_vmin_vx_i32m1(exponent, 128, vl);
    exponent = __riscv_vadd_vx_i32m1(exponent, 127, vl);
    exponent = __riscv_vsll_vx_i32m1(exponent, 23, vl);
    return __riscv_vreinterpret_v_i32m1_f32m1(exponent);
}

void
rvv_gelu(const float *input, float *output, size_t count)
{
    for (size_t i = 0; i < count;) {
        const size_t vl = __riscv_vsetvl_e32m1(count - i);
        const vfloat32m1_t x = __riscv_vle32_v_f32m1(input + i, vl);
        vfloat32m1_t denominator = pow2_integer(
            __riscv_vfmul_vf_f32m1(x, -2.0f, vl), vl);
        denominator = __riscv_vfadd_vf_f32m1(denominator, 1.0f, vl);
        const vfloat32m1_t reciprocal =
            __riscv_vfrdiv_vf_f32m1(denominator, 1.0f, vl);
        __riscv_vse32_v_f32m1(output + i,
            __riscv_vfmul_vv_f32m1(x, reciprocal, vl), vl);
        i += vl;
    }
}

void
rvv_softmax(const float *input, float *output, size_t rows, size_t cols)
{
    for (size_t row = 0; row < rows; ++row) {
        vfloat32m1_t maximum = __riscv_vfmv_v_f_f32m1(input[row * cols], 1);
        for (size_t col = 0; col < cols;) {
            const size_t vl = __riscv_vsetvl_e32m1(cols - col);
            const vfloat32m1_t x =
                __riscv_vle32_v_f32m1(input + row * cols + col, vl);
            maximum = __riscv_vfredmax_vs_f32m1_f32m1(x, maximum, vl);
            col += vl;
        }
        const float max_value = __riscv_vfmv_f_s_f32m1_f32(maximum);
        vfloat32m1_t sum = __riscv_vfmv_v_f_f32m1(0.0f, 1);
        for (size_t col = 0; col < cols;) {
            const size_t vl = __riscv_vsetvl_e32m1(cols - col);
            vfloat32m1_t x =
                __riscv_vle32_v_f32m1(input + row * cols + col, vl);
            x = pow2_integer(__riscv_vfsub_vf_f32m1(x, max_value, vl), vl);
            __riscv_vse32_v_f32m1(output + row * cols + col, x, vl);
            /* Ordered reduction preserves the host's summation order. */
            sum = __riscv_vfredosum_vs_f32m1_f32m1(x, sum, vl);
            col += vl;
        }
        const float reciprocal = 1.0f / __riscv_vfmv_f_s_f32m1_f32(sum);
        for (size_t col = 0; col < cols;) {
            const size_t vl = __riscv_vsetvl_e32m1(cols - col);
            const vfloat32m1_t x =
                __riscv_vle32_v_f32m1(output + row * cols + col, vl);
            __riscv_vse32_v_f32m1(output + row * cols + col,
                __riscv_vfmul_vf_f32m1(x, reciprocal, vl), vl);
            col += vl;
        }
    }
}

void
rvv_rmsnorm(const float *input, float *output, size_t rows, size_t cols)
{
    for (size_t row = 0; row < rows; ++row) {
        vfloat32m1_t sum = __riscv_vfmv_v_f_f32m1(0.0f, 1);
        for (size_t col = 0; col < cols;) {
            const size_t vl = __riscv_vsetvl_e32m1(cols - col);
            const vfloat32m1_t x =
                __riscv_vle32_v_f32m1(input + row * cols + col, vl);
            const vfloat32m1_t square = __riscv_vfmul_vv_f32m1(x, x, vl);
            sum = __riscv_vfredosum_vs_f32m1_f32m1(square, sum, vl);
            col += vl;
        }
        sum = __riscv_vfmul_vf_f32m1(sum, 1.0f / (float)cols, 1);
        const float root = __riscv_vfmv_f_s_f32m1_f32(
            __riscv_vfsqrt_v_f32m1(sum, 1));
        const float reciprocal = root > 0.0f ? 1.0f / root : 0.0f;
        for (size_t col = 0; col < cols;) {
            const size_t vl = __riscv_vsetvl_e32m1(cols - col);
            const vfloat32m1_t x =
                __riscv_vle32_v_f32m1(input + row * cols + col, vl);
            __riscv_vse32_v_f32m1(output + row * cols + col,
                __riscv_vfmul_vf_f32m1(x, reciprocal, vl), vl);
            col += vl;
        }
    }
}

/* Double precision Taylor evaluation for the example's angles in [0, 3].
 * 14 terms bound the truncation error well below FP32 rounding precision.
 * This is an example-domain implementation, not a general libm replacement. */
static vfloat32m1_t
trig(vfloat32m1_t angle, int cosine, size_t vl)
{
    const vfloat64m2_t x = __riscv_vfwcvt_f_f_v_f64m2(angle, vl);
    const vfloat64m2_t negative_square = __riscv_vfneg_v_f64m2(
        __riscv_vfmul_vv_f64m2(x, x, vl), vl);
    vfloat64m2_t term = cosine ? __riscv_vfmv_v_f_f64m2(1.0, vl) : x;
    vfloat64m2_t sum = term;
    for (unsigned k = 1; k < 14; ++k) {
        const unsigned denominator = cosine ? (2*k - 1)*(2*k)
                                             : (2*k)*(2*k + 1);
        term = __riscv_vfmul_vv_f64m2(term, negative_square, vl);
        term = __riscv_vfmul_vf_f64m2(term, 1.0 / denominator, vl);
        sum = __riscv_vfadd_vv_f64m2(sum, term, vl);
    }
    return __riscv_vfncvt_f_f_w_f32m1(sum, vl);
}

void
rvv_rope(const float *input, const float *angles, float *output, size_t count)
{
    for (size_t i = 0; i < count;) {
        const size_t vl = __riscv_vsetvl_e32m1(count - i);
        const vfloat32m1_t x = __riscv_vle32_v_f32m1(input + i, vl);
        const vfloat32m1_t angle = __riscv_vle32_v_f32m1(angles + i, vl);
        const vfloat32m1_t cosine = trig(angle, 1, vl);
        const vfloat32m1_t sine = trig(angle, 0, vl);
        const vuint32m1_t indices = __riscv_vadd_vx_u32m1(
            __riscv_vid_v_u32m1(vl), i, vl);
        const vuint32m1_t offsets = __riscv_vsll_vx_u32m1(
            __riscv_vxor_vx_u32m1(indices, 1, vl), 2, vl);
        vfloat32m1_t paired = __riscv_vluxei32_v_f32m1(input, offsets, vl);
        const vbool32_t even = __riscv_vmseq_vx_u32m1_b32(
            __riscv_vand_vx_u32m1(indices, 1, vl), 0, vl);
        paired = __riscv_vmerge_vvm_f32m1(
            paired, __riscv_vfneg_v_f32m1(paired, vl), even, vl);
        paired = __riscv_vfmul_vv_f32m1(paired, sine, vl);
        const vfloat32m1_t product = __riscv_vfmul_vv_f32m1(x, cosine, vl);
        __riscv_vse32_v_f32m1(output + i,
            __riscv_vfadd_vv_f32m1(product, paired, vl), vl);
        i += vl;
    }
}
#endif
