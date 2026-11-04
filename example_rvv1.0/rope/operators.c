/*
 * Copyright (c) 2026 BOSC & ICT, CAS
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met: redistributions of source code must retain the above copyright
 * notice, this list of conditions and the following disclaimer;
 * redistributions in binary form must reproduce the above copyright
 * notice, this list of conditions and the following disclaimer in the
 * documentation and/or other materials provided with the distribution;
 * neither the name of the copyright holders nor the names of its
 * contributors may be used to endorse or promote products derived from
 * this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#if !defined(__riscv)
#include <math.h>

#endif
#include <stdint.h>

#include "operators.h"
#include "ztt_llm_case.h"
#include "rvv_kernels.h"

_Static_assert(ZTT_LLM_TILE == 4, "This example uses FP32 4x4 tiles");

static float ztt_llm_output[ZTT_LLM_TILE_ELEMENTS] ZTT_LLM_ALIGNED;

uint64_t
ztt_llm_rope_fp32_tile(const float *input, const float *angles, float *output)
{
#if defined(__riscv)
    rvv_rope(input, angles, output, ZTT_LLM_TILE_ELEMENTS);
    return 0;
#else
    for (unsigned i = 0; i < ZTT_LLM_TILE_ELEMENTS; i += 2) {
        const float even = input[i];
        const float odd = input[i + 1];
        /* gem5 evaluates transcendental functions in long double, then
         * rounds to the destination FP32 datatype. */
        const float cosine = (float)cosl((long double)angles[i]);
        const float sine = (float)sinl((long double)angles[i]);
        const float even_cos = even * cosine;
        const float odd_sin = -odd * sine;
        const float odd_cos = odd * cosine;
        const float even_sin = even * sine;
        output[i] = even_cos + odd_sin;
        output[i + 1] = odd_cos + even_sin;
    }
    return 0;
#endif
}

uint64_t
ztt_llm_run_case(struct ztt_llm_case_result *result)
{
    float input[ZTT_LLM_TILE_ELEMENTS] ZTT_LLM_ALIGNED;
    float angles[ZTT_LLM_TILE_ELEMENTS] ZTT_LLM_ALIGNED;
    /* Four positions (0..3), head_dim=4, base=10000:
     * inverse frequencies are [1, 0.01], each repeated for its pair. */
    for (unsigned row = 0; row < ZTT_LLM_TILE; ++row) {
        for (unsigned col = 0; col < ZTT_LLM_TILE; ++col) {
            const unsigned i = row * ZTT_LLM_TILE + col;
            input[i] = (float)((int)i - 7) * 0.25f;
            angles[i] = (float)row * (col < 2 ? 1.0f : 0.01f);
        }
    }

    result->status = ztt_llm_rope_fp32_tile(input, angles, ztt_llm_output);
    result->output = ztt_llm_output;
    result->element_count = ZTT_LLM_TILE_ELEMENTS;
    result->element_bytes = sizeof(ztt_llm_output[0]);
    return result->status;
}
