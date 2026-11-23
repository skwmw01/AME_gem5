"""Logical-layout exact oracle; no simulated backend or suite adapter calls."""
import sys, struct, random
from pathlib import Path
import importlib.util
_scalar_path=Path(__file__).resolve().parents[3]/'tests/ame_explicit_v1/common/ieee.py'
_spec=importlib.util.spec_from_file_location('ame_compare_ieee',_scalar_path)
ieee=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ieee)
TASKS=('A1','A2','M1','M2','G1','G2','G3','C1','C2','C3')
TYPES=(0x40000020,0x20300120,0x40000020,0x20,0x40000008,0x14300110,0x20300110,0x40000020,0x20300120,0x14300110)
DEST=(0x40000020,0x20300120,0x40000020,0x20,0x40000020,0x20300120,0x20300120,0x20300120,0x48000020,0x20300120)

def values(seed,n):
 x=seed+1;out=[]
 for _ in range(n):
  x ^= (x<<13)&0xffffffff;x ^= x>>17;x ^= (x<<5)&0xffffffff;x &= 0xffffffff
  out.append(x%7-3)
 return out

def f32(n):return struct.unpack('<I',struct.pack('<f',n))[0]
def half(n,bf=False):return (f32(n)>>16) if bf else struct.unpack('<H',struct.pack('<e',n))[0]
def ints(raw):return struct.unpack('<'+'I'*(len(raw)//4),raw)
def words(data):return struct.pack('<'+'I'*len(data),*data)

def scalar(op,x,y):
 if op==0:return (x+y)&0xffffffff,0
 if op==1:return ieee.add(x,y)
 if op==2:return (x if (x^0x80000000)>=(y^0x80000000) else y),0
 if op==3:return max(x,y),0
 if op==7:return ieee.int_to_float(x)
 if op==8:return ieee.float_to_int(x)
 raise ValueError(op)

def tile(op,seed):
 v=values(seed,144)
 if op in (4,5,6):
  k=16 if op==4 else 8
  a=v[:4*k];b=v[64:64+k*4];c=v[128:144]
  return a,b,c
 a=[n&0xffffffff for n in v[:16]];b=[n&0xffffffff for n in v[16:32]]
 if op in (1,8):a=[f32(n*0.5) for n in v[:16]]
 if op==1:b=[f32(n*0.5) for n in v[16:32]]
 if op==9:a=[half(n*0.5) for n in v[:32]]
 return a,b,[0]*16

def pack_mac(group,a,b,op):
 k=16 if op==4 else 8;size=1 if op==4 else 2
 aa=[0]*(4*k);bb=[0]*(4*k)
 for i in range(4):
  for t in range(k):
   ai=(t//4)*16+i*4+t%4 if group=='P' else i*k+t
   aa[ai]=a[i*k+t]
 for t in range(k):
  for j in range(4):
   bi=(t//4)*16+j*4+t%4 if group=='P' else j*k+t if group=='X06' else t*4+j
   bb[bi]=b[t*4+j]
 def enc(v):return bytes(n&255 for n in v) if size==1 else struct.pack('<32H',*(half(n,op==6) for n in v))
 return enc(aa),enc(bb)

def mac(op,a,b,c,repeats=1):
 k=16 if op==4 else 8;out=list(c);flags=0
 for _ in range(repeats):
  for i in range(4):
   for j in range(4):
    z=out[i*4+j]
    for t in range(k):
     x,y=a[i*k+t],b[t*4+j]
     if op==4:z=(z+x*y)&0xffffffff
     else:
      x,xf=ieee.widen(half(x,op==6),op==6);y,yf=ieee.widen(half(y,op==6),op==6)
      z,f=ieee.fma(x,y,z);flags |= xf|yf|f
    out[i*4+j]=z
 return out,flags

def tile_expected(op,seed,repeats=1):
 a,b,c=tile(op,seed)
 if op in (4,5,6):return mac(op,a,b,[n&0xffffffff if op==4 else f32(n) for n in c],repeats)
 if op==9:
  r=[ieee.widen(n) for n in a];return [x[0] for x in r],sum(set(x[1] for x in r))
 r=[scalar(op,x,y) for x,y in zip(a,b)];flags=0
 for _,f in r:flags |= f
 return [x[0] for x in r],flags

def exact_integer_mac(op,a,b,c,repeats=1):
 """All benchmark operands are integers |x|<=3; sums stay below 2**24.
 Each product and each sequential FP32 FMA is therefore exact, including
 the largest W4 matrix and W2/W3 accumulations. No host float arithmetic.
 """
 k=16 if op==4 else 8
 assert max(map(abs,a+b),default=0)<=3
 assert max(map(abs,c),default=0)+9*k*repeats<2**24
 sums=[sum(a[i*k+t]*b[t*4+j] for t in range(k))*repeats+c[i*4+j] for i in range(4) for j in range(4)]
 assert max(map(abs,sums)) < 2**24
 return [x&0xffffffff if op==4 else ieee.int_to_float(x&0xffffffff)[0] for x in sums]


def expected(c,group):
 op=c['op'];work=c['work'];flags=0
 if work==0:return words([0]*16),0
 if work==1:
  a,b,initial=tile(op,c['seed'])
  if op in (4,5,6):out=exact_integer_mac(op,a,b,initial,c['repeat'])
  else:out,flags=tile_expected(op,c['seed'],c['repeat'])
  return words(out),flags
 if work in (2,3):
  ops=([0,1],[2,3],[4,5,6],[7,8])[op]
  if work==2 and op==2:ops=[5,6]
  types=len(ops);blocks=c['repeat']//c['batch']
  if op==2:assert 3+9*16*c['repeat']<2**24
  seq=[(i//(blocks//types))%types if c['pattern']==0 else i%types for i in range(blocks)]
  if c['pattern']==2:
   x=c['seed']+101
   for i in range(blocks-1,0,-1):
    x ^= (x<<13)&0xffffffff;x ^= x>>17;x ^= (x<<5)&0xffffffff;x &=0xffffffff
    j=x%(i+1);seq[i],seq[j]=seq[j],seq[i]
  result=[0]*96
  # prepare retains the C generated for the final type, then initializes once.
  cumulative=tile(ops[-1],c['seed']+types-1)[2] if op==2 else [0]*16
  per_type=[tile(o,c["seed"]+t)[2] for t,o in enumerate(ops)]
  for t in seq:
   operation=ops[t]
   if op==2:
    if work==3:cumulative=per_type[t]
    a,b,_=tile(operation,c['seed']+t);k=16 if operation==4 else 8
    cumulative=[cumulative[i*4+j]+sum(a[i*k+z]*b[z*4+j] for z in range(k))*c['batch'] for i in range(4) for j in range(4)]
    assert max(map(abs,cumulative))<2**24
    r=[x&0xffffffff if operation==4 else ieee.int_to_float(x&0xffffffff)[0] for x in cumulative]
    if work==3:per_type[t]=cumulative
   else:r,f=tile_expected(operation,c['seed']+t);flags |= f
   result[t*32:t*32+16]=r
  return words(result),flags
 if work==4:
  m,n,k=c['m'],c['n'],c['k'];v=values(c['seed'],m*k+k*n+m*n);a=v[:m*k];b=v[m*k:m*k+k*n];initial=v[m*k+k*n:]
  assert 3+9*k<2**24
  result=[]
  for i in range(m):
   for j in range(n):
    val=(initial[i*n+j] if c['c0'] else 0)+sum(a[i*k+t]*b[t*n+j] for t in range(k))
    assert abs(val)<2**24
    result.append(val&0xffffffff if op==4 else ieee.int_to_float(val&0xffffffff)[0])
  if c['roi']!=2:
   packed=[]
   for ti in range((m+3)//4):
    for tj in range((n+3)//4):
     for r in range(4):
      for col in range(4):packed.append(result[(ti*4+r)*n+tj*4+col] if ti*4+r<m and tj*4+col<n else 0)
   result=packed
  return words(result),0
 if work==5:
  r=[ieee.widen(half(x*0.5)) for x in values(c['seed'],c['n'])]
  return words([x[0] for x in r]),0
 if work==6:
  n=c['n'];v=values(c['seed'],n*2);result=[]
  for a,b in zip(v[:n],v[n:]):
   if op==0:r=max(a+b,b)&0xffffffff
   else:
    x,f=ieee.int_to_float(a&0xffffffff);y=f32(b*0.5);z,f=ieee.add(x,y);r,f=ieee.float_to_int(z);flags |= f
   result.append(r)
  return words(result),flags
 raise ValueError(c)
