"""Generate data and raw-word ELF probes from each suite's own encoding table."""
import csv
import importlib
import json
import random
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def table(suite):
    with (ROOT / suite / 'encoding.csv').open() as f:
        return list(csv.DictReader(f))


def assembly(suite, chain=False):
    lines = ['.text', '.option norvc']
    for op, row in enumerate(table(suite)):
        for variant in range(4):
            # All sources are reloaded after descriptor setup by the harness.
            rd = 0 if chain or row['kind'] == 'mac' else [8, 0, 4, 30][variant]
            word = int(row['match'], 0) | rd << 7
            if row['kind'] in ('binary', 'mac'):
                word |= 4 << 20
            name = f'kernel_{op}_{variant}'
            lines += [f'.globl {name}', f'{name}:', f'.word 0x{word:08x}']
            if chain:
                second = (int(table(suite)[0]['match'],0) | 8<<7 | 1<<15 | 1<<20) if row['kind']=='wide' else word
                lines += [f'.word 0x{second:08x}']
            lines += ['ret']
    return '\n'.join(lines) + '\n'


def cases(suite, random_count=100):
    reference = importlib.import_module(suite + '.reference')
    output = []
    words = [0, 0x80000000, 1, 0x007fffff, 0x00800000, 0x7fffffff,
             0xffffffff, 0x7f7fffff, 0xff7fffff, 0x7f800000, 0xff800000,
             0x7fc12345, 0x7f800001, 0x3f000000, 0x3fc00000, 0x40200000,
             0xbf000000, 0xbfc00000, 0xc0200000, 0x4b800001, 0x4effffff,
             0x4f000000, 0xcf000000, 0xcf000001, 0x01000001, 0xfeffffff]
    halves = [0, 0x8000, 1, 0x03ff, 0x0400, 0x7bff, 0x7c00, 0xfc00,
              0x7e00, 0x7c01, 0x3c00, 0x3f80, 0x7f80, 0x7f81, 0x7fc0, 0x7f7f]
    def append(op, tag, a, b, c):
        result, flags = reference.execute(table(suite)[op]['mnemonic'], a, b, c)
        output.append(dict(op=op, tag=tag, a=a.hex(), b=b.hex(), c=c.hex(),
                           expected=result.hex(), flags=flags))
    for op, row in enumerate(table(suite)):
        if row['kind'] == 'mac':
            size = 1 if op == 4 else 2
            depth = 16 if size == 1 else 8
            av = [((r*7+k*3)%255) if size==1 else (0x3c00 if op==5 else 0x3f80) for r in range(4) for k in range(depth)]
            bv = [[(k*9+j*5+1)%255 if size==1 else ((0x3c00 if op==5 else 0x3f80)+(k+j)*3) for j in range(4)] for k in range(depth)]
            packed = [bv[k][j] for j in range(4) for k in range(depth)] if suite=='xuantie_v06' else [v for rowb in bv for v in rowb]
            a=b''.join(v.to_bytes(size,'little') for v in av)
            b=b''.join(v.to_bytes(size,'little') for v in packed)
            c=struct.pack('<16I',*range(16)) if size==1 else struct.pack('<16I',*([0x3f000000]*16))
            append(op,'same-logical-matmul',a,b,c)
        for shift in range(len(words)):
            a = struct.pack('<16I', *(words[(i+shift)%len(words)] for i in range(16)))
            b = struct.pack('<16I', *(words[(i*3+shift+1)%len(words)] for i in range(16)))
            c = struct.pack('<16I', *(words[(i*5+shift+2)%len(words)] for i in range(16)))
            if 'f16' in row['mnemonic']:
                a = struct.pack('<32H', *(halves[(i+shift)%16] for i in range(32)))
                b = struct.pack('<32H', *(halves[(3*i+shift)%16] for i in range(32)))
            append(op, f'boundary-{shift}', a, b, c)
        for seed in range(10):
            rng = random.Random(seed*100+op)
            for trial in range(random_count):
                blocks = [bytes(rng.getrandbits(8) for _ in range(64)) for _ in range(3)]
                append(op, f'seed-{seed}-{trial}', *blocks)
    # Every half input, including all signaling and quiet NaN payloads.
    stride = 16 if suite == 'xuantie_v06' else 32
    for start in range(0, 65536, stride):
        h = [0x3555]*32
        for n in range(stride):
            pos = (n//4)*8+n%4 if stride == 16 else n
            h[pos] = start+n
        append(9, f'exhaustive-half-{start}', struct.pack('<32H', *h), bytes(64), bytes(64))
    return output


def prepare(suite, destination, random_count=100, limit=0, chain=False):
    destination.mkdir(parents=True, exist_ok=True)
    records = cases(suite, random_count)
    if limit:
        records = records[:limit]
    if chain:
        reference=importlib.import_module(suite+'.reference')
        for r in records:
            first=bytes.fromhex(r['expected'])
            row=table(suite)[r['op']]
            if row['kind']=='wide':
                values=struct.unpack('<16I',first[64:])
                result=struct.pack('<16I',*((n*2)&0xffffffff for n in values))
                flags=0
            elif row['kind']=='mac':
                result,flags=reference.execute(row['mnemonic'],bytes.fromhex(r['a']),bytes.fromhex(r['b']),first)
            else:
                result,flags=reference.execute(row['mnemonic'],first,bytes.fromhex(r['b']),bytes.fromhex(r['c']))
            r['expected']=result.hex(); r['flags'] |= flags
    (destination / 'cases.json').write_text(json.dumps(records))
    # The oracle stays on the host; the guest never reads expected values.
    raw = b''.join(struct.pack('<II', r['op'], len(bytes.fromhex(r['expected']))) +
                   bytes.fromhex(r['a']+r['b']+r['c']) for r in records)
    (destination / 'inputs.bin').write_bytes(raw)
    (destination / 'data.S').write_text('.section .rodata\n.balign 64\n.globl test_data\ntest_data:\n'
        f'.incbin "{destination / "inputs.bin"}"\n.globl test_count\ntest_count:\n.word {len(records)}\n')
    (destination / 'kernels.S').write_text(assembly(suite,chain))
    return records
