import csv,json,subprocess,sys
from pathlib import Path
from cases import population
ROOT=Path(__file__).resolve().parents[3]; HERE=ROOT/'experiments/ame_compare_v1'; OUT=ROOT/'results/ame_compare_v1'
GROUPS=('P','X06','S05A')

def ops(group,control=False):
 if group=='P':matches=[0x0400002b,0x0400002b,0x0c00002b,0x0c00002b,0x9e00002b,0x9e00002b,0x9e00002b,0xa200002b|(13<<20),0xa200002b|(13<<20),0xa200002b|(13<<20)]
 else:
  suite='xuantie_v06' if group=='X06' else 'spec_v05a'
  matches=[int(r['match'],0) for r in csv.DictReader((ROOT/'tests/ame_explicit_v1'/suite/'encoding.csv').open())]
 lines=['.option norvc','.option norelax'];defs=[]
 for op,match in enumerate(matches):
  for bank in (0,1):
   name=f'compute_{op}_{bank}';a=16 if bank else 0;b=20 if bank else 4;d=24 if bank else 8
   if op in (4,5,6):d=0
   if group=='P' and not control and op in (1,3,5,6,8,9):
    alias={1:0,3:2,5:4,6:4,8:7,9:7}[op]
    lines += [f'.globl {name}',f'.set {name},compute_{alias}_{bank}']
   else:
    word=match|(d<<7)|(a<<15)|((b<<20) if op<7 else 0)
    lines += [f'.section .text.compute_{op}_{bank},"ax"','.balign 64',f'.globl {name}',f'.type {name},@function',name+':',f'.word 0x{word:08x}']
    if op==9 and group=='X06':lines += [f'.word 0x{match|(9<<7)|(1<<15):08x}']
    lines += ['ret',f'.size {name},.-{name}']
   defs.append('extern void '+name+'(void);')
 # Whole compute loops keep R/config loads and type dispatch out of the inner loop.
 for op,match in enumerate(matches):
  for bank in (0,1):
   aa=16 if bank else 0;bb=20 if bank else 4;dd=0 if op in (4,5,6) else 24 if bank else 8
   word=match|(dd<<7)|(aa<<15)|((bb<<20) if op<7 else 0)
   for mode in ('repeat','mixed','gemm'):
    name=f'{mode}_{op}_{bank}'
    proto='unsigned' if mode=='repeat' else 'const void*,const void*,unsigned'
    defs.append('extern void '+name+'('+proto+');')
    if group=='P' and not control and op in (1,3,5,6,8,9):
     alias={1:0,3:2,5:4,6:4,8:7,9:7}[op]
     lines += [f'.globl {name}',f'.set {name},{mode}_{alias}_{bank}'];continue
    lines += [f'.section .text.compute_{name},"ax"','.balign 64',f'.globl {name}',f'.type {name},@function',name+':',f'.L_{name}:']
    if mode!='repeat':
     lines += [f'mls.1r m{aa},a0']
     if op<7:lines += [f'mls.1r m{bb},a1']
    lines += [f'.word 0x{word:08x}']
    if op==9 and group=='X06':lines += [f'.word 0x{match|((dd+1)<<7)|((aa+1)<<15):08x}']
    if mode=='gemm':lines += ['addi a0,a0,64','addi a1,a1,64']
    counter='a0' if mode=='repeat' else 'a2'
    lines += [f'addi {counter},{counter},-1',f'bnez {counter},.L_{name}','ret',f'.size {name},.-{name}']
 for name,op,rd,rs1,rs2 in [('pipeline_max',2,9,8,4),('pipeline_add',1,8,8,4),('pipeline_convert',8,9,8,0)]:
  word=matches[op]|rd<<7|rs1<<15|((rs2<<20) if op<7 else 0)
  lines += [f'.section .text.compute_{name},"ax"','.balign 64',f'.globl {name}',f'.type {name},@function',name+':',f'.word 0x{word:08x}','ret',f'.size {name},.-{name}']
  defs.append('extern void '+name+'(void);')
 return '\n'.join(lines)+'\n','\n'.join(defs)+'\n'

def build():
 OUT.mkdir(parents=True,exist_ok=True);cases=population();(OUT/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
 keys=[k for k in cases[0] if k!='label'];h=['#include <stdint.h>','struct Case {'+' '.join('uint32_t '+k+';' for k in keys)+'};',f'#define CASE_COUNT {len(cases)}','static const struct Case cases[]={']
 h += ['{'+','.join(str(c[k]) for k in keys)+'},' for c in cases];h += ['};']
 clang=ROOT/'toolchain/install/bin/clang';resource=sorted((ROOT/'toolchain/install/lib/clang').iterdir())[-1];gcc=list((ROOT/'toolchain/install').rglob('libgcc.a'))[0]
 for control in (False,True):
  for g,group in enumerate(GROUPS):
   build_one(control,g,group,cases,h,clang,resource,gcc)

def build_one(control,g,group,cases,h,clang,resource,gcc):
  d=OUT/('control-build' if control else 'build')/group;d.mkdir(parents=True,exist_ok=True);(d/'cases.h').write_text('\n'.join(h));asm,header=ops(group,control);(d/'ops.S').write_text(asm);(d/'ops.h').write_text(header)
  cmd=[str(clang),'-target','riscv64-unknown-elf','-resource-dir',str(resource),'-march=rv64gv_xxiangshanztt','-mabi=lp64d','-O2','-g','-ffreestanding','-fno-builtin','-mcmodel=medany','-fno-vectorize','-fno-slp-vectorize','-ffp-contract=off','-mno-relax','-nostdlib','-nostartfiles','-static','-I'+str(ROOT/'example/common/include'),'-I'+str(d),'-DGROUP='+str(g),'-DCONTROL='+str(int(control)),'-Wl,-T,'+str(HERE/'guest/common/link.ld'),'-Wl,-Map,'+str(d/'guest.map'),str(ROOT/'example/common/crt0.S'),str(ROOT/'tests/ame_explicit_v1/common/runtime.c'),str(ROOT/'tests/ame_explicit_v1/common/trap.S'),str(HERE/'guest/common/measure.S'),str(HERE/'guest/common/bench.c'),str(d/'ops.S'),str(gcc),'-o',str(d/'guest.elf')]
  (d/'compile-command.json').write_text(json.dumps(cmd,indent=2)+'\n')
  with (d/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
  for flag,name in [('-d','disassembly.txt'),('-t','symbols.txt'),('-h','sections.txt')]:
   with (d/name).open('w') as f:subprocess.run([ROOT/'toolchain/install/bin/llvm-objdump',flag,d/'guest.elf'],stdout=f,check=True)
  print(group,'built',flush=True)
if __name__=='__main__':build()
