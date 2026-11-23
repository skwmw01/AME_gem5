"""Run coordinate MAC probes and exhaustive half widening on all three groups."""
import json,struct,subprocess,time
from build import ROOT,HERE,OUT,GROUPS
from model import ieee,words,f32
from run import sha,save

def run_gates():
 run=OUT/'gates'/time.strftime('%Y%m%d-%H%M%S');results=[]
 for group in GROUPS:
  d=run/group;d.mkdir(parents=True)
  cmd=json.loads((OUT/'build'/group/'compile-command.json').read_text())
  old=next(x for x in cmd if x.endswith('/bench.c'));cmd[cmd.index(old)]=str(HERE/'guest/common/gates.c')
  cmd[cmd.index('-o')+1]=str(d/'guest.elf')
  cmd=[x if not x.startswith('-Wl,-Map,') else '-Wl,-Map,'+str(d/'guest.map') for x in cmd]
  with (d/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
  command=[str(ROOT/'build/AME_B11/gem5.opt'),'-d',str(d/'m5out'),str(ROOT/'example/ame_config.py'),'--cmd',f'{d/"guest.elf"} {d/"guest.bin"}']
  save(d/'command.json',command)
  with (d/'simulate.log').open('w') as f:subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1800)
  raw=(d/'guest.bin').read_bytes();pos=0;failures=[];counts={}
  while pos<len(raw):
   ident,op,i,j,k,status=struct.unpack_from('<6Q',raw,pos);pos+=48
   if op!=9:
    expected=[(n-8)-(6 if n==i*4+j else 0) for n in range(16)]
    actual=raw[pos:pos+64];pos+=64
    reference=words([x&0xffffffff if op==4 else f32(x) for x in expected]);flags=0
   else:
    r=[ieee.widen(v) for v in range(i,i+32)];flags=0
    for _,f in r:flags |= f
    values=[x[0] for x in r];double=[ieee.add(x,x)[0] for x in values[16:]]
    reference=words(values+double);actual=raw[pos:pos+192];pos+=192
   if actual!=reference or status!=(flags<<32):failures.append(dict(case=ident,op=op,i=i,j=j,k=k,status=status,flags=flags,actual=actual.hex(),expected=reference.hex()))
   counts[op]=counts.get(op,0)+1
  result=dict(group=group,status='FAIL' if failures else 'PASS',counts=counts,failures=failures,elf_sha256=sha(d/'guest.elf'),report_sha256=sha(d/'guest.bin'),half_patterns=65536,second_destination_consumers=2048)
  save(d/'result.json',result);results.append(result);print(group,result['status'],counts,flush=True)
 save(run/'summary.json',dict(status='PASS' if all(r['status']=='PASS' for r in results) else 'FAIL',results=results))
 if any(r['status']!='PASS' for r in results):raise RuntimeError('logical-layout gate failed')
if __name__=='__main__':run_gates()
