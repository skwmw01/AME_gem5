"""Negative decoder/access probes, including exact trap PC/mtval checks."""
from pathlib import Path
from common.generate import table


def generate(suite, directory):
    rows = table(suite)
    probes = []
    opcode = int(rows[0]['match'], 0) & 127
    # All reserved family/type combinations at the experimental opcode.
    for family in range(128):
        for typ in range(8):
            word = family << 25 | typ << 12 | opcode
            if not any(word & int(r['mask'],0) == int(r['match'],0) for r in rows):
                probes.append((word, 'reserved'))
    for row in rows:
        word = int(row['match'],0)
        if row['kind'] == 'mac':
            probes += [(word | rd << 7, 'invalid-acc') for rd in range(4,32)]
        elif row['kind'] in ('cvt','wide'):
            probes += [(word | rs2 << 20, 'reserved-rs2') for rs2 in range(1,32)]
        if row['kind'] == 'wide':
            probes.append((word | 31 << 7, 'invalid-span'))
    asm=['.text','.option norvc']
    for n,(word,_) in enumerate(probes):
        asm += [f'.globl negative_{n}',f'negative_{n}:',f'.word 0x{word:08x}','ret']
    (directory/'negative.S').write_text('\n'.join(asm)+'\n')
    declarations = '\n'.join(f'extern void negative_{n}(void);' for n in range(len(probes)))
    entries = ',\n'.join(f'{{negative_{n}, 0x{word:08x}}}' for n,(word,_) in enumerate(probes))
    (directory/'negative.h').write_text(declarations+'\nstruct Probe { void (*run)(void); uint32_t word; };\n'
        +'static const struct Probe probes[] = {\n'+entries+'\n};\n')
    return [dict(word=word,kind=kind) for word,kind in probes]
