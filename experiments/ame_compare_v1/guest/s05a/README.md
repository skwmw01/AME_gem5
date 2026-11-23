# S05A software kernels

`tools/build.py` reads the independently validated S05A encoding.csv and emits
`results/ame_compare_v1/build/S05A/ops.S`. A/B are both row-major. One widening
word consumes all 32 halves and writes two consecutive M destinations. The
compiler emits raw .word values; the same immutable B11 simulator independently
decodes/executes S05A and X06. Peripheral timing code is shared for fairness.
