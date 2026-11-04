CASE_BINARY := test_llm_gemm_int8
CASE_DESCRIPTION := RVV 1.0 INT8 x INT8 to INT32
REQUIRED_MNEMONICS := vsext.vf4 vmacc.vx vwcvt.x.x.v/vwadd.vx/vsext.vf2 vnsrl.wi/vncvt.x.x.w
include ../common/case_rules.mk

$(HOST_BINARY) $(TARGET_BINARY): $(wildcard *.h)
