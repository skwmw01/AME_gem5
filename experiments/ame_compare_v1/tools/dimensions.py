"""Explain the planned D1-D5 dimensions and map each measured artifact to them."""
import json
from build import OUT,GROUPS
from figure_notes import blocks

def section(flat):
 notes=blocks(flat)
 def figure(ident,title,filename):
  return [f'![{title}](figures/{filename}.png)']+notes[ident]
 lines=['## 3. 按D1—D5组织实验结果','',
  'D1—D5是评价维度，W1—W5是工作负载；二者不一一对应。同一个W实验可以同时产生指令数、代码大小和周期数据，但这些指标回答不同问题。正确性PASS和测量校准是各维度结果的使用门槛，不是性能优势。','',
  '| 评价维度 | 要回答的问题 | 对应实验与指标 | 本报告中的结果及原始证据 |',
  '|---|---|---|---|',
  '| D1 编码空间 | 表达相同类型任务占用多少译码规则和机器字？ | 十种任务静态核算；4→7→10类型增长 | §3.1；static-audit.json、encoding-growth.json |',
  '| D2 动态指令开销 | 完成同一任务执行多少条指令，额外指令花在哪里？ | W1总退休指令；W2分类计数；W3分派/调用/循环占比；W5等量计算条数 | §3.2、§4.1；records.csv中的retired_insts、insts_*，paired.csv中的instruction_reduction |',
  '| D3 静态代码大小 | 提供同样可调用功能需要多少机器代码和常量？ | W3固定/运行时API及支持类型增长；主镜像section清单 | §3.3、§4.2代码表、§4.4；api-summary.json、image-size.json |',
  '| D4 执行性能 | 完成同一任务需要多少目标周期，有效吞吐多少？ | W1配置复用；W2类型切换；W3匹配API计时；W4完整算子；W5等量扩宽 | §3.4、§4聚合表、§4.2计时表、§4.3；records.csv、paired.csv、api-paired.json、boundary-fractions.json |',
  '| D5 软件支持与扩展性 | 来宾需要哪些配置、分派和布局支持？扩展类型需要哪些工程改动？ | W3可调用接口与共享主体、W4/W5布局及正确性维护；W6本轮未做 | §3.5、§4.5工程记录；来宾/API源代码及门槛记录。只有软件支持部分证据，未完成新增类型工程实验 |','',
  '| 工作负载 | 本轮实际改变的因素 | 产生结果的维度 |',
  '|---|---|---|',
  '| W1 固定类型与配置复用 | R=1/4/16/64/256；resident热、已打包冷/热；另有六任务同准备控制 | D2指令数、D4周期 |',
  '| W2 类型切换 | 总计算Q=1024不变，改变批长G和寄存器复用策略 | D2分类指令、D4周期 |',
  '| W3 固定/运行时类型API | 类型族、批长、类型序列、固定/运行时入口、支持类型数 | D2分派开销、D3代码大小、D4周期、D5软件接口 |',
  '| W4 GEMM与组合算子 | 类型、形状、C0、尾块、已打包/端到端 | D4主结果；D2计数和字节量用于解释，D5布局支持 |',
  '| W5 FP16扩宽 | 相同有效元素N=32/256/4096；已打包/端到端 | D2计算条数与流量、D4周期、D5布局适配 |',
  '| W6 BF16扩宽工程扩展 | 需要修改模拟器，本轮未执行 | D5扩展性证据缺项，不记为PASS |','',
  '以下各图的P/X06/S05A均是三组实现；图中多个子图是条件或指标切片，不代表新增了不同的评价维度。','',
  '### 3.1 D1：编码空间','',
  '该维度来自静态编码核算，不使用运行周期。十种共同逻辑任务的结果如下。','',
  '| 组别 | 计算规则 | mask包络 | 静态合法字段 |','|---|---:|---:|---:|']
 for r in json.loads((OUT/'static-audit.json').read_text())['encoding']:
  lines.append(f"| {r['group']} | {r['rules']} | {r['mask_envelope']:,} | {r['legal_fields']:,} |")
 lines += ['', 'P用4条计算规则覆盖本轮十种类型任务，X06/S05A各用10条。P的运行合法性还依赖描述符；S05A全量扩宽排除rd=31。该结果只描述本研究子集，不是完整原生ISA的空间占用，也不是程序代码大小。',
  '支持类型按固定顺序从4→7→10增长的规则数和机器字数见 [encoding-growth.json](evidence/encoding-growth.json)。','',
  '### 3.2 D2：动态指令开销','',
  '退休指令是处理器最终提交的架构指令。此处纵轴统计整个ROI内的计算、配置、搬运、访存、分派/循环和测量边界指令；它既不是计算指令条数，也不是源代码行数。其用途是判断“是否为了同一任务多执行了指令”，再用分类计数定位额外成本。指令数不等于周期，运行快慢在D4单独报告。','',
  *figure('D2-1','W1总退休指令数','w1_retired_instructions'),
  '| 条件 | 初始状态与测量范围 | 对照目的 |','|---|---|---|',
  '| resident/hot | 类型和输入已在寄存器中；计入计算、循环和边界 | 观察移出初始配置/装载后，计算与控制序列的指令量 |',
  '| packed_call/cold | 输入已打包在内存；计入配置、装载、计算、存储和调用 | 观察一次完整冷调用的指令成本 |',
  '| packed_call/hot | 类型已匹配，输入已打包在内存；仍计入装载、计算、存储和调用 | 观察复用类型后还需要多少指令 |','',
  '三种条件用于区分配置复用、寄存器驻留和完整调用的影响；冷/热指软件类型状态，与cache无关。','',

  '| A1、R=1 | P退休指令 | X06退休指令 | S05A退休指令 |','|---|---:|---:|---:|']
 for roi,state in [('resident','hot'),('packed_call','cold'),('packed_call','hot')]:
  rows=[next(r for r in flat if r['label']=='W1' and r['group']==g and r['task']=='A1' and r['R']==1 and r['roi']==roi and r['state']==state) for g in GROUPS]
  lines.append('| '+roi+'/'+state+' | '+' | '.join(str(r['retired_insts']) for r in rows)+' |')
 lines += ['', *figure('D2-2','W2分类指令数','w2_instruction_categories'),
  *figure('D2-3','W3分派调用循环占比','w3_dispatch_fraction'),
  'W5另提供等量扩宽的计算条数：每32个FP16元素P/S05A各1条、X06为2条，见§4.3。分类总和与同一ROI的总退休计数闭合；类型隐式读取不另计一条架构指令。逐例计数、每元素/每MAC计数及指令减少率见 [records.csv](evidence/records.csv) 和 [paired.csv](evidence/paired.csv)。','',
  '### 3.3 D3：静态代码大小','',
  *figure('D3-1','W3可调用代码大小','w3_callable_code_size'),
  '§4.2给出完整API与section GC后的单入口text/rodata表；§4.4给出主实验镜像section清单，启动/测量/运行时与内核分列。三组均禁用压缩、relaxation、LTO/ICF。实际大小来自 [api-summary.json](evidence/api-summary.json) 和 [image-size.json](evidence/image-size.json)。','',

  '### 3.4 D4：执行性能','',
  '本维度使用目标周期、每有效元素/MAC周期和配对加速比P周期/显式组周期。宿主运行时长和退休指令数都不能代替这些指标。§4按同一ROI/状态分别聚合，不生成跨任务总冠军分数。','',
  *figure('D4-1','W1配置复用周期','w1_configuration_amortization'),
  *figure('D4-2','W2类型切换周期','w2_type_switching'),
  '**W3匹配API计时表（§4.2）**：相同输入、各128次独立冷调用，对比固定/运行时入口，报告额外周期/调用；同表额外指令/调用归D2。混合序列W3-runtime的配对加速比见§4聚合表。MAC三类型保留各自逻辑累加器，不能将整数/浮点位模式直接视为同一个数值。','',
  *figure('D4-3','W4 GEMM成本','w4_gemm_cost'),
  *figure('D4-4','W5等量扩宽成本','w5_equal_work_widening'),
  '逐例cycles、cycles_per_element、cycles_per_MAC、有效吞吐见records.csv；配对加速比见paired.csv；匹配API差值见 [api-paired.json](evidence/api-paired.json)。短区间边界占比见 [boundary-fractions.json](evidence/boundary-fractions.json)，W1长批次最大值三组均低于1%。','',
  '### 3.5 D5：软件支持与扩展性（本轮部分覆盖）','',
  '本轮软件支持证据包括W3固定/运行时API、配置表与共享主体、各组独立发码接口，以及W4/W5布局和正确性维护。详见§4.5工程记录表；API源代码与来宾pack函数是实际可审查产物。D3代码大小和D4运行成本帮助量化这些接口的成本，但不能单独证明完整工具生态更成熟。',
  '目前工具链通过.word发出研究指令，未实现完整LLVM/GCC后端。W6新增BF16→FP32转换需要修改模拟器，按本轮要求未执行；因此新增类型的译码/执行净改动、开发工时、修复次数均无本轮实测结果。D5的新增类型扩展性部分保持未验证，不从既有API推导普遍工程复杂度排名。','']
 return lines
