CASE_BINARY := test_llm_rope
CASE_DESCRIPTION := RVV 1.0 Interleaved FP32 rotary position embedding
REQUIRED_MNEMONICS := vluxei32.v vfwcvt.f.f.v vfncvt.f.f.w
HOST_LDLIBS += -lm
include ../common/case_rules.mk

$(HOST_BINARY) $(TARGET_BINARY): $(wildcard *.h)
