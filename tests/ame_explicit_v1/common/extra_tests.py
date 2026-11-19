import sys,struct,json
from pathlib import Path
sys.path.insert(0,'tests/ame_explicit_v1')
import run
from run import REPO,HERE,RESULTS,command,sha,save,compile_guest
clang=REPO/'toolchain/install/bin/clang';resource=sorted((REPO/'toolchain/install/lib/clang').iterdir())[-1];gcc=list((REPO/'toolchain/install').rglob('libgcc.a'))[0]
for suite,opcode in [('xuantie_v06',0x2b),('spec_v05a',0x77)]:
 d=RESULTS/'baseline'/('native-'+suite)
 records,probes=compile_guest(suite,d,0,263)
 elf=bytearray((d/'guest.elf').read_bytes())
 phoff=struct.unpack_from('<Q',elf,32)[0];phsize,phnum=struct.unpack_from('<HH',elf,54)
 headers=[struct.unpack_from('<II6Q',elf,phoff+n*phsize) for n in range(phnum)]
 for v in probes.values():
  pc=v['pc'];h=next(h for h in headers if h[0]==1 and h[3]<=pc<h[3]+h[5])
  offset=h[2]+pc-h[3];old=struct.unpack_from('<I',elf,offset)[0]
  struct.pack_into('<I',elf,offset,(old&~127)|opcode)
 out=RESULTS/'baseline/elf'/('native_primary_'+suite);out.write_bytes(elf)
 save(d/'mutation.json',dict(opcode=opcode,elf_sha256=sha(out),probes=probes,note='Original-primary mutation, baseline behavior is the oracle.'))
d=RESULTS/'interleave';d.mkdir(exist_ok=True)
command([clang,'-target','riscv64-unknown-elf','-resource-dir',resource,'-march=rv64gcv_xxiangshanztt','-mabi=lp64d','-O2','-g','-ffreestanding','-fno-builtin','-mcmodel=medany','-fno-vectorize','-fno-slp-vectorize','-nostdlib','-nostartfiles','-static','-I'+str(REPO/'example/common/include'),'-Wl,-T,'+str(REPO/'example/common/link.ld'),REPO/'example/common/crt0.S',HERE/'common/runtime.c',HERE/'common/interleave.c',HERE/'common/trap.S',HERE/'xuantie_v06/kernels.S',gcc,'-o',d/'guest.elf'],d/'compile.log')
command([REPO/'build/AME_B11/gem5.opt','-d',d/'m5out',REPO/'example/ame_config.py','--cmd',f'{d/"guest.elf"} {d/"guest.txt"}'],d/'simulate.log',1800)
lines=(d/'guest.txt').read_text().splitlines();passed=len(lines)==200 and all(l.split()[-1]=='1' for l in lines)
save(d/'interleave.json',dict(status='PASS' if passed else 'FAIL',executions=len(lines),elf_sha256=sha(d/'guest.elf'),report_sha256=sha(d/'guest.txt')))
print('interleave',passed)
