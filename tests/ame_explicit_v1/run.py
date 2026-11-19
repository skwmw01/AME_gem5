#!/usr/bin/env python3
"""Reproducible dual-subset validation. Missing evidence never means PASS."""
import argparse
import csv
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time
from common.generate import table, prepare, assembly

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RESULTS = REPO / 'results/ame_explicit_v1'
SUITES = ('xuantie_v06', 'spec_v05a')
BASE = '6677b2c8f6e76363050427009d47c5481f9e53bf'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda: f.read(1024*1024), b''):
            h.update(data)
    return h.hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    temporary.replace(path)


def command(args, log, timeout=None):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w') as f:
        p = subprocess.run([str(x) for x in args], cwd=REPO, stdout=f,
                           stderr=subprocess.STDOUT, timeout=timeout)
    with (RESULTS / 'commands.log').open('a') as f:
        f.write(json.dumps(dict(time=time.time(), argv=[str(x) for x in args],
                                returncode=p.returncode, log=str(log)))+'\n')
    if p.returncode:
        raise RuntimeError(f'{args[0]} exited {p.returncode}: {log}')


def audit(args):
    rows = [(s, r) for s in SUITES for r in table(s)]
    errors = []
    checked = 0
    for suite in SUITES:
        if len(table(suite)) != 10:
            errors.append(f'{suite}: expected ten encodings')
        if (HERE/suite/'kernels.S').exists() and (HERE/suite/'kernels.S').read_text() != assembly(suite):
            errors.append(f'{suite}: stale ELF probe source')
    for i, (suite, row) in enumerate(rows):
        match, mask = int(row['match'], 0), int(row['mask'], 0)
        if match & ~mask:
            errors.append(row['mnemonic']+': noncanonical match')
        for _, other in rows[i+1:]:
            if not ((match ^ int(other['match'], 0)) & mask & int(other['mask'], 0)):
                errors.append(row['mnemonic']+': overlap with '+other['mnemonic'])
        for rd in range(4 if row['kind'] == 'mac' else 31 if row['kind']=='wide' else 32):
            for rs1 in range(32):
                for rs2 in range(1 if row['kind'] in ('cvt', 'wide') else 32):
                    word = match | rd << 7 | rs1 << 15 | rs2 << 20
                    hits = [r['mnemonic'] for _, r in rows if word & int(r['mask'],0) == int(r['match'],0)]
                    if hits != [row['mnemonic']]:
                        errors.append(f'{word:08x}: {hits}')
                    checked += 1
    # Preserve scope: every tracked old file except six integration points.
    allowed = {'src/arch/riscv/'+p for p in ('Kconfig', 'SConscript',
        'isa/formats/formats.isa','isa/decoder.isa','isa/includes.isa','isa/operands.isa')}
    changed = subprocess.check_output(['git','diff',BASE,'--name-only','--diff-filter=M'], cwd=REPO, text=True).splitlines()
    errors += ['protected baseline file changed: '+p for p in changed if p not in allowed and not p.startswith(('tests/ame_explicit_v1/','docs/ame_explicit_v1/'))]
    dependencies = {}
    for suite, other in [('xuantie_v06','S05A'),('spec_v05a','X06')]:
        paths = [REPO/f'src/arch/riscv/insts/{suite}_explicit.{ext}' for ext in ('cc','hh')]
        paths += [REPO/f'src/arch/riscv/isa/{part}/{suite}_explicit.isa' for part in ('formats','decoder')]
        findings = []
        for p in paths:
            hits = re.findall(r'\b(?:ztt\w+|Ztt\w+|'+other+r'\w*)\b', p.read_text())
            if hits:
                findings.append(dict(file=str(p.relative_to(REPO)), hits=hits))
        dependencies[suite] = findings
        errors += [f'{suite}: forbidden dependency {f}' for f in findings]
    report = dict(status='FAIL' if errors else 'PASS', rules=len(rows), legal_field_combinations=checked,
                  errors=errors, tables={s:sha(HERE/s/'encoding.csv') for s in SUITES},
                  note='Table/field audit; actual decoder and ELF validation recorded separately.')
    save(RESULTS/'encoding_audit.json', report)
    save(RESULTS/'independence.json', dict(static_dependencies=dependencies,
         static_status='FAIL' if any(dependencies.values()) else 'PASS',
         generated_code='NOT_RUN', fault_injection='NOT_RUN'))
    print(json.dumps(report, indent=2))
    if errors: raise RuntimeError('audit failed')


