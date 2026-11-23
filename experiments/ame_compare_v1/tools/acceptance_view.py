"""Render measured quantities and acceptance criteria without empty cells."""
import json
from build import ROOT,OUT,GROUPS
from run import sha

def table(result,flat):
 def read(name):return json.loads((OUT/name).read_text())
 def latest(category):return json.loads(sorted(OUT.glob(category+'/*/summary.json'))[-1].read_text())
 static=read('static-audit.json');layout=read('layout-checks.json');artifact=read('artifact-audit.json')
 gates=latest('gates');boundary=latest('boundary');api=latest('api');perf=latest('api-perf')
 selected=read('selected-records.json');fractions=read('boundary-fractions.json');frozen=read('frozen.json')
 builds={(group,control):sha(OUT/('control-build' if control else 'build')/group/'guest.elf') for group in GROUPS for control in (0,1)}
 paired={}
 for row in flat:paired.setdefault(row['case_id'],[]).append(row)
 calibration=read('environment.json')['trace_format_calibration']
 rows=['表中“实际结果”列从已有记录提取数量或观测值，“验收要求”列说明通过条件。记录数、三组配对数、执行次数和文件数使用不同单位，不相加作为新的用例总数。条件检查直接列条件；没有数据时应写未取得记录，不能以横线代替。','',
       '| 检查 | 状态 | 实际结果 | 验收要求 |','|---|---|---|---|']
 details={
  'cross-group outputs':('三组输出一致性',f"{len({r['case_id'] for r in flat})} 个配对，输出不一致 {sum(len({r['output_sha256'] for r in data})!=1 for data in paired.values())} 个",'1,236个配对均输出一致'),
  'paired logical inputs and useful/padded work agree':('三组输入及有效/填充工作量',f"{len({r['case_id'] for r in flat})} 个配对；不一致 {sum(len({(r['input_hash'],r['useful_elements'],r['useful_MACs'],r['executed_MACs']) for r in data})!=1 for data in paired.values())} 个",'1,236个配对的逻辑输入、有效及填充工作量一致'),
  'encoding and identical control preparation':('编码与同准备控制审计',f"{sum(r['status']=='PASS' for r in static['encoding'])}/{len(static['encoding'])} 组编码审计；{sum(r['status']=='PASS' for r in static['control_preparation'])}/{len(static['control_preparation'])} 个外围函数通过",'3组编码规则通过核算；10个外围函数的机器码和地址在三组间一致'),
  'host layout reversibility':('宿主打包/解包可逆性',f"{sum(r['status']=='PASS' for r in layout['checks'])}/{len(layout['checks'])} 项通过；MAC坐标 {sum(r.get('coordinate_cases',0) for r in layout['checks'])} 个，C3元素 {sum(r.get('elements',0) for r in layout['checks'])} 个",'12项均通过：三组×3种MAC布局及C3；合计384个坐标、96个C3元素'),
  'saved ELF/report/config/trace artifact integrity':('运行产物完整性',f"{sum(r['status']=='PASS' for r in artifact['results'])}/{artifact['directories']} 个目录通过，关联 {artifact['timing_records']} 条计时记录",'81个目录的必需文件齐全，ELF/报告/配置哈希符合各自清单；关联5,220条计时记录'),
  'MAC coordinates, all half patterns, second target':('MAC坐标、半精度全集及第二目标', '；'.join(f"{r['group']}：MAC探针{sum(r['counts'].get(str(op),0) for op in (4,5,6))}、半精度位模式{r['half_patterns']}、第二目标消费{r['second_destination_consumers']}、失败{len(r['failures'])}" for r in gates['results']), '每组512个MAC探针、65,536种半精度位模式、2,048次第二目标消费；数值与标志符合参考'),
  'M/Acc register boundaries':('M/Acc寄存器边界', '；'.join(f"{r['group']}：{sum(x['status']=='PASS' for x in r['checks'])}/{len(r['checks'])} 项通过" for r in boundary['results']), '每组4项均符合对应契约：M30/M31转换、Acc3合法、Acc4非法；X06单目标允许M31'),
  'callable API linked size and correctness':('可调用API代码大小与正确性',f"{len(api['results'])} 组链接大小；{sum(r.get('checks',0) for r in api['results'])} 次输出核对；失败API {sum(r.get('status')=='FAIL' for r in api['results'])}", '27组类型增长链接记录齐全；完整类型API共108次输出核对均通过'),
  'matched fixed/runtime API measurements':('固定/运行时API配对计时', f"{perf['records']} 条记录，汇总状态{perf['status']}", '1,080条计时记录，数值、标志及轨迹检查均通过'),
  'W1 batch boundary fraction below 1 percent':('W1批量测量边界占比', '；'.join(f"{g}最大{max(r['boundary_fraction'] for r in fractions if r['group']==g):.4%}" for g in GROUPS), '405条批量记录中，每条空ROI周期/批量ROI周期均小于1%'),
  'final guest compact/full trace equivalence':('最终ELF两种trace格式等价性', '；'.join(f"{name}：{r['simInsts']}条、{r['system.cpu.numCycles']}周期" for name,r in calibration['results'].items())+f"；输出哈希种类{len({r['report'] for r in calibration['results'].values()})}", '同一最终ELF下两格式的simInsts、simOps、ticks、周期与输出哈希一致'),
  'frozen simulator and integration files unchanged':('冻结模拟器与集成文件哈希',f"{sum((ROOT/n).exists() and sha(ROOT/n)==h for n,h in frozen['files'].items())}/{len(frozen['files'])} 个文件哈希一致",'冻结清单中所有文件SHA256一致，包含同一B11二进制'),
  'no simulator/platform source edits':('模拟器/平台/既有测试源码改动',f"相对冻结提交的改动文件数：{len(next(c for c in result['checks'] if c['name']=='no simulator/platform source edits')['evidence'])}",'src、example、build_opts、tests下相对冻结提交的改动文件数为0'),
 }
 suffixes={
  ' W1-W5 declared population':('W1—W5预声明配置','每组1,236条记录齐全，数值/标志/trap/计数检查均通过'),
  ' retired/category/compute count closure':('退休/分类/计算计数闭合','每组1,236条；分类计数之和=退休数，计算条数符合预期，无未知PC'),
  ' rdinstret boundary calibration':('rdinstret边界校准','每组1,236条，退休数−rdinstret差值均为9条'),
  ' frozen main/control guest ELF identity':('主/控制程序ELF身份','每组1,236条记录的ELF哈希均匹配相应冻结主/控制构建'),
 }
 for c in result['checks']:
  name=c['name'];detail=details.get(name)
  for suffix,(title,requirement) in suffixes.items():
   if name.endswith(suffix):
    group=name.split()[0];data=[r for r in selected if r['group']==group]
    if suffix==' W1-W5 declared population':actual=f"{len(data)} 条记录；非PASS {sum(r['status']!='PASS' for r in data)} 条"
    elif suffix==' rdinstret boundary calibration':actual=f"{len(data)} 条；观测差值集合 {sorted({r['retired_insts']-r['rdinstret_delta'] for r in data})}"
    elif suffix==' frozen main/control guest ELF identity':actual=f"{len(data)} 条；ELF哈希不匹配 {sum(r['elf_sha256']!=builds[group,r['case']['control']] for r in data)} 条"
    else:actual=f"{len(data)} 条；不闭合 {sum(r.get('trace_count_delta')!=0 or bool(r.get('unknown_pcs')) or sum(r['compute_words'].values())!=r['expected_compute_insts'] for r in data)} 条"
    detail=(group+' '+title,actual,requirement)
  if name in ('short-call batched measurements','matched API full population and trace closure','logical input and reference archive integrity'):
   title,unit,requirement={
    'short-call batched measurements':('短调用批量测量','条记录','405条均通过数值及轨迹核验'),
    'matched API full population and trace closure':('匹配API完整集合与计数闭合','条记录','1,080条唯一配置记录，数值及最终trace计数均通过'),
    'logical input and reference archive integrity':('逻辑输入与参考归档','条索引记录','5,193条索引；所指输入文件和参考文件均存在且哈希一致'),
   }[name]
   detail=(title,f"{c['completed']}/{c['expected']} {unit}",requirement)
  if name.startswith('determinism '):
   _,group,_,ident=name.split();paths=[ROOT/p for p in c['evidence']]
   data=[r for p in paths for r in json.loads(p.read_text()) if r['group']==group and r['case']['id']==int(ident)]
   detail=(f'{group} 用例{ident}独立重复',f"{len(data)} 次；(周期、指令数、输出哈希)组合数 {len({(r['cycles'],r['retired_insts'],r['output_sha256']) for r in data})}",'3次全新启动；周期、退休指令数和输出哈希完全一致')
  if name.startswith('platform full '):
   r=json.loads((ROOT/c['evidence']).read_text())
   detail=(f"原平台 {r['suite']} 全量功能回归",f"{r['cases']} 个用例、{r['executions']} 次执行；失败{r['failed']}",'完整suite、无limit截断、random_per_seed=100；失败0')
  if name=='platform frozen old ELF regression':
   r=json.loads((ROOT/c['evidence']).read_text());detail=('原平台冻结ELF回归',f"{len(r['results'])} 条回归记录，汇总状态{r['status']}",'13个冻结ELF×5个配置=65条，均通过原回归判据')
  if detail is None:raise ValueError('Acceptance check has no readable criterion: '+name)
  title,actual,requirement=detail
  rows.append(f'| {title} | {c["status"]} | {actual} | {requirement} |')
 return rows
