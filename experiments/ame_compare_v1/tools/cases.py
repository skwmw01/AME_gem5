"""Predeclared paired experiment population. No postmeasurement pruning."""
from model import TASKS

def population():
 out=[]
 def add(work,op=0,repeat=1,n=16,m=0,k=0,seed=0,roi=1,state=0,regpolicy=0,batch=1,pattern=1,c0=0,control=0,label=''):
  out.append(dict(id=len(out),work=work,op=op,repeat=repeat,n=n,m=m,k=k,seed=seed,roi=roi,state=state,regpolicy=regpolicy,batch=batch,pattern=pattern,c0=c0,control=control,label=label))
 for _ in range(3):add(0,label='calibration-empty')
 for op in range(10):add(1,op,label='gate-'+TASKS[op])
 for op in (0,4,8):
  for repeat in (1,256):
   for _ in range(3):add(1,op,repeat,roi=0,state=1,label='determinism')
 for op in range(9):
  for repeat in (1,4,16,64,256):
   for roi,state in ((0,1),(1,0),(1,1)):add(1,op,repeat,roi=roi,state=state,label='W1')
 for op in (0,1,2,3,7,8):
  for repeat in (1,4,16,64,256):
   for roi in (0,1):add(1,op,repeat,roi=roi,state=1,control=1,label='W1-control')
 for family in range(3):
  for g in (1,4,16,64,256):
   for rp in (0,1):add(2,family,1024,regpolicy=rp,batch=g,label='W2')
 for family in range(4):
  for batch in (1,16):
   for pattern in range(3):
    for seed in range(10):add(3,family,768 if family==2 else 1024,batch=batch,pattern=pattern,seed=seed,label='W3-runtime')
 # Compile-time known entries for every supported member of each W3 family.
 for op in range(9):
  for batch in (1,16):
   for seed in range(10):add(1,op,batch,seed=seed,label='W3-known')
 for op in (4,5,6):
  for m,n,k in ((16,16,16),(32,32,32),(128,128,128),(13,19,11)):
   for c0 in (0,1) if m!=13 else (1,):
    for roi in (1,2):
     for seed in range(10):add(4,op,n=n,m=m,k=k,c0=c0,roi=roi,seed=seed,label='W4-GEMM')
 for op in (0,1):
  for n in (256,4096):
   for roi in (1,2):
    for seed in range(10):add(6,op,n=n,roi=roi,seed=seed,label='W4-pipeline')
 for n in (32,256,4096):
  for roi in (1,2):
   for seed in range(10):add(5,9,n=n,roi=roi,seed=seed,label='W5')
 return out
