# Independent oracle

`tools/model.py` computes answers in standard logical layout; it never calls
simulator helpers or takes another group as the sole expected result. Scalar
IEEE primitives are imported by file path from the existing exact Fraction
reference (`tests/ame_explicit_v1/common/ieee.py`). That file's hash is retained.

Small-integer MAC datasets guarantee exact products and every FP32 partial sum
within 2**24, so arbitrary-precision integer accumulation proves the ordered
FP32-FMA result. Flags are checked. Conversion/addition use exact bit-pattern
IEEE routines. Gates also cover every half pattern, NaNs and signed zeros.
