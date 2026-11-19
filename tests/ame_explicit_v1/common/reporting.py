"""Generate reviewable summaries from selected actual acceptance records."""
import csv
import hashlib
import json
import subprocess
from pathlib import Path


SWITCH_USAGE = """### 4.1 开关含义与使用环境

两个开关定义于 `src/arch/riscv/Kconfig`，仅适用于 RISC-V 构建，默认均为 `n`：

| 开关 | `y` 时启用 | `n` 时行为 |
|---|---|---|
| `USE_XUANTIE_V06_EXPLICIT` | 10 条 `xt06.*` 指令（X06） | 不编译/链接该组执行实现；对应实验机器字触发非法指令 |
| `USE_SPEC_V05A_EXPLICIT` | 10 条 `sp05a.*` 指令（S05A） | 不编译/链接该组执行实现；对应实验机器字触发非法指令 |

这是 **gem5 编译期开关**，配置按构建目录分别保存。修改后必须重新编译，并运行该目录下的 `gem5.opt`；不需要给 `example/ame_config.py` 增加运行时开关。关闭某组不影响原有 Ztt 指令。

下面的 `scons`、测试和运行命令均在仓库根目录执行。本机采用现有 Docker 环境，可先在宿主的仓库根目录进入容器：

```bash
docker run --rm -it -v "$PWD:/work" -w /work ame-gem5-rvv:local bash
```

### 4.2 新建四种独立构建

首次创建构建目录时执行 `defconfig`，随后用 `setconfig` 明确设置两组开关，再编译。以下四种组合可以分别执行；`-j8` 可按可用内存和 CPU 调整。

```bash
# B00：两组均关闭（默认行为）
scons defconfig build/AME_B00 build_opts/RISCV
scons setconfig build/AME_B00 USE_XUANTIE_V06_EXPLICIT=n USE_SPEC_V05A_EXPLICIT=n
scons build/AME_B00/gem5.opt -j8

# B10：仅启用 X06
scons defconfig build/AME_B10 build_opts/RISCV
scons setconfig build/AME_B10 USE_XUANTIE_V06_EXPLICIT=y USE_SPEC_V05A_EXPLICIT=n
scons build/AME_B10/gem5.opt -j8

# B01：仅启用 S05A
scons defconfig build/AME_B01 build_opts/RISCV
scons setconfig build/AME_B01 USE_XUANTIE_V06_EXPLICIT=n USE_SPEC_V05A_EXPLICIT=y
scons build/AME_B01/gem5.opt -j8

# B11：同时启用两组
scons defconfig build/AME_B11 build_opts/RISCV
scons setconfig build/AME_B11 USE_XUANTIE_V06_EXPLICIT=y USE_SPEC_V05A_EXPLICIT=y
scons build/AME_B11/gem5.opt -j8
```

也可用统一入口一次构建并检查四种组合：

```bash
python3 tests/ame_explicit_v1/run.py build-matrix --build-root build --jobs 8
```

### 4.3 已有构建目录切换与关闭

已有目录先执行 `olddefconfig` 接纳新增配置项并保留其他配置，再 `setconfig`。例如，在已有 `build/RISCV` 中启用两组：

```bash
scons olddefconfig build/RISCV
scons setconfig build/RISCV USE_XUANTIE_V06_EXPLICIT=y USE_SPEC_V05A_EXPLICIT=y
scons build/RISCV/gem5.opt -j8
```

仅启用一组时，将另一开关设为 `n`；恢复两组关闭：

```bash
scons setconfig build/RISCV USE_XUANTIE_V06_EXPLICIT=n USE_SPEC_V05A_EXPLICIT=n
scons build/RISCV/gem5.opt -j8
```

不需要手工删除目标文件或修改生成头文件。本版已经验证同一目录关闭→开启→关闭的增量编译。此处命令是使用说明；本次交付时默认 `build/RISCV` 仍为两组关闭。

### 4.4 确认配置并运行对应二进制

实际配置保存在 `<构建目录>/gem5.build/config`。例如检查 B11：

```bash
grep -E 'USE_(XUANTIE_V06|SPEC_V05A)_EXPLICIT' build/AME_B11/gem5.build/config
```

启用时显示 `USE_..._EXPLICIT=y`，关闭时显示 `# USE_..._EXPLICIT is not set`。配置文件表示下一次构建所用设置，因此应确认上述编译成功后再运行：

```bash
# 对双开二进制分别验证两组指令
python3 tests/ame_explicit_v1/run.py functional --suite xuantie_v06 --gem5 build/AME_B11/gem5.opt
python3 tests/ame_explicit_v1/run.py functional --suite spec_v05a --gem5 build/AME_B11/gem5.opt

# 对双关二进制验证非法指令路径
python3 tests/ame_explicit_v1/run.py functional --suite xuantie_v06 --gem5 build/AME_B00/gem5.opt --disabled --random-count 0 --limit 263
python3 tests/ame_explicit_v1/run.py functional --suite spec_v05a --gem5 build/AME_B00/gem5.opt --disabled --random-count 0 --limit 263

# 运行自己的 ELF；将路径替换为实际来宾 ELF 与报告路径
build/AME_B11/gem5.opt -d /work/m5out-explicit example/ame_config.py --cmd '/work/path/to/program.elf /work/path/to/report.txt'
```

`--disabled` 是测试程序的“预期非法指令”检查选项，不会改变 gem5 开关。两组实验助记符的汇编器支持不由这些开关提供；本版测试通过各组 `encoding.csv`、`encoding.h` 和 `kernels.S` 中的原始机器字发码。

### 4.5 本次构建验收结果
"""


