"""Link each callable entry with section GC; exclude unreachable startup/API code."""
import json,re,subprocess
from pathlib import Path
from build import ROOT,OUT
from run import save,sha

def augment():
 summary=sorted(OUT.glob('api/*/summary.json'))[-1];data=json.loads(summary.read_text())
 for r in data['results']:
  d=ROOT/r['evidence'];sizes={}
  for name in ['api_runtime']+['api_known_'+str(i) for i in range(r['types'])]:
   elf=d/(name+'.elf')
   cmd=[str(ROOT/'toolchain/install/bin/clang'),'-target','riscv64-unknown-elf','-march=rv64gv_xxiangshanztt','-mabi=lp64d','-nostdlib','-static','-Wl,--no-relax','-Wl,--gc-sections','-Wl,-e,'+name,str(d/'api.o'),'-o',str(elf)]
   subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)
   text=subprocess.check_output([ROOT/'toolchain/install/bin/llvm-objdump','-h',elf],text=True)
   (d/(name+'-sections.txt')).write_text(text)
   s={k:int(v,16) for k,v in re.findall(r'^\s*\d+\s+(\S+)\s+([0-9a-f]+)',text,re.M)}
   sizes[name]=dict(text_bytes=s.get('.text',0),rodata_bytes=s.get('.rodata',0),data_bytes=s.get('.data',0),bss_bytes=s.get('.bss',0),elf_sha256=sha(elf))
  r['entries']=sizes;save(d/'result.json',r)
 save(summary,data)
if __name__=='__main__':augment()
