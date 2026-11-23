"""Build callable fixed/dispatch APIs, count real linked code and validate them."""
import json,re,struct,subprocess,time
from pathlib import Path
from build import ROOT,HERE,OUT,GROUPS,ops
from run import sha,save
from model import TYPES,DEST,tile,exact_integer_mac,tile_expected,words
FAMILIES=((0,1),(2,3),(4,5,6),(7,8))

def source(group,members):
 lines=['#include <stdint.h>','#define NI __attribute__((noinline))']
 def body(op,word,poly=False):
  a=['{']
  if poly:a+=['uint64_t st=source_type,dt=destination_type;']
  else:a+=[f'uint64_t st={TYPES[op]}UL,dt={DEST[op]}UL;']
  if group=='P':
   a+=['__asm__ volatile("msettyp m0,%0"::"r"(st):"memory");']
   if op<7:a+=['__asm__ volatile("msettyp m4,%0"::"r"(st):"memory");']
   if op not in (4,5,6):a+=['__asm__ volatile("msettyp m8,%0"::"r"(dt):"memory");']
  if op in (4,5,6):a+=['__asm__ volatile("msettyp m12,%0\\n asettyp acc0,%0\\n mls.1r m12,%1\\n mmov.a.m acc0,m12"::"r"(dt),"r"(c):"memory");']
  a+=['__asm__ volatile("mls.1r m0,%0"::"r"(a):"memory");']
  if op<7:a+=['__asm__ volatile("mls.1r m4,%0"::"r"(b):"memory");']
  a += [f'for(unsigned i=0;i<repeat;++i)__asm__ volatile(".word 0x{word:08x}":::"memory");']
  if op in (4,5,6):a+=['__asm__ volatile("mmov.m.a m12,acc0\\n mss.1r m12,%0"::"r"(out):"memory");']
  else:a+=['__asm__ volatile("mss.1r m8,%0"::"r"(out):"memory");']
  a+=['}'];return '\n'.join(a)
 # Extract the raw computation words from the independent emitters.
 asm,_=ops(group);raw={}
 for name,word in re.findall(r'(compute_\d+_0):\n.word 0x([0-9a-f]+)',asm):raw[int(name.split('_')[1])]=int(word,16)
 if group=='P':
  for i,j in ((1,0),(3,2),(5,4),(6,4),(8,7)):raw[i]=raw[j]
 proto='const void *a,const void *b,const void *c,void *out,unsigned repeat'
 if group=='P':
  op=members[0]
  lines += ['static NI void common(uint64_t source_type,uint64_t destination_type,'+proto+')',body(op,raw[op],True)]
  for t,op in enumerate(members):lines += [f'NI void api_known_{t}('+proto+')'+f'{{common({TYPES[op]}UL,{DEST[op]}UL,a,b,c,out,repeat);}}']
  lines += [f'static const uint64_t types[{len(members)}][2]={{'+','.join('{'+f'{TYPES[o]}UL,{DEST[o]}UL'+'}' for o in members)+'};',
            'NI void api_runtime(unsigned type,'+proto+'){if(type<'+str(len(members))+')common(types[type][0],types[type][1],a,b,c,out,repeat);}']
 else:
  for t,op in enumerate(members):lines += [f'NI void api_known_{t}('+proto+')',body(op,raw[op])]
  lines += ['NI void api_runtime(unsigned type,'+proto+'){switch(type){']
  for t,_ in enumerate(members):lines += [f'case {t}:api_known_{t}(a,b,c,out,repeat);break;']
  lines += ['}}']
 return '\n'.join(lines)+'\n'

