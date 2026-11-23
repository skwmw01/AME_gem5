"""Paired known/runtime API timing with identical inputs and cold-call policy."""
import json,subprocess,time
from pathlib import Path
from api_size import FAMILIES
from build import ROOT,HERE,OUT,GROUPS
from run import save,analyse,sha

def run_api_perf():
 original=json.loads((OUT/'cases.json').read_text())[3];rows=[]
 latest=sorted((OUT/'api').glob('*/summary.json'))[-1].parent
 run=OUT/'api-perf'/time.strftime('%Y%m%d-%H%M%S')
 for group in GROUPS:
  for family,members in enumerate(FAMILIES):
   source=latest/group/f'family{family}-types{len(members)}';d=run/group/f'family{family}';d.mkdir(parents=True)
   proto=['extern void api_runtime(unsigned,const void*,const void*,const void*,void*,unsigned);']+[f'extern void api_known_{t}(const void*,const void*,const void*,void*,unsigned);' for t,_ in enumerate(members)]
   lines=['#define main compare_main','#include "bench.c"','#undef main']+proto+['static unsigned api_type,api_repeat;']
   for t,_ in enumerate(members):lines += [f'FN("kernel") static void thunk_{t}(void){{for(unsigned i=0;i<128;++i)api_known_{t}(ta,tb,tc,output,api_repeat);}}']
   lines += ['FN("kernel") static void dynamic(void){for(unsigned i=0;i<128;++i)api_runtime(api_type,ta,tb,tc,output,api_repeat);}',
    'int main(int argc,char **argv){if(argc<2)return 2;FILE *f=fopen(argv[1],"w");if(!f)return 3;__asm__ volatile("li t0,0x3c\\n ame.acquire t1,t0":::"t0","t1","memory");__asm__ volatile("csrw mtvec,%0"::"r"(trap_handler):"memory");cfg=&cases[0];unsigned id=0;',
    'for(unsigned seed=0;seed<10;++seed)for(unsigned batch=0;batch<2;++batch)for(unsigned t=0;t<'+str(len(members))+';++t)for(unsigned mode=0;mode<2;++mode){',
    'unsigned ops[]={'+','.join(str(x) for x in members)+'};api_type=t;api_repeat=batch?16:1;make_tile(ops[t],seed);traps=cause=trap_pc=trap_value=0;__asm__ volatile("csrw amefflags,zero\\n csrw fcsr,zero\\n csrw amexsat,zero":::"memory");',
    'void(*known[])(void)={'+','.join('thunk_'+str(t) for t,_ in enumerate(members))+'};uint64_t h[13]={0};measure(mode?dynamic:known[t],h+3);h[0]=id++;h[1]=16;h[2]=traps;__asm__ volatile("csrr %0,amefflags\\n csrr %1,fcsr\\n csrr %2,amexsat":"=r"(h[7]),"=r"(h[8]),"=r"(h[9])::"memory");h[10]=cause;h[11]=trap_pc;h[12]=trap_value;write_binary(f,h,sizeof(h));write_binary(f,output,64);}',
    'fclose(f);return 0;}']
   (d/'perf.c').write_text('\n'.join(lines))
   cases=[]
   for seed in range(10):
    for batch in (1,16):
     for t,op in enumerate(members):
      for mode in (0,1):cases.append(dict(original,id=len(cases),op=op,repeat=batch,seed=seed,pattern=mode,label='W3-api-'+('runtime' if mode else 'known'),outer=128,family=family))
   save(d/'cases.json',cases)
   cmd=json.loads((OUT/'build'/group/'compile-command.json').read_text());cmd=[str(d/'perf.c') if x.endswith('/bench.c') else '-Wl,-Map,'+str(d/'guest.map') if x.startswith('-Wl,-Map,') else x for x in cmd];cmd[cmd.index('-o')+1]=str(d/'guest.elf');cmd.insert(cmd.index('-o'),str(source/'api.o'));cmd += ['-I'+str(HERE/'guest/common')]
   with (d/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
   for flag,name in [('-d','disassembly.txt'),('-t','symbols.txt'),('-h','sections.txt')]:
    with (d/name).open('w') as f:subprocess.run([ROOT/'toolchain/install/bin/llvm-objdump',flag,d/'guest.elf'],stdout=f,check=True)
   cmd=[str(ROOT/'build/AME_B11/gem5.opt'),'--debug-flags=Exec','--debug-file=trace.gz','-d',str(d/'m5out'),str(ROOT/'example/ame_config.py'),'--cmd',f'{d/"guest.elf"} {d/"guest.bin"}']
   save(d/'command.json',cmd)
   with (d/'simulate.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=3600)
   records=analyse(d,group,cases,0,len(cases),True);rows+=records
   print(group,family,'API timing',len(records),'FAIL',sum(r['status']=='FAIL' for r in records),flush=True)
 save(run/'summary.json',dict(status='FAIL' if any(r['status']=='FAIL' for r in rows) else 'PASS',records=len(rows)))
 if any(r['status']=='FAIL' for r in rows):raise RuntimeError('API timing correctness failure')
if __name__=='__main__':run_api_perf()
