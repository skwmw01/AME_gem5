# P software kernels

`tools/build.py` emits this group's `results/ame_compare_v1/build/P/ops.S`.
Four polymorphic words cover the ten type tasks: madd.ew, mmax.ew,
mmulbtacc.2d and mconv.ew. Per-type names alias the same computational body
where legal. Md/Ad setup supplies the actual type. FP32-to-I32 uses the RNE
I32 descriptor 0x48000020. Packed MAC operands use 4x4-square order, not X06
row-contiguous packing. FP16 widening writes 32 elements into two M registers.