def build_apis():
 all_results=[];run=OUT/'api'/time.strftime('%Y%m%d-%H%M%S')
 for group in GROUPS:
  base=json.loads((OUT/'build'/group/'compile-command.json').read_text())
  cindex=next(i for i,x in enumerate(base) if x.endswith('/crt0.S'))
  flags=base[:cindex]
  flags=[x for x in flags if not x.startswith(('-Wl,','-nostdlib','-nostartfiles','-static'))]+['-ffunction-sections','-fdata-sections']
  for family,members in enumerate(FAMILIES):
   for count in range(1,len(members)+1):
    d=run/group/f'family{family}-types{count}';d.mkdir(parents=True)
    (d/'api.c').write_text(source(group,members[:count]))
    cmd=flags+['-c',str(d/'api.c'),'-o',str(d/'api.o')]
    with (d/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
    # Link all API entry points, no ICF/LTO/relaxation, no runtime/startup.
    cmd=[base[0],'-target','riscv64-unknown-elf','-march=rv64gv_xxiangshanztt','-mabi=lp64d','-nostdlib','-static','-Wl,--no-relax','-Wl,-e,api_runtime',str(d/'api.o'),'-o',str(d/'api.elf')]
    with (d/'link.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
    text=subprocess.check_output([ROOT/'toolchain/install/bin/llvm-objdump','-h',d/'api.elf'],text=True);(d/'sections.txt').write_text(text)
    sections={name:int(size,16) for name,size in re.findall(r'^\s*\d+\s+(\S+)\s+([0-9a-f]+)',text,re.M)}
    syms=subprocess.check_output([ROOT/'toolchain/install/bin/llvm-objdump','-t',d/'api.elf'],text=True);(d/'symbols.txt').write_text(syms)
    record=dict(group=group,family=family,types=count,ops=members[:count],text_bytes=sections.get('.text',0),rodata_bytes=sections.get('.rodata',0),data_bytes=sections.get('.data',0),bss_bytes=sections.get('.bss',0),elf_sha256=sha(d/'api.elf'),evidence=str(d.relative_to(ROOT)))
    if count==len(members):
     prototypes=['extern void api_runtime(unsigned,const void*,const void*,const void*,void*,unsigned);']+[f'extern void api_known_{i}(const void*,const void*,const void*,void*,unsigned);' for i in range(count)]
     gate=['#define main compare_main','#include "bench.c"','#undef main']+prototypes+['int main(int argc,char **argv){if(argc<2)return 2;FILE *f=fopen(argv[1],"w");if(!f)return 3;__asm__ volatile("li t0,0x3c\\n ame.acquire t1,t0":::"t0","t1","memory");cfg=&cases[0];']
     for repeat in (1,16):
      for t,op in enumerate(members):
       for mode in (0,1):
        call=f'api_runtime({t},ta,tb,tc,output,{repeat});' if mode else f'api_known_{t}(ta,tb,tc,output,{repeat});'
        gate += [f'make_tile({op},0);__asm__ volatile("csrw amefflags,zero":::"memory");'+call+'write_binary(f,output,64);']
     gate += ['fclose(f);return 0;}'];(d/'api_gate.c').write_text('\n'.join(gate))
     command=[x if not x.endswith('/bench.c') else str(d/'api_gate.c') for x in base]
     command=[x if not x.startswith('-Wl,-Map,') else '-Wl,-Map,'+str(d/'gate.map') for x in command]
     command.insert(command.index('-o'),str(d/'api.o'));command[command.index('-o')+1]=str(d/'gate.elf');command += ['-I'+str(HERE/'guest/common')]
     with (d/'gate-compile.log').open('w') as f:subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,check=True)
     command=[str(ROOT/'build/AME_B11/gem5.opt'),'-d',str(d/'m5out'),str(ROOT/'example/ame_config.py'),'--cmd',f'{d/"gate.elf"} {d/"gate.bin"}']
     save(d/'command.json',command)
     with (d/'simulate.log').open('w') as f:subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=600)
     raw=(d/'gate.bin').read_bytes();reference=[]
     for repeat in (1,16):
      for op in members:
       if op in (4,5,6):a,b,c=tile(op,0);r=exact_integer_mac(op,a,b,c,repeat)
       else:r,_=tile_expected(op,0,repeat)
       reference.extend([words(r),words(r)])
     record.update(status='PASS' if raw==b''.join(reference) else 'FAIL',checks=len(reference),report_sha256=sha(d/'gate.bin'))
    all_results.append(record)
    save(d/'result.json',record)
   print(group,family,'API built and checked',flush=True)
 save(run/'summary.json',dict(status='FAIL' if any(r.get('status')=='FAIL' for r in all_results) else 'PASS',results=all_results))
 if any(r.get('status')=='FAIL' for r in all_results):raise RuntimeError('API correctness failure')
if __name__=='__main__':
 build_apis()
 from size_entries import augment
 augment()
