"""Collect actual records; incomplete obligations stay NOT_RUN."""
import collections
import json
import re
import struct
import subprocess
from pathlib import Path

SUITES=('xuantie_v06','spec_v05a')


def collect(api):
    O,R=api.RESULTS,api.REPO
    checks=[]
    full_runs={}
    def read(path):
        return json.loads(path.read_text()) if path.exists() else None
    def add(name,passed,evidence,**extra):
        checks.append(dict(name=name,status='NOT_RUN' if passed is None else 'PASS' if passed else 'FAIL',evidence=evidence,**extra))
    for suite in SUITES:
        records=[(p,read(p)) for p in sorted((O/suite).glob('*/functional.json'))]
        full={}
        for build in (('B10','B11') if suite=='xuantie_v06' else ('B01','B11')):
            candidates=[(p,r) for p,r in records if r.get('random_per_seed')==100 and r.get('limit')==0 and not r.get('chain') and not r.get('disabled') and r['run'].endswith('AME_'+build)]
            selected=candidates[-1] if candidates else None
            if selected:
                p,r=selected;full[build]=r
                if build=='B11': full_runs[suite]=R/r['run']
                add(suite+' full '+build,r['status']=='PASS',str(p.relative_to(R)),executions=r['executions'])
            else:add(suite+' full '+build,None,'missing full record')
        if len(full)==2:
            add(suite+' single/dual equality',len({r['report_sha256'] for r in full.values()})==1,[r['run'] for r in full.values()])
            r=full['B11'];cases=read(R/r['run']/'cases.json');seeds=collections.Counter();halves=set()
            for c in cases:
                if c['tag'].startswith('seed-'):
                    seeds[(c['op'],int(c['tag'].split('-')[1]))]+=1
                if c['tag'].startswith('exhaustive-half-'):
                    values=struct.unpack('<32H',bytes.fromhex(c['a']))
                    halves.update(values[(i//4)*8+i%4] for i in range(16)) if suite=='xuantie_v06' else halves.update(values)
            add(suite+' random/exhaustive coverage',len(seeds)==100 and min(seeds.values())>=100 and len(halves)==65536,r['run'],random_cases=sum(seeds.values()),half_patterns=len(halves))
        for build in (('B00','B01') if suite=='xuantie_v06' else ('B00','B10')):
            selected=[(p,r) for p,r in records if r.get('disabled') and r['run'].endswith('AME_'+build) and r['cases']>=263]
            p,r=selected[-1] if selected else (None,None)
            add(suite+' disabled '+build,None if not r else r['status']=='PASS',str(p.relative_to(R)) if p else 'missing',executions=r['executions'] if r else 0)
        chains=[(p,r) for p,r in records if r.get('chain') and r['run'].endswith('AME_B11')]
        p,r=chains[-1] if chains else (None,None)
        add(suite+' dependencies',None if not r else r['status']=='PASS',str(p.relative_to(R)) if p else 'missing',executions=r['executions'] if r else 0)
        for category in ('checkpoint','negative_state','shape','storage','decode_fields'):
            p=O/suite/(category+'.json');r=read(p)
            add(suite+' '+category,None if not r else r['status']=='PASS',str(p.relative_to(R)),executions=(sum(len(f['traps']) for f in r['findings']) if category=='shape' else sum(len(o['checks']) for o in r['outcomes']) if category=='storage' else r.get('executions',r.get('denied_instructions',0))) if r else 0)
        for build in ('B00','B10','B01','B11'):
            selected=[(p,read(p)) for p in sorted((O/suite).glob('*-edge-AME_'+build+'/edge.json'))]
            p,r=selected[-1] if selected else (None,None)
            add(suite+' negative/access '+build,None if not r else r['status']=='PASS',str(p.relative_to(R)) if p else 'missing',executions=r['executions'] if r else 0)
    # Compare the same mathematical products after each suite's own packing.
    packing = []
    for suite, directory in full_runs.items():
        cases = read(directory/'cases.json')
        observations = list(struct.iter_unpack('<13Q128s', (directory/'guest.bin').read_bytes()))
        products = {}
        for i, case in enumerate(cases):
            if case['tag'] == 'same-logical-matmul':
                products[case['op']] = dict(case=case, result=[(r[6], r[13][:64]) for r in observations if r[0]==i])
        packing.append(products)
    passed = None
    if len(packing)==2:
        passed = set(packing[0])==set(packing[1])=={4,5,6}
        for op in (4,5,6):
            if op not in packing[0] or op not in packing[1]:
                continue
            x,y = packing[0][op], packing[1][op]
            passed &= (x['case']['a']==y['case']['a'] and x['case']['b']!=y['case']['b']
                       and x['case']['expected']==y['case']['expected']
                       and len(x['result'])==len(y['result'])==2 and x['result']==y['result'])
    add('same mathematical products with distinct B packing', passed,
        [str(p.relative_to(R)) for p in full_runs.values()], executions=6 if passed is not None else 0)
    for build in ('B00','B10','B01','B11'):
        p=O/(build+'-inspection.json');r=read(p)
        add(build+' compile/link/operands',None if not r else r['status']=='PASS',str(p.relative_to(R)))
    for phase,enabled in [('off-before',False),('on',True),('off-after',False)]:
        p=O/'incremental'/phase/'gem5.opt';c=p.parent/'config'
        ready=p.exists() and c.exists() and 'done building targets.' in (p.parent/'build.log').read_text()
        if not ready:
            add('incremental '+phase,None,str(p.relative_to(R)));continue
        config=c.read_text();actual=all('USE_'+name+'_EXPLICIT=y' in config for name in ('XUANTIE_V06','SPEC_V05A'))
        symbols=subprocess.check_output(['nm','-C',p],text=True)
        linked=(bool(re.search(r'\bX06::',symbols)),bool(re.search(r'\bS05A::',symbols)))
        passed=actual==enabled and linked==(enabled,enabled)
        evidence=[]
        for suite in SUITES:
            records=[(f,read(f)) for f in sorted((O/suite).glob('*-'+phase+'/functional.json'))]
            if not records:passed=None;continue
            f,r=records[-1];evidence.append(str(f.relative_to(R)))
            if passed is not None:passed &= r['status']=='PASS' and r['disabled'] != enabled
        add('incremental '+phase,passed,evidence,gem5_sha256=api.sha(p),linked=linked)
    final_config=R/'build/RISCV/gem5.build/config'
    final=final_config.read_text() if final_config.exists() else ''
    add('default switches restored off',all('# USE_'+n+'_EXPLICIT is not set' in final for n in ('XUANTIE_V06','SPEC_V05A')),str(final_config.relative_to(R)))
    for mutated,other in [('x06','s05'),('s05','x06')]:
        p=O/'fault_injection'/(mutated+'-mutated.json');q=O/'fault_injection'/(other+'-unaffected.json')
        a,b=read(p),read(q)
        passed=None if not a or not b else a['status']=='FAIL' and a['failed']>0 and all(f['op'] in (0,1) for f in a['failures']) and b['status']=='PASS'
        add(mutated+' fault isolation',passed,[str(p.relative_to(R)),str(q.relative_to(R))],expected_failures=a['failed'] if a else 0)
    for name,path in [('encoding audit',O/'encoding_audit.json'),('interleave P/X06/S05A',O/'interleave/interleave.json')]:
        r=read(path);add(name,None if not r else r['status']=='PASS',str(path.relative_to(R)))
    # Select the most recent completed record per exact frozen ELF/build pair.
    regressions={}
    for p in sorted((O/'regression').glob('*/regression.json')):
        for r in read(p)['results']:regressions[(r['elf'],r['build'])]=(r,str(p.relative_to(R)))
    expected_elfs=sorted(p.name for p in (O/'baseline/elf').iterdir())
    for elf in expected_elfs:
        selected=[regressions.get((elf,b)) for b in ('baseline','B00','B10','B01','B11')]
        passed=None if not all(selected) else all(r[0]['status']=='PASS' for r in selected)
        add('regression '+elf,passed,[r[1] for r in selected if r],builds=5)
    status='FAIL' if any(c['status']=='FAIL' for c in checks) else 'NOT_RUN' if any(c['status']=='NOT_RUN' for c in checks) else 'PASS'
    result=dict(status=status,checks=checks,summary=dict(collections.Counter(c['status'] for c in checks)))
    api.save(O/'acceptance.json',result)
    return result
