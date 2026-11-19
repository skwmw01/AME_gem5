"""Replay real checkpoints with poisoned container tails and invalid types."""
import configparser
import hashlib
import importlib
import json
import re
import shutil
from pathlib import Path
from common.generate import table


def run_storage(api,args):
    R,H,O=api.REPO,api.HERE,api.RESULTS
    shape=json.loads((O/args.suite/'shape.json').read_text())
    source=R/shape['run']
    d=O/args.suite/(api.time.strftime('%Y%m%d-%H%M%S')+'-storage');d.mkdir(parents=True)
    raw=(R/'src/arch/riscv/regs/misc.hh').read_text().split('enum MiscRegIndex')[1].split('};')[0]
    names=re.findall(r'\bMISCREG_\w+',re.sub(r'//[^\n]*','',raw))
    tracked=[names.index(n) for n in names if n.startswith('MISCREG_AME') or n in ('MISCREG_FRM','MISCREG_FFLAGS','MISCREG_MCAUSE','MISCREG_MEPC','MISCREG_MTVAL')]
    def read(path):
        c=configparser.ConfigParser(interpolation=None);c.read(path)
        matrix=next(v for sec in c.values() for k,v in sec.items() if k=='regs.matrix')
        misc=next(v for sec in c.values() for k,v in sec.items() if k=='miscregfile')
        return bytearray(map(int,matrix.split())),list(map(int,misc.split()))
    reference=importlib.import_module(args.suite+'.reference')
    outcomes=[]
    for invalid in (False,True):
        dest=d/('invalid-types' if invalid else 'matching-types')
        shutil.copytree(source/'initial/0',dest/'restore')
        p=dest/'restore/m5.cpt';data,csrs=read(p)
        if len(data)%72: raise RuntimeError('register bank structure changed')
        size=len(data)//72
        for reg in range(36):data[reg*size+64:(reg+1)*size]=bytes([0xa5])*(size-64)
        if invalid:
            for reg in range(36,72):data[reg*size:reg*size+8]=bytes([0xff])*8
            csrs[names.index('MISCREG_AMESTYPE')]=(1<<64)-1
        text=p.read_text();text=re.sub(r'^regs.matrix=.*$',lambda m:'regs.matrix='+' '.join(map(str,data)),text,flags=re.M)
        text=re.sub(r'^miscRegFile=.*$',lambda m:'miscRegFile='+' '.join(map(str,csrs)),text,flags=re.M);p.write_text(text)
        (source/'guest.txt').write_bytes(b'')
        gem5=Path(args.gem5).resolve()
        api.command(['env','AME_CHECKPOINT_ROOT='+str(dest/'snapshots'),'AME_RESTORE='+str(dest/'restore'),gem5,'-d',dest/'m5out',H/'common/checkpoint_config.py','--cmd',f'{source/"guest.elf"} {source/"guest.txt"}'],dest/'run.log',1800)
        shutil.copyfile(source/'guest.txt',dest/'guest.txt')
        checks=[]
        for op,row in enumerate(table(args.suite)):
            target=32 if row['kind']=='mac' else 8
            value,flags=reference.execute(row['mnemonic'],bytes(data[:64]),bytes(data[4*size:4*size+64]),bytes(data[32*size:32*size+64]))
            data[target*size:target*size+64]=value[:64]
            if len(value)==128:data[9*size:9*size+64]=value[64:]
            csrs[names.index('MISCREG_AMEFFLAGS')] |= flags
            observed,actual_csrs=read(dest/'snapshots'/str(op)/'m5.cpt')
            passed=data==observed and all(csrs[n]==actual_csrs[n] for n in tracked)
            checks.append(dict(instruction=row['mnemonic'],status='PASS' if passed else 'FAIL',
                expected_matrix_sha256=hashlib.sha256(data).hexdigest(),actual_matrix_sha256=hashlib.sha256(observed).hexdigest(),
                csr_differences={names[n]:[csrs[n],actual_csrs[n]] for n in tracked if csrs[n]!=actual_csrs[n]}))
        outcomes.append(dict(invalid_descriptors=invalid,register_count=72,bytes_per_register=size,checks=checks))
    result=dict(status='PASS' if all(c['status']=='PASS' for o in outcomes for c in o['checks']) else 'FAIL',outcomes=outcomes,run=str(d.relative_to(R)),gem5_sha256=api.sha(gem5))
    api.save(d/'storage.json',result);api.save(O/args.suite/'storage.json',result)
    print(result['status'],d)
    if result['status']!='PASS':raise RuntimeError('full storage state check failed')