def compile_guest(suite, directory, count, limit=0, chain=False):
    records = prepare(suite, directory, count, limit, chain)
    clang = REPO/'toolchain/install/bin/clang'
    resource = sorted((REPO/'toolchain/install/lib/clang').iterdir())[-1]
    gcc = list((REPO/'toolchain/install').rglob('libgcc.a'))[0]
    cmd = [clang,'-target','riscv64-unknown-elf','-resource-dir',resource,
        '-march=rv64gcv_xxiangshanztt','-mabi=lp64d','-O2','-g',
        '-ffreestanding','-fno-builtin','-mcmodel=medany','-fno-vectorize',
        '-fno-slp-vectorize','-nostdlib','-nostartfiles','-static',
        '-I'+str(REPO/'example/common/include'),
        '-Wl,-T,'+str(REPO/'example/common/link.ld'),
        REPO/'example/common/crt0.S',HERE/'common/runtime.c',
        HERE/'common/guest.c',HERE/'common/trap.S',directory/'kernels.S',
        directory/'data.S',gcc,'-o',directory/'guest.elf']
    if chain: cmd += ['-DCHAIN_TEST']
    if suite=='spec_v05a': cmd += ['-DS05A_TEST']
    command(cmd, directory/'compile.log')
    # Parse symbol addresses and raw instruction bytes; no mnemonic dependency.
    objdump = REPO/'toolchain/install/bin/llvm-objdump'
    command([objdump,'-d',directory/'guest.elf'], directory/'disassembly.txt')
    dis = (directory/'disassembly.txt').read_text()
    probes = {}
    for op, row in enumerate(table(suite)):
        for variant in range(4):
            symbol = f'kernel_{op}_{variant}'
            m = re.search(r'([0-9a-f]+) <'+symbol+r'>:\n\s*[0-9a-f]+:\s*([0-9a-f]{8}|(?:[0-9a-f]{2} ){3}[0-9a-f]{2})',dis)
            if not m: raise RuntimeError('missing ELF probe '+symbol)
            actual = int(m[2],16) if ' ' not in m[2] else int.from_bytes(bytes.fromhex(m[2]),'little')
            rd = 0 if chain or row['kind']=='mac' else [8,0,4,30][variant]
            expected = int(row['match'],0) | rd<<7 | (4<<20 if row['kind'] in ('binary','mac') else 0)
            if actual != expected: raise RuntimeError(f'ELF encoding mismatch {symbol}')
            probes[symbol] = dict(pc=int(m[1],16),word=actual)
    save(directory/'elf_audit.json',dict(status='PASS',probes=probes,elf_sha256=sha(directory/'guest.elf')))
    return records, probes


