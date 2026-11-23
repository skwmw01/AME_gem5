"""Compare compact/full commit trace calibration from the final guest ELF."""
import json,re
from build import OUT
from run import save,sha

def check():
 d=OUT/'tracer-check/final';results={}
 for mode in ('mini','text'):
  s=(d/mode/'stats.txt').read_text().split('---------- End Simulation Statistics')[0]
  r={k:int(re.search(r'^'+re.escape(k)+r'\s+(\d+)',s,re.M)[1]) for k in ('simInsts','simOps','simTicks','system.cpu.numCycles')}
  r['report']=sha(d/mode/'guest.bin');results[mode]=r
 assert results['mini']==results['text'],results
 r=dict(status='PASS',results=results,elf_sha256=sha(OUT/'build/P/guest.elf'),
        evidence='results/ame_compare_v1/tracer-check/final',
        note='Identical final guest ELF, input, ROI code and target counts; compact trace omits formatting only.')
 save(d/'calibration.json',r)
 environment=OUT/'environment.json';e=json.loads(environment.read_text());e['trace_format_calibration']=r;save(environment,e)
 print(json.dumps(r,indent=2))
if __name__=='__main__':check()
