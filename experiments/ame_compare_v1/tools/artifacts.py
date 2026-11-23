"""Verify saved run identities and retain command/stats/mapping hashes."""
import hashlib,json
from pathlib import Path
from build import ROOT,OUT
from run import save

def digest(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def audit():
 rows=json.loads((OUT/'selected-records.json').read_text())+json.loads((OUT/'batch-records.json').read_text())
 latest=sorted(OUT.glob('api-perf/*/summary.json'))[-1].parent
 rows += [r for p in latest.glob('*/*/records.json') for r in json.loads(p.read_text())]
 rows += [r for p in OUT.glob('runs/*formal-repeat-*/*/records.json') for r in json.loads(p.read_text())]
 dirs={}
 for row in rows:
  directory=ROOT/row['evidence']
  if directory.name=='records.json':directory=directory.parent
  dirs[str(directory)]=directory
 results=[]
 for directory in sorted(dirs.values()):
  names=('guest.elf','guest.bin','command.json','symbols.txt','disassembly.txt','sections.txt','m5out/config.ini','m5out/config.json','m5out/stats.txt','m5out/trace.gz')
  hashes={n:digest(directory/n) for n in names if (directory/n).exists()}
  errors=[n for n in names if n not in hashes]
  path=directory/'manifest.json'
  if path.exists():
   manifest=json.loads(path.read_text())
   for key,name in (('elf_sha256','guest.elf'),('report_sha256','guest.bin'),('config_sha256','m5out/config.ini')):
    if hashes.get(name)!=manifest[key]:errors.append(key+' mismatch')
  command=json.loads((directory/'command.json').read_text())
  if not command[0].endswith('/build/AME_B11/gem5.opt'):errors.append('wrong simulator')
  results.append(dict(directory=str(directory.relative_to(ROOT)),status='FAIL' if errors else 'PASS',errors=errors,command=command,files=hashes))
 result=dict(status='PASS' if len(rows)==5220 and all(r['status']=='PASS' for r in results) else 'FAIL',timing_records=len(rows),directories=len(results),results=results)
 save(OUT/'artifact-audit.json',result)
 print(result['status'],'records',len(rows),'directories',len(results),flush=True)
 if result['status']!='PASS':raise RuntimeError('artifact integrity check failed')
if __name__=='__main__':audit()
