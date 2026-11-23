import json,subprocess
from build import ROOT,HERE,OUT,GROUPS

def build_batched():
 for group in GROUPS:
  d=OUT/'batch-build'/group;d.mkdir(parents=True,exist_ok=True)
  source=OUT/'build'/group
  cmd=json.loads((source/'compile-command.json').read_text())
  cmd=[str(HERE/'guest/common/batched.c') if x.endswith('/bench.c') else '-Wl,-Map,'+str(d/'guest.map') if x.startswith('-Wl,-Map,') else x for x in cmd]
  cmd[cmd.index('-o')+1]=str(d/'guest.elf')
  with (d/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
  for flag,name in [('-d','disassembly.txt'),('-t','symbols.txt'),('-h','sections.txt')]:
   with (d/name).open('w') as f:subprocess.run([ROOT/'toolchain/install/bin/llvm-objdump',flag,d/'guest.elf'],stdout=f,check=True)
  for name in ('ops.S',):
   (d/name).write_bytes((source/name).read_bytes())
if __name__=='__main__':build_batched()
