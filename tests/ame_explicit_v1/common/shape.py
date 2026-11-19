"""Change only capability CSR values in a real checkpoint, then resume probes."""
import configparser
import hashlib
import json
import re
import shutil
from pathlib import Path


def run_shape(api, args):
    REPO,HERE,RESULTS=api.REPO,api.HERE,api.RESULTS
    run=RESULTS/args.suite/(api.time.strftime('%Y%m%d-%H%M%S')+'-shape')
    run.mkdir(parents=True,exist_ok=True)
    clang=REPO/'toolchain/install/bin/clang'
    resource=sorted((REPO/'toolchain/install/lib/clang').iterdir())[-1]
    gcc=list((REPO/'toolchain/install').rglob('libgcc.a'))[0]
    api.command([clang,'-target','riscv64-unknown-elf','-resource-dir',resource,
        '-march=rv64gcv_xxiangshanztt','-mabi=lp64d','-O2','-g','-ffreestanding',
        '-fno-builtin','-mcmodel=medany','-fno-vectorize','-fno-slp-vectorize',
        '-nostdlib','-nostartfiles','-static','-DSHAPE_TEST',
        '-I'+str(REPO/'example/common/include'),'-Wl,-T,'+str(REPO/'example/common/link.ld'),
        REPO/'example/common/crt0.S',HERE/'common/runtime.c',
        HERE/'common/checkpoint_guest.c',HERE/'common/trap.S',HERE/args.suite/'kernels.S',
        gcc,'-o',run/'guest.elf'],run/'compile.log')
    gem5=Path(args.gem5).resolve()
    cmdline=f'{run/"guest.elf"} {run/"guest.txt"}'
    api.command(['env','AME_CHECKPOINT_ROOT='+str(run/'initial'),'AME_STOP_AFTER_CHECKPOINT=1',
        gem5,'-d',run/'initial-out',HERE/'common/checkpoint_config.py','--cmd',cmdline],run/'initial.log',1800)
    raw=(REPO/'src/arch/riscv/regs/misc.hh').read_text().split('enum MiscRegIndex')[1].split('};')[0]
    names=re.findall(r'\bMISCREG_\w+',re.sub(r'//[^\n]*','',raw))
    tracked=[names.index(n) for n in names if n.startswith('MISCREG_AME') or n in ('MISCREG_FRM','MISCREG_FFLAGS')]
    def state(path):
        c=configparser.ConfigParser(interpolation=None);c.read(path)
        matrix=next(v for sec in c.values() for k,v in sec.items() if k=='regs.matrix')
        misc=next(v for sec in c.values() for k,v in sec.items() if k=='miscregfile').split()
        return dict(matrix=hashlib.sha256(matrix.encode()).hexdigest(),csr=[misc[n] for n in tracked])
    findings=[]
    for field,value in [('MISCREG_AMENLEN',8),('MISCREG_AMEUDSZ',16)]:
        destination=run/field
        shutil.copytree(run/'initial/0',destination/'restore')
        p=destination/'restore/m5.cpt';text=p.read_text()
        def patch(m):
            items=m[1].split();items[names.index(field)]=str(value)
            return 'miscRegFile='+' '.join(items)
        text=re.sub(r'^miscRegFile=(.*)$',patch,text,flags=re.M);p.write_text(text)
        before=state(p)
        (run/'guest.txt').write_bytes(b'')
        api.command(['env','AME_CHECKPOINT_ROOT='+str(destination/'snapshots'),'AME_RESTORE='+str(destination/'restore'),
            gem5,'-d',destination/'m5out',HERE/'common/checkpoint_config.py','--cmd',cmdline],destination/'run.log',1800)
        lines=(run/'guest.txt').read_text().splitlines()
        shutil.copyfile(run/'guest.txt',destination/'guest.txt')
        after=[state(destination/'snapshots'/str(n)/'m5.cpt') for n in range(10)]
        passed=len(lines)==10 and all(line.split()[-1]=='1' for line in lines) and all(s==before for s in after)
        findings.append(dict(field=field,value=value,status='PASS' if passed else 'FAIL',traps=lines,before=before,after=after))
    result=dict(status='PASS' if all(f['status']=='PASS' for f in findings) else 'FAIL',findings=findings,run=str(run.relative_to(REPO)),elf_sha256=api.sha(run/'guest.elf'),gem5_sha256=api.sha(gem5))
    api.save(run/'shape.json',result);api.save(RESULTS/args.suite/'shape.json',result)
    print(result['status'],run)
    if result['status']!='PASS': raise RuntimeError('shape validation failed')
