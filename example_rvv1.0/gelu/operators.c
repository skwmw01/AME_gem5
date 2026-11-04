#include <stdint.h>

#include "ztt_llm_case.h"
#include "rvv_kernels.h"

static float ztt_llm_output[ZTT_LLM_TILE_ELEMENTS] ZTT_LLM_ALIGNED;

#if !defined(__riscv)
static float
ztt_llm_pow2_integer(int exponent)
{
    uint32_t bits;
    if (exponent < -126)
        bits = 0;
    else if (exponent > 127)
        bits = UINT32_C(0x7f800000);
    else
        bits = (uint32_t)(exponent + 127) << 23;
    float value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}
#endif

uint64_t
ztt_llm_run_case(struct ztt_llm_case_result *result)
{
    float input[ZTT_LLM_TILE_ELEMENTS] ZTT_LLM_ALIGNED;
    for (unsigned i = 0; i < ZTT_LLM_TILE_ELEMENTS; ++i) {
        input[i] = (float)((int)(i % 5) - 2);
    }

#if defined(__riscv)
    rvv_gelu(input, ztt_llm_output, ZTT_LLM_TILE_ELEMENTS);
    result->status = 0;
#else
    for (unsigned i = 0; i < ZTT_LLM_TILE_ELEMENTS; ++i) {
        const float exponent = 0.0f - input[i] * 2.0f;
        const float denominator = 1.0f +
            ztt_llm_pow2_integer((int)exponent);
        ztt_llm_output[i] = input[i] * (1.0f / denominator);
    }
    result->status = 0;
#endif

    result->output = ztt_llm_output;
    result->element_count = ZTT_LLM_TILE_ELEMENTS;
    result->element_bytes = sizeof(ztt_llm_output[0]);
    return result->status;
}
