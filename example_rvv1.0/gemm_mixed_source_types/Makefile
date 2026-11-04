CASE_BINARY := test_gemm_mixed_types
CASE_DESCRIPTION := RVV 1.0 INT4 INT8 UINT4 UINT8 FP8 mixed GEMM, transpose, rounding, saturation
REQUIRED_MNEMONICS := vfmacc.vv/vfmacc.vf/vfmadd.vv/vfmadd.vf vsadd.vv vssub.vv vfncvt.rod.f.f.w
include ../common/case_rules.mk

$(HOST_BINARY) $(TARGET_BINARY): $(wildcard *.h)
