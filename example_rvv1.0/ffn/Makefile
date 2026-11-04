CASE_BINARY := test_llm_ffn
CASE_DESCRIPTION := RVV 1.0 Two-layer FFN with base-2 GELU approximation
REQUIRED_MNEMONICS := vfmul.vf vfadd.vv vfrdiv.vf
include ../common/case_rules.mk

$(HOST_BINARY) $(TARGET_BINARY): $(wildcard *.h)
