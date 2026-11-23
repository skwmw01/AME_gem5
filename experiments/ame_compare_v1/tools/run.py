#!/usr/bin/env python3
"""Build/run read-only simulator experiments; retain every run and failure."""
import argparse,collections,csv,gzip,hashlib,json,os,re,struct,subprocess,time
from pathlib import Path
from build import ROOT,HERE,OUT,GROUPS,build
from model import expected
TRACE_PARSER_VERSION=6

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')

def freeze():
 p=ROOT/'build/AME_B11/gem5.opt';config=ROOT/'build/AME_B11/gem5.build/config'
 assert sha(p)=='6ddf3e8b74544dbe52acad7265fec506f54da96fd9c0c02caf25479ef9355ef9'
 assert all('USE_'+n+'_EXPLICIT=y' in config.read_text() for n in ('XUANTIE_V06','SPEC_V05A'))
 files=[p,config,ROOT/'example/ame_config.py']+list((ROOT/'src/arch/riscv/insts').glob('*explicit.*'))
 for suffix in ('decoder','formats'):files+=list((ROOT/f'src/arch/riscv/isa/{suffix}').glob('*explicit.isa'))
 save(OUT/'frozen.json',dict(simulator_sha256=sha(p),files={str(x.relative_to(ROOT)):sha(x) for x in files},config=config.read_text()))

def symbols(group,control=False,batch=False,directory=None):
 result=[]
 for line in ((directory/'symbols.txt') if directory else OUT/('batch-build' if batch else 'control-build' if control else 'build')/group/'symbols.txt').read_text().splitlines():
  m=re.match(r'^([0-9a-f]+)\s+\w+\s+F\s+(\S+)\s+([0-9a-f]+)\s+(.+)$',line)
  if m:result.append((int(m[1],16),int(m[3],16),m[4],m[2]))
 return sorted(result)

def pcmap(group,control=False,batch=False,directory=None):
 syms=symbols(group,control,batch,directory);out={}
 for line in ((directory/'disassembly.txt') if directory else OUT/('batch-build' if batch else 'control-build' if control else 'build')/group/'disassembly.txt').read_text().splitlines():
  m=re.match(r'^\s*([0-9a-f]+):\s+([0-9a-f]{8})\s+(.+)',line)
  if not m:continue
  pc=int(m[1],16);word=int(m[2],16);text=m[3]
  containing=[s for s in syms if s[0]<=pc<s[0]+s[1]]
  symbol=containing[-1][2] if containing else ''
  if (word&0xfe00707f) in (0x0400002b,0x0c00002b,0x9e00002b,0x2000000b,0x2000100b,0x2200000b,0x2200100b,0x2400000b,0x2400100b,0x2400200b,0x2600000b,0x2600100b,0x2600200b,0x4000005b,0x4000105b,0x4200005b,0x4200105b,0x4400005b,0x4400105b,0x4400205b,0x4600005b,0x4600105b,0x4600205b) or (word&0xfff0707f)==0xa2d0002b:kind='compute'
  elif symbol in ('pack_gemm','pack_tile','pack_half','pack_widen','scatter'):kind='layout'
  elif re.match(r'(?:b\w+|j\w*|ret|call)\b',text):kind='dispatch_loop'
  elif (word&0xfe00707f)==0xa200002b and ((word>>20)&31) in (0,1,2,3):kind='type_setup'
  elif (word&0xfe00707f)==0xa200002b and ((word>>20)&31) in (22,25):kind='memory'
  elif (word&0xfe00707f)==0xa200002b and ((word>>20)&31) in (28,29):kind='init_move'
  elif symbol in ('input_type','configure'):
   kind='memory' if '(sp)' in text else 'type_setup'
  elif word&127 in (3,0x23,7,0x27):kind='memory'
  else:kind='other'
  out[pc]=(kind,symbol,word,text)
 # Backward data slices of the scalar type operands. This includes expanded
 # constants and table addresses/loads, but never crosses a function boundary.
 # The P callable API passes source/destination descriptors to common(a0,a1).
 by_symbol=collections.defaultdict(list)
 for pc,info in out.items():by_symbol[info[1]].append(pc)
 for symbol,pcs in by_symbol.items():
  definitions={};producers={}
  def mark(reg):
   pc=definitions.get(reg)
   if pc is None:return
   visit(pc,set())
  def visit(pc,seen):
   if pc in seen:return
   seen.add(pc);kind,sym,word,asm=out[pc]
   if kind not in ('other','memory','type_setup'):return
   out[pc]=('type_setup',sym,word,asm)
   for previous in producers.get(pc,()):visit(previous,seen)
  for pc in sorted(pcs):
   kind,sym,word,asm=out[pc];opcode=word&127;rd=(word>>7)&31;rs1=(word>>15)&31;rs2=(word>>20)&31
   if (word&0xfe00707f)==0xa200002b and rs2 in (0,1,2,3):mark(rs1)
   if '<common' in asm and opcode in (0x6f,0x67):mark(10);mark(11)
   sources=[rs1] if opcode in (0x13,0x1b,3) else [rs1,rs2] if opcode in (0x33,0x3b) else []
   if opcode in (0x37,0x17,0x13,0x1b,0x33,0x3b,3) and rd:
    producers[pc]=[definitions[r] for r in sources if r and r!=2 and r in definitions];definitions[rd]=pc
   elif opcode in (0x6f,0x67) and rd:
    # Caller-saved values become unknown after a real function call.
    for reg in (1,5,6,7,10,11,12,13,14,15,16,17,28,29,30,31):definitions.pop(reg,None)
 return out

