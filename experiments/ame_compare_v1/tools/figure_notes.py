"""Numbered captions and data-backed interpretations for all report figures."""
import json,statistics
from build import OUT,GROUPS

def blocks(flat):
 def rows(**filters):return [r for r in flat if all(r[k]==v for k,v in filters.items())]
 def one(group,**filters):return rows(group=group,**filters)[0]
 def triplet(key,**filters):return ' / '.join(str(one(g,**filters)[key]) for g in GROUPS)
 def means(key,denominator=None,**filters):
  return [statistics.mean(r[key]/(r[denominator] if denominator else 1) for r in rows(group=g,**filters)) for g in GROUPS]
 def fmt(values,digits=3):return ' / '.join(f'{v:.{digits}f}' for v in values)
 api=json.loads(sorted(OUT.glob('api/*/summary.json'))[-1].read_text())['results']
 encoding={r['group']:r for r in json.loads((OUT/'static-audit.json').read_text())['encoding']}
 from summaries import encoding_growth
 growth=encoding_growth()
 def enc_values(key):return ' / '.join(f'{encoding[g][key]:,}' for g in GROUPS)
 def growth_values(group,key):return '→'.join(f'{r[key]:,}' for r in growth if r['group']==group)
 def sizes(family):
  return ' / '.join(str(next(r for r in api if r['group']==g and r['family']==family and r['types']==(3 if family==2 else 2))['text_bytes']+next(r for r in api if r['group']==g and r['family']==family and r['types']==(3 if family==2 else 2))['rodata_bytes']) for g in GROUPS)
 a1=dict(label='W1',task='A1')
 resident1=triplet('retired_insts',**a1,roi='resident',state='hot',R=1)
 resident256=triplet('retired_insts',**a1,roi='resident',state='hot',R=256)
 cold1=triplet('retired_insts',**a1,roi='packed_call',state='cold',R=1)
 hot1=triplet('retired_insts',**a1,roi='packed_call',state='hot',R=1)
 w2=dict(label='W2',task='family0',register_policy='reuse')
 w2small=triplet('retired_insts',**w2,G=1);w2large=triplet('retired_insts',**w2,G=256)
 def shares(G,family):return [statistics.mean(r['insts_dispatch_loop']/r['retired_insts']*100 for r in rows(label='W3-runtime',group=g,G=G,task='family'+str(family))) for g in GROUPS]
 def costs(roi,n,task='G1'):return means('cycles','useful_MACs',label='W4-GEMM',task=task,roi=roi,n=n,c0=1)
 def widen(roi,n):return means('cycles','n',label='W5',roi=roi,n=n)
 def caption(ident,title,axes,purpose,analysis,conclusion):
  return ['',f'**图{ident}　{title}**','',f'**坐标与数据：** {axes}','',f'**作图目的：** {purpose}','',f'**观察与分析：** {analysis}','',f'**结论：** {conclusion}','']
 return {
  'D1-1':caption('D1-1','相同十种类型任务的译码规则与机器字空间',
   '三个子图横轴均为P、X06、S05A三组，逻辑类型任务均为10种。左图纵轴是计算译码规则数，单位为条规则；中图纵轴是按match/mask匹配集合并集得到的32位机器字数量；右图纵轴是进一步施加静态寄存器字段限制后的机器字数量。三图纵轴均为从0开始的线性刻度，柱顶标实际数值。数据来自static-audit.json的rules、mask_envelope、legal_fields，是静态核算结果，不是指令执行次数或程序字节数，也不跨随机种子取均值。',
   '在完成相同十种逻辑类型任务的范围内，分别比较规则复用程度和编码分配量，并区分mask匹配空间与静态合法字段空间。',
   f'按P / X06 / S05A顺序，规则数为{enc_values("rules")}，mask包络为{enc_values("mask_envelope")}个机器字，静态字段限制后为{enc_values("legal_fields")}个。P的4条规则比各显式组10条少{(1-encoding["P"]["rules"]/encoding["X06"]["rules"])*100:.0f}%；机器字mask包络少{(1-encoding["P"]["mask_envelope"]/encoding["X06"]["mask_envelope"])*100:.2f}%，两种比例不同，因为二元、MAC、转换规则的可变寄存器字段数量不同。S05A全量扩宽禁止rd=31，排除32种源/目标组合，因此右图比中图少32个；该差异只占S05A包络的0.022%左右，柱高难以肉眼区分，应看数值标签。',
   '在本研究子集及当前编码设计下，多态P通过类型状态复用规则，分配的计算编码空间较少；显式组按类型分别编码，需要更多规则。该结论不包含类型配置/访存/搬运的支持编码，也不表示P的所有机器字在任意描述符状态下均可执行；不能据此推出执行更快、硬件译码面积更小或完整原生ISA的编码空间排名。'),
  'D1-2':caption('D1-2','共同类型任务集合从4种扩展到7种和10种时的编码分配',
   '横轴是共同逻辑类型任务数量4、7、10，每个位置按P、X06、S05A绘制三根分组柱。左图纵轴为计算译码规则数，右图纵轴为按mask匹配的32位机器字数量，均采用从0开始的线性刻度。按固定顺序先加入A1/A2/M1/M2，再加入G1/G2/G3，最后加入C1/C2/C3；数据来自encoding-growth.json，与主表采用同一静态计数口径。右图未扣S05A在10任务时的32个非法字段组合，其区别见图D1-1右图。',
   '观察同一语义子集逐步增加时，计算规则和机器字分配量如何增长，解释规则数量增长与机器字空间增长并不成正比。',
   f'P规则数为{growth_values("P","rules")}，X06/S05A均为{growth_values("X06","rules")}；P的mask包络为{growth_values("P","mask_envelope")}，X06/S05A均为{growth_values("X06","mask_envelope")}。从4到10任务，P增加2条规则和5,120个机器字，各显式组增加6条规则和15,360个机器字。不同类型共享P的同一计算规则，而显式组分别分配类型编码；两者机器字增长都相对平缓，因为先加入的二元规则每条覆盖2¹⁵种寄存器组合，MAC每条2¹²种、转换每条2¹⁰种。',
   '在固定加入顺序和当前十种任务内，P的计算规则与机器字增量均较少；增加类型数量不能简单按规则条数同比估计编码空间。这里是对已有任务子集的静态核算，不是W6新增指令的开发实验，也不足以判断未来是否需要更长指令或是否会耗尽编码空间。'),
  'D2-1':caption('D2-1','W1固定类型加法的退休指令数与配置复用',
   '横轴是一次调用内的计算次数R=1、4、16、64、256，纵轴是该单调用ROI提交的架构指令总数，单位为条；两轴均为对数坐标。左、中、右分别是resident/hot、packed_call/cold、packed_call/hot；每种颜色对应P、X06、S05A中的一组。本图只展示A1（每条计算完成16元素I32加法），每点是一条正式测量记录，数据来自records.csv的retired_insts，未按计算次数归一化。',
   '区分初始配置、内存装载/存储与寄存器驻留三种条件，判断相同计算任务是否需要额外架构指令，以及一次配置被多次计算复用后相对开销如何变化。',
   f'按P / X06 / S05A顺序，resident的R=1为{resident1}条，R=256为{resident256}条；三条曲线完全重合，绿色后绘制而覆盖其余颜色，均符合I(R)=3R+32。R=1冷调用为{cold1}条，热调用为{hot1}条：P在冷调用中多执行38/39条指令，热调用差距缩至3/4条。随着R增大，计算与循环指令增加，这些固定额外指令占总数的比例下降。',
   '在当前A1软件序列中，显式组主要减少冷调用的配置及配套标量开销；初始类型/数据均已驻留时，三组没有动态指令数差异。该图只证明指令量关系，不能据此判定周期完全相同，也不能代表全部九种任务。'),
  'D2-2':caption('D2-2','W2类型切换下的退休指令分类',
   '横轴是P、X06、S05A三组，纵轴是整个ROI的退休指令数，单位为条，采用线性刻度。左右子图分别取批长G=1、G=256；总计算Q=1024、I32/FP32 add类型对和复用寄存器策略保持相同。堆叠颜色依次表示compute（计算）、type_setup（类型准备）、init_move（初始化/搬运）、memory（装载/存储）、layout（布局）、dispatch_loop（分派/调用/循环）、other（其他），各层相加等于总退休数。数据来自对应单条W2记录的insts_*字段；零计数类别没有可见柱段。',
   '在计算工作量相同的条件下，定位频繁类型切换增加的是计算、类型准备、访存还是控制指令，而不只比较总柱高。',
   f'G=1时三组总数为{w2small}条，G=256时为{w2large}条；三组compute始终都是1024条。P的type_setup从{one("P",**w2,G=1)["insts_type_setup"]}降为{one("P",**w2,G=256)["insts_type_setup"]}条，X06/S05A在这组add中为0。显式组总数也随G增加而大幅下降，说明批次循环、调用和每批结果写回同样贡献开销；输入矩阵装载频率保持相同，G改变并非只影响类型设置。type_setup包含准备描述符的标量指令，不等于msettyp指令条数。',
   '频繁切换时P有额外类型准备成本，增大同类型批次可显著摊薄它；三组共同减少的批次控制/写回成本也必须计入解释。不能把两幅柱图之间全部减少的指令都归因于类型机制。'),
  'D2-3':caption('D2-3','W3运行时类型入口的分派、调用和循环占比',
   '横轴是add（I32/FP32）、max（I32/U32）、MAC（I8/FP16/BF16）、convert（I32↔FP32）四个离散类型族；连线仅便于比较，不表示连续类型插值。纵轴是dispatch_loop退休指令数/总退休指令数的比例，单位为无量纲小数，0.25表示25%。左右子图为批长G=1、G=16。每点是同组/同类型族/同批长下30条记录（三种类型序列×十个种子）的比例算术均值，数据来自W3-runtime记录。每例add/max/convert共1024次计算，MAC共768次，族内各类型次数平衡。',
   '观察同类型批处理能否摊薄运行时接口的控制指令负担，并识别不同类型族的控制占比差异。',
   f'add在G=1时三组占比为{fmt(shares(1,0))}%，G=16时为{fmt(shares(16,0))}%；批长增大后该比例下降。MAC的对应值为{fmt(shares(1,2))}%和{fmt(shares(16,2))}%，变化较小。MAC需要维护各类型的逻辑累加器状态，且循环本身仍在执行；各类型族分母中的计算、配置和访存量也不同，因而曲线高低不能只解释为分派算法差异。X06/S05A的多条曲线近乎重合。',
   '批级接口对add等类型族的控制占比有改善，但对本实现MAC的改善较小。此指标含分派、函数调用/返回和循环，不是纯分派次数；占比低也不保证总指令数更少或运行更快，须结合§4.2的匹配API周期和指令差值。'),
  'D3-1':caption('D3-1','W3支持类型增长时的可调用API代码大小',
   '横轴是单个类型族支持的类型数量，add/max/convert为1或2，MAC为1、2或3；纵轴是链接后.text+.rodata的实际字节数，采用线性刻度。四个子图对应四个类型族，每点来自一次独立编译链接，共27组大小记录。本图保留该类型集合的全部固定入口及运行时入口，共享函数只计一次；不计ELF文件头、调试段、公共启动和输出运行时，工作缓冲区另列。数据来自api-summary.json。',
   '量化提供相同可调用功能随支持类型增加所需的程序字节，观察主体共享与配置/分派支持代码的综合成本。',
   f'完整类型集合按P / X06 / S05A顺序，add为{sizes(0)}B，max为{sizes(1)}B，MAC为{sizes(2)}B，convert为{sizes(3)}B。P虽然共享部分计算主体，仍需要固定入口包装及描述符表，所以本图中完整接口集合并未比显式组更小。X06和S05A的大小逐点相同，曲线完全重合。若只保留运行时可达入口，MAC的P为172B、显式组各288B，这一不同保留口径的数值列于§4.2，未混入本图。',
   '代码大小取决于导出的入口集合、描述符表、共享方式和链接裁剪；本图仅支持“当前完整API集合下显式组更小”的观察，不能把主体共享直接等同于整体代码更小。静态代码字节数与D1编码空间、D2执行指令数量是不同指标。'),
  'D4-1':caption('D4-1','W1固定类型加法的周期与配置复用',
   '横轴是一次调用中的计算次数R=1、4、16、64、256，纵轴是每调用目标周期，两轴均为对数刻度；每调用总周期越低越快。本图为A1，三个子图依次对应resident/hot、packed_call/cold、packed_call/hot。实线是单调用原始ROI，虚线为同一ROI内重复max(1,1024/R)次完整调用后的周期/调用次数。每次冷调用都保留自身必需的配置和装载。数据分别来自records.csv与batch-records.json，每种测量条件各有15个原始点和15个批量均值点（三组×五个R）。',
   '观察配置和调用成本在重复计算中如何摊销，并通过区间内重复测量检查短调用边界对周期的影响。与图D2-1结合，区分额外指令成本和相同指令数量下的执行差异。',
   f'冷调用R=1时，P / X06 / S05A原始周期为{triplet("cycles",**a1,roi="packed_call",state="cold",R=1)}；R=256为{triplet("cycles",**a1,roi="packed_call",state="cold",R=256)}，相对差距缩小。resident在R=256为{triplet("cycles",**a1,roi="resident",state="hot",R=256)}周期，最大组间差不到0.4%，但数值并非完全相等。R增加时总周期上升，固定配置/边界成本在每次计算中的占比却下降；虚实线在短R更容易分离，不能把它们的差当作固定可扣除常数。',
   '当前A1的显式组优势主要出现在冷短调用；当计算次数增加或配置已复用时差距缩小。单调用边界、无cache取指与DDR/前端历史会影响周期，因此应同时参考批量曲线，不能把全部周期差推断为硬件类型解析延迟。'),
  'D4-2':caption('D4-2','W2类型切换频率与目标周期',
   '横轴为同类型批长G=1、4、16、64、256，采用对数刻度；纵轴为完成整例1024次计算的目标周期，线性刻度，越低越快。三行依次为I32/FP32 add、I32/U32 max、FP16/BF16 MAC；左右列为复用一组寄存器、两种类型各驻留一组寄存器。每点对应一条W2测量记录，共30个配置×三组。各类型各512次，G改变时批次数为1024/G，相邻批次类型切换次数为1024/G−1。FP16/BF16共享同一个FP32 Acc且持续累加。',
   '在总计算量固定时，测量降低类型切换频率和预留寄存器驻留类型能带来多少周期变化；检查配置复用能否减少P与显式组的差距。',
   f'以左上add为例，G=1时P / X06 / S05A为{triplet("cycles",**w2,G=1)}周期，G=256时为{triplet("cycles",**w2,G=256)}周期；三组都明显下降。右上add的P在G=1为{one("P",label="W2",task="family0",register_policy="dedicated",G=1)["cycles"]}周期，低于复用策略的{one("P",**w2,G=1)["cycles"]}。高G时三组通常接近，FP16/BF16某些点仍有小幅起伏或次序变化；本图每点未跨种子平均，不能以个别小差异推出稳定优势。',
   '同类型批处理和类型寄存器驻留可减轻频繁切换的成本，P在高切换频率、复用寄存器时的额外成本较明显。G同时改变批次循环和每批存储成本，所以这不是独立的类型解析延迟测量；显式组也保留Acc/搬运所需配置。'),
  'D4-3':caption('D4-3','W4 GEMM的每有效MAC周期与布局成本',
   '横轴是方阵维度L=16、32、128，表示M=N=K=L，采用对数刻度；纵轴为ROI周期/(M×N×K)，单位为周期/有效标量MAC，线性刻度，越低越好。三行标题G1、G2、G3分别表示I8→I32、FP16→FP32、BF16→FP32乘加，左列为已打包调用，右列为从统一行序输入开始的端到端调用；均取非零C0。每点是十个固定种子的周期/MAC算术均值，每组180条、三组合计540条记录。每种类型三组采用相同分块、k顺序和一个Acc预算；GEMM内层没有逐MAC类型分派。数据来自records.csv。',
   '观察从微基准转为完整GEMM后，固定开销是否被计算规模摊薄，以及计入布局转换后各组的实际部署成本是否改变。',
   f'I8的已打包调用在16³时P / X06 / S05A为{fmt(costs("packed_call",16),4)}周期/MAC，在128³时降为{fmt(costs("packed_call",128),4)}。128³端到端I8为{fmt(costs("end_to_end",128),4)}，FP16为{fmt(costs("end_to_end",128,"G2"),4)}，都显著高于相应已打包成本。三组已打包曲线接近，局部次序随类型/大小变化；端到端128³中S05A在上述I8/FP16两项的成本略高，说明本实现布局代码及其访存/取指同样影响结果。两种ROI分别测量，差值不能当作完全隔离的纯打包延迟。',
   '当前完整GEMM中，三组计算内核的整体成本接近，布局适配占明显成本，冷原语调用的优势不能直接外推到GEMM。该图只覆盖非零C0方阵；零C0、尾块和组合算子的结论需查对应原始记录，不能由本图替代。'),
  'D4-4':caption('D4-4','W5等量FP16扩宽的每元素周期',
   '横轴为有效输入元素数N=32、256、4096，采用对数刻度；纵轴为整个ROI周期/N，单位为周期/有效元素，线性刻度，越低越好。左右子图为已打包调用、端到端调用；每点是十个固定种子的每元素周期算术均值，三组共180条记录。三组都将N个FP16转换成N个FP32；每32个输入元素，P/S05A各1条转换、X06为2条并使用重排的两份输入。数据来自W5的records.csv。',
   '在相同有效输出数量下比较扩宽原语、必要数据组织和完整调用的成本，避免将三组各执行一条指令误当作等工作量。',
   f'已打包N=32时，P / X06 / S05A为{fmt(widen("packed_call",32),4)}周期/元素，N=4096时为{fmt(widen("packed_call",4096),4)}；X06在小N更快、到大N却比P更慢，排序发生变化。端到端N=4096为{fmt(widen("end_to_end",4096),4)}周期/元素，明显高于已打包成本，说明布局工作不能忽略。大N时X06两条转换及更大的准备后输入跨度需要更多计算/读取，而小N受固定配置、调用和测量历史影响更大；单靠计算条数不能预测最终周期。',
   '扩宽应按有效元素数比较，且已打包与端到端必须分开报告；不同N下不存在统一的三组排名。该图的差异包含原语覆盖量、配置和布局成本，不能归结为多态/显式类型机制本身。'),
 }