def functional(args):
    gem5 = Path(args.gem5).resolve()
    run = RESULTS/args.suite/(time.strftime('%Y%m%d-%H%M%S')+'-'+gem5.parent.name)
    records, probes = compile_guest(args.suite, run, args.random_count, args.limit, args.chain)
    guest_report = run/'guest.bin'
    command([gem5,'-d',run/'m5out',REPO/'example/ame_config.py',
             '--cmd',f'{run/"guest.elf"} {guest_report}'],run/'simulate.log',3600)
    raw = guest_report.read_bytes()
    if len(raw) % 232:
        raise RuntimeError('incomplete binary guest record')
    observations = list(struct.iter_unpack('<13Q128s',raw))
    failures = []
    for index, fields in enumerate(observations):
        case, mode = fields[:2]
        if case >= len(records) or mode not in (0,1):
            raise RuntimeError('corrupt guest record identity')
        r = records[case]
        actual = dict(zip(('traps','cause','pc','mtval','flags','fcsr','dtype','stype','sat','scalar','adtype'),fields[2:13]))
        actual['data'] = fields[13][:len(bytes.fromhex(r['expected']))].hex()
        src_types = [0x40000020,0x20300120,0x40000020,0x20,0x40000008,0x14300110,0x20300110,0x40000020,0x20300120,0x14300110]
        dst_types = [0x40000020,0x20300120,0x40000020,0x20,0x40000020,0x20300120,0x20300120,0x20300120,0x40000020,0x20300120]
        expected_type = src_types[r['op']]
        expected_ad = dst_types[r['op']]
        if mode:
            expected_type = 0x20300120 if expected_type==0x20 else 0x20
            expected_ad = 0x20300120 if expected_ad==0x20 else 0x20
        expected = dict(traps=0,cause=0,pc=0,mtval=0,flags=r['flags']|8,
                        fcsr=((case%5)<<5)|3,dtype=expected_type,stype=expected_type,sat=0,scalar=0x3f800001 if case%5 in (3,4) else 0x3f800000,adtype=expected_ad,data=r['expected'])
        if args.disabled:
            probe = probes[f'kernel_{r["op"]}_{case%4}']
            variant = case%4
            before = r['c'] if r['op'] in (4,5,6) else r['a'] if variant==1 else r['b'] if variant==2 else 'a5'*64
            # Extra untouched register for wide aliases has no defined preload yet.
            expected.update(traps=1,cause=2,pc=probe['pc'],mtval=probe['word'],flags=8,data=before)
            if len(r['expected'])==256:
                expected['data'] += 'a5'*64
        if actual != expected:
            failures.append(dict(case=case,mode=mode,tag=r['tag'],op=r['op'],actual=actual,expected=expected))
    if len(observations) != len(records)*2:
        failures.append(dict(error='missing/extra guest records',actual=len(observations),expected=len(records)*2))
    result = dict(status='FAIL' if failures else 'PASS',suite=args.suite,disabled=args.disabled,chain=args.chain,
        cases=len(records),executions=len(observations),random_per_seed=args.random_count,limit=args.limit,failed=len(failures),failures=failures,
        gem5_sha256=sha(gem5),elf_sha256=sha(run/'guest.elf'),inputs_sha256=sha(run/'inputs.bin'),
        oracle_sha256=sha(run/'cases.json'),report_sha256=sha(guest_report),run=str(run.relative_to(REPO)))
    save(run/'functional.json',result)
    save(RESULTS/args.suite/'functional.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='failures'},indent=2))
    if failures: raise RuntimeError(f'{len(failures)} mismatches; see {run}/functional.json')


def edge(args):
    from common.edge_generate import generate
    run=RESULTS/args.suite/(time.strftime('%Y%m%d-%H%M%S')+'-edge-'+Path(args.gem5).parent.name)
    run.mkdir(parents=True,exist_ok=True)
    probes=generate(args.suite,run)
    clang=REPO/'toolchain/install/bin/clang'
    resource=sorted((REPO/'toolchain/install/lib/clang').iterdir())[-1]
    gcc=list((REPO/'toolchain/install').rglob('libgcc.a'))[0]
    command([clang,'-target','riscv64-unknown-elf','-resource-dir',resource,
        '-march=rv64gcv_xxiangshanztt','-mabi=lp64d','-O2','-g','-ffreestanding',
        '-fno-builtin','-mcmodel=medany','-fno-vectorize','-fno-slp-vectorize',
        '-nostdlib','-nostartfiles','-static','-I'+str(REPO/'example/common/include'),
        '-I'+str(run),'-Wl,-T,'+str(REPO/'example/common/link.ld'),
        REPO/'example/common/crt0.S',HERE/'common/runtime.c',
        HERE/'common/edge_guest.c',HERE/'common/trap.S',HERE/args.suite/'kernels.S',
        run/'negative.S',gcc,'-o',run/'guest.elf'],run/'compile.log')
    gem5=Path(args.gem5).resolve()
    command([gem5,'-d',run/'m5out',REPO/'example/ame_config.py',
        '--cmd',f'{run/"guest.elf"} {run/"guest.txt"}'],run/'simulate.log',1800)
    lines=(run/'guest.txt').read_text().splitlines()
    failures=[line for line in lines if line.split()[2 if line.startswith('negative') else 3]!='1']
    if len(lines)!=len(probes)+20: failures.append('missing observations')
    result=dict(status='FAIL' if failures else 'PASS',executions=len(lines),
        failures=failures,probes=len(probes),run=str(run.relative_to(REPO)),
        elf_sha256=sha(run/'guest.elf'),gem5_sha256=sha(gem5),
        owner_state_observation='NOT_RUN: architectural reads forbidden; reacquire clears registers')
    save(run/'edge.json',result)
    save(RESULTS/args.suite/'edge.json',result)
    print(json.dumps(result,indent=2))
    if failures: raise RuntimeError('negative/access probes failed')


def checkpoint(args):
    import configparser
    run=RESULTS/args.suite/(time.strftime('%Y%m%d-%H%M%S')+'-checkpoint-'+Path(args.gem5).parent.name)
    run.mkdir(parents=True,exist_ok=True)
    clang=REPO/'toolchain/install/bin/clang'
    resource=sorted((REPO/'toolchain/install/lib/clang').iterdir())[-1]
    gcc=list((REPO/'toolchain/install').rglob('libgcc.a'))[0]
    kernel=HERE/args.suite/'kernels.S'
    extra=[]
    count=22
    if args.negative:
        extra=['-DSHAPE_TEST']
        count=11
        lines=['.text','.option norvc']
        for op,row in enumerate(table(args.suite)):
            word=int(row['match'],0)
            if row['kind']=='mac': word |= 4<<7
            elif row['kind']=='wide': word |= 31<<7
            elif row['kind']=='cvt': word |= 1<<20
            else: word=(word&~0x7000)|0x7000
            for variant in range(4):
                lines += [f'.globl kernel_{op}_{variant}',f'kernel_{op}_{variant}:',f'.word 0x{word:08x}','ret']
        kernel=run/'negative-kernels.S'
        kernel.write_text('\n'.join(lines)+'\n')
    command([clang,'-target','riscv64-unknown-elf','-resource-dir',resource,
        '-march=rv64gcv_xxiangshanztt','-mabi=lp64d','-O2','-g','-ffreestanding',
        '-fno-builtin','-mcmodel=medany','-fno-vectorize','-fno-slp-vectorize',
        '-nostdlib','-nostartfiles','-static','-I'+str(REPO/'example/common/include'),
        '-Wl,-T,'+str(REPO/'example/common/link.ld'),
        REPO/'example/common/crt0.S',HERE/'common/runtime.c',
        HERE/'common/checkpoint_guest.c',HERE/'common/trap.S',kernel,
        gcc,'-o',run/'guest.elf']+extra,run/'compile.log')
    gem5=Path(args.gem5).resolve()
    command(['env','AME_CHECKPOINT_ROOT='+str(run/'snapshots'),gem5,'-d',run/'m5out',
        HERE/'common/checkpoint_config.py','--cmd',f'{run/"guest.elf"} {run/"guest.txt"}'],run/'simulate.log',1800)
    text=(REPO/'src/arch/riscv/regs/misc.hh').read_text().split('enum MiscRegIndex')[1].split('};')[0]
    text=re.sub(r'//[^\n]*','',text)
    names=re.findall(r'\bMISCREG_\w+',text)
    tracked={n:names.index(n) for n in ['MISCREG_AMESTATUS','MISCREG_AMENLEN','MISCREG_AMEUDSZ','MISCREG_AMESTYPE','MISCREG_AMEOWN','MISCREG_AMEFFLAGS','MISCREG_AMEXSAT','MISCREG_FRM','MISCREG_FFLAGS']}
    observed=[]
    for n in range(count):
        p=run/'snapshots'/str(n)/'m5.cpt'
        config=configparser.ConfigParser(interpolation=None)
        config.read(p)
        matrix=[v for sec in config.values() for k,v in sec.items() if k=='regs.matrix']
        misc=[v for sec in config.values() for k,v in sec.items() if k=='miscregfile']
        if len(matrix)!=1 or len(misc)!=1: raise RuntimeError('missing checkpoint register banks')
        regs=misc[0].split()
        observed.append(dict(matrix=hashlib.sha256(matrix[0].encode()).hexdigest(),
            matrix_bytes=len(matrix[0].split()),csr={key:regs[idx] for key,idx in tracked.items()}))
    failures=[]
    for start in ((0,) if args.negative else (0,11)):
        for n in range(start+1,start+11):
            if observed[n]!=observed[start]: failures.append(dict(snapshot=n,before=observed[start],after=observed[n]))
    lines=(run/'guest.txt').read_text().splitlines()
    failures += [line for line in lines if line.split()[-1]!='1']
    if len(lines)!=count-count//11: failures.append('missing trap observations')
    result=dict(status='FAIL' if failures else 'PASS',snapshots=count,negative=args.negative,denied_instructions=count-count//11,
        failures=failures,observed=observed,elf_sha256=sha(run/'guest.elf'),gem5_sha256=sha(gem5),run=str(run.relative_to(REPO)))
    save(run/'checkpoint.json',result); save(RESULTS/args.suite/('negative_state.json' if args.negative else 'checkpoint.json'),result)
    print(json.dumps({k:v for k,v in result.items() if k!='observed'},indent=2))
    if failures: raise RuntimeError('checkpoint state differs after denied instruction')


def shape(args):
    from common.shape import run_shape
    run_shape(sys.modules[__name__],args)


def fields(args):
    from common.decode_fields import run_fields
    run_fields(sys.modules[__name__],args)


def storage(args):
    from common.storage import run_storage
    run_storage(sys.modules[__name__],args)


def build_matrix(args):
    outcomes = []
    for name,x,s in [('B00','n','n'),('B10','y','n'),('B01','n','y'),('B11','y','y')]:
        target = Path(args.build_root)/('AME_'+name)
        log = RESULTS/'builds'/name
        command(['scons','defconfig',target,'build_opts/RISCV'],log/'defconfig.log')
        command(['scons','setconfig',target,'USE_XUANTIE_V06_EXPLICIT='+x,
                 'USE_SPEC_V05A_EXPLICIT='+s],log/'setconfig.log')
        try:
            command(['scons',target/'gem5.opt','-j'+str(args.jobs)],log/'build.log')
            from common.inspect_build import inspect
            inspection = inspect(target, x == 'y', s == 'y')
            inspection.update(build=name, sha256=sha(target/'gem5.opt'),
                              config=(target/'gem5.build/config').read_text())
            save(RESULTS/(name+'-inspection.json'), inspection)
            outcomes.append(inspection)
        except RuntimeError as e:
            outcomes.append(dict(build=name,status='FAIL',error=str(e)))
        save(RESULTS/'build_matrix.json',dict(builds=outcomes,incremental='NOT_RUN',
             decode='NOT_RUN',link_isolation='NOT_RUN'))
    if any(r['status']!='PASS' for r in outcomes): raise RuntimeError('build matrix failed')


def regression(args):
    baseline = Path(args.baseline).resolve()
    frozen = RESULTS/'baseline/elf'
    results = []
    run_id=time.strftime('%Y%m%d-%H%M%S')
    shared=RESULTS/'regression/shared'
    shared.mkdir(parents=True,exist_ok=True)
    if not baseline.exists() or not frozen.exists():
        save(RESULTS/'regression.json',dict(status='NOT_RUN',reason='missing frozen baseline/ELFs'))
        return
    simulators = [('baseline',baseline)]+[(n,Path(args.build_root).resolve()/('AME_'+n)/'gem5.opt') for n in ('B00','B10','B01','B11')]
    for elf in sorted(frozen.iterdir()):
        if args.elf and elf.name != args.elf: continue
        reference = None
        for name,sim in simulators:
            run = RESULTS/'regression'/run_id/elf.name/name
            report_path=shared/(elf.name+'.txt')
            if not sim.exists():
                results.append(dict(elf=elf.name,build=name,status='NOT_RUN')); continue
            try:
                command([sim,'-d',run/'m5out',REPO/'example/ame_config.py',
                         '--cmd',f'{elf} {report_path}'],run/'run.log',1800)
                shutil.copyfile(report_path,run/'report.txt')
                stats = (run/'m5out/stats.txt').read_text().split('---------- Begin Simulation Statistics ----------')[-1]
                selected = dict(re.findall(r'^(simInsts|simOps|simTicks|system.cpu.numCycles)\s+(\d+)',stats,re.M))
                if set(selected) != {'simInsts','simOps','simTicks','system.cpu.numCycles'}:
                    raise RuntimeError('missing deterministic statistics in final section')
                observed = dict(report=sha(run/'report.txt'),stats=selected)
                if name=='baseline': reference=observed
                results.append(dict(elf=elf.name,build=name,status='PASS' if observed==reference else 'FAIL',observed=observed,reference=reference))
            except Exception as e:
                results.append(dict(elf=elf.name,build=name,status='FAIL',error=str(e)))
    result=dict(status='PASS' if results and all(r['status']=='PASS' for r in results) else 'FAIL',results=results,run=run_id)
    save(RESULTS/'regression'/run_id/'regression.json',result)
    save(RESULTS/'regression.json',result)


def acceptance(args):
    from common.acceptance import collect
    result=collect(sys.modules[__name__])
    print(json.dumps(result['summary'],indent=2))
    print(result['status'])
    if result['status'] != 'PASS':
        raise RuntimeError('acceptance incomplete or failed; see acceptance.json')


def report(args):
    from common.reporting import generate_report
    generate_report(sys.modules[__name__], args)


def main():
    parser=argparse.ArgumentParser(__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('audit')
    sub.add_parser('acceptance')
    f=sub.add_parser('functional'); f.add_argument('--suite',choices=SUITES,required=True)
    f.add_argument('--gem5',required=True); f.add_argument('--random-count',type=int,default=100)
    f.add_argument('--chain',action='store_true'); f.add_argument('--disabled',action='store_true'); f.add_argument('--limit',type=int,default=0)
    e=sub.add_parser('edge'); e.add_argument('--suite',choices=SUITES,required=True); e.add_argument('--gem5',required=True)
    c=sub.add_parser('checkpoint'); c.add_argument('--suite',choices=SUITES,required=True); c.add_argument('--gem5',required=True); c.add_argument('--negative',action='store_true')
    sh=sub.add_parser('shape'); sh.add_argument('--suite',choices=SUITES,required=True); sh.add_argument('--gem5',required=True)
    fi=sub.add_parser('fields'); fi.add_argument('--suite',choices=SUITES,required=True); fi.add_argument('--gem5',required=True)
    st=sub.add_parser('storage'); st.add_argument('--suite',choices=SUITES,required=True); st.add_argument('--gem5',required=True)
    b=sub.add_parser('build-matrix'); b.add_argument('--build-root',default='build'); b.add_argument('--jobs',type=int,default=8)
    r=sub.add_parser('regression'); r.add_argument('--baseline',required=True); r.add_argument('--build-root',default='build'); r.add_argument('--elf')
    sub.add_parser('report').add_argument('--results',default=str(RESULTS))
    args=parser.parse_args()
    RESULTS.mkdir(parents=True,exist_ok=True)
    globals()[args.command.replace('-','_')](args)

if __name__=='__main__': main()
