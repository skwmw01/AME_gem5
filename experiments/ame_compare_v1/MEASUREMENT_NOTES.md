# Measurement decisions and limits

The immutable simulator is the existing B11 binary at commit 26b042f07e.
All source changes for this experiment are under experiments/docs; no simulated
instruction, CPU/FU, register or default platform behavior is changed.

- Each configuration runs the same mathematical task across P/X06/S05A.
  MAC packing is explicitly different; half widening compares 32 useful elements.
- W1 uses handwritten repeat loops. W2/W3 dispatch once per homogeneous batch.
  GEMM chooses a type-specific function before ROI; its k-tile loop is assembly
  loads + one MAC + pointer/count updates. It never dispatches per MAC.
- Matrix register resources: one physical Acc for the GEMM kernels. The W3
  mixed-type family preserves three logical accumulators in ordinary memory,
  restoring I32/FP32 state at batch switches. W2 FP16/BF16 shares one FP32 Acc.
- A W3 random sequence is random at the batch level. Every operation in a batch
  has the same type; total type counts remain balanced. Separate paired API
  timings compare known/runtime types under an identical cold-call policy.
- All FMA benchmark operands are small integers with exact FP16/BF16 encodings;
  every sequential FP32 sum is below 2**24. Thus the exact integer oracle is a
  valid independent sequential-FMA reference, without relying on host float
  multiplication. The assertion is checked while generating expected results.
- Whole-register traffic is 64 bytes per mls.1r/mss.1r. Actual retired scalar
  loads/stores are also decoded by width. These are requested architectural
  bytes, including stack/packing where applicable, not measured DRAM bus bytes.
- Logical/prepared input/output spans and accumulated transfers are separate
  fields. Input hashes describe the documented logical/oracle representation.
  Inputs/references can be archived with materialize.py; packed bytes follow
  the group-specific indexing in the source and plan.
- Matrix serialization triggers Minor frontend redirection. With no I/D cache,
  function addresses and code organization can affect cycles even at equal
  instruction counts. The six-task control has identical peripheral machine
  code/addresses, but differs in simulated operand dependency declarations.
- Fence before dump establishes the program's memory-ordering boundary. It is
  not a statement about physical DRAM write-cell completion. The wrapper's
  raw stats and rdinstret deltas differ by nine calibrated boundary instructions.
- Main runs place several independent, nonnested ROIs in one invocation; the
  group/range and case ordering match across groups. m5 reset clears statistics,
  not DDR controller/frontend history. A fresh single-case invocation can have
  different cycles from the same case inside a multi-case run even when its
  instruction count and output match. Fresh repetition checks establish
  determinism for an identical invocation, not equivalence of these histories.
  Use batched W1 results for short-call interpretation; the remaining fetch and
  memory-history effects are part of this measured software/model experiment.
- Every primary trace is a commit trace. Compact and full text formatting were
  calibrated to produce identical target counts/output for the same program.
  No RVV occurs inside ROI; ordinary scalar and matrix instructions each yield
  one architectural record. Category sums and compute counts are checked.
  The final classifier also recognizes unsigned scalar loads and Acc moves
  outside helper functions, and follows scalar producers of descriptor operands
  so expanded constants/table preparation enter type_setup. Shared caller state
  remains ordinary scalar overhead. Chunked extraction was compared with the
  line parser on three resident tasks and all 80 records of a full-format API
  family; output counts and classifications were identical. Saved PC-frequency
  caches are tied to the SHA256 of the original compressed trace.
- Binary InstPBTrace was tried as a logging optimization but its protobuf enum
  rejects Matrix opclasses in this frozen build. It is not used for results;
  the diagnostic failure is retained without modifying gem5.
- Batching repeats complete cold calls (including setup/load/store), or continuous
  resident computations, inside one ROI. At least 1024 computations are measured
  for W1. Raw single calls remain available; no arbitrary fixed subtraction is
  used. Source-generated software and type setup dominate some short tasks.
- The implementation uses common callable load/store helpers and scalar packing
  templates, not a claim of globally minimal or fully tuned assembly. Further
  specialization of helper constant branches, zero-copy packing cases, wider
  register blocking and more accumulators could change costs. The same selected
  tiling and optimization budget is used across groups in the primary run.
- No overall winner score combines primitive tasks, GEMM and widening. Ratios
  are paired P/X06 and P/S05A; any geometric mean names its workload/ROI/state.
  Cold/hot denotes type/software state, not cache state. No confidence intervals
  are manufactured from deterministic repeated simulator runs.

Provisional data used a generic per-MAC dispatch loop. That was discovered to
violate the intended comparison and stopped. It remains under the old main tags,
but only formal tags are eligible for the final report. The trace classifier
also initially confused P's R2 subfunctions; its preserved trace is reanalysed
with the corrected full match and old JSON is retained.
