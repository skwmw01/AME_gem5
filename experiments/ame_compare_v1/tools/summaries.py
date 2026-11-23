"""Predeclared per-ROI aggregates; no cross-ROI overall winner score."""
import collections,csv,json,math
from pathlib import Path
from build import ROOT,OUT
from run import save

def gmean(values):return math.exp(sum(math.log(x) for x in values)/len(values))
def summarise(pairs,flat,batches,api_rows):
 buckets=collections.defaultdict(list)
 for row in pairs:
  label=row['label']
  if row['status']!='PASS' or label not in ('W1','W2','W3-runtime','W4-GEMM','W4-pipeline','W5','W1-control'):continue
  if label=='W1':key=(label,row['roi'],row['state'],'all-nine-tasks-R1..256')
  elif label=='W1-control':key=(label,row['roi'],row['state'],'six-same-layout-tasks')
  elif label=='W2':key=(label,row['roi'],row['register_policy'],'all-three-type-pairs')
  elif label=='W3-runtime':key=(label,row['G'],row['pattern'],'four-families-ten-seeds')
  elif label=='W4-GEMM':key=(label,row['roi'],row['c0'],'three-types-all-declared-shapes')
  elif label=='W4-pipeline':key=(label,row['roi'],row['task'],'two-N-ten-seeds')
  else:key=(label,row['roi'],row['state'],'N32-256-4096-ten-seeds')
  buckets[key].append(row)
 aggregate=[]
 for key,rows in sorted(buckets.items(),key=lambda z:str(z[0])):
  aggregate.append(dict(label=key[0],conditions=str(key[1:]),pairs=len(rows),X06_speedup_gmean=gmean([x['X06_speedup'] for x in rows]),S05A_speedup_gmean=gmean([x['S05A_speedup'] for x in rows])))
 save(OUT/'aggregate.json',aggregate)
 # Record boundary fractions, including short raw calls, rather than adjusting.
 empty={g:max(r['cycles'] for r in flat if r['group']==g and r['label']=='calibration-empty') for g in ('P','X06','S05A') if any(r['group']==g and r['label']=='calibration-empty' for r in flat)}
 fractions=[]
 for (g,ident),(p,r) in sorted(batches.items()):
  fractions.append(dict(group=g,case_id=ident,batch_count=r['batch_count'],cycles=r['cycles'],cycles_per_call=r['cycles']/r['batch_count'],empty_cycles=empty.get(g),boundary_fraction=empty.get(g,0)/r['cycles'],status=r['status']))
 save(OUT/'boundary-fractions.json',fractions)
 # API known/runtime pairs have exactly the same per-call work and inputs.
 api={}
 for r in api_rows:
  c=r['case'];api[r['group'],c['family'],c['op'],c['repeat'],c['seed'],c['pattern']]=r
 api_pairs=[]
 for key,known in api.items():
  if key[-1]!=0:continue
  runtime=api.get((*key[:-1],1))
  if not runtime:continue
  api_pairs.append(dict(group=key[0],family=key[1],op=key[2],repeat=key[3],seed=key[4],known_cycles_per_call=known['cycles']/128,runtime_cycles_per_call=runtime['cycles']/128,extra_cycles_per_call=(runtime['cycles']-known['cycles'])/128,known_insts_per_call=known['retired_insts']/128,runtime_insts_per_call=runtime['retired_insts']/128,outputs_match=known['output_sha256']==runtime['output_sha256'],status='PASS' if known['status']==runtime['status']=='PASS' and known['output_sha256']==runtime['output_sha256'] else 'FAIL'))
 save(OUT/'api-paired.json',api_pairs)
 # Growth uses the fixed insertion order A1,A2,M1,M2,G1,G2,G3,C1,C2,C3.
 growth=[]
 for count,pcount in ((4,2),(7,3),(10,4)):
  for g in ('P','X06','S05A'):
   rules=pcount if g=='P' else count
   words=(65536+(4096 if count>=7 else 0)+(1024 if count==10 else 0)) if g=='P' else 131072+(12288 if count>=7 else 0)+(3072 if count==10 else 0)
   growth.append(dict(tasks=count,group=g,rules=rules,mask_envelope=words,legal_fields=words-(32 if g=='S05A' and count==10 else 0)))
 save(OUT/'encoding-growth.json',growth)
 return aggregate,fractions,api_pairs
