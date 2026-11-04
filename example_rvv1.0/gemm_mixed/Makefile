CASE_BINARY := test_llm_gemm_mixed
CASE_DESCRIPTION := RVV 1.0 INT8 inputs with INT32 accumulation
REQUIRED_MNEMONICS := vsext.vf4 vmacc.vx
include ../common/case_rules.mk

$(HOST_BINARY) $(TARGET_BINARY): $(wildcard *.h)
