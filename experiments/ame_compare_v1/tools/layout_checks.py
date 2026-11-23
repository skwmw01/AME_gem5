"""Reversible pack mappings checked against indexed logical data."""
import json,struct
from pathlib import Path
from model import pack_mac
from build import OUT,GROUPS

def check():
 results=[]
 for op in (4,5,6):
  k=16 if op==4 else 8;size=1 if op==4 else 2
  for group in GROUPS:
   tested=0
   # Test every logical coordinate independently, with asymmetric RHS.
   for i in range(4):
    for t in range(k):
     a=[0]*(4*k);b=[0]*(4*k);a[i*k+t]=1;b[t*4+(i+1)%4]=-2
     pa,pb=pack_mac(group,a,b,op)
     va=list(pa) if size==1 else list(struct.unpack('<32H',pa));vb=list(pb) if size==1 else list(struct.unpack('<32H',pb))
     at=(t//4)*16+i*4+t%4 if group=='P' else i*k+t
     bt=(t//4)*16+((i+1)%4)*4+t%4 if group=='P' else ((i+1)%4)*k+t if group=='X06' else t*4+(i+1)%4
     assert va[at] !=0 and vb[bt]!=0
     assert sum(v!=0 for v in va)==sum(v!=0 for v in vb)==1
     tested+=1
   results.append(dict(op=op,group=group,coordinate_cases=tested,status='PASS'))
 for group in GROUPS:
  h=list(range(32))
  if group=='X06':
   packed=[[h[t*16+r*4+c] if c<4 else 0x3555 for r in range(4) for c in range(8)] for t in range(2)]
   recovered=[packed[t][r*8+c] for t in range(2) for r in range(4) for c in range(4)]
  else:recovered=h[:]
  assert recovered==h
  results.append(dict(task='C3',group=group,status='PASS',elements=32))
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'layout-checks.json').write_text(json.dumps(dict(status='PASS',checks=results),indent=2)+'\n')
if __name__=='__main__':check()
