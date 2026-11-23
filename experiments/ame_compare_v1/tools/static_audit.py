import csv,json,hashlib,re,sys
from pathlib import Path
from build import ROOT,HERE,OUT,GROUPS
from run import save,pcmap

def audit():
 result=[]
 for group in GROUPS:
  if group=='P':rows=[dict(mnemonic=n,match=hex(a),mask=hex(b)) for n,a,b in [('madd.ew',0x0400002b,0xfe00707f),('mmax.ew',0x0c00002b,0xfe00707f),('mmulbtacc.2d',0x9e00002b,0xfe007e7f),('mconv.ew',0xa2d0002b,0xfff0707f)]]
  else:rows=list(csv.DictReader((ROOT/'tests/ame_explicit_v1'/('xuantie_v06' if group=='X06' else 'spec_v05a')/'encoding.csv').open()))
  errors=[]
  for i,row in enumerate(rows):
   a,m=int(row['match'],0),int(row['mask'],0)
   for other in rows[i+1:]:
    if not ((a^int(other['match'],0))&m&int(other['mask'],0)):errors.append('overlap')
  envelope=sum(2**(32-int(r['mask'],0).bit_count()) for r in rows)
  result.append(dict(group=group,rules=len(rows),mask_envelope=envelope,legal_fields=envelope-(32 if group=='S05A' else 0),rows=rows,status='FAIL' if errors else 'PASS',errors=errors))
 mapping={g:pcmap(g,True) for g in GROUPS};control=[]
 for name in ['input_type','configure','load','store']+['w1_'+str(i) for i in (0,1,2,3,7,8)]:
  bodies=[{pc:x[2] for pc,x in mapping[g].items() if x[1]==name} for g in GROUPS]
  control.append(dict(symbol=name,status='PASS' if all(x==bodies[0] and x for x in bodies) else 'FAIL',instructions=len(bodies[0])))
 save(OUT/'static-audit.json',dict(status='PASS' if all(r['status']=='PASS' for r in result+control) else 'FAIL',encoding=result,control_preparation=control))
if __name__=='__main__':audit()
