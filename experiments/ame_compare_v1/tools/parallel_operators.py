"""Independent operator ranges, with per-group/range locks in run.py."""
import concurrent.futures,subprocess,sys
from build import ROOT,OUT,GROUPS

def job(task):
 group,start,end=task
 cmd=[sys.executable,str(ROOT/'experiments/ame_compare_v1/tools/run.py'),'run','--group',group,'--start',str(start),'--end',str(end),'--trace','--tag','formal']
 log=OUT/f'parallel-{group}-{start}-{end}.log'
 with log.open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
 print(group,start,end,'exit',r.returncode,flush=True)
 return r.returncode
if __name__=='__main__':
 tasks=[(g,a,b) for a,b in [(816,956),(956,1096),(1096,1176),(1176,1236)] for g in GROUPS]
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:codes=list(pool.map(job,tasks))
 if any(codes):raise SystemExit(1)
