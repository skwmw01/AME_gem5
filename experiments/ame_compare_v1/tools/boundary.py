import json,subprocess,time,struct
from build import ROOT,HERE,OUT,GROUPS
from run import save
from model import tile_expected,tile,exact_integer_mac,words

def run():
 root=OUT/'boundary'/time.strftime('%Y%m%d-%H%M%S');results=[]
 for group in GROUPS:
  d=root/group;d.mkdir(parents=True);cmd=json.loads((OUT/'build'/group/'compile-command.json').read_text())
  cmd=[str(HERE/'guest/common/boundary.c') if x.endswith('/bench.c') else '-Wl,-Map,'+str(d/'guest.map') if x.startswith('-Wl,-Map,') else x for x in cmd];cmd[cmd.index('-o')+1]=str(d/'guest.elf')
  with (d/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
  cmd=[str(ROOT/'build/AME_B11/gem5.opt'),'-d',str(d/'m5out'),str(ROOT/'example/ame_config.py'),'--cmd',f'{d/"guest.elf"} {d/"guest.bin"}'];save(d/'command.json',cmd)
  with (d/'simulate.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
  data=(d/'guest.bin').read_bytes();pos=0;checks=[];ref,_=tile_expected(9,0);half=words(ref)
  a,b,c=tile(4,0);mac=words(exact_integer_mac(4,a,b,c));initial=words([n&0xffffffff for n in c])
  for i in range(4):
   ident,traps,cause,flags=struct.unpack_from('<4Q',data,pos);pos+=32;size=128 if i<2 else 64;actual=data[pos:pos+size];pos+=size
   denied=(i==1 and group!='X06') or i==3
   expected=half if i==0 and group!='X06' else half[:64]+bytes([0xa5])*64 if i==0 else bytes([0xa5])*64+half[:64] if i==1 and group=='X06' else bytes([0xa5])*128 if i==1 else mac if i==2 else initial
   passed=actual==expected and traps==int(denied) and cause==(2 if denied else 0) and flags==0
   checks.append(dict(id=i,status='PASS' if passed else 'FAIL',traps=traps,cause=cause,actual=actual.hex(),expected=expected.hex()))
  result=dict(group=group,status='PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL',checks=checks);results.append(result);save(d/'result.json',result);print(group,result['status'],flush=True)
 save(root/'summary.json',dict(status='PASS' if all(r['status']=='PASS' for r in results) else 'FAIL',results=results))
if __name__=='__main__':run()
