"""Static encoding comparisons: rules and machine words have separate axes."""
import json,os
from pathlib import Path
from build import OUT,GROUPS

def render(figdir):
 os.environ.setdefault('MPLCONFIGDIR','/tmp/ame-compare-matplotlib')
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.ticker import MaxNLocator,StrMethodFormatter
 from summaries import encoding_growth
 rows=json.loads((OUT/'static-audit.json').read_text())['encoding']
 data={r['group']:r for r in rows};colors={'P':'#365f9d','X06':'#d27828','S05A':'#27946f'}
 plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
 figdir=Path(figdir);figdir.mkdir(parents=True,exist_ok=True)
 def finish(fig,name):
  fig.tight_layout()
  fig.savefig(figdir/(name+'.png'),dpi=180)
  fig.savefig(figdir/(name+'.pdf'),metadata={'CreationDate':None,'ModDate':None})
  plt.close(fig)
 fig,axes=plt.subplots(1,3,figsize=(12,3.8))
 for ax,key,title,ylabel in zip(axes,('rules','mask_envelope','legal_fields'),
  ('Decode rules','Mask envelope','After static register restrictions'),
  ('Number of computation rules','Number of 32-bit machine words','Number of 32-bit machine words')):
  vals=[data[g][key] for g in GROUPS]
  bars=ax.bar(GROUPS,vals,color=[colors[g] for g in GROUPS],width=.58)
  ax.bar_label(bars,labels=[f'{v:,}' for v in vals],padding=4)
  ax.set(title=title,xlabel='Implementation group (10 common tasks)',ylabel=ylabel,ylim=(0,max(vals)*1.22))
  ax.yaxis.set_major_locator(MaxNLocator(integer=True,nbins=6))
  ax.yaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
 finish(fig,'d1_encoding_space')
 growth=encoding_growth()
 fig,axes=plt.subplots(1,2,figsize=(11,4))
 counts=(4,7,10);width=.23
 for ax,key,title,ylabel in zip(axes,('rules','mask_envelope'),
  ('Decode rules as the task set grows','Mask envelope as the task set grows'),
  ('Number of computation rules','Number of 32-bit machine words')):
  highest=0
  for i,g in enumerate(GROUPS):
   vals=[next(r[key] for r in growth if r['group']==g and r['tasks']==n) for n in counts]
   highest=max(highest,max(vals));xs=[x+(i-1)*width for x in range(len(counts))]
   bars=ax.bar(xs,vals,width=width,color=colors[g],label=g)
   ax.bar_label(bars,labels=[f'{v:,}' for v in vals],padding=3,fontsize=8,rotation=0 if key=='rules' else 90)
  ax.set(title=title,xlabel='Number of common logical type tasks',ylabel=ylabel,xticks=range(3),xticklabels=counts,ylim=(0,highest*(1.22 if key=='rules' else 1.40)))
  ax.yaxis.set_major_locator(MaxNLocator(integer=True,nbins=6))
  ax.yaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
  ax.legend(loc='upper left',ncol=3,fontsize=8)
 finish(fig,'d1_encoding_growth')

if __name__=='__main__':
 from build import ROOT
 render(ROOT/'docs/ame_compare_v1/figures')