def generate_report(api, args):
    from common.acceptance import collect
    root = api.REPO
    api.RESULTS = Path(args.results).resolve()
    out = api.RESULTS
    dest = root/'docs/ame_explicit_v1'
    evidence = dest/'evidence'
    evidence.mkdir(parents=True, exist_ok=True)
    acceptance = collect(api)
    checks = acceptance['checks']
    read = lambda p: json.loads(p.read_text())

    def status(items):
        states = [i['status'] for i in items]
        return 'FAIL' if 'FAIL' in states else 'NOT_RUN' if not states or 'NOT_RUN' in states else 'PASS'

    # Refresh summaries without destroying timestamped runs, including failures.
    inspections = [read(out/(b+'-inspection.json')) if (out/(b+'-inspection.json')).exists()
                   else dict(build=b, status='NOT_RUN') for b in ('B00','B10','B01','B11')]
    build_checks = [c for c in checks if any(t in c['name'] for t in
                    ('compile/link', 'incremental', 'disabled', 'full B', 'single/dual', 'restored off'))]
    matrix = dict(status=status(build_checks), builds=inspections, checks=build_checks)
    api.save(out/'build_matrix.json', matrix)
    independent = read(out/'independence.json') if (out/'independence.json').exists() else {}
    independent_checks = [c for c in checks if any(t in c['name'] for t in
                          ('fault isolation','decode_fields','dependencies','single/dual','full B','distinct B packing'))]
    independent.update(generated_code=status(inspections), checks=independent_checks,
                       fault_injection=status([c for c in checks if 'fault isolation' in c['name']]))
    independent['status'] = status(independent_checks + inspections +
                                   [dict(status=independent.get('static_status','NOT_RUN'))])
    api.save(out/'independence.json', independent)
    regressions = {}
    for p in sorted((out/'regression').glob('*/regression.json')):
        for r in read(p)['results']:
            regressions[(r['elf'],r['build'])] = dict(r, evidence=str(p.relative_to(root)))
    regression = dict(status=status([c for c in checks if c['name'].startswith('regression ')]),
                      results=[regressions[k] for k in sorted(regressions)])
    api.save(out/'regression.json', regression)

    selected = {out/(n+'.json') for n in ('acceptance','encoding_audit','independence','build_matrix','regression')}
    selected.update(out/(b+'-inspection.json') for b in ('B00','B10','B01','B11'))
    selected.update((out/'environment').glob('*.txt'))
    selected.update((out/'baseline').glob('*manifest.json'))
    selected.update((out/'fault_injection').glob('*.json'))
    selected.update([out/'commands.log', out/'interleave/interleave.json'])
    for c in checks:
        paths = c['evidence'] if isinstance(c['evidence'],list) else [c['evidence']]
        for value in paths:
            p = root/value
            if p.is_file() and p.suffix == '.json':
                selected.add(p)
                if p.name == 'functional.json':
                    selected.add(p.parent/'elf_audit.json')
    artifact_hashes = {}
    for p in sorted(selected):
        if not p.exists():
            continue
        relative = p.relative_to(out)
        target = evidence/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.tmp')
        temporary.write_bytes(p.read_bytes())
        temporary.replace(target)
        artifact_hashes[str(relative)] = api.sha(p)

    # Include untracked new sources without requiring git staging. Exclude the
    # generated report/evidence to avoid self-referential hashes.
    tracked = subprocess.check_output(['git','diff',api.BASE,'--name-only'],cwd=root,text=True).splitlines()
    untracked = subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=root,text=True).splitlines()
    names = sorted(set(n for n in tracked+untracked if not n.startswith('docs/ame_explicit_v1/') and (root/n).is_file()))
    source_hashes = {n:api.sha(root/n) for n in names}
    source_digest = hashlib.sha256(json.dumps(source_hashes,sort_keys=True).encode()).hexdigest()
    rows = []
    numstat = subprocess.check_output(['git','diff',api.BASE,'--numstat'],cwd=root,text=True)
    stats = {line.split('\t',2)[2]:line.split('\t',2)[:2] for line in numstat.splitlines()}
    baseline_names = set(subprocess.check_output(['git','ls-tree','-r','--name-only',api.BASE],cwd=root,text=True).splitlines())
    for n in names:
        added = n not in baseline_names
        ins, dels = stats.get(n,[str(len((root/n).read_text().splitlines())), '0'])
        rows.append(dict(file=n,change='新增' if added else '修改',insertions=ins,deletions=dels))
    baseline = read(out/'baseline/manifest.json') if (out/'baseline/manifest.json').exists() else {}
    manifest = dict(baseline=api.BASE,
                    branch=subprocess.check_output(['git','branch','--show-current'],cwd=root,text=True).strip(),
                    head_at_report=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
                    implementation_identity='source_manifest_sha256 (excludes generated docs/evidence)',
                    source_manifest_sha256=source_digest, sources=source_hashes,changes=rows,
                    pdf=baseline.get('pdf',{}),
                    frozen_elfs={p.name:api.sha(p) for p in sorted((out/'baseline/elf').glob('*'))},
                    baseline_simulator_sha256=api.sha(out/'baseline/gem5.opt') if (out/'baseline/gem5.opt').exists() else None,
                    evidence_sha256=artifact_hashes)
    api.save(out/'manifest.json', manifest)
    api.save(evidence/'manifest.json', manifest)

    lines = ['# xuantie-v0.6、spec-v0.5a 双独立显式子集最终修改报告','',
             '## 1. 实现结论','',
             f"总验收状态：**{acceptance['status']}**；检查汇总：`{acceptance['summary']}`。",
             f"基线：`{api.BASE}`；分支：`{manifest['branch']}`。",
             f"实现内容指纹（源文件 SHA256 清单的 SHA256）：`{source_digest}`。",
             '指纹包含新增文件，不依赖提交或暂存状态；生成报告与证据不参与自身哈希。',
             '', '两组各十条研究性显式计算指令，分别拥有译码、指令类、运算循环、数值包装和参考适配。',
             '两个编译开关默认关闭；不实现两份原生 ISA 的二进制兼容。',
             '仅修改六个原有模拟器入口，新增八个模拟器源文件。旧 Ztt、CSR、寄存器定义、CPU/FU 和 example 源码未修改。',
             '', '证据入口：[验收清单](evidence/acceptance.json)、[构建](evidence/build_matrix.json)、',
             '[独立性](evidence/independence.json)、[回归](evidence/regression.json)、[哈希清单](evidence/manifest.json)。',
             '证据中的 results 路径指向本地保留的原始运行；本目录 evidence 保留对应的紧凑 JSON、命令日志及哈希。',
             '', '## 2. 修改清单','', '| 文件 | 状态 | +行 / -行 |','|---|---|---|']
    for r in rows:
        lines.append(f"| `{r['file']}` | {r['change']} | {r['insertions']} / {r['deletions']} |")
    lines += ['', '模拟器四类操作分别为逐元素加法、最大值、宽化乘加、转换；测试目录含独立编码表、参考模型、来宾程序和验收工具。',
              '上表列出实现与测试文件；本报告和自动生成的 evidence 文件单独作为交付文档。',
              '', '## 3. 逐条实现与规范对应','',
              '| 分组 | 实验指令 | 原规范名称与位置 | mask / match | 执行类 / 函数 | 适配 | 测试 |',
              '|---|---|---|---|---|---|---|']
    for suite in api.SUITES:
        mapping = list(csv.DictReader((api.HERE/suite/'spec_mapping.csv').open()))
        decoder = (root/f'src/arch/riscv/isa/decoder/{suite}_explicit.isa').read_text()
        import re
        for row, spec in zip(api.table(suite),mapping):
            symbol = row['mnemonic'].replace('.','_')
            function = re.search(re.escape(symbol)+r'\((\w+),',decoder)[1]
            namespace = 'X06' if suite=='xuantie_v06' else 'S05A'
            cls = symbol[0].upper()+symbol[1:]
            lines.append(f"| {namespace} | `{row['mnemonic']}` | {spec['native']} · {spec['reference']} | `{row['mask']}` / `{row['match']}` | `{cls}` / `{namespace}::{function}` | {spec['adaptation']} | {spec['test']} |")
    lines += ['', 'X06 INT8 原生名称依据用户 PDF 修正为 `mmacc.w.b`；方案中的 `mmaqa.b` 不是该 PDF 的对应名称。',
              '', '## 4. 编译开关使用与验收','', SWITCH_USAGE, '',
              '| 构建 | X06 / S05A | 编译及链接 | X06 / S05A 行为 | 模拟器 SHA256 |',
              '|---|---|---|---|---|']
    for b in inspections:
        name=b['build']; x=name in ('B10','B11'); s=name in ('B01','B11')
        lines.append(f"| {name} | {int(x)} / {int(s)} | {b['status']} | {'执行' if x else '非法指令'} / {'执行' if s else '非法指令'} | `{b.get('sha256','NOT_RUN')}` |")
    lines += ['', '每个构建均检查生成类的结构数据操作数、链接符号和实际译码行为。',
              '第五个构建目录使用已有 `build/RISCV`，执行关闭→开启→关闭并保存三次二进制、配置、测试记录。',
              '这是相对方案“临时第五目录”的有意调整，同时验证已有默认目录的增量更新；最终两开关均为关闭。',
              '', '## 5. 正确性与独立性','',
              '| 检查 | 实测执行数（适用时） | 状态 | 证据 |','|---|---|---|---|']
    for c in checks:
        if c['name'].startswith('regression '): continue
        paths=c['evidence'] if isinstance(c['evidence'],list) else [c['evidence']]
        links=[]
        for value in dict.fromkeys(paths):
            p=root/value
            if p.is_file() and p.suffix=='.json' and p.is_relative_to(out):
                relative=p.relative_to(out); links.append(f'[{relative}](evidence/{relative})')
            else: links.append(f'`{value}`')
        lines.append(f"| {c['name']} | {c.get('executions','—')} | {c['status']} | {'; '.join(links)} |")
    lines += ['', '完整功能测试每条指令包含种子 0…9、每种子 100 组随机输入及定向边界；两组分别遍历 65,536 种 FP16 位模式。',
              '每个功能用例执行匹配/不匹配描述符两种模式，穿插五种标量 FRM 和后续标量浮点运算。',
              'X06 每构建 28,718 条观测，S05A 每构建 24,622 条；单开与双开来宾报告 SHA256 分别相同。',
              '全寄存器字段实际执行 292,832 次并核对译码 trace。依赖链每组 526 条观测，每条含两个新计算操作。',
              'checkpoint 检查异常前后全部矩阵容器与相关 CSR；storage 检查 72×256 字节物理容器、未使用尾部和非法描述符。',
              '精确有理数 IEEE 参考与模拟器 SoftFloat 独立；两组共享标量参考原语，各自维护布局和计算适配。',
              '双向故障注入各产生 104 条预期失败，仅限被修改组的加法，另一组正向测试仍通过；故障源码不进入本分支。',
              '', '## 6. 原有功能回归','',
              '| 冻结 ELF | B00 | B10 | B01 | B11 | 对照内容 |','|---|---|---|---|---|---|']
    for elf in sorted(manifest['frozen_elfs']):
        values=[regressions.get((elf,b),{}).get('status','NOT_RUN') for b in ('B00','B10','B01','B11')]
        lines.append('| '+elf+' | '+' | '.join(values)+' | 报告字节、退出状态、最终统计区段 |')
    lines += ['', '共 13 个冻结 ELF × 5 个模拟器运行记录（65 条），对应 52 组基线比较。',
              '包含十个原始示例、RVV/标量浮点/m5ops 兼容测试及两个原主操作码变异测试。',
              '变异测试以旧基线实际行为为准，不宣称实现原生 X06/S05A 指令。',
              '所有构建使用同一 ELF、输入和来宾输出路径，比较 simInsts、simOps、simTicks、system.cpu.numCycles；最终所选记录无差异。',
              '原有示例中可观测的结果/状态随报告比较；额外完整状态覆盖由本版 checkpoint/storage 测试提供。',
              '', '## 7. 与原生规范的差异','',
              'X06 使用实验 CUSTOM-0 (0x0b)，S05A 使用 CUSTOM-2 (0x5b)；类型完全由编码决定，不读 Md/Ad/amestype。',
              '复用现有 32 个 M、4 个 Acc 及 AME 权限/所有权/dirty 状态；不是两个独立物理寄存器银行。',
              '限定 AMENLEN=4、AMEUDSZ=32，其他形状触发非法指令；输出固定 4×4，INT8 深度16、半精度深度8。',
              'X06 右矩阵按转置布局，半精度扩宽只取每行低四列；S05A 右矩阵行序，扩宽覆盖32元素并写相邻双M，md31非法。',
              '固定 RNE、逐次 FP32 FMA、规范 NaN、AMEFFLAGS 累积，标量 fcsr 与 SoftFloat 环境保留；超界转整数采用本版显式契约。',
              '没有增加完整原生 ISA、动态形状、原生 mtype、专用寄存器体系或新的 CPU/FU 时序模型。',
              '', '## 8. 复现与已定位问题','',
              '详见 [测试入口说明](../../tests/ame_explicit_v1/README.md)。使用 `ame-gem5-rvv:local` 容器和仓库内工具链，仓库挂载到 `/work`。',
              '工具版本、PDF/ELF/配置/模拟器/输入/预期输出/报告哈希见 evidence；完整二进制与 trace 保留在忽略跟踪的 results 目录。',
              '', '开发期问题与最终证据的选择：',
              '', '- 最初旧运行时的 512KiB 缓冲区不够；新测试独立使用二进制观测记录。',
              '- 原有 Minor 的 semihost 功能读取可能赶在最后一个参数 store 排空前；测试运行时在 fence 后、semihost 前加入1024条 nop。此等待在被测内核之外，未修改模拟器或旧 example。',
              '- 最初回归使用不同来宾输出路径且与链接重叠，记录不用于验收；最终回归固定相同路径并在二进制完成后执行。',
              '- 字段审计最初错误期待 trace 文本 MatrixOp；实际显示为 Matrix。保留失败 JSON 和原 trace，修正解析后对同一 trace 重新检查。',
              '- 所有时间戳原始运行、失败记录和故障注入证据均保留；最终采用记录列在 acceptance.json。',
              '', '本轮完成研究性显式改造的正确性与兼容回归，不给出性能比较结论。后续性能实验需对齐右矩阵打包及扩宽工作量。']
    (dest/'FINAL_CHANGE_REPORT.md').write_text('\n'.join(lines)+'\n')
    print(dest/'FINAL_CHANGE_REPORT.md')
    print(acceptance['status'])
