#!/usr/bin/env python3
"""Collect selected actual runs; produce CSVs, figures and a bounded report."""
import collections,csv,hashlib,json,math,os,re,shutil,subprocess,sys
from pathlib import Path
from build import ROOT,HERE,OUT,GROUPS
from cases import population
from metadata import work
from model import TASKS
from run import save,sha,symbols,pcmap,TRACE_PARSER_VERSION
DOC=ROOT/'docs/ame_compare_v1'

def latest_records(pattern):
 return [(p,r) for p in sorted(OUT.glob(pattern)) for r in json.loads(p.read_text())]
def write_csv(path,rows):
 if not rows:return
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def gmean(a):return math.exp(sum(map(math.log,a))/len(a)) if a else None

def identities(directory):
 meta=directory/'manifest.json'
 if meta.exists():return json.loads(meta.read_text())
 return dict(elf_sha256=sha(directory/'guest.elf'),simulator_sha256='6ddf3e8b74544dbe52acad7265fec506f54da96fd9c0c02caf25479ef9355ef9',config_sha256=sha(directory/'m5out/config.ini'),report_sha256=sha(directory/'guest.bin'))

def collect():
 DOC.mkdir(parents=True,exist_ok=True);checks=[]
 def check(name,ok,evidence,**kw):checks.append(dict(name=name,status='NOT_RUN' if ok is None else 'PASS' if ok else 'FAIL',evidence=evidence,**kw))
 selected={}
 for p,r in latest_records('runs/*formal/*/records.json')+latest_records('runs/*formal-control/*/records.json'):
  selected[r['group'],r['case']['id']]=(p,r)
 meta_cache={}
 for p,r in selected.values():
  if p.parent not in meta_cache:meta_cache[p.parent]=identities(p.parent)
  r.update(meta_cache[p.parent]);r['simulator_commit']='26b042f07e3c460037ca151778c0fc3aa2e80f2a'
 cases=population()
 for group in GROUPS:
  rows=[selected.get((group,c['id'])) for c in cases]
  check(group+' W1-W5 declared population',None if not all(rows) else all(x[1]['status']=='PASS' for x in rows),[str(x[0].relative_to(ROOT)) for x in rows if x],expected=len(cases),completed=sum(x is not None for x in rows))
  good=[x[1] for x in rows if x]
  check(group+' retired/category/compute count closure',None if not good else all(x.get('trace_count_delta')==0 and not x.get('unknown_pcs') and x.get('trace_parser_version')==TRACE_PARSER_VERSION and sum(x['compute_words'].values())==x['expected_compute_insts'] for x in good),'records.json',records=len(good))
  check(group+' rdinstret boundary calibration',None if not good else all(x['retired_insts']-x['rdinstret_delta']==9 for x in good),'records.json',records=len(good))
  build_hashes={control:sha(OUT/('control-build' if control else 'build')/group/'guest.elf') for control in (0,1)}
  check(group+' frozen main/control guest ELF identity',None if not good else all(x['elf_sha256']==build_hashes[x['case']['control']] for x in good),'manifest.json',records=len(good))
 pair_rows=[];flat=[]
 for c in cases:
  triple=[selected.get((g,c['id'])) for g in GROUPS]
  if not all(triple):continue
  data=[x[1] for x in triple];matched=len({x['output_sha256'] for x in data})==1
  # Packed C3/layout inputs differ, but every output ABI is canonical/tile-row.
  if not matched:check('paired output '+str(c['id']),False,[str(x[0].relative_to(ROOT)) for x in triple])
  for (p,r),group in zip(triple,GROUPS):
   m=work(c,group);b=r.get('batch_count',1)
   for key in ('useful_elements','useful_MACs','executed_MACs'):m[key]*=b
   row=dict(case_id=c['id'],label=c['label'],group=group,task=TASKS[c['op']] if c['work'] in (0,1,4,5) else ('I32-add-max','I32-F32-add-I32')[c['op']] if c['work']==6 else 'family'+str(c['op']),roi=('resident','packed_call','end_to_end')[c['roi']],state=('cold','hot')[c['state']],R=c['repeat'],G=c['batch'],seed=c['seed'],m=c['m'],n=c['n'],k=c['k'],c0=c['c0'],register_policy=('reuse','dedicated')[c['regpolicy']],pattern=c['pattern'],control=c['control'],batch_count=b,status=r['status'],cycles=r['cycles'],cycles_per_call=r['cycles']/b,ticks=r['ticks'],retired_insts=r['retired_insts'],rdcycle_delta=r['rdcycle_delta'],rdinstret_delta=r['rdinstret_delta'],flags=r['flags'],output_sha256=r['output_sha256'],reference_sha256=r['reference_sha256'],evidence=str(p.relative_to(ROOT)))
   row.update(m);row.update({key:r[key] for key in ('simulator_commit','simulator_sha256','elf_sha256','config_sha256')});row['matrix_load_bytes']=r.get('matrix_load_bytes',m['matrix_load_bytes']);row['matrix_store_bytes']=r.get('matrix_store_bytes',m['matrix_store_bytes'])
   row.update({key:r.get(key,'NA') for key in ('scalar_load_bytes','scalar_store_bytes','all_load_bytes','all_store_bytes')})
   row.update({'insts_'+k:r['categories'].get(k,0) for k in ('compute','type_setup','init_move','memory','layout','dispatch_loop','other')})
   row.update(cycles_per_element=r['cycles']/m['useful_elements'] if m['useful_elements'] else None,
              cycles_per_MAC=r['cycles']/m['useful_MACs'] if m['useful_MACs'] else None,
              instructions_per_element=r['retired_insts']/m['useful_elements'] if m['useful_elements'] else None,
              instructions_per_MAC=r['retired_insts']/m['useful_MACs'] if m['useful_MACs'] else None,
              type_setup_fraction=row['insts_type_setup']/r['retired_insts'],IPC=r['retired_insts']/r['cycles'],
              useful_elements_per_second=m['useful_elements']*1e9/r['cycles'] if m['useful_elements'] else None,
              useful_MACs_per_second=m['useful_MACs']*1e9/r['cycles'] if m['useful_MACs'] else None)
   flat.append(row)
  pair_rows.append(dict(case_id=c['id'],label=c['label'],task=TASKS[c['op']] if c['work'] in (0,1,4,5) else ('I32-add-max','I32-F32-add-I32')[c['op']] if c['work']==6 else 'family'+str(c['op']),roi=c['roi'],state=c['state'],R=c['repeat'],G=c['batch'],seed=c['seed'],register_policy=c['regpolicy'],pattern=c['pattern'],m=c['m'],n=c['n'],k=c['k'],c0=c['c0'],P_cycles=data[0]['cycles'],X06_cycles=data[1]['cycles'],S05A_cycles=data[2]['cycles'],X06_speedup=data[0]['cycles']/data[1]['cycles'],S05A_speedup=data[0]['cycles']/data[2]['cycles'],X06_instruction_reduction=(data[0]['retired_insts']-data[1]['retired_insts'])/data[0]['retired_insts'],S05A_instruction_reduction=(data[0]['retired_insts']-data[2]['retired_insts'])/data[0]['retired_insts'],outputs_match=matched,status='PASS' if matched and all(r['status']=='PASS' for r in data) else 'FAIL'))
 check('cross-group outputs',None if not pair_rows else all(r['outputs_match'] for r in pair_rows),'paired.csv',pairs=len(pair_rows))
 identity_groups=collections.defaultdict(set)
 for r in flat:identity_groups[r['case_id']].add((r['input_hash'],r['useful_elements'],r['useful_MACs'],r['executed_MACs']))
 check('paired logical inputs and useful/padded work agree',None if len(identity_groups)<len(cases) else all(len(x)==1 for x in identity_groups.values()),'records.csv',pairs=len(identity_groups))
 for file,name in [('static-audit.json','encoding and identical control preparation'),('layout-checks.json','host layout reversibility'),('artifact-audit.json','saved ELF/report/config/trace artifact integrity')]:
  p=OUT/file;r=json.loads(p.read_text()) if p.exists() else None;check(name,None if r is None else r['status']=='PASS',str(p.relative_to(ROOT)))
 for pattern,name in [('gates/*/summary.json','MAC coordinates, all half patterns, second target'),('boundary/*/summary.json','M/Acc register boundaries'),('api/*/summary.json','callable API linked size and correctness'),('api-perf/*/summary.json','matched fixed/runtime API measurements')]:
  p=sorted(OUT.glob(pattern));r=json.loads(p[-1].read_text()) if p else None;check(name,None if r is None else r['status']=='PASS',str(p[-1].relative_to(ROOT)) if p else 'missing')
 batch={}
 for p,r in latest_records('runs/*formal-batches-v2/*/records.json'):batch[r['group'],r['case']['id']]=(p,r)
 check('short-call batched measurements',None if len(batch)<405 else all(r['status']=='PASS' for _,r in batch.values()),[str(p.relative_to(ROOT)) for p,_ in batch.values()],expected=405,completed=len(batch))
 empty={g:max((r['cycles'] for (gg,_),(p,r) in selected.items() if gg==g and r['case']['label']=='calibration-empty'),default=0) for g in GROUPS}
 check('W1 batch boundary fraction below 1 percent',None if len(batch)<405 or not all(empty.values()) else all(empty[g]/r['cycles']<.01 for (g,_),(_,r) in batch.items()),'boundary-fractions.json')
 api_latest=sorted(OUT.glob('api-perf/*/summary.json'))
 api_rows=[r for p in api_latest[-1].parent.glob('*/*/records.json') for r in json.loads(p.read_text())] if api_latest else []
 api_keys={(r['group'],r['case']['family'],r['case']['op'],r['case']['repeat'],r['case']['seed'],r['case']['pattern']) for r in api_rows}
 check('matched API full population and trace closure',None if len(api_rows)<1080 else len(api_rows)==len(api_keys)==1080 and all(r['status']=='PASS' and r.get('trace_parser_version')==TRACE_PARSER_VERSION and r.get('trace_count_delta')==0 and not r.get('unknown_pcs') for r in api_rows),'api-perf-records.json',expected=1080,completed=len(api_rows))
 environment=json.loads((OUT/'environment.json').read_text())
 calibration=environment.get('trace_format_calibration',{})
 check('final guest compact/full trace equivalence',calibration.get('status')=='PASS' and calibration.get('elf_sha256')==sha(OUT/'build/P/guest.elf'),'environment.json')
 index=OUT/'input-reference-index.json';archive=json.loads(index.read_text())['cases'] if index.exists() else []
 archived_files={}
 for r in archive:
  for key,hashkey in (('input_file','input_file_sha256'),('reference_file','reference_hash')):
   name=r[key];path=OUT/name
   if name not in archived_files:archived_files[name]=sha(path) if path.exists() else None
 check('logical input and reference archive integrity',None if len(archive)<5193 else len(archive)==5193 and all(archived_files[r[k]]==r[h] for r in archive for k,h in (('input_file','input_file_sha256'),('reference_file','reference_hash'))),'input-reference-index.json',expected=5193,completed=len(archive))
 repeat=[]
 for group in GROUPS:
  for ident in (43,103,163):
   found=[(p,r) for p,r in latest_records('runs/*formal-repeat-*/*/records.json') if r['group']==group and r['case']['id']==ident]
   distinct={(r['cycles'],r['retired_insts'],r['output_sha256']) for _,r in found}
   check(f'determinism {group} case {ident}',None if len(found)<3 else len(found)==3 and len(distinct)==1,[str(p.relative_to(ROOT)) for p,_ in found],runs=len(found))
   repeat.extend(dict(group=group,case_id=ident,cycles=r['cycles'],retired_insts=r['retired_insts'],evidence=str(p.relative_to(ROOT))) for p,r in found)
 # Platform rerun must use newly completed timestamped records, not old snapshots.
 explicit=ROOT/'results/ame_explicit_v1'
 for suite in ('xuantie_v06','spec_v05a'):
  p=sorted((explicit/suite).glob('2026112*-AME_B11/functional.json'))
  r=json.loads(p[-1].read_text()) if p else None
  check('platform full '+suite,None if r is None else r['status']=='PASS' and r['random_per_seed']==100,str(p[-1].relative_to(ROOT)) if p else 'missing')
 p=sorted((explicit/'regression').glob('2026112*/regression.json'))
 r=json.loads(p[-1].read_text()) if p else None
 check('platform frozen old ELF regression',None if r is None else r['status']=='PASS' and len(r['results'])==65,str(p[-1].relative_to(ROOT)) if p else 'missing')
 frozen=json.loads((OUT/'frozen.json').read_text());unchanged=all((ROOT/n).exists() and sha(ROOT/n)==h for n,h in frozen['files'].items())
 check('frozen simulator and integration files unchanged',unchanged,'frozen.json')
 modified=subprocess.check_output(['git','diff','26b042f07e','--name-only','--','src','example','build_opts','tests'],cwd=ROOT,text=True).splitlines()
 check('no simulator/platform source edits',not modified,modified)
 status='FAIL' if any(c['status']=='FAIL' for c in checks) else 'NOT_RUN' if any(c['status']=='NOT_RUN' for c in checks) else 'PASS'
 result=dict(status=status,checks=checks,summary=dict(collections.Counter(c['status'] for c in checks)),selected_records=len(selected),paired_cases=len(pair_rows),batch_records=len(batch),api_records=len(api_rows),repeat_records=len(repeat),total_timing_records=len(selected)+len(batch)+len(api_rows)+len(repeat))
 save(OUT/'acceptance.json',result)
 write_csv(OUT/'records.csv',flat);write_csv(OUT/'paired.csv',pair_rows);write_csv(OUT/'repeat.csv',repeat)
 save(OUT/'selected-records.json',[dict(r,evidence=str(p.relative_to(ROOT))) for p,r in selected.values()])
 save(OUT/'batch-records.json',[dict(r,evidence=str(p.relative_to(ROOT))) for p,r in batch.values()])
 return result,flat,pair_rows,batch

