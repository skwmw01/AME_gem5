# Frozen baseline regression

Rebuild the exact baseline before adding the six integration edits. Save the
simulator/config hashes and copy the ten built example ELF files into
results/ame_explicit_v1/baseline/elf. Run those exact files under baseline and
B00/B10/B01/B11 with identical configuration. Compare report bytes, return
code and final stats section simInsts/simOps/simTicks/system.cpu.numCycles.
Additional permissions, native opcode, RVV, scalar and checkpoint obligations
must be listed explicitly in acceptance.json; ten examples alone are not the
entire required regression suite.
