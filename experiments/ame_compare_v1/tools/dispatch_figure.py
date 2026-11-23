"""Compare independent type families with grouped bars and a shared scale."""
import csv,os,statistics
from pathlib import Path
from build import ROOT,GROUPS

def summaries(flat):
 return [dict(group=g,G=G,family=f,records=len(rows),fraction=statistics.mean(float(r['insts_dispatch_loop'])/float(r['retired_insts']) for r in rows))
         for G in (1,16) for g in GROUPS for f in range(4)
         for rows in [[r for r in flat if r['label']=='W3-runtime' and r['group']==g and int(r['G'])==G and r['task']=='family'+str(f)]]]

def render(flat,figdir):
 os.environ.setdefault('MPLCONFIGDIR','/tmp/ame-compare-matplotlib')
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.ticker import PercentFormatter
 data=summaries(flat);colors={'P':'#365f9d','X06':'#d27828','S05A':'#27946f'}
 plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
 fig,axes=plt.subplots(1,2,figsize=(12,3.8),sharey=True);width=.22
 for ax,G in zip(axes,(1,16)):
  for i,g in enumerate(GROUPS):
   vals=[next(r['fraction'] for r in data if r['group']==g and r['G']==G and r['family']==f) for f in range(4)]
   bars=ax.bar([f+(i-1)*.25 for f in range(4)],vals,width=width,color=colors[g],label=g)
   ax.bar_label(bars,labels=[f'{v:.1%}' for v in vals],padding=3,fontsize=6.5)
  ax.set(xticks=range(4),xticklabels=['add','max','MAC','convert'],xlabel='Type family',ylabel='Dispatch + call + loop instruction fraction',title='W3 batch length '+str(G),ylim=(0,.34))
  ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=0))
  ax.legend(loc='upper center',ncol=3,fontsize=8)
 fig.tight_layout();figdir=Path(figdir);figdir.mkdir(parents=True,exist_ok=True)
 fig.savefig(figdir/'w3_dispatch_fraction.png',dpi=180)
 fig.savefig(figdir/'w3_dispatch_fraction.pdf',metadata={'CreationDate':None,'ModDate':None})
 plt.close(fig)

if __name__=='__main__':
 doc=ROOT/'docs/ame_compare_v1'
 with (doc/'evidence/records.csv').open(newline='') as stream:flat=list(csv.DictReader(stream))
 render(flat,doc/'figures')
