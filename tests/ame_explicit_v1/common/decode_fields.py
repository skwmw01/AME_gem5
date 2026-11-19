"""Execute every legal register-field tuple and verify its traced mnemonic."""
import collections
import re
import struct
from pathlib import Path
from common.generate import table


def run_fields(api,args):
    R,H,O=api.REPO,api.HERE,api.RESULTS
    d=O/args.suite/(api.time.strftime('%Y%m%d-%H%M%S')+'-all-fields');d.mkdir(parents=True)
    words=[];expected=[]
    for row in table(args.suite):
        for rd in range(4 if row['kind']=='mac' else 31 if row['kind']=='wide' else 32):
            for rs1 in range(32):
                for rs2 in range(1 if row['kind'] in ('cvt','wide') else 32):
                    words.append(int(row['match'],0)|rd<<7|rs1<<15|rs2<<20)
                    expected.append(row['mnemonic'])
    (d/'words.bin').write_bytes(struct.pack('<'+'I'*len(words),*words))
    (d/'fields.S').write_text('.text\n.option norvc\n.globl fields\nfields:\n'+f'.incbin "{d/"words.bin"}"\n.globl fields_end\nfields_end:\nret\n')
    (d/'guest.c').write_text('''#include <stdint.h>
#include <stdio.h>
volatile uint64_t traps,cause,trap_pc,trap_value;
extern void fields(void); extern void trap_handler(void);
int main(int argc,char **argv) {
 if(argc<2)return 2;
 FILE *f=fopen(argv[1],"w");if(!f)return 3;
 __asm__ volatile("li t0,0x3c\\n ame.acquire t1,t0":::"t0","t1","memory");
 __asm__ volatile("csrw mtvec,%0"::"r"(trap_handler):"memory");
 fields();
 uint64_t flags;__asm__ volatile("csrr %0,amefflags":"=r"(flags));
 fprintf(f,"%lu %lu\\n",traps,flags);fclose(f);return traps||flags;
}
''')
    clang=R/'toolchain/install/bin/clang';resource=sorted((R/'toolchain/install/lib/clang').iterdir())[-1];gcc=list((R/'toolchain/install').rglob('libgcc.a'))[0]
    api.command([clang,'-target','riscv64-unknown-elf','-resource-dir',resource,'-march=rv64gcv_xxiangshanztt','-mabi=lp64d','-O2','-g','-ffreestanding','-fno-builtin','-mcmodel=medany','-nostdlib','-nostartfiles','-static','-I'+str(R/'example/common/include'),'-Wl,-T,'+str(R/'example/common/link.ld'),R/'example/common/crt0.S',H/'common/runtime.c',H/'common/trap.S',d/'guest.c',d/'fields.S',gcc,'-o',d/'guest.elf'],d/'compile.log')
    api.command([R/'toolchain/install/bin/llvm-objdump','-t',d/'guest.elf'],d/'symbols.txt')
    syms=(d/'symbols.txt').read_text();start=int(re.search(r'^([0-9a-f]+) .*\bfields$',syms,re.M)[1],16)
    gem5=Path(args.gem5).resolve()
    api.command([gem5,'--debug-flags=ExecEnable,ExecKernel,ExecOpClass','--debug-file='+str(d/'trace.txt'),'-d',d/'m5out',R/'example/ame_config.py','--cmd',f'{d/"guest.elf"} {d/"guest.txt"}'],d/'simulate.log',3600)
    seen=[];errors=[]
    with (d/'trace.txt').open() as f:
        for line in f:
            m=re.search(r'0x([0-9a-f]+)\s+:\s+(\S+)',line)
            if not m:continue
            pc=int(m[1],16)
            if start<=pc<start+4*len(words):
                n=(pc-start)//4
                if m[2]!=expected[n] or not re.search(r':\s+Matrix\s*:',line):
                    errors.append(dict(index=n,expected=expected[n],trace=line.strip()))
                seen.append(n)
    if seen!=list(range(len(words))):errors.append(dict(error='missing, reordered or repeated instruction records',count=len(seen),expected=len(words)))
    result=dict(status='FAIL' if errors else 'PASS',executions=len(seen),by_instruction=dict(collections.Counter(expected)),errors=errors,
                run=str(d.relative_to(R)),elf_sha256=api.sha(d/'guest.elf'),words_sha256=api.sha(d/'words.bin'),trace_sha256=api.sha(d/'trace.txt'),gem5_sha256=api.sha(gem5))
    api.save(d/'decode_fields.json',result);api.save(O/args.suite/'decode_fields.json',result)
    print(result['status'],len(seen))
    if errors:raise RuntimeError('actual decode field sweep failed')
