CASE_BINARY := test_llm_gemm_fp32
CASE_DESCRIPTION := RVV 1.0 FP32 C += A B
REQUIRED_MNEMONICS := vfmul.vf vfadd.vv
include ../common/case_rules.mk

.PHONY: test-host-golden test-reference
test-host-golden:
	+$(MAKE) --no-print-directory test GOLDEN=host
test-reference:
	+$(MAKE) --no-print-directory test GOLDEN=reference

$(HOST_BINARY) $(TARGET_BINARY): $(wildcard *.h)
