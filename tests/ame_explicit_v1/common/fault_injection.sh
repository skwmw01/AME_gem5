#!/bin/bash
set -eu
# Run only in a disposable /work copy with the real source mounted read-only
# at /original. Prepare/copy the B11 build tree before invoking this script.
test -f /original/src/arch/riscv/insts/xuantie_v06_explicit.cc
if [ /work -ef /original ]; then exit 22; fi
mkdir -p /work/toolchain /work/results/ame_explicit_v1/fault
if [ ! -e /work/toolchain/install ]; then
    ln -s /original/toolchain/install /work/toolchain/install
fi
cp /original/src/arch/riscv/insts/xuantie_v06_explicit.cc src/arch/riscv/insts/xuantie_v06_explicit.cc
cp /original/src/arch/riscv/insts/spec_v05a_explicit.cc src/arch/riscv/insts/spec_v05a_explicit.cc
python3 - <<'MUTATE'
from pathlib import Path
p = Path('src/arch/riscv/insts/xuantie_v06_explicit.cc')
s = p.read_text()
needle = '        write(result, i, z);'
assert s.count(needle) == 1
p.write_text(s.replace(needle, '        write(result, i, i == 0 ? z ^ 1 : z);', 1))
MUTATE
scons build/AME_B11/gem5.opt -j16 > results/ame_explicit_v1/fault/x06-build.log 2>&1
set +e
python3 tests/ame_explicit_v1/run.py functional --suite xuantie_v06 --gem5 build/AME_B11/gem5.opt --random-count 0 --limit 263 > results/ame_explicit_v1/fault/x06-mutated.log 2>&1
rc=$?
set -e
if [ "$rc" = 0 ]; then exit 20; fi
cp results/ame_explicit_v1/xuantie_v06/functional.json results/ame_explicit_v1/fault/x06-mutated.json
python3 tests/ame_explicit_v1/run.py functional --suite spec_v05a --gem5 build/AME_B11/gem5.opt --random-count 0 --limit 263 > results/ame_explicit_v1/fault/s05-unaffected.log 2>&1
cp results/ame_explicit_v1/spec_v05a/functional.json results/ame_explicit_v1/fault/s05-unaffected.json
cp /original/src/arch/riscv/insts/xuantie_v06_explicit.cc src/arch/riscv/insts/xuantie_v06_explicit.cc
python3 - <<'PY'
from pathlib import Path
p=Path('src/arch/riscv/insts/spec_v05a_explicit.cc')
s=p.read_text().replace('    store(target, result);','    result[0] ^= 1;\n    store(target, result);',1)
p.write_text(s)
PY
scons build/AME_B11/gem5.opt -j16 > results/ame_explicit_v1/fault/s05-build.log 2>&1
set +e
python3 tests/ame_explicit_v1/run.py functional --suite spec_v05a --gem5 build/AME_B11/gem5.opt --random-count 0 --limit 263 > results/ame_explicit_v1/fault/s05-mutated.log 2>&1
rc=$?
set -e
if [ "$rc" = 0 ]; then exit 21; fi
cp results/ame_explicit_v1/spec_v05a/functional.json results/ame_explicit_v1/fault/s05-mutated.json
python3 tests/ame_explicit_v1/run.py functional --suite xuantie_v06 --gem5 build/AME_B11/gem5.opt --random-count 0 --limit 263 > results/ame_explicit_v1/fault/x06-unaffected.log 2>&1
cp results/ame_explicit_v1/xuantie_v06/functional.json results/ame_explicit_v1/fault/x06-unaffected.json

# Restore source in the disposable tree; preserve faulty binaries and logs.
cp /original/src/arch/riscv/insts/spec_v05a_explicit.cc src/arch/riscv/insts/spec_v05a_explicit.cc
