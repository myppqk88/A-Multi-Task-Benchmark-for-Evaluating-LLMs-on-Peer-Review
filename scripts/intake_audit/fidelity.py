import json,os,sys,re,subprocess,html,collections as C
B=os.path.join(sys.argv[1],'intake/batch-01')
def norm(s): return re.sub(r'[^a-z0-9]+',' ',html.unescape(s).lower()).split()
def strip(h):
  h=re.sub(r'(?is)<(script|style).*?</\1>',' ',h); return re.sub(r'<[^>]+>',' ',h)
def cover(txt,src):
  # fraction of txt word 8-grams found in src
  t=norm(txt); s=' '.join(norm(src))
  if len(t)<8: return None
  grams=[' '.join(t[i:i+8]) for i in range(0,len(t)-7,8)]
  return sum(g in s for g in grams)/len(grams)
out=[];stats=C.Counter();unlisted={}
for d in sorted(os.listdir(B)):
  P=os.path.join(B,d)
  if not os.path.isdir(P) or d.startswith('fill_'): continue
  m=json.load(open(os.path.join(P,'metadata.json')))
  for r in m['reviews']+m['responses']:
    tf=r.get('text_file') or r['file']
    if not tf.endswith('.txt'): continue
    txt=open(os.path.join(P,tf),encoding='utf-8',errors='replace').read()
    f=os.path.join(P,r['file'])
    if f.endswith('.pdf'):
      src=subprocess.run(['pdftotext','-layout',f,'-'],capture_output=True,text=True).stdout
    elif f.endswith(('.html','.htm')): src=strip(open(f,encoding='utf-8',errors='replace').read())
    else: stats['other_fmt']+=1; continue
    c=cover(txt,src); out.append((d,r['id'],c,len(txt.split())))
  # report ids visible on version pages
  ids=set()
  for sp in os.listdir(os.path.join(P,'source_pages')):
    if sp.endswith('.html'):
      h=open(os.path.join(P,'source_pages',sp),encoding='utf-8',errors='replace').read()
      ids|=set(re.findall(r'\.r(\d{4,7})\b',h))
  listed={str(r.get('publisher_report_id')) for r in m['reviews']}
  unlisted[d]=(sorted(ids-listed),sorted(listed))
low=[o for o in out if o[2] is not None and o[2]<0.9]
print('texts',len(out),'low coverage',len(low)); [print(o) for o in low[:30]]
print('papers with report ids on pages not listed:',sum(1 for v in unlisted.values() if v[0]))
json.dump(unlisted,open(sys.argv[2],'w'),indent=0)
