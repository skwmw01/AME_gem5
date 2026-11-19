# Independent explicit matrix subsets

Baseline: `6677b2c8f6e76363050427009d47c5481f9e53bf` (`ztt-v0.6-dev`).
Branch: `ztt0.6-xuantie0.6-spec0.5a-vs`.

X06 and S05A have separate tables, generated instruction classes, execution
functions, SoftFloat state wrappers and reference adapters. Shared reference
scalar primitives use exact Python fractions and do not call SoftFloat.
The simulator shares only register containers, access/dirty infrastructure,
generic ISA templates and the raw third-party SoftFloat library.

```
python3 tests/ame_explicit_v1/run.py audit
python3 tests/ame_explicit_v1/run.py build-matrix --jobs 8
python3 tests/ame_explicit_v1/run.py functional --suite xuantie_v06 --gem5 build/AME_B10/gem5.opt
python3 tests/ame_explicit_v1/run.py functional --suite spec_v05a --gem5 build/AME_B01/gem5.opt
python3 tests/ame_explicit_v1/run.py regression --baseline results/ame_explicit_v1/baseline/gem5.opt
python3 tests/ame_explicit_v1/run.py report
```

Use `--disabled` for a disabled suite. `--random-count 100` (default) generates
100 inputs for each seed 0..9 and instruction, plus directed edge cases and
all FP16 bit patterns. Smaller counts are development runs, not acceptance.
Outputs retain timestamped raw guest reports and mismatches. A missing test
is NOT_RUN; numeric success alone does not imply full acceptance.

Build/runtime environment used here: existing `ame-gem5-rvv:local` Docker
image, repository mounted at `/work`, bundled `toolchain/install` compiler.
Baseline source and ten example ELF files are frozen before integration.
Large logs/binaries stay in `results/ame_explicit_v1/`; summary evidence and
hashes are copied into the documentation evidence directory for review.

## Complete reproduction

Run build/guest commands in the existing container (the host glibc cannot run
this gem5/toolchain). For example, from the repository root:

```bash
docker run --rm -v "$PWD:/work" -w /work ame-gem5-rvv:local \
  python3 tests/ame_explicit_v1/run.py build-matrix --jobs 8
```

The commands below run inside that container from `/work`. Run them serially:
checkpoint/shape/storage share restored guest report paths, and regression
intentionally shares one output path across simulators.

```bash
python3 tests/ame_explicit_v1/run.py audit
python3 tests/ame_explicit_v1/run.py build-matrix --jobs 8
for build in B00 B10 B01 B11; do
  for suite in xuantie_v06 spec_v05a; do
    extra=(--random-count 100)
    if [[ "$build" = B00 || "$build:$suite" = B01:xuantie_v06 || "$build:$suite" = B10:spec_v05a ]]; then
      extra=(--disabled --random-count 0 --limit 263)
    fi
    python3 tests/ame_explicit_v1/run.py functional --suite "$suite" \
      --gem5 "build/AME_$build/gem5.opt" "${extra[@]}"
    python3 tests/ame_explicit_v1/run.py edge --suite "$suite" \
      --gem5 "build/AME_$build/gem5.opt"
  done
done
for suite in xuantie_v06 spec_v05a; do
  python3 tests/ame_explicit_v1/run.py functional --suite "$suite" \
    --gem5 build/AME_B11/gem5.opt --chain --random-count 0 --limit 263
  python3 tests/ame_explicit_v1/run.py checkpoint --suite "$suite" --gem5 build/AME_B11/gem5.opt
  python3 tests/ame_explicit_v1/run.py checkpoint --suite "$suite" --gem5 build/AME_B11/gem5.opt --negative
  python3 tests/ame_explicit_v1/run.py shape --suite "$suite" --gem5 build/AME_B11/gem5.opt
  python3 tests/ame_explicit_v1/run.py storage --suite "$suite" --gem5 build/AME_B11/gem5.opt
  python3 tests/ame_explicit_v1/run.py fields --suite "$suite" --gem5 build/AME_B11/gem5.opt
done
bash tests/ame_explicit_v1/common/incremental.sh
python3 tests/ame_explicit_v1/common/compile_compat.py
python3 tests/ame_explicit_v1/common/extra_tests.py
python3 tests/ame_explicit_v1/run.py regression --baseline results/ame_explicit_v1/baseline/gem5.opt
python3 tests/ame_explicit_v1/run.py acceptance
python3 tests/ame_explicit_v1/run.py report
```

`extra_tests.py` creates two original-primary mutation ELFs and runs the
P/X06/S05A/scalar interleave test. The mutations use the frozen baseline as
oracle; they do not test native ISA compatibility. `fields` executes every
legal register-field combination and checks the actual instruction trace.
`shape` must precede `storage`, which reuses its initial checkpoint.
`acceptance` exits nonzero for FAIL or NOT_RUN.

For a clean baseline rebuild, create a detached worktree at the frozen commit,
mount that tree at `/work` and the current `toolchain` directory at
`/work/toolchain`. Inside that container run:

```bash
scons defconfig build/RISCV build_opts/RISCV
scons build/RISCV/gem5.opt -j8
make -C example build
```

Copy that simulator and `build/RISCV/gem5.build/config` into this checkout's
`results/ame_explicit_v1/baseline/`, and each
`example/<case>/build/target/test_llm_<case>` into `baseline/elf/<case>`.
Freeze their hashes before testing. The ten case names and hashes from this
run are in `docs/ame_explicit_v1/evidence/baseline/manifest.json`.
No baseline source edits are needed.

Fault isolation must run in a disposable worktree/copy, mounted at `/work`,
with the unmodified implementation mounted **read-only** at `/original`.
Populate the disposable tree with this branch's simulator integration and
tests, and copy its completed `build/AME_B11` tree there (or build B11 there).
Invoke `bash tests/ame_explicit_v1/common/fault_injection.sh` in that container.
It injects X06 first, restores it, then injects S05A, checking expected failures
and the unaffected suite each time. Copy its `results/ame_explicit_v1/fault/`
JSON/logs into the original checkout's `results/ame_explicit_v1/fault_injection/`
before the final acceptance/report commands. Do not run it against the real
implementation tree. The actual validation worktree was `/tmp/ame_dual_fault_x06`.

The fifth incremental tree is `build/RISCV`, which ends with both switches
disabled. This intentionally tests the existing default directory as well as
stale-object removal. Keep all timestamped runs: top-level suite summaries can
refer to a later short run; acceptance selects completed full runs explicitly.
The report copies selected evidence and hashes without deleting failed runs.
