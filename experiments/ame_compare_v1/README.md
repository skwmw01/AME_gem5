# P / X06 / S05A comparison, without simulator changes

The frozen plan is [PLAN_v1.md](PLAN_v1.md). Main simulator commit:
`26b042f07e3c460037ca151778c0fc3aa2e80f2a`. All three groups execute the
same `build/AME_B11/gem5.opt`; its SHA256 is checked by every run.
W6 is deferred because it requires new simulated instructions.

## Run environment

From the repository root:

```bash
docker run --rm -it -v "$PWD:/work" -w /work ame-gem5-rvv:local bash
```

Inside `/work`, build the guest programs (this never builds gem5):

```bash
python3 experiments/ame_compare_v1/tools/build.py
python3 experiments/ame_compare_v1/tools/run.py run --end 13 --trace --tag gates
python3 experiments/ame_compare_v1/tools/layout_checks.py
python3 experiments/ame_compare_v1/tools/gates.py
python3 experiments/ame_compare_v1/tools/boundary.py
python3 experiments/ame_compare_v1/tools/static_audit.py
```

The emitters are independent for P/X06/S05A; X06/S05A encoding tables are
read from their existing validated CSVs. P uses four polymorphic encodings.
`guest/common/bench.c` performs all actual loads, computes and stores.
The host oracle works in logical layout and never calls simulator backends.

The guest linker fixes measurement code, helper categories, W1 functions,
logical input, output and scratch buffer addresses. All code is 32-bit,
nonrelaxed, scalar packing (no RVV packing), O2, no LTO or ICF. Different
main groups can have different useful code sizes. In the six same-layout
control tasks, code and addresses of W1 and all preparation helpers are
checked byte for byte; only the chosen computation words differ.

## Complete W1—W5 population

`tools/cases.py` declares every case before running; `results/ame_compare_v1/cases.json`
retains all parameters and IDs. The 1,236 configurations include calibration,
W1 (135 ROI/state records = 45 logical pairings × three policies), W1 control
(60), W2 (30), W3 runtime (240) and known entry (180), W4 GEMM (420),
W4 pipelines (80), and W5 (60). Each configuration runs under all three groups.

```bash
bash experiments/ame_compare_v1/tools/full_group.sh P
bash experiments/ame_compare_v1/tools/full_group.sh X06
bash experiments/ame_compare_v1/tools/full_group.sh S05A
```

Independent groups can run concurrently. Keep each workload range sequential;
its cases share fixed guest report and buffers within each invocation.
Every invocation gets its own timestamped directory and exact ELF snapshot.
Do not rebuild while measurements are running.

Additional short-call batches and software APIs:

```bash
python3 experiments/ame_compare_v1/tools/batched.py
python3 experiments/ame_compare_v1/tools/run.py run --start 31 --end 166 --trace --batch --tag formal-batches-v2
python3 experiments/ame_compare_v1/tools/api_size.py
python3 experiments/ame_compare_v1/tools/api_perf.py
python3 experiments/ame_compare_v1/tools/static_audit.py
python3 experiments/ame_compare_v1/tools/reparse.py
```

The batched variant repeats each W1 call `max(1, 1024/R)` times within one ROI.
Every packed cold invocation still performs its own descriptor setup, loads
and initialization; a resident MAC batch continuously accumulates and the
oracle includes every repeated MAC. Raw single-call results are retained. Each batched ROI covers at least 1024
computations: the number of full calls is max(1, 1024/R).
Known/runtime API supplemental timings use exactly the same input and
128 independent cold calls for both modes. Each call does 1 or 16 computations.
The mixed W3 sequence uses batches of one type: randomization permutes batch
types, not elements within a batch. P uses a shared compute body where possible.
W3 MAC preserves separate logical accumulators per type in memory across
batches, restoring the proper I32 or FP32 representation on a switch. W2
FP16/BF16 instead continuously shares one FP32 accumulator. These are
explicitly different state policies, identical across P/X06/S05A within each
paired case.

## Measurement and interpretation

`measure.S` issues m5 reset/dump (zero delay), reads rdcycle/rdinstret, invokes
one kernel or batch, and fences stores before dump. Statistics include boundary
instructions; raw counts are never blindly adjusted. For the calibrated
wrapper, the stats instruction count exceeds the rdinstret delta by nine.
Exec trace is emitted on Minor commit; the parser counts the reset-exclusive,
dump-inclusive range. It classifies actual machine instructions, not source
lines or pseudoinstructions, and checks category sum and expected compute count.
It also counts the 64-byte whole-M transfers. Scalar packing and stack traffic
are classified separately; matrix transfer bytes are not total bus traffic.

No cache is installed. Matrix operations serialize and cause Minor pipeline
redirection. Results describe this model's task costs, including fetch,
configuration and serialization effects; they do not measure hardware type
resolution latency, area, power or native ISA superiority.

The complete output lives under `results/ame_compare_v1/` (ignored by Git).
Documentation copies compact records, hashes, CSV tables and plots. Failed
or provisional runs remain in their original directories. Reanalysis preserves
`records-parser-v1.json` before correcting a trace-classification error.

To reproduce the platform gate, run both existing complete B11 functional
suites and the original frozen ELF regression as described in the old report.
All groups in this experiment still run B11, including P.

After all jobs finish, use the current parser against preserved traces, then
produce the report on the host (requires matplotlib; does not run gem5):

```bash
python3 experiments/ame_compare_v1/tools/reparse.py
python3 experiments/ame_compare_v1/tools/report.py --collect-only
python3 experiments/ame_compare_v1/tools/materialize.py
python3 experiments/ame_compare_v1/tools/artifacts.py
python3 experiments/ame_compare_v1/tools/report.py
```

The report exits nonzero unless every required population and gate is complete
and passes. W6 is explicitly excluded by this experiment's no-simulator-change
constraint, not counted as a successful extension experiment.

## 一个完整调用的复现示例

以下命令在上述容器的 `/work` 中执行，使用已经冻结的B11，不重编译模拟器：

```bash
python3 experiments/ame_compare_v1/tools/run.py run --start 32 --end 33 --trace --tag demo-A1-cold
```

这是W1的A1、R=1、冷`packed_call`，默认依次运行P/X06/S05A。
每组都包含必要配置、装载、一次16元素I32加法、结果存储和返回；
因此“一次计算”不等于整段程序只执行一条指令。
`guest/common/bench.c` 的 `w1_0` 定义完整调用，`tools/build.py` 的
`ops()` 生成其中的 `repeat_0_0` 汇编循环。
结果在打印出的目录中：`records.json`保存与独立参考的位模式比较、flags、
周期及分类计数，`ops.S`/`disassembly.txt`保存真实机器字，
`m5out/trace.gz`与`m5out/stats.txt`保存提交轨迹和测量统计。
正式W1还将同样的完整冷调用在ROI内重复1024次，以降低测量边界占比。
主集合在同一进程内包含多个独立ROI；统计清零不重置DDR/前端历史。
因此单独启动示例的周期可以与主集合里的同一用例不同；数值和真实计算次数均应通过，
不能用不同启动/前序历史下的短区间周期差来判定指令正确性失败。

最终输入/参考索引由`materialize.py`生成；再次运行`report.py`把索引和哈希
收录到报告证据中。原始大文件保留在忽略的results目录，不进入Git。