def figures(flat,pairs,batches):
 os.environ.setdefault('MPLCONFIGDIR','/tmp/ame-compare-matplotlib')
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 import numpy as np
 plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
 colors={'P':'#365f9d','X06':'#d27828','S05A':'#27946f'}
 figdir=DOC/'figures';figdir.mkdir(parents=True,exist_ok=True)
 def finish(fig,name):
  fig.tight_layout();fig.savefig(figdir/(name+'.png'),dpi=180);fig.savefig(figdir/(name+'.pdf'));plt.close(fig)
 from encoding_figures import render
 render(figdir)
 fig,axs=plt.subplots(1,3,figsize=(12,3.5))
 for ax,(roi,state,title) in zip(axs,[('resident','hot','Resident, A1'),('packed_call','cold','Cold packed call, A1'),('packed_call','hot','Hot packed call, A1')]):
  for g in GROUPS:
   data=sorted([r for r in flat if r['label']=='W1' and r['group']==g and r['task']=='A1' and r['roi']==roi and r['state']==state],key=lambda r:r['R'])
   if not data:continue
   ax.plot([r['R'] for r in data],[r['cycles'] for r in data],'-o',color=colors[g],label=g)
   valid=[(r,batches.get((g,r['case_id']))) for r in data]
   ax.plot([r['R'] for r,b in valid if b],[b[1]['cycles']/b[1]['batch_count'] for r,b in valid if b],'--',color=colors[g])
  ax.set(xscale='log',yscale='log',xlabel='computations per call R',ylabel='target cycles per call',title=title);ax.legend() if ax.get_legend_handles_labels()[0] else None
 finish(fig,'w1_configuration_amortization')
 fig,axs=plt.subplots(3,2,figsize=(10,9))
 for family in range(3):
  for rp in range(2):
   ax=axs[family,rp]
   for g in GROUPS:
    data=sorted([r for r in flat if r['label']=='W2' and r['group']==g and r['task']=='family'+str(family) and r['register_policy']==('reuse','dedicated')[rp]],key=lambda r:r['G'])
    if data:ax.plot([r['G'] for r in data],[r['cycles'] for r in data],'-o',label=g,color=colors[g])
   ax.set(xscale='log',xlabel='batch length G',ylabel='cycles / 1024 computations',title=['I32/F32 add','I32/U32 max','F16/BF16 MAC'][family]+'; '+['reuse','dedicated'][rp]);ax.legend() if ax.get_legend_handles_labels()[0] else None
 finish(fig,'w2_type_switching')
 fig,axs=plt.subplots(1,3,figsize=(12,3.5))
 for ax,(roi,state) in zip(axs,[('resident','hot'),('packed_call','cold'),('packed_call','hot')]):
  for g in GROUPS:
   rows=sorted([r for r in flat if r['label']=='W1' and r['group']==g and r['task']=='A1' and r['roi']==roi and r['state']==state],key=lambda r:r['R'])
   if rows:ax.plot([r['R'] for r in rows],[r['retired_insts'] for r in rows],'-o',label=g,color=colors[g])
  ax.set(xscale='log',yscale='log',xlabel='computations R',ylabel='retired instructions',title=roi+' / '+state)
  if ax.get_legend_handles_labels()[0]:ax.legend()
 finish(fig,'w1_retired_instructions')
 fig,axs=plt.subplots(1,2,figsize=(12,4))
 cats=('compute','type_setup','init_move','memory','layout','dispatch_loop','other')
 for ax,G in zip(axs,(1,256)):
  rows=[r for g in GROUPS for r in flat if r['label']=='W2' and r['group']==g and r['task']=='family0' and r['register_policy']=='reuse' and r['G']==G]
  bottom=np.zeros(len(rows))
  for cat in cats:
   vals=np.array([r['insts_'+cat] for r in rows]);ax.bar(range(len(rows)),vals,bottom=bottom,label=cat);bottom+=vals
  ax.set(xticks=range(len(rows)),xticklabels=[r['group'] for r in rows],ylabel='retired instructions',title='W2 I32/F32 add, reuse, G='+str(G))
 axs[-1].legend(fontsize=7);finish(fig,'w2_instruction_categories')
 from dispatch_figure import render as render_dispatch
 render_dispatch(flat,figdir)
 api=sorted(OUT.glob('api/*/summary.json'))
 if api:
  data=json.loads(api[-1].read_text())['results'];fig,axs=plt.subplots(1,4,figsize=(13,3.5))
  for family,ax in enumerate(axs):
   for g in GROUPS:
    rows=[r for r in data if r['family']==family and r['group']==g]
    ax.plot([r['types'] for r in rows],[r['text_bytes']+r['rodata_bytes'] for r in rows],'-o',label=g,color=colors[g])
   ax.set(xlabel='supported types',ylabel='linked text + rodata bytes',title=['add','max','MAC','convert'][family]);ax.legend() if ax.get_legend_handles_labels()[0] else None
  finish(fig,'w3_callable_code_size')
 fig,axs=plt.subplots(3,2,figsize=(10,9))
 for ty,op in enumerate((4,5,6)):
  for ri,roi in enumerate(('packed_call','end_to_end')):
   ax=axs[ty,ri]
   for g in GROUPS:
    xs=[];ys=[]
    for n in (16,32,128):
     rows=[r for r in flat if r['label']=='W4-GEMM' and r['group']==g and r['task']==TASKS[op] and r['n']==n and r['c0']==1 and r['roi']==roi]
     if rows:xs.append(n);ys.append(sum(r['cycles']/r['useful_MACs'] for r in rows)/len(rows))
    if xs:ax.plot(xs,ys,'-o',label=g,color=colors[g])
   ax.set(xscale='log',xlabel='square matrix dimension',ylabel='cycles / useful MAC',title=TASKS[op]+'; '+roi);ax.set_xticks([16,32,128],['16','32','128']);ax.tick_params(axis='x',which='minor',bottom=False,labelbottom=False);ax.legend() if ax.get_legend_handles_labels()[0] else None
 finish(fig,'w4_gemm_cost')
 fig,axs=plt.subplots(1,2,figsize=(10,3.5))
 for ax,roi in zip(axs,('packed_call','end_to_end')):
  for g in GROUPS:
   xs=[];ys=[]
   for n in (32,256,4096):
    rows=[r for r in flat if r['label']=='W5' and r['group']==g and r['n']==n and r['roi']==roi]
    if rows:xs.append(n);ys.append(sum(r['cycles']/n for r in rows)/len(rows))
   if xs:ax.plot(xs,ys,'-o',label=g,color=colors[g])
  ax.set(xscale='log',xlabel='half elements converted',ylabel='cycles / element',title=roi);ax.set_xticks([32,256,4096],['32','256','4096']);ax.tick_params(axis='x',which='minor',bottom=False,labelbottom=False);ax.legend() if ax.get_legend_handles_labels()[0] else None
 finish(fig,'w5_equal_work_widening')


