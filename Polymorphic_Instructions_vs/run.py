#!/usr/bin/env python3
"""Build, run two independent trials per scheme, preserve evidence, analyze."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def capture(args, cwd=ROOT):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--smoke', action='store_true', help='R=1, all seven sequences')
    p.add_argument('--simulate-only', action='store_true', help='analyze later on host')
    p.add_argument('--gem5', type=Path, default=Path(os.environ.get(
        'AMEGEM5_GEM5', ROOT / 'build/RISCV/gem5.opt')))
    p.add_argument('--output', type=Path)
    group = p.add_mutually_exclusive_group()
    group.add_argument('--prepare-only', action='store_true')
    group.add_argument('--execute-prepared', action='store_true')
    args = p.parse_args()
    mode = 'smoke' if args.smoke else 'full'
    out = (args.output or HERE / 'build' / mode).resolve()
    manifest = out / 'environment.json'
    if args.execute_prepared:
        env = json.loads(manifest.read_text())
        if env['runs'] or env['mode'] != mode:
            raise SystemExit('prepared run already executed or mode differs')
        if sha256(args.gem5) != env['gem5_sha256']:
            raise SystemExit('simulator differs from preparation')
        if sha256(out / 'experiment.elf') != env['elf_sha256']:
            raise SystemExit('ELF differs from preparation')
    else:
        # Preserve previous runs, including partially failed runs, for review.
        if out.exists():
            raise SystemExit(f'{out} already exists; choose --output for a fresh run')
        subprocess.run(['make', '-B', 'all'], cwd=HERE, check=True)
        out.mkdir(parents=True)
        for name in ('experiment.elf', 'experiment.dis', 'experiment.symbols'):
            shutil.copy2(HERE / 'build' / name, out / name)
        sources = sorted(f for f in HERE.iterdir() if f.is_file())
        sources += [ROOT / 'example/common' / n for n in
                    ('crt0.S', 'runtime.c', 'link.ld')]
        (out / 'sources').mkdir()
        source_hashes = {}
        for path in sources:
            relative = str(path.relative_to(ROOT))
            source_hashes[relative] = sha256(path)
            dest = out / 'sources' / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
        tool_paths = capture(['make', '-s', 'tools'], HERE).splitlines()
        clang, objdump, linker, libgcc = ((HERE / path).resolve() for path in tool_paths)
        env = {
            'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'mode': mode, 'git_commit': capture(['git', 'rev-parse', 'HEAD']),
            'git_branch': capture(['git', 'branch', '--show-current']),
            'git_status': capture(['git', 'status', '--short']),
            'platform': platform.platform(), 'python': sys.version,
            'os_release': Path('/etc/os-release').read_text(),
            'gem5': str(args.gem5.resolve()), 'gem5_sha256': sha256(args.gem5),
            'elf_sha256': sha256(out / 'experiment.elf'),
            'static_artifacts_sha256': {name: sha256(out / name) for name in
                                       ('experiment.dis', 'experiment.symbols')},
            'source_sha256': source_hashes,
            'build_commands': capture(['make', '-Bn', 'all'], HERE),
            'clang_version': capture([str(clang), '--version']),
            'objdump_version': capture([str(objdump), '--version']),
            'toolchain_sha256': {str(path): sha256(path) for path in
                                (clang, objdump, linker, libgcc)},
            'runtime_image': os.environ.get('EXPERIMENT_RUNTIME_IMAGE'),
            'runs': [],
        }
        (out / 'source.diff').write_text(capture(['git', 'diff', 'HEAD']))
        manifest.write_text(json.dumps(env, indent=2) + '\n')
    if args.prepare_only:
        print(f'Prepared: {out}', flush=True)
        return
    env['runtime_platform'] = platform.platform()
    env['runtime_python'] = sys.version
    env['runtime_os_release'] = Path('/etc/os-release').read_text()
    env['runtime_image'] = os.environ.get('EXPERIMENT_RUNTIME_IMAGE')
    config = out / 'sources/Polymorphic_Instructions_vs/config.py'
    for scheme in ('specialized', 'shared'):
        for trial in (1, 2):
            folder = out / f'{scheme}-{trial}'
            folder.mkdir()
            cmd = [str(args.gem5.resolve()), '-d', str(folder),
                   '--debug-file=trace.gz', str(config),
                   '--cmd', f'{out / "experiment.elf"} {folder / "results.bin"} {scheme} {mode}']
            if any(' ' in str(x) for x in (out, HERE)):
                raise SystemExit('bare-metal command paths must not contain spaces')
            print(f'Running {scheme}, trial {trial}, {mode}: {folder}', flush=True)
            started = time.monotonic()
            with (folder / 'gem5.log').open('w') as log:
                completed = subprocess.run(cmd, cwd=ROOT, stdout=log,
                                           stderr=subprocess.STDOUT)
            entry = {'scheme': scheme, 'trial': trial, 'command': cmd,
                     'returncode': completed.returncode,
                     'wall_seconds': time.monotonic() - started}
            env['runs'].append(entry)
            if completed.returncode == 0:
                entry['artifacts_sha256'] = {
                    name: sha256(folder / name) for name in
                    ('trace.gz', 'results.bin', 'stats.txt', 'config.ini', 'gem5.log')}
            manifest.write_text(json.dumps(env, indent=2) + '\n')
            if completed.returncode:
                raise SystemExit((folder / 'gem5.log').read_text()[-6000:])
            print(f'Finished in {entry["wall_seconds"]:.1f}s', flush=True)
    if not args.simulate_only:
        subprocess.run([sys.executable, str(HERE / 'analyze.py'), str(out)], check=True)
    print(f'Evidence saved: {out}', flush=True)


if __name__ == '__main__':
    main()
