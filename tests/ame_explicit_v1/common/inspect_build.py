"""Inspect generated dependency declarations and actual link symbols."""
import json
from pathlib import Path
import re
import subprocess


def inspect(build, x06, s05a):
    generated = build/'arch/riscv/generated'
    constructors = (generated/'decoder-ns.cc.inc').read_text()
    execution = (generated/'exec-ns.cc.inc').read_text()
    errors, dependencies = [], []
    for prefix, enabled in [('Xt06_',x06),('Sp05a_',s05a)]:
        names = sorted(set(re.findall(r'\b('+prefix+r'\w+)::\1\(', constructors)))
        if len(names)!=10: errors.append(f'{prefix}: {len(names)} parsed classes, expected 10')
        for name in names:
            match=re.search(r'\b'+name+r'::'+name+r'\(.*?(?=\n//|\Z)',constructors,re.S)
            code=match.group()
            sources=code.count('setSrcRegIdx(')
            targets=code.count('setDestRegIdx(')
            wide=name=='Sp05a_cvt_f32_f16'
            conversion='_cvt' in name
            expected=(3,2) if wide else (2,1) if conversion else (3,1)
            if (sources,targets)!=expected:
                errors.append(f'{name}: operands {(sources,targets)} != {expected}')
            if 'DataReg' in code: errors.append(f'{name}: descriptor dependency')
            body=re.search(r'\b'+name+r'::execute\(.*?(?=\n//|\Z)',execution,re.S).group()
            if re.search(r'\bztt\w+\(',body): errors.append(f'{name}: Ztt behavior call')
            other='S05A::' if prefix=='Xt06_' else 'X06::'
            if other in body: errors.append(f'{name}: cross-suite behavior call')
            dependencies.append(dict(instruction=name,sources=sources,destinations=targets,enabled=enabled))
    symbols=subprocess.check_output(['nm','-C',build/'gem5.opt'],text=True)
    found_x=bool(re.search(r'\bX06::|\bXt06_\w+::execute',symbols))
    found_s=bool(re.search(r'\bS05A::|\bSp05a_\w+::execute',symbols))
    if (found_x,found_s)!=(x06,s05a): errors.append('linked extension symbols disagree with configuration')
    return dict(status='FAIL' if errors else 'PASS',errors=errors,dependencies=dependencies,
                symbols={'X06':found_x,'S05A':found_s})