def report(render_figures=True):
 result,flat,pairs,batches=collect()
 if render_figures:figures(flat,pairs,batches)
 evidence=DOC/'evidence';evidence.mkdir(exist_ok=True)
 names=['acceptance.json','frozen.json','static-audit.json','layout-checks.json','artifact-audit.json','records.csv','paired.csv','repeat.csv','selected-records.json','batch-records.json','input-reference-index.json']
 for n in names:
  if (OUT/n).exists():shutil.copyfile(OUT/n,evidence/n)
 for category in ('gates','boundary','api','api-perf'):
  paths=sorted(OUT.glob(category+'/*/summary.json'))
  if paths:shutil.copyfile(paths[-1],evidence/(category+'-summary.json'))
 api_latest=sorted(OUT.glob('api-perf/*/summary.json'))
 extra=[(p,r) for p in sorted(api_latest[-1].parent.glob('*/*/records.json')) for r in json.loads(p.read_text())] if api_latest else []
 for p,r in extra:r.update(identities(p.parent))
 save(evidence/'api-perf-records.json',[dict(r,evidence=str(p.relative_to(ROOT))) for p,r in extra])
 demos=sorted(OUT.glob('runs/*-demo-A1-cold'))
 demo_text='README提供独立启动的A1冷调用命令：`--start 32 --end 33 --trace --tag demo-A1-cold`。来宾入口为bench.c中的w1_0，计算循环由build.py生成repeat_0_0；完整调用包含配置、装载、计算和存储。'
 if demos:
  demo=[r for p in demos[-1].glob('*/records.json') for r in json.loads(p.read_text())]
  save(evidence/'demo-A1-cold.json',demo)
  demo_text+='本次额外复现结果为'+str({r['group']:dict(status=r['status'],retired=r['retired_insts'],compute=sum(r['compute_words'].values())) for r in demo})+'，详见 [示例记录](evidence/demo-A1-cold.json)。此示例不混入主计时汇总。'
 from summaries import summarise
 aggregate,fractions,api_pairs=summarise(pairs,flat,batches,[r for _,r in extra])
 for name in ('aggregate','boundary-fractions','api-paired','encoding-growth'):
  shutil.copyfile(OUT/(name+'.json'),evidence/(name+'.json'))
 shutil.copyfile(OUT/'environment.json',evidence/'environment.json')
 # Copy newly completed platform gate summaries too.
 gate=json.loads((OUT/'acceptance.json').read_text())
 for c in gate['checks']:
  if c['name'].startswith('platform ') and c['status']=='PASS':
   source=ROOT/c['evidence']
   shutil.copyfile(source,evidence/('platform-'+source.parent.name+'-'+source.name))
 src=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
 src += [ROOT/n for n in ('example/common/crt0.S','tests/ame_explicit_v1/common/runtime.c','tests/ame_explicit_v1/common/trap.S','tests/ame_explicit_v1/common/ieee.py','tests/ame_explicit_v1/xuantie_v06/encoding.csv','tests/ame_explicit_v1/spec_v05a/encoding.csv')]
 manifest=dict(simulator_commit='26b042f07e3c460037ca151778c0fc3aa2e80f2a',branch='ztt0.6-xuantie0.6-spec0.5a-vs',sources={str(p.relative_to(ROOT)):sha(p) for p in src},evidence={str(p.relative_to(DOC)):sha(p) for p in evidence.rglob('*') if p.is_file() and p.name!='manifest.json'})
 save(evidence/'manifest.json',manifest)
 lines=['# P、X06、S05A 三组公平对比实验报告（不修改模拟器）','',
        f"验收状态：**{result['status']}**；检查汇总：`{result['summary']}`。已收集主配置记录 {result['selected_records']} 条，完整三组配对 {result['paired_cases']} 个。",
        f"另含W1批量 {result['batch_records']} 条、匹配API {result['api_records']} 条及独立重复 {result['repeat_records']} 条；合计 {result['total_timing_records']} 条计时记录。专项正确性门槛另计。",
        '', '## 1. 范围与冻结平台','',
        '按用户提供的 v1 方案执行 W1—W5。W6 需要新增模拟指令，按本轮“不修改模拟器”的要求未执行。',
        '模拟器提交为 `26b042f07e3c460037ca151778c0fc3aa2e80f2a`，三组均使用同一个 B11。',
        'B11 SHA256：`6ddf3e8b74544dbe52acad7265fec506f54da96fd9c0c02caf25479ef9355ef9`。',
        '平台为单核 RiscvMinorCPU / 1GHz / 无 I、D cache / DDR3；矩阵 FU opLat=issueLat=16，向量延迟6。',
        '实验新增来宾程序、链接脚本、发码、参考、统计及报告工具；src、example、CPU/FU 和既有测试源码保持冻结内容。',
        '', '## 2. 工作负载与正确性','']
 from acceptance_view import table
 lines += table(result,flat)
 lines += ['', '完整预声明配置为1,236个：W1主集合135（45个任务/R组合×三种ROI/状态）、控制60、W2 30、W3运行时240、固定入口180、W4 GEMM420、组合算子80、W5 60，以及31个校准/门槛配置。',
           '三组在每个配对中使用同一逻辑输入、非零/零 C0、相同有效工作量和独立参考。W3/W4/W5使用固定种子0…9。',
           'MAC专项逐位置验证：每组I8 256、FP16 128、BF16 128个探针；每组全部65,536种半精度扩宽及2,048次第二目标立即消费。',
           '数值主集合使用有界整数/有限二进制数：MAC操作数绝对值不超过3，所有累加中间值小于2²⁴，因此FP32逐k FMA严格精确；参考用任意精度整数计算并断言此界限。加法/转换参考复用独立的精确有理数IEEE标量原语。',
           '主性能数据没有将NaN、Inf、越界转换混入等语义集合；特殊半精度由独立正确性专项覆盖。',
          ]
 from dimensions import section
 lines += ['']+section(flat)
 lines += [
           '', '## 4. 测量方法与结果边界','',
           '- 测量入口固定在0x80010000，计算/类型/搬运/布局/W1函数分区放置；输入、输出、scratch分别固定于0x81000000、0x81800000、0x82000000。',
           '- 每ROI以m5 reset/dump建立边界，结束前fence；保留标记自身指令。结果存储以该模型的fence和已提交指令为可见性边界，不宣称DRAM单元已经完成物理写入。',
           '- 主运行在同一进程内按相同配置顺序测多个独立、不嵌套ROI。m5 reset只清统计，不重置DDR控制器/前端历史；独立启动的单用例示例与主运行同一用例可以有不同周期，但指令数和结果应一致。27次独立重复验证的是相同启动条件的确定性，不是不同前序历史的等价性。',
           '- 正确性生成、参考答案、结果比较和semihosting均在ROI外。1024 NOP等待也在ROI外。',
           '- Exec在当前Minor实现的提交处输出；按PC、机器字和调用上下文分类，检查真实计算条数及64B整寄存器访存。matrix_load/store_bytes不冒充总线流量，标量layout/stack访问另计。',
           '- 空ROI、单次和长批次分别记录。短调用保留原始结果和区间内重复结果；统计不人为制造置信区间。种子均值反映输入差异。',
           '- 主实验使用当前实现的合法软件序列和公共调用约定；公共循环/可调用辅助函数本身属于实测成本，不宣称每一序列达到理论全局最短指令数。控制实验的六种任务经静态审计确认外围机器码和地址相同，仅计算机器字不同。',
           '- 初始类型冷/热与cache无关。无cache、固定矩阵FU和串行化会影响取指、重定向与访存周期。相同计算条数下的剩余差异不能全部归因于描述符读取。',
           '- 主结果衡量当前研究实现的任务成本，不推出完整原生Xuantie/spec优劣，也不把C++宿主执行速度当作目标周期。',
           '', '## 5. 原始证据与复现','',
           '见 [README](../../experiments/ame_compare_v1/README.md) 和冻结的 [PLAN_v1.md](../../experiments/ame_compare_v1/PLAN_v1.md)。',
           demo_text,
           '结果CSV与紧凑JSON见 [evidence](evidence/acceptance.json)；原始ELF、输入生成配置、链接map、指令trace、stats、命令和失败记录保留在 results/ame_compare_v1。',
           'SHA256及源码来源见 [manifest.json](evidence/manifest.json)。所有未完成项目显示NOT_RUN，不以既有功能测试PASS替代本次性能验收。',
           '', '开发期先采集了通用内层分派版本，发现其逐MAC分派不符合方案后中止，保留为provisional数据；正式报告只采用formal标签、已移除内层分派的程序。另曾修正trace分类器：P的R2族共享funct7，必须同时检查rs2子功能，避免将类型配置当作转换计算。原始数值输出没有变化，旧解析结果和trace保留，最终采用修正后的重新解析记录。']
 from findings import tables
 offset=lines.index('## 4. 测量方法与结果边界')
 lines[offset:offset]=tables(flat,batches,aggregate,fractions,api_pairs)+['']
 lines=[x.replace('## 4. 测量方法与结果边界','## 5. 测量方法与结果边界').replace('## 5. 原始证据与复现','## 6. 原始证据与复现') for x in lines]
 shutil.copyfile(OUT/'image-size.json',evidence/'image-size.json')
 manifest['evidence']={str(p.relative_to(DOC)):sha(p) for p in evidence.rglob('*') if p.is_file() and p.name!='manifest.json'}
 save(evidence/'manifest.json',manifest)
 (DOC/'EXPERIMENT_REPORT.md').write_text('\n'.join(lines)+'\n')
 print(result['status'],result['summary'],flush=True)
 return result['status']
if __name__=='__main__':
 if sys.argv[1:]==['--collect-only']:
  result,*_=collect()
  print('Collected',result['selected_records'],'main records; archive/audit and final report still required.')
  raise SystemExit(0)
 status=report(render_figures='--no-figures' not in sys.argv[1:])
 raise SystemExit(0 if status=='PASS' else 1)
