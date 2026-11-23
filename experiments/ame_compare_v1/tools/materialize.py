"""Archive logical input vectors and exact references, deduplicated by hash."""
import hashlib,json
from pathlib import Path
from build import OUT,GROUPS
from model import tile,values,expected
from metadata import work
from run import save

def logical(c):
 w,op=c['work'],c['op']
 if w==0:return None
 if w==1:
  x=tile(op,c['seed']);return x[0] if op in (7,8,9) else x
 if w in (2,3):
  ops=([0,1],[2,3],[4,5,6],[7,8])[op]
  if w==2 and op==2:ops=[5,6]
  return [tile(o,c['seed']+t) for t,o in enumerate(ops)]
 if w==4:
  m,n,k=c['m'],c['n'],c['k'];v=values(c['seed'],m*k+k*n+m*n)
  if not c['c0']:v[m*k+k*n:]=[0]*(m*n)
  return v
 if w==5:return values(c['seed'],c['n'])
 return values(c['seed'],2*c['n'])

def materialize():
 selected=json.loads((OUT/'selected-records.json').read_text());batch=json.loads((OUT/'batch-records.json').read_text())
 latest=sorted((OUT/'api-perf').glob('*/summary.json'))[-1].parent
 api=[r for p in latest.glob('*/*/records.json') for r in json.loads(p.read_text())]
 idir=OUT/'inputs';rdir=OUT/'references';idir.mkdir(exist_ok=True);rdir.mkdir(exist_ok=True);index=[];cache={}
 for r in selected+batch+api:
  c=r['case'];m=work(c,r['group']);h=m['input_hash'];p=idir/(h+'.json')
  if not p.exists():
   v=work(c,r['group'],True)['input_identity'];assert hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()==h
   p.write_text(json.dumps(v,separators=(',',':'))+'\n')
  rh=r['reference_sha256'];q=rdir/(rh+'.bin')
  if rh not in cache:
   rc=dict(c)
   if r.get('batch_count',1)>1 and c['roi']==0 and c['op'] in (4,5,6):rc['repeat']*=r['batch_count']
   data,flags=expected(rc,r['group']);assert hashlib.sha256(data).hexdigest()==rh
   q.write_bytes(data);cache[rh]=flags
  index.append(dict(group=r['group'],case_id=c['id'],source_records=r.get('evidence'),batch_count=r.get('batch_count',1),logical_input_hash=h,input_file=str(p.relative_to(OUT)),input_file_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),reference_hash=rh,reference_file=str(q.relative_to(OUT)),expected_flags=r['flags']))
 save(OUT/'input-reference-index.json',dict(format='Logical oracle vectors; encoding/scaling are specified by case/op and model.py. Packed guest bytes are reproducible from group emitters.',cases=index))
 print('Archived',len(index),'records,',len(list(idir.glob('*.json'))),'unique inputs,',len(cache),'unique references',flush=True)
if __name__=='__main__':materialize()
