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

#include <stdint.h>

#include "ztt_llm_case.h"
#include "rvv_kernels.h"

static int8_t ztt_llm_a_i8[ZTT_LLM_MATRIX_ELEMENTS] ZTT_LLM_ALIGNED;
static int8_t ztt_llm_b_i8[ZTT_LLM_MATRIX_ELEMENTS] ZTT_LLM_ALIGNED;
static int32_t ztt_llm_c_i32[ZTT_LLM_MATRIX_ELEMENTS] ZTT_LLM_ALIGNED;

uint64_t
ztt_llm_run_case(struct ztt_llm_case_result *result)
{
    for (unsigned i = 0; i < ZTT_LLM_N; ++i) {
        for (unsigned j = 0; j < ZTT_LLM_N; ++j) {
            ztt_llm_a_i8[i * ZTT_LLM_N + j] =
                (int8_t)((int)((i * 3 + j * 5 + 1) % 5) - 2);
            ztt_llm_b_i8[i * ZTT_LLM_N + j] =
                (int8_t)((int)((i * 7 + j * 2 + 3) % 7) - 3);
            ztt_llm_c_i32[i * ZTT_LLM_N + j] = (int32_t)((i + j) % 3) - 1;
        }
    }

#if defined(__riscv)
    rvv_gemm_i8(ztt_llm_a_i8, ztt_llm_b_i8, ztt_llm_c_i32, ZTT_LLM_N);
    rvv_i32_i64_roundtrip(ztt_llm_c_i32, ZTT_LLM_MATRIX_ELEMENTS);
    result->status = 0;
#else
    for (unsigned i = 0; i < ZTT_LLM_N; ++i) {
        for (unsigned j = 0; j < ZTT_LLM_N; ++j) {
            int32_t value = ztt_llm_c_i32[i * ZTT_LLM_N + j];
            for (unsigned k = 0; k < ZTT_LLM_N; ++k) {
                value += (int32_t)ztt_llm_a_i8[i * ZTT_LLM_N + k] *
                         ztt_llm_b_i8[k * ZTT_LLM_N + j];
            }
            ztt_llm_c_i32[i * ZTT_LLM_N + j] = value;
        }
    }
    result->status = 0;
#endif

    result->output = ztt_llm_c_i32;
    result->element_count = ZTT_LLM_MATRIX_ELEMENTS;
    result->element_bytes = sizeof(ztt_llm_c_i32[0]);
    return result->status;
}
