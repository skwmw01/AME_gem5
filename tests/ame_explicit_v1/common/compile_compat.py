import sys
from pathlib import Path
sys.path.insert(0,'tests/ame_explicit_v1')
from run import REPO,HERE,RESULTS,command,sha,save
clang=REPO/'toolchain/install/bin/clang'
resource=sorted((REPO/'toolchain/install/lib/clang').iterdir())[-1]
gcc=list((REPO/'toolchain/install').rglob('libgcc.a'))[0]
output=RESULTS/'baseline/elf/compat_rvv_scalar_m5'
command([clang,'-target','riscv64-unknown-elf','-resource-dir',resource,'-march=rv64gcv_xxiangshanztt','-mabi=lp64d','-O2','-g','-ffreestanding','-fno-builtin','-mcmodel=medany','-fno-vectorize','-fno-slp-vectorize','-nostdlib','-nostartfiles','-static','-I'+str(REPO/'example/common/include'),'-Wl,-T,'+str(REPO/'example/common/link.ld'),REPO/'example/common/crt0.S',HERE/'common/runtime.c',HERE/'regression/compat.c',gcc,'-o',output],RESULTS/'baseline/compat-compile.log')
save(RESULTS/'baseline/compat-manifest.json',dict(elf_sha256=sha(output),source_sha256=sha(HERE/'regression/compat.c')))
