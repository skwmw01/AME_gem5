"""Task work counts and input identities; separate logical/prepared/traffic sizes."""
import hashlib,json,struct
from model import tile,values,TASKS

def work(c,group,include_identity=False):
 w,op=c['work'],c['op'];n=c['n'];repeat=c['repeat'];useful=macs=executed=0
 if w==0:
  result=dict(useful_elements=0,useful_MACs=0,executed_MACs=0,compute_insts=0,logical_input_span_bytes=0,prepared_input_span_bytes=0,matrix_load_bytes=0,matrix_store_bytes=0,logical_output_span_bytes=0,prepared_output_span_bytes=0,traffic_note='empty ROI',peak_M=0,peak_Acc=0,input_hash=hashlib.sha256(b'null').hexdigest())
  if include_identity:result['input_identity']=None
  return result
 if w in (0,1):
  compute=0 if w==0 else repeat*(2 if op==9 and group=='X06' else 1)
  if op in (4,5,6):macs=executed=repeat*(256 if op==4 else 128);size=192
  else:useful=repeat*(32 if op==9 else 16);size=64+(64 if op<4 else 0)
  logical=tile(op,c['seed']);
  if op in (7,8,9):logical=logical[0]
  prepared=(128 if group=='X06' else 64) if op==9 else size
  inputs=0 if c['roi']==0 else prepared
  outputs=0 if c['roi']==0 else 128 if op==9 else 64
  peak_m=3 if op in (4,5,6) else (4 if group=='X06' else 3) if op==9 else 2 if op>=7 else 3;peak_acc=int(op in (4,5,6))
 elif w in (2,3):
  compute=repeat;ops=([0,1],[2,3],[4,5,6],[7,8])[op]
  if w==2 and op==2:ops=[5,6]
  logical=[tile(o,c['seed']+t) for t,o in enumerate(ops)]
  if op==2:macs=executed=(repeat//len(ops))*sum(256 if x==4 else 128 for x in ops)
  else:useful=repeat*16
  size=prepared=(len(ops)*192 if w==3 else len(ops)*128+64) if op==2 else len(ops)*64 if op==3 else len(ops)*128
  inputs=repeat*(64 if op==3 else 128);outputs=(repeat//c['batch'])*64
  peak_m=(5 if op==2 else 4 if op==3 else 6) if c['regpolicy'] else 2 if op==3 else 3;peak_acc=int(op==2)
 elif w==4:
  m,k=c['m'],c['k'];k0=16 if op==4 else 8;mt=(m+3)//4;nt=(n+3)//4;kt=(k+k0-1)//k0
  compute=mt*nt*kt;macs=m*n*k;executed=compute*16*k0
  count=m*k+k*n+m*n;logical=values(c['seed'],count)
  if not c['c0']:logical[m*k+k*n:]=[0]*(m*n)
  size=(m*k+k*n)*(1 if op==4 else 2)+m*n*4
  prepared=(mt*kt+nt*kt)*64+m*n*4
  inputs=compute*128+mt*nt*64;outputs=mt*nt*64
  peak_m=3;peak_acc=1
 elif w==5:
  compute=n//32*(2 if group=='X06' else 1);useful=n;logical=values(c['seed'],n);size=n*2;prepared=n*(4 if group=='X06' else 2);inputs=prepared;outputs=n*4;peak_m=4 if group=='X06' else 3;peak_acc=0
 else:
  compute=n//16*(2 if op==0 else 3);useful=n;logical=values(c['seed'],2*n);size=prepared=n*8;inputs=n*8;outputs=n*4;peak_m=4;peak_acc=0
 identity=dict(task=TASKS[op] if w in (0,1,4,5) else op,seed=c['seed'],values=logical)
 if w in (2,3):identity.update(batch=c['batch'],pattern=c['pattern'],repeat=repeat)
 if w==4:identity.update(shape=(c['m'],n,c['k']),c0=c['c0'])
 output_span=(128 if op==9 else 64) if w==1 else len(ops)*64 if w in (2,3) else c['m']*n*4 if w==4 else n*4
 prepared_output=384 if w in (2,3) else ((c['m']+3)//4)*((n+3)//4)*64 if w==4 and c['roi']!=2 else output_span
 result=dict(useful_elements=useful,useful_MACs=macs,executed_MACs=executed,compute_insts=compute,
             logical_input_span_bytes=size,prepared_input_span_bytes=prepared,logical_output_span_bytes=output_span,prepared_output_span_bytes=prepared_output,
             matrix_load_bytes=inputs,matrix_store_bytes=outputs,
             traffic_note='Matrix whole-register transfers only; scalar layout/stack traffic remains in trace categories.',
             peak_M=peak_m,peak_Acc=peak_acc,input_hash=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest())

 if include_identity:result['input_identity']=identity
 return result
