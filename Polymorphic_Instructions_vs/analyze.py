#!/usr/bin/env python3
"""Fail-closed ELF/commit-trace/instret/correctness audit and report generator."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import struct

REPEATS = (1, 2, 4, 8, 16, 64, 256)
KINDS = ('FP32', 'INT32', 'INT8→INT32')
SEQUENCES = ('fp32', 'int32', 'int8', 'mixed-1', 'mixed-4', 'mixed-16', 'mixed-32')
CATEGORIES = ('type_prepare', 'other_prepare', 'type_init', 'dispatch',
              'compute', 'matrix_move', 'control_address', 'call_return', 'unclassified')
TITLES = ('类型准备', '其他准备', '类型设置/初始化', '分派', '计算',
          '矩阵搬运', '控制/寻址', '调用/返回', '未分类')
TRACE = re.compile(r'^\s*(\d+): system\.cpu: (0x[\da-f]+)(?:\.\s*(\d+))?\s+:')
FLAGS = re.compile(r'flags=\(([^)]*)\)')
ADDRESS = re.compile(r' A=(0x[\da-f]+)')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_elf(disassembly, symbol_file):
    code, symbols, categories = {}, {}, {}
    for line in Path(disassembly).read_text().splitlines():
        m = re.match(r'^([\da-f]+):\s+([\da-f]{8})\s+(.+)$', line)
        if m:
            pc, raw, text = m.groups()
            code[int(pc, 16)] = {'word': raw, 'text': text.strip(),
                                'mnemonic': text.split()[0]}
    for line in Path(symbol_file).read_text().splitlines():
        fields = line.split()
        if len(fields) >= 5 and '.text' in fields:
            symbols[fields[-1]] = (int(fields[0], 16), int(fields[-2], 16))
    for name, (pc, size) in symbols.items():
        if not name.startswith('pi_'):
            continue
        category = name[3:].rsplit('_', 1)[0]
        require(category in (*CATEGORIES, 'auxiliary'), f'unknown category: {name}')
        require(size > 0 and size % 4 == 0, f'invalid instruction width: {name}')
        for address in range(pc, pc + size, 4):
            require(address in code, f'undecoded PC: {address:x}')
            require(address not in categories, f'overlapping PC labels: {address:x}')
            categories[address] = category
    for scheme in ('specialized', 'shared'):
        pc, size = symbols[f'run_{scheme}']
        require(all(x in categories for x in range(pc, pc + size, 4)),
                f'unclassified static instruction in {scheme}')
        # Both dispatches must have three single instructions in the same order.
        require([code[pc + i * 4]['mnemonic'] for i in range(3)] == ['beqz', 'li', 'beq'],
                f'dispatch expanded/changed in {scheme}')
        begin = symbols[f'measure_{scheme}_begin'][0]
        end = symbols[f'measure_{scheme}_end'][0]
        require(end - begin == 8 and code[begin]['mnemonic'] == 'rdinstret'
                and code[end]['mnemonic'] == 'rdinstret'
                and code[begin + 4]['mnemonic'] == 'jal', 'invalid wrapper')
    bodies = []
    for name in ('gemm_fp32_body', 'gemm_int32_body', 'gemm_int8_body', 'shared_body'):
        pc, size = symbols[name]
        body = [code[x]['word'] for x in range(pc, pc + size, 4)]
        require(sum(code[x]['mnemonic'] == 'mmulacc.2d'
                    for x in range(pc, pc + size, 4)) == 1, f'unrolled loop: {name}')
        bodies.append(body)
    require(all(body == bodies[0] for body in bodies), 'loop machine code differs')
    compute_pcs = [p for p, c in categories.items() if c == 'compute']
    require(len(compute_pcs) == 4, 'expected three specialized loops plus one shared')
    return code, symbols, categories


def reference():
    seed, values = 0x6a09e667, []
    for _ in range(128):
        seed = (seed * 1664525 + 1013904223) & 0xffffffff
        values.append(((seed >> 16) % 7) - 3)
    a, b = values[:64], values[64:]
    c = [sum(a[i * 16 + k] * b[k * 4 + j] for k in range(16))
         for i in range(4) for j in range(4)]
    return {'seed': '0x6a09e667', 'A_row_major': a, 'B_row_major': b, 'C_R1': c}


def read_results(path, mode):
    data = Path(path).read_bytes()
    require(len(data) >= 64, 'missing binary results header')
    magic, nr, count, acquired, owned, nlen, udsz, status = struct.unpack_from('<8Q', data)
    require(magic == 0x5a54545049303601, 'wrong results format')
    require(nr == (1 if mode == 'smoke' else 7), 'wrong repeat matrix')
    require(count == nr * 7 * 96 and len(data) == 64 + count * 88,
            'truncated/extra result records')
    require(acquired & 1 and owned == 1 and nlen == 4 and udsz == 32 and status == 0,
            'AME acquire/geometry/status check failed')
    rows = []
    golden = reference()['C_R1']
    for index in range(count):
        r = REPEATS[index // (7 * 96)]
        seq = (index // 96) % 7
        call = index % 96
        kind = seq if seq < 3 else (call // (1, 4, 16, 32)[seq - 3]) % 3
        before, after, status, *output = struct.unpack_from('<3Q16I', data, 64 + index * 88)
        expected = [(struct.unpack('<I', struct.pack('<f', v * r))[0]
                     if kind == 0 else (v * r) & 0xffffffff) for v in golden]
        require(output == expected, f'element mismatch: {path}, call {index}')
        require(status == 0 and after > before, f'status/counter failure: {index}')
        rows.append({'index': index, 'repeats': r, 'sequence': SEQUENCES[seq],
                     'call': call, 'kind': kind, 'instret_before': before,
                     'instret_after': after, 'status': status,
                     'output_hex': ' '.join(f'{x:08x}' for x in output)})
    return rows


def parse_trace(path, scheme, code, symbols, categories):
    begin, end = (symbols[f'measure_{scheme}_{s}'][0] for s in ('begin', 'end'))
    rows, active = [], None
    with gzip.open(path, 'rt') as trace:
        for line_no, line in enumerate(trace, 1):
            match = TRACE.match(line)
            if not match:
                require('system.cpu:' not in line, f'unparsed CPU record at {line_no}')
                continue
            tick, pc = int(match[1]), int(match[2], 16)
            fm = FLAGS.search(line)
            require(fm is not None, f'missing flags at {line_no}')
            flags = set(fm[1].split('|'))
            require('FAULTING' not in line, f'faulting instruction at {line_no}')
            # ExeTracer is emitted only at commit; microops are counted at their
            # last member, exactly like MinorCPU doInstCommitAccounting.
            is_micro = 'IsMicroop' in flags
            if is_micro and 'IsLastMicroop' not in flags:
                if active is not None:
                    active['microop_records'] += 1
                continue
            if pc == begin:
                require(active is None, 'nested measurement interval')
                active = {'counts': Counter(), 'opcodes': Counter(), 'pc_counts': Counter(),
                          'auxiliary': Counter(), 'raw_architectural': 0,
                          'microop_records': 0, 'begin_tick': tick,
                          'memory': hashlib.sha256(), 'memory_events': 0}
            if pc == end:
                require(active is not None, 'end without measurement begin')
                active['end_tick'] = tick
                active['memory_sha256'] = active.pop('memory').hexdigest()
                rows.append(active)
                active = None
                continue
            if active is None:
                continue
            active['microop_records'] += int(is_micro)
            active['raw_architectural'] += 1
            category = categories.get(pc, 'unclassified')
            require(category != 'unclassified', f'unclassified executed PC {pc:x}')
            active['pc_counts'][f'0x{pc:x}'] += 1
            if category == 'auxiliary':
                active['auxiliary'][f'0x{pc:x}'] += 1
            else:
                active['counts'][category] += 1
                mnemonic = code[pc]['mnemonic']
                active['opcodes'][mnemonic] += 1
                if mnemonic in ('mls.rm', 'mss.rm'):
                    address = ADDRESS.search(line)
                    require(address is not None, f'missing matrix address at {line_no}')
                    addr = int(address[1], 16)
                    require(addr % 64 == 0, 'matrix address not aligned')
                    active['memory'].update(f'{mnemonic}:{addr:x}\n'.encode())
                    active['memory_events'] += 1
    require(active is None, 'unterminated measurement interval')
    require(rows, 'no measurement intervals')
    return rows


def verify_call(row, interval):
    counts = interval['counts']
    require(sum(counts.values()) + sum(interval['auxiliary'].values()) ==
            interval['raw_architectural'] == row['instret_after'] - row['instret_before'],
            f'commit reconciliation failed: call {row["index"]}')
    # Auxiliary PCs are individually classified from the ELF, not a fixed
    # numeric subtraction. Save their exact disassembly in pc_map.json.
    blocks = 1 if row['kind'] == 2 else 4
    r = row['repeats']
    for opcode, expected in {'mmulacc.2d': r * blocks, 'mls.rm': 2 * r * blocks,
                             'mss.rm': 1, 'mmov.m.a': 1, 'msettyp': 3,
                             'asettyp': 1}.items():
        require(interval['opcodes'][opcode] == expected, f'wrong {opcode} count: {row}')
    require(counts['call_return'] == 2, 'call/return count differs')
    row.update({c: counts[c] for c in CATEGORIES})
    row.update(total=sum(counts.values()), raw_architectural=interval['raw_architectural'],
               auxiliary=sum(interval['auxiliary'].values()), effective_macs=256 * r,
               matrix_input_bytes=128 * r * blocks, matrix_output_bytes=64,
               accumulator_move_bytes=64, memory_sha256=interval['memory_sha256'])
    row['instructions_per_mac'] = row['total'] / row['effective_macs']
    row['prepare_per_compute'] = (counts['type_prepare'] + counts['other_prepare']) / counts['compute']
    row['matrix_memory_bytes'] = row['matrix_input_bytes'] + row['matrix_output_bytes']
    expected = dict(type_prepare=4 if row['kind'] == 2 else 3,
                    other_prepare=r + 4, type_init=4,
                    dispatch=(1 if row['kind'] == 0 else 3) +
                    int(row['scheme'] == 'shared' and row['kind'] != 1),
                    compute=blocks * r, matrix_move=2 * blocks * r + 2,
                    control_address=4 * blocks * r + 4 * r,
                    call_return=2, unclassified=0)
    require(all(row[k] == v for k, v in expected.items()),
            f'trace disagrees with assembly path formula: call {row["index"]}')


def write_csv(path, rows):
    with Path(path).open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path)
    p.add_argument('--no-plots', action='store_true')
    args = p.parse_args()
    out = args.directory.resolve()
    # A failed re-audit must not leave an old success report in place.
    for name in ('REPORT.md', 'validation.json'):
        (out / name).unlink(missing_ok=True)
    env = json.loads((out / 'environment.json').read_text())
    require(sha256(out / 'experiment.elf') == env['elf_sha256'], 'ELF hash changed')
    for name, digest in env.get('static_artifacts_sha256', {}).items():
        require(sha256(out / name) == digest, f'static artifact changed: {name}')
    for name, digest in env['source_sha256'].items():
        require(sha256(out / 'sources' / name) == digest, f'source snapshot changed: {name}')
    require(len(env['runs']) == 4 and all(r['returncode'] == 0 for r in env['runs']),
            'both independent trials of both schemes are required')
    for run in env['runs']:
        folder = out / f'{run["scheme"]}-{run["trial"]}'
        for name, digest in run['artifacts_sha256'].items():
            require(sha256(folder / name) == digest, f'changed run artifact: {folder / name}')
    code, symbols, categories = read_elf(out / 'experiment.dis', out / 'experiment.symbols')
    (out / 'pc_map.json').write_text(json.dumps({f'0x{pc:x}': dict(code[pc], category=c)
                                               for pc, c in categories.items()}, indent=2) + '\n')
    (out / 'reference.json').write_text(json.dumps(reference(), indent=2) + '\n')
    all_rows, run_rows = [], {}
    for scheme in ('specialized', 'shared'):
        for trial in (1, 2):
            folder = out / f'{scheme}-{trial}'
            rows = read_results(folder / 'results.bin', env['mode'])
            intervals = parse_trace(folder / 'trace.gz', scheme, code, symbols, categories)
            require(len(rows) == len(intervals), 'trace/output call count mismatch')
            for row, interval in zip(rows, intervals):
                row.update(scheme=scheme, trial=trial)
                verify_call(row, interval)
            with (folder / 'intervals.jsonl').open('w') as f:
                for row, interval in zip(rows, intervals):
                    f.write(json.dumps(dict(row, trace=interval)) + '\n')
            write_csv(folder / 'calls.csv', rows)
            all_rows.extend(rows)
            run_rows[scheme, trial] = rows
            print(f'PASS {scheme}-{trial}: {len(rows)} calls', flush=True)
    equality_fields = (*CATEGORIES, 'total', 'output_hex', 'memory_sha256')
    for scheme in ('specialized', 'shared'):
        for a, b in zip(run_rows[scheme, 1], run_rows[scheme, 2]):
            require(all(a[k] == b[k] for k in equality_fields), 'trials not reproducible')
    pairs = []
    for a, b in zip(run_rows['specialized', 1], run_rows['shared', 1]):
        require(all(a[k] == b[k] for k in equality_fields if k not in ('dispatch', 'total')),
                'paired schemes differ beyond dispatch')
        pairs.append({k: a[k] for k in ('index', 'repeats', 'sequence', 'call', 'kind')}
                     | {'specialized': a['total'], 'shared': b['total'],
                        'delta': b['total'] - a['total']})
    write_csv(out / 'calls.csv', all_rows)
    write_csv(out / 'pairs.csv', pairs)
    configurations = defaultdict(list)
    for row in all_rows:
        configurations[row['scheme'], row['trial'], row['repeats'], row['sequence']].append(row)
    configuration_rows = []
    for (scheme, trial, r, sequence), rows in sorted(configurations.items()):
        require(len(rows) == 96, 'configuration must contain 96 calls')
        configuration_rows.append(dict(scheme=scheme, trial=trial, repeats=r,
            sequence=sequence, calls=len(rows), **{
                c: sum(row[c] for row in rows) for c in
                (*CATEGORIES, 'total', 'effective_macs', 'matrix_memory_bytes')}))
    write_csv(out / 'configurations.csv', configuration_rows)
    grouped = defaultdict(list)
    for row in all_rows:
        grouped[row['scheme'], row['repeats'], row['sequence'], row['kind']].append(row)
    summaries = []
    metrics = (*CATEGORIES, 'total', 'instructions_per_mac', 'prepare_per_compute',
               'matrix_memory_bytes', 'accumulator_move_bytes')
    for (scheme, r, sequence, kind), rows in sorted(grouped.items()):
        require(all(all(row[k] == rows[0][k] for k in metrics) for row in rows),
                'within-configuration count differs')
        summaries.append(dict(scheme=scheme, repeats=r, sequence=sequence, kind=kind,
                              calls_both_trials=len(rows), **{k: rows[0][k] for k in metrics}))
    write_csv(out / 'summary.csv', summaries)
    (out / 'summary.json').write_text(json.dumps(summaries, indent=2) + '\n')
    validation = {'passed': True, 'mode': env['mode'], 'calls': len(all_rows),
                  'configurations_including_trials': len(all_rows) // 96,
                  'elements_checked': 16 * len(all_rows), 'unclassified': 0,
                  'reproducible': True, 'paired_memory_addresses_identical': True,
                  'bodies_byte_identical': True, 'static_bytes': {
                      s: symbols[f'run_{s}'][1] for s in ('specialized', 'shared')},
                  'microop_records_inside_intervals': sum(
                      json.loads(line)['trace']['microop_records']
                      for folder in out.glob('*-[12]')
                      for line in (folder / 'intervals.jsonl').read_text().splitlines())}
    (out / 'analysis_environment.json').write_text(json.dumps({
        'analyzer_sha256': sha256(Path(__file__)),
        'analyzer_source': Path(__file__).read_text(),
        'python_version': __import__('sys').version,
        'input_manifest_sha256': sha256(out / 'environment.json'),
    }, indent=2) + '\n')
    if not args.no_plots:
        plot(out, run_rows)
    report(out, env, validation, run_rows, not args.no_plots)
    (out / 'validation.json').write_text(json.dumps(validation, indent=2) + '\n')
    print(f'PASS all checks: {out / "REPORT.md"}')


def unique_rows(rows):
    result = {}
    for row in rows:
        key = row['kind'], row['repeats']
        if key in result:
            require(all(result[key][c] == row[c] for c in (*CATEGORIES, 'total')),
                    'task ordering changed per-kind counts')
        result[key] = row
    return result


def plot(out, runs):
    os.environ.setdefault('MPLCONFIGDIR', str(out / 'mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    unique = {s: unique_rows(runs[s, 1]) for s in ('specialized', 'shared')}
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), constrained_layout=True)
    for kind, title in enumerate(('FP32', 'INT32', 'INT8 to INT32')):
        for scheme, marker in (('specialized', 'o'), ('shared', 'x')):
            rows = [row for (k, r), row in sorted(unique[scheme].items()) if k == kind]
            x = [row['repeats'] for row in rows]
            axes[0, kind].plot(x, [row['instructions_per_mac'] for row in rows],
                               marker=marker, label=scheme)
            axes[1, kind].plot(x, [row['prepare_per_compute'] for row in rows],
                               marker=marker, label=scheme)
        for ax in axes[:, kind]:
            ax.set_xscale('log', base=2)
            ax.set_xlabel('R')
            ax.grid(alpha=0.25)
        axes[0, kind].set_title(title)
        axes[0, kind].legend()
    axes[0, 0].set_ylabel('Dynamic instructions / effective MAC')
    axes[1, 0].set_ylabel('(Type + other preparation) / mmulacc')
    fig.savefig(out / 'overhead.png', dpi=180)
    fig.savefig(out / 'overhead.svg')
    plt.close(fig)


def report(out, env, validation, runs, has_plots):
    spec, shared = (unique_rows(runs[s, 1]) for s in ('specialized', 'shared'))
    lines = ['# Ztt v0.6 专用函数与共享函数：实测报告', '',
             f'模式：`{env["mode"]}`。通过 {validation["calls"]:,} 次调用、'
             f'{validation["elements_checked"]:,} 个元素检查；'
             f'{validation["configurations_including_trials"]} 个配置（含两次重复）。', '',
             '两方案都使用多态 Ztt 指令；结论仅涉及预打包 GEMM 的软件组织方式。'
             '不计预打包、AME 获取/释放、输出验证与日志，不以周期或吞吐作结论。', '',
             '## 成对动态指令结果', '',
             'ΔN = N_shared − N_specialized；正值表示共享版执行更多指令。', '',
             '| 类型 | R | 专用 | 共享 | ΔN | 专用指令/MAC | 共享指令/MAC | 内存搬运字节 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for (kind, r), a in sorted(spec.items()):
        b = shared[kind, r]
        lines.append(f'| {KINDS[kind]} | {r} | {a["total"]} | {b["total"]} | '
                     f'{b["total"]-a["total"]:+d} | {a["instructions_per_mac"]:.6f} | '
                     f'{b["instructions_per_mac"]:.6f} | {a["matrix_memory_bytes"]} |')
    lines += ['', '## 分类（每次调用；专用/共享）', '']
    for kind, title in enumerate(KINDS):
        lines += ['', f'### {title}', '', '| R | ' + ' | '.join(TITLES) + ' |',
                  '|---:|' + '---:|' * len(CATEGORIES)]
        for (k, r), a in sorted(spec.items()):
            if k == kind:
                b = shared[k, r]
                lines.append(f'| {r} | ' + ' | '.join(f'{a[c]}/{b[c]}' for c in CATEGORIES) + ' |')
    lines += ['', '## 汇编路径解释', '',
              'FP32 在首个条件分支进入类型准备；INT32/INT8 经过两次比较和一个判断常量构造。'
              '专用版直接尾分派到独立函数。共享版的 FP32 和 INT8 准备路径各增加一次跳转，'
              'INT32 准备路径直接落入公共循环。因此 FP32、INT8 的 ΔN=+1，INT32 的 ΔN=0，'
              '均不随 R 改变。这里没有共享版动态指令优势。INT32 的零差来自本实现的代码布局；'
              '改变落入公共循环的类型会转移这一次跳转开销，不能推论为该类型的 ISA 特性。', '',
              '实测专用版总数为 FP32: 33R+16、INT32: 33R+18、INT8: 12R+19。'
              '分类公式：类型准备 3/3/4，其他准备 R+4，类型设置/初始化 4，'
              '专用分派 1/3/3，计算 BR，矩阵搬运 2BR+2，控制/寻址 4BR+4R，'
              '调用/返回 2；B=4/4/1。公式由汇编解释，并与逐条轨迹独立核验。', '',
              '准备/计算指标严格定义为 (类型准备+其他准备)/mmulacc.2d，详细值见 summary.csv。'
              '每轮块计数初始化仍随 R 增长，故这一比值不会趋于零。'
              '每次内存传输为 128BR+64 字节，另有 acc0→m8 的 64 字节寄存器搬运。'
              '每次任务为 256R 个有效 MAC。不同精度只分别成对比较。', '',
              '三种单类型序列各 96 次；四种混合序列各类型 32 次，同类型分组为 1、4、16、32。'
              '同类型同 R 的分类计数在各序列和两次重复中完全一致。每次都重新设类型，'
              '所以分组仅改变顺序，没有跨调用类型缓存收益。', '',
              '每组 96 次混合调用，专用合计 2496R+1696 条，共享多 64 条；'
              '四种分组大小的结果相同。每个独立配置的总计见 configurations.csv。', '',
              '## 验证与统计边界', '',
              '逐次比较全部 16 个输出的原始位模式与宿主 Python 从逻辑行主序输入算出的参考值；'
              'FP32 输入及所有中间和均为可精确表示的小整数。AME 获取、几何参数及每次状态均通过。', '',
              '轨迹来自 MinorCPU 的提交路径，ExecMicro+ExecFlags 标识微操作，'
              '仅普通指令和最后一个微操作计为架构指令。实际区间微操作记录数：'
              f'{validation["microop_records_inside_intervals"]}。ExecCPSeq 未用作指令计数：'
              '当前 MinorCPU 在 trace dump 之后才执行记账，且 CPSeq 定义为 numOps。', '',
              '原始区间是起始 rdinstret 到结束 rdinstret 的半开区间，包含前者、排除后者。'
              '有效区间包含公共 jal、分派、准备、类型设置、循环、写回和内核 ret。'
              '逐项从 PC 标签识别辅助指令；本实现只有起始 rdinstret。'
              '每次满足：分类之和 = 原始架构指令数 − 已识别辅助数 = 两次 instret 差 − 已识别辅助数。'
              '未分类数为零。pc_map.json 保存辅助 PC 与反汇编，intervals.jsonl 保存其动态次数。', '',
              '反汇编确认专用三份循环、共享一份循环；四份循环机器码逐字相同。'
              '两方案采用同一 ELF、同一输入与输出地址及 64 字节对齐；逐次内存地址序列摘要一致。'
              '静态入口与函数体合计：专用 '
              f'{validation["static_bytes"]["specialized"]} 字节，共享 '
              f'{validation["static_bytes"]["shared"]} 字节；不含测量包装，仅作辅助信息。', '',
              '## 可复现材料', '',
              f'- 源码提交：`{env["git_commit"]}`，分支 `{env["git_branch"]}`。',
              f'- ELF SHA256：`{env["elf_sha256"]}`。',
              f'- gem5 SHA256：`{env["gem5_sha256"]}`。',
              '- environment.json：构建命令、工具链版本、源文件与运行产物哈希、实际运行命令。',
              '- analysis_environment.json：实际分析器源码、哈希与 Python 版本。',
              '- sources/、source.diff：此次源码快照及工作树差异。',
              '- experiment.dis、experiment.symbols、pc_map.json：静态分类依据。',
              '- specialized-{1,2}/、shared-{1,2}/：trace.gz、results.bin、stats.txt、gem5.log、calls.csv、intervals.jsonl。',
              '- calls.csv、pairs.csv、configurations.csv、summary.csv/json：逐调用、成对差值、配置总计与分类汇总。',
              '- reference.json、validation.json：宿主参考输入/结果和验收状态。', '']
    if has_plots:
        lines += ['![按类型的开销曲线](overhead.png)', '', '可缩放图： [overhead.svg](overhead.svg)。', '']
    if env['mode'] == 'smoke':
        lines += ['**此为 R=1 的短测报告，不能代替完整实验。**', '']
    (out / 'REPORT.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    main()
