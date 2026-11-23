"""Audit preserved committed traces again; keep prior parser output intact."""
import concurrent.futures,fcntl,json
from pathlib import Path
from build import OUT,GROUPS
from run import trace_audit,save,TRACE_PARSER_VERSION

def one(p):
 with (p.parent/'reparse.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  # Only final performance populations, not provisional prefreeze smoke runs.
  if p.parents[1].name.endswith(('-gates','-calibration-v2','-calibration-final','-smoke')):return
  if '-formal-batches/' in str(p):return
  records=json.loads(p.read_text())
  if not records or all(r.get('trace_parser_version')==TRACE_PARSER_VERSION for r in records):return
  if not (p.parent/'m5out/trace.gz').exists():return
  group=records[0]['group'];control=records[0]['case'].get('control',0)==1
  batch='batches' in str(p)
  if not (p.parent/'records-parser-v1.json').exists():save(p.parent/'records-parser-v1.json',records)
  backup=p.parent/('records-parser-v'+str(records[0].get('trace_parser_version',1))+'.json')
  if not backup.exists():save(backup,records)
  trace_audit(p.parent,group,records,control,batch)
  save(p,records);print(p,'PASS',sum(r['status']=='PASS' for r in records),'FAIL',sum(r['status']=='FAIL' for r in records),flush=True)

def reparse():
 paths=list((OUT/'runs').glob('*formal*/*/records.json'))+list((OUT/'api-perf').glob('*/*/*/records.json'))
 with concurrent.futures.ProcessPoolExecutor(max_workers=3) as workers:list(workers.map(one,sorted(paths)))
 # Refresh API aggregate after reanalysis; preserve its original analysis too.
 for p in (OUT/'api-perf').glob('*/summary.json'):
  rows=[r for q in p.parent.glob('*/*/records.json') for r in json.loads(q.read_text())]
  old=json.loads(p.read_text())
  if not (p.parent/'summary-parser-v1.json').exists():save(p.parent/'summary-parser-v1.json',old)
  save(p,dict(status='PASS' if rows and all(r['status']=='PASS' for r in rows) else 'FAIL',records=len(rows),reanalysis=True))
if __name__=='__main__':reparse()