def analyse(directory,group,cases,start,end,trace,control=False,batch=False):
 raw=(directory/'guest.bin').read_bytes();offset=0;records=[]
 stats=(directory/'m5out/stats.txt').read_text().split('---------- Begin Simulation Statistics ----------')[1:]
 # Each reset/dump pair emits one ROI; final exit emits one extra non-ROI block.
 for ident in range(start,end):
  header=struct.unpack_from('<13Q',raw,offset);offset+=104
  id,n,traps=header[:3];data=raw[offset:offset+n*4];offset+=n*4
  assert id==ident
  case=cases[id];batch_count=max(1,1024//case['repeat']) if batch else case.get('outer',1)
  reference_case=dict(case)
  if batch and case['roi']==0 and case['op'] in (4,5,6):reference_case['repeat']*=batch_count
  ref,flags=expected(reference_case,group)
  failure=[]
  if data!=ref:failure.append('output')
  if traps:failure.append('trap')
  if header[7]!=flags:failure.append('flags')
  if header[8]!=0:failure.append('fcsr')
  if header[9]!=0:failure.append('saturation')
  st=dict(re.findall(r'^(\S+)\s+([-+0-9.e]+)',stats[id-start],re.M))
  record=dict(case=case,group=group,batch_count=batch_count,status='FAIL' if failure else 'PASS',failures=failure,
              counters=header[3:7],cycles=int(st['system.cpu.numCycles']),ticks=int(st['simTicks']),
              retired_insts=int(st['simInsts']),simOps=int(st['simOps']),rdcycle_delta=header[4]-header[3],rdinstret_delta=header[6]-header[5],
              flags=header[7],traps=traps,trap=[header[10],header[11],header[12]],output_sha256=hashlib.sha256(data).hexdigest(),reference_sha256=hashlib.sha256(ref).hexdigest(),
              evidence=str(directory.relative_to(ROOT)),stats_block=id-start)
  if failure:record.update(actual=data.hex(),expected=ref.hex(),expected_flags=flags)
  records.append(record)
 assert offset==len(raw),(offset,len(raw))
 if trace:trace_audit(directory,group,records,control,batch)
 for r in records:
  if r['status']=='FAIL':print('FAIL',group,r['case']['id'],r['case']['label'],r['failures'],r.get('trap'),flush=True)
 save(directory/'records.json',records)
 return records

def trace_audit_slow(directory,group,records,control=False,batch=False):
 mapping=pcmap(group,control,batch,directory if (directory/'symbols.txt').exists() else None);counts=[];active=None;words=[];transfers=[];layout_returns=[];pending_return=None
 # Dump at commit is the MinorCPU default; timestamps may be execution times.
 for line in gzip.open(directory/'m5out/trace.gz','rt'):
  m=re.search(r'\b0x([0-9a-f]+)(?:[.:@\s])',line)
  if not m:continue
  pc=int(m[1],16)
  info=mapping.get(pc)
  if not info:continue
  kind,symbol,word,text=info
  if word==0x8000007b:
   active=collections.Counter();layout_returns=[];pending_return=None;counts.append(active);words.append(collections.Counter());transfers.append(collections.Counter())
   continue
  if active is not None:
   while layout_returns and pc==layout_returns[-1]:layout_returns.pop()
   if kind=='layout' and pending_return is not None and not layout_returns:layout_returns.append(pending_return)
   in_layout=kind=='layout' or bool(layout_returns)
   if in_layout:
    rd=(word>>7)&31;opcode=word&127
    if rd==1 and opcode in (0x6f,0x67):layout_returns.append(pc+4)
    kind='layout'
   pending_return=pc+4 if ((word>>7)&31)==1 and (word&127) in (0x6f,0x67) and not in_layout else None
   active[kind]+=1
   if (word&0xfe00707f)==0xa200002b:
    sub=(word>>20)&31
    if sub in (22,25):transfers[-1]['load' if sub==22 else 'store']+=1
   opcode=word&127;funct3=(word>>12)&7
   if opcode==3:transfers[-1]['scalar_load']+=(1,2,4,8,1,2,4,0)[funct3]
   elif opcode==0x23:transfers[-1]['scalar_store']+=(1,2,4,8,0,0,0,0)[funct3]
   elif opcode==7:transfers[-1]['scalar_load']+=4 if funct3==2 else 8 if funct3==3 else 0
   elif opcode==0x27:transfers[-1]['scalar_store']+=4 if funct3==2 else 8 if funct3==3 else 0
   if kind=='compute':words[-1][f'{word:08x}']+=1
   if word==0x8200007b:active=None
 assert len(counts)==len(records),(len(counts),len(records))
 for r,c,w,t in zip(records,counts,words,transfers):
  r['trace_parser_version']=4
  r['matrix_load_bytes']=64*t.get('load',0);r['matrix_store_bytes']=64*t.get('store',0)
  r['scalar_load_bytes']=t.get('scalar_load',0);r['scalar_store_bytes']=t.get('scalar_store',0)
  r['all_load_bytes']=r['matrix_load_bytes']+r['scalar_load_bytes'];r['all_store_bytes']=r['matrix_store_bytes']+r['scalar_store_bytes']
  r['failures']=[f for f in r['failures'] if f!='trace/count gate']
  r['status']='FAIL' if r['failures'] else 'PASS'
  r['categories']=dict(c);r['compute_words']=dict(w);r['trace_insts']=sum(c.values())
  r['trace_count_delta']=sum(c.values())-r['retired_insts']
  case=r['case'];work=case['work'];op=case['op']
  count=0 if work==0 else case['repeat']*(2 if op==9 and group=='X06' else 1) if work==1 else case['repeat'] if work in (2,3) else ((case['m']+3)//4)*((case['n']+3)//4)*((case['k']+(16 if op==4 else 8)-1)//(16 if op==4 else 8)) if work==4 else case['n']//32*(2 if group=='X06' else 1) if work==5 else case['n']//16*(2 if op==0 else 3)
  count *= r.get('batch_count',1)
  r['expected_compute_insts']=count
  if r['trace_count_delta'] or sum(w.values())!=count:
   r['status']='FAIL';r['failures'].append('trace/count gate')

def trace_audit(directory,group,records,control=False,batch=False):
 """Count actual committed PCs first; classify unique PCs per workload ROI.

 In W4/W5 end-to-end kernels memcpy/memset are reachable only from packing
 or result scattering; in mixed W3 they are ordinary accumulator-state moves.
 This avoids per-instruction disassembly or Python call-stack bookkeeping.
 """
 mapping=pcmap(group,control,batch,directory if (directory/'symbols.txt').exists() else None)
 reset=next(pc for pc,v in mapping.items() if v[2]==0x8000007b)
 dump=next(pc for pc,v in mapping.items() if v[2]==0x8200007b)
 ranges=trace_frequencies(directory/'m5out/trace.gz',reset,dump)
 assert len(ranges)==len(records),(len(ranges),len(records))
 for r,frequencies in zip(records,ranges):
  categories=collections.Counter();words=collections.Counter();transfers=collections.Counter();unknown=[]
  case=r['case'];layout_context=case['work'] in (4,5) and case['roi']==2
  for pc,count in frequencies.items():
   info=mapping.get(pc)
   if info is None:unknown.append(pc);categories['other']+=count;continue
   kind,symbol,word,text=info
   if layout_context and symbol in ('memcpy','memset'):kind='layout'
   categories[kind]+=count
   if kind=='compute':words[f'{word:08x}']+=count
   if (word&0xfe00707f)==0xa200002b:
    sub=(word>>20)&31
    if sub in (22,25):transfers['load' if sub==22 else 'store']+=count*64
   opcode=word&127;funct3=(word>>12)&7
   if opcode==3:transfers['scalar_load']+=count*(1,2,4,8,1,2,4,0)[funct3]
   elif opcode==0x23:transfers['scalar_store']+=count*(1,2,4,8,0,0,0,0)[funct3]
   elif opcode==7:transfers['scalar_load']+=count*(4 if funct3==2 else 8 if funct3==3 else 0)
   elif opcode==0x27:transfers['scalar_store']+=count*(4 if funct3==2 else 8 if funct3==3 else 0)
  r.update(trace_parser_version=TRACE_PARSER_VERSION,categories=dict(categories),compute_words=dict(words),trace_insts=sum(frequencies.values()),trace_count_delta=sum(frequencies.values())-r['retired_insts'],unknown_pcs=unknown,matrix_load_bytes=transfers['load'],matrix_store_bytes=transfers['store'],scalar_load_bytes=transfers['scalar_load'],scalar_store_bytes=transfers['scalar_store'],all_load_bytes=transfers['load']+transfers['scalar_load'],all_store_bytes=transfers['store']+transfers['scalar_store'])
  w,op=case['work'],case['op']
  expected_count=0 if w==0 else case['repeat']*(2 if op==9 and group=='X06' else 1) if w==1 else case['repeat'] if w in (2,3) else ((case['m']+3)//4)*((case['n']+3)//4)*((case['k']+(16 if op==4 else 8)-1)//(16 if op==4 else 8)) if w==4 else case['n']//32*(2 if group=='X06' else 1) if w==5 else case['n']//16*(2 if op==0 else 3)
  expected_count *= r.get('batch_count',1)
  r['expected_compute_insts']=expected_count
  r['failures']=[f for f in r['failures'] if f!='trace/count gate']
  if unknown or r['trace_count_delta'] or sum(words.values())!=expected_count:r['failures'].append('trace/count gate')
  r['status']='FAIL' if r['failures'] else 'PASS'

def trace_frequencies(path,reset,dump):
 """Count PC tokens in bounded chunks; keep only committed ROI intervals.

 Regex extraction and Counter.update run in C rather than converting every
 trace line in Python. Boundary markers are matched only at the PC position.
 """
 cache=path.with_name('committed-pc-counts.json.gz')
 with path.open('rb') as stream:identity=hashlib.file_digest(stream,'sha256').hexdigest()
 if cache.exists():
  with gzip.open(cache,'rt') as stream:saved=json.load(stream)
  if saved['trace_sha256']==identity and saved['reset']==reset and saved['dump']==dump:
   return [collections.Counter({int(pc):count for pc,count in row.items()}) for row in saved['ranges']]
 token=rb'^[^\n]*?\b0x([0-9a-f]+)(?:\.[0-9]+)?(?=[:@\s])'
 pcs=re.compile(token,re.M)
 boundary=re.compile(rb'^[^\n]*?\b0x('+f'{reset:x}|{dump:x}'.encode()+rb')(?:\.[0-9]+)?(?=[:@\s])[^\n]*\n',re.M)
 active=None;ranges=[];pending=b'';dump_token=f'{dump:x}'.encode()
 with gzip.open(path,'rb') as stream:
  while True:
   chunk=stream.read(8*1024*1024)
   data=pending+chunk;end=data.rfind(b'\n')+1
   pending=data[end:];data=data[:end];position=0
   for match in boundary.finditer(data):
    if active is not None:active.update(pcs.findall(data[position:match.start()]))
    if int(match[1],16)==reset:
     assert active is None,'nested ROI reset'
     active=collections.Counter();ranges.append(active)
    else:
     assert active is not None,'dump without reset'
     active[dump_token]+=1;active=None
    position=match.end()
   if active is not None:active.update(pcs.findall(data[position:]))
   if not chunk:break
 assert active is None,'unterminated ROI'
 result=[collections.Counter({int(pc,16):n for pc,n in counter.items()}) for counter in ranges]
 try:
  with gzip.open(cache,'wt') as stream:json.dump(dict(trace_sha256=identity,reset=reset,dump=dump,ranges=result),stream)
 except PermissionError:pass
 return result

def run_unlocked(args):
 freeze();cases=json.loads((OUT/'cases.json').read_text());end=args.end or len(cases)
 groups=GROUPS if args.group=='all' else [args.group]
 runid=time.strftime('%Y%m%d-%H%M%S')+'-'+f'{time.time_ns()%1000000000:09d}'+'-'+args.tag
 all_records=[]
 for group in groups:
  d=OUT/'runs'/runid/group;d.mkdir(parents=True,exist_ok=True)
  elf=OUT/('batch-build' if args.batch else 'control-build' if args.control else 'build')/group/'guest.elf'
  cmd=[str(ROOT/'build/AME_B11/gem5.opt')]
  if args.trace:cmd+=['--debug-flags=ExecEnable,ExecMacro,ExecKernel,ExecUser,FmtTicksOff','--debug-file=trace.gz']
  cmd+=['-d',str(d/'m5out'),str(ROOT/'example/ame_config.py'),'--cmd',f'{elf} {d/"guest.bin"} {args.start} {end}']
  for name in ('guest.elf','symbols.txt','disassembly.txt','sections.txt','ops.S','guest.map'):
   source=elf.parent/name
   __import__('shutil').copyfile(source,d/name)
  save(d/'command.json',cmd)
  with (d/'simulate.log').open('w') as log:
   result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout)
  if result.returncode:raise RuntimeError(f'gem5 failed {result.returncode}: {d}')
  records=analyse(d,group,cases,args.start,end,args.trace,args.control,args.batch);all_records+=records
  save(d/'manifest.json',dict(elf_sha256=sha(elf),simulator_sha256=sha(ROOT/'build/AME_B11/gem5.opt'),config_sha256=sha(d/'m5out/config.ini'),report_sha256=sha(d/'guest.bin')))
  print(group,'records',len(records),'failures',sum(r['status']=='FAIL' for r in records),d,flush=True)
 save(OUT/'runs'/runid/'summary.json',dict(status='FAIL' if any(r['status']=='FAIL' for r in all_records) else 'PASS',records=len(all_records)))
 if any(r['status']=='FAIL' for r in all_records):raise RuntimeError('incorrect benchmark; results excluded from performance tables')

def run(args):
 if args.tag!='formal' or args.group=='all':return run_unlocked(args)
 import fcntl
 lock=OUT/'locks'/f'{args.group}-{args.start}-{args.end}.lock'
 lock.parent.mkdir(parents=True,exist_ok=True)
 with lock.open('w') as f:
  fcntl.flock(f,fcntl.LOCK_EX)
  target_hash=sha(OUT/'build'/args.group/'guest.elf')
  for p in sorted((OUT/'runs').glob('*-formal/'+args.group+'/records.json')):
   manifest=p.parent/'manifest.json'
   if not manifest.exists():continue
   if json.loads(manifest.read_text())['elf_sha256']!=target_hash:continue
   rows=json.loads(p.read_text())
   if rows and {r['case']['id'] for r in rows}==set(range(args.start,args.end)) and all(r['status']=='PASS' for r in rows):
    print('Already complete:',args.group,args.start,args.end,p,flush=True);return
  run_unlocked(args)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['build','run']);p.add_argument('--group',choices=['all',*GROUPS],default='all');p.add_argument('--start',type=int,default=0);p.add_argument('--end',type=int,default=0);p.add_argument('--trace',action='store_true');p.add_argument('--control',action='store_true');p.add_argument('--batch',action='store_true');p.add_argument('--tag',default='run');p.add_argument('--timeout',type=int,default=14400);a=p.parse_args()
 build() if a.command=='build' else run(a)
