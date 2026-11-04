CASE_BINARY := test_llm_mha
CASE_DESCRIPTION := RVV 1.0 Two-head QKV, scores, base-2 Softmax, context
REQUIRED_MNEMONICS := vlse32.v vfredmax.vs vfredosum.vs
include ../common/case_rules.mk

$(HOST_BINARY) $(TARGET_BINARY): $(wildcard *.h)
