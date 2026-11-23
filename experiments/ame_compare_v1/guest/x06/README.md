# X06 software kernels

`tools/build.py` reads the independently validated X06 encoding.csv and emits
`results/ame_compare_v1/build/X06/ops.S`. No LLVM mnemonic support is assumed.
A is row-major, B is row-major BT. For 32-element half widening, two M source
tiles contain four useful low columns per row; two conversion words produce
consecutive canonical output halves. Acc initialization/extraction retains the
necessary common M/Acc move descriptors, even though compute ignores types.
