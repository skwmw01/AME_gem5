"""Concrete tables derived only from selected measured records."""
import collections,json,math,re
from build import OUT,GROUPS
from run import save

def tables(flat,batches,aggregate,fractions,api_pairs):
 lines=['## 4. 实测数值与分析','']
 cold=[r for r in aggregate if r['label']=='W1' and r['conditions'].startswith("(1, 0,")]
 if cold:
  r=cold[0];lines += [f"W1九种任务、五个R的冷packed_call共{r['pairs']}个配对，X06/S05A相对P的原始单调用几何平均加速比分别为{r['X06_speedup_gmean']:.4f}× / {r['S05A_speedup_gmean']:.4f}×。这组包含可摊销的配置/调用成本，不能外推为每条计算指令的固定加速。",'']
 batchpairs=[]
 for (g,ident),(_,r) in batches.items():
  if g!='P' or r['case']['roi']!=1 or r['case']['state']!=0:continue
  x=batches.get(('X06',ident));s=batches.get(('S05A',ident))
  if x and s:batchpairs.append((r['cycles']/x[1]['cycles'],r['cycles']/s[1]['cycles']))
 if batchpairs:
  mean=lambda i:math.exp(sum(math.log(r[i]) for r in batchpairs)/len(batchpairs))
  lines += [f"同样45个冷调用配对在区间内重复完整调用后，X06/S05A几何平均加速比为{mean(0):.4f}× / {mean(1):.4f}×；每次冷调用的必要配置、装载和存储仍然执行。",'']
 gemm=[r for r in aggregate if r['label']=='W4-GEMM']
 if gemm:
  lines += ['完整GEMM的结果与冷微基准不同。以下按ROI、C0分别给出聚合值；128³的逐类型每MAC成本也单列。无cache下的取指、数据打包和辅助代码影响不能归结为单一类型机制。','']
 lines += [
  '下列加速比均为 `P周期 / 显式组周期`：大于1表示显式组较快，小于1表示P较快。每行仅聚合所列同一口径；没有跨工作负载总分。',
  '条件编码：ROI 0=resident、1=packed_call、2=end_to_end；状态0=冷、1=热；W2第二项0=复用寄存器、1=专属寄存器；W3条件为(批长G, 类型序列0成组/1交替/2乱序, 集合)；GEMM条件第二项为C0是否非零。','',
  '| 集合 | 条件（ROI/状态/其余参数） | 配对数 | X06几何平均加速比 | S05A几何平均加速比 |',
  '|---|---|---:|---:|---:|']
 for r in aggregate:lines.append(f"| {r['label']} | {r['conditions']} | {r['pairs']} | {r['X06_speedup_gmean']:.4f} | {r['S05A_speedup_gmean']:.4f} |")
 lines += ['', 'W1短调用的测量边界占比较大，解释配置摊销时同时查看批量结果；上表W1为保留的原始单调用结果。', '',
  '| 组别 | W1批量记录数 | 批量ROI中最大空区间占比 |','|---|---:|---:|']
 for g in GROUPS:
  rows=[r for r in fractions if r['group']==g]
  if rows:lines.append(f"| {g} | {len(rows)} | {max(r['boundary_fraction'] for r in rows):.4%} |")
 lines += ['', '### 4.1 动态分类示例','',
  'W2 I32/FP32 add、复用寄存器：G=1与256均完成1024次计算，区别是批次切换频率。各列是同一ROI真实退休指令；类别互斥。','',
  '| 组别 | G | compute | type_setup | init_move | memory | layout | dispatch_loop | other | 总指令 | 周期 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
 for g in GROUPS:
  for G in (1,256):
   rows=[r for r in flat if r['group']==g and r['label']=='W2' and r['task']=='family0' and r['register_policy']=='reuse' and r['G']==G]
   if rows:
    r=rows[0];lines.append('| '+g+' | '+str(G)+' | '+' | '.join(str(r['insts_'+c]) for c in ('compute','type_setup','init_move','memory','layout','dispatch_loop','other'))+f" | {r['retired_insts']} | {r['cycles']} |")
 lines += ['', '类型配置、分派/循环和普通访存分别列出，避免把总周期差全部解释为类型解析延迟。完整逐例每元素/每MAC工作量及字节计数见CSV。', '',
  '### 4.2 可调用API的实际代码与分派成本','',
  '下表单位为字节。完整集合计入所有固定入口、运行时入口及共享函数一次；单入口列经section GC只保留可达代码。固定入口来自完整类型API对象，保留该编译条件，不冒称全局最短代码。','',
  '| 组别 | 类型族 | 类型数 | 完整text | 完整rodata | runtime可达text+rodata | 每种known可达text+rodata | data/bss |','|---|---|---:|---:|---:|---:|---|---|']
 api=json.loads(sorted(OUT.glob('api/*/summary.json'))[-1].read_text())
 families=('add','max','MAC','convert')
 for r in api['results']:
  if r['types']!=(3 if r['family']==2 else 2):continue
  entries=r['entries'];size=lambda x:x['text_bytes']+x['rodata_bytes']
  known=', '.join(str(size(entries['api_known_'+str(i)])) for i in range(r['types']))
  lines.append(f"| {r['group']} | {families[r['family']]} | {r['types']} | {r['text_bytes']} | {r['rodata_bytes']} | {size(entries['api_runtime'])} | {known} | {r['data_bytes']}/{r['bss_bytes']} |")
 lines += ['', '下表是同一逻辑输入和128次独立冷调用下，运行时入口减固定入口的每调用均值。每行覆盖该类型族所有类型与10个种子；R表示每次调用计算次数。','',
  '| 组别 | 类型族 | R | 配对数 | 额外周期/调用 | 额外指令/调用 |','|---|---|---:|---:|---:|---:|']
 for g in GROUPS:
  for f in range(4):
   for R in (1,16):
    rows=[r for r in api_pairs if r['group']==g and r['family']==f and r['repeat']==R]
    if rows:lines.append(f"| {g} | {families[f]} | {R} | {len(rows)} | {sum(r['extra_cycles_per_call'] for r in rows)/len(rows):.3f} | {sum(r['runtime_insts_per_call']-r['known_insts_per_call'] for r in rows)/len(rows):.3f} |")
 lines += ['', '代码大小与周期回答不同问题：P的可共享主体仍需要描述符常量和调用，显式类型族可通过一次分派进入整批内核。差值同时包含分派、调用和无cache代码组织成本，不能推广成所有编译器的必然开销。', '',
  '### 4.3 完整算子与扩宽的具体结果','',
  '下表GEMM取128³、非零C0，所有10个种子的每有效MAC周期均值；端到端包含来宾打包和整理。','',
  '| 任务 | ROI | P周期/MAC | X06周期/MAC | S05A周期/MAC |','|---|---|---:|---:|---:|']
 for task in ('G1','G2','G3'):
  for roi in ('packed_call','end_to_end'):
   vals=[]
   for g in GROUPS:
    rows=[r for r in flat if r['group']==g and r['label']=='W4-GEMM' and r['task']==task and r['n']==128 and r['c0']==1 and r['roi']==roi]
    vals.append(f"{sum(r['cycles']/r['useful_MACs'] for r in rows)/len(rows):.5f}" if rows else 'NOT_RUN')
   lines.append('| '+task+' | '+roi+' | '+' | '.join(vals)+' |')
 lines += ['', 'W5取N=4096，周期/元素为10种子的均值。访存字节是架构请求量，含重复整寄存器访问，与准备后缓冲区跨度不同。','',
  '| 组别 | ROI | 计算指令 | 峰值M | 矩阵读B | 矩阵写B | 周期/元素 |','|---|---|---:|---:|---:|---:|---:|']
 for g in GROUPS:
  for roi in ('packed_call','end_to_end'):
   rows=[r for r in flat if r['group']==g and r['label']=='W5' and r['n']==4096 and r['roi']==roi]
   if rows:
    r=rows[0];lines.append(f"| {g} | {roi} | {r['insts_compute']} | {r.get('peak_M','see CSV')} | {r['matrix_load_bytes']} | {r['matrix_store_bytes']} | {sum(x['cycles']/4096 for x in rows)/len(rows):.4f} |")
 lines += ['', '### 4.4 编译后的主实验镜像清单','',
  '以下统计实际section字节，公共启动/运行时单列。kernels包含W2—W5各入口，types/moves/layout为共享支持代码；rodata还包含完整配置表。这是整个实验镜像清单，不把全部配置表或不可达函数计作单个算子的最小代码。','',
  '| 组别 | compute | types | moves | layout | W1合计 | kernels | 启动/测量/运行时 | rodata | data | bss | input/output/scratch保留 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
 inventory=[]
 for g in GROUPS:
  s={k:int(v,16) for k,v in re.findall(r'^\s*\d+\s+(\S+)\s+([0-9a-f]+)',(OUT/'build'/g/'sections.txt').read_text(),re.M)}
  inventory.append(dict(group=g,sections=s))
  vals=[s.get('.'+k,0) for k in ('compute','types','moves','layout')]+[sum(v for k,v in s.items() if k.startswith('.w1_')),s.get('.kernels',0),sum(s.get('.'+k,0) for k in ('startup','measure','text'))]+[s.get('.'+k,0) for k in ('rodata','data','bss')]
  lines.append('| '+g+' | '+' | '.join(map(str,vals))+' | '+'/'.join(str(s.get('.'+k,0)) for k in ('input','output','scratch'))+' |')
 save(OUT/'image-size.json',inventory)
 lines += ['', '### 4.5 软件支持与工程记录','',
  '| 层次 | 本轮实际工作 | 可追溯证据 / 未测范围 |','|---|---|---|',
  '| 发码 | P保留现有类型指令；X06/S05A读取各自encoding.csv生成32位计算字 | build.py、每次运行的ops.S和反汇编；未实现LLVM/GCC新后端 |',
  '| 类型管理 | P通过Md/Ad配置并共享合法主体；显式组仅保留搬运/Acc所需配置 | bench.c、API源代码与真实type_setup计数 |',
  '| 布局 | P按4×4块、X06按A/BT行、S05A按A/B行打包；X06扩宽重排两份输入 | 来宾pack函数、逐坐标门槛、全部半精度位模式门槛 |',
  '| 运行时接口 | 相同type_id/指针、批级分派；另作固定/运行时同输入冷调用配对 | API链接大小、1080条计时、540个固定/运行时配对 |',
  '| 正确性维护 | 每组实际数值/flags/trap/饱和检查、跨组三方输出比对及原平台回归 | acceptance.json及原始records；异常语义差异不混入主性能样本 |',
  '| 模拟器扩展 | 本轮src/example/tests/build_opts净改动为零 | 冻结哈希与git差异检查；X06/S05A既有独立执行实现保持原状 |',
  '| W6 BF16扩宽 | 按本轮范围未执行 | 无新增规则/扩展代码/开发工时数据；不虚填复杂度等级或开发时间 |',
  '', '本轮代码包含工具生成的内核与公共模板，未记录可比较的人工主动开发计时，因此不能据此给三种ISA的开发时间排序。']
 return lines
