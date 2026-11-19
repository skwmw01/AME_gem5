#!/bin/bash
set -eu
# The existing default build is the fifth independently tracked build tree.
root=results/ame_explicit_v1/incremental
mkdir -p "$root"
scons olddefconfig build/RISCV > "$root/olddefconfig.log" 2>&1
for phase in off-before on off-after; do
    enabled=n
    if [ "$phase" = on ]; then enabled=y; fi
    mkdir -p "$root/$phase"
    scons setconfig build/RISCV USE_XUANTIE_V06_EXPLICIT="$enabled" USE_SPEC_V05A_EXPLICIT="$enabled" > "$root/$phase/setconfig.log" 2>&1
    scons build/RISCV/gem5.opt -j24 > "$root/$phase/build.log" 2>&1
    cp build/RISCV/gem5.opt "$root/$phase/gem5.opt"
    cp build/RISCV/gem5.build/config "$root/$phase/config"
    extra=()
    if [ "$enabled" = n ]; then extra+=(--disabled); fi
    for suite in xuantie_v06 spec_v05a; do
        python3 tests/ame_explicit_v1/run.py functional --suite "$suite" --gem5 "$root/$phase/gem5.opt" --random-count 0 --limit 263 "${extra[@]}" > "$root/$phase/$suite.log" 2>&1
    done
done
