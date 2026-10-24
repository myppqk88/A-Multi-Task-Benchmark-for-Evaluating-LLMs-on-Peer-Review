import json,os,sys,glob,collections as C,hashlib,re
root=sys.argv[1]; catalog=json.load(open(sys.argv[2]))
B=os.path.join(root,'intake/batch-01')
dirs=sorted(d for d in os.listdir(B) if os.path.isdir(os.path.join(B,d)) and not d.startswith('fill_'))
issues=C.defaultdict(list); rows=[]; dois=C.Counter()
def pdfok(p):
  with open(p,'rb') as f: return f.read(5)==b'%PDF-'
for d in dirs:
  m=json.load(open(os.path.join(B,d,'metadata.json'))); pid=f"{m['platform']}:{m['article_id']}"
  dois[m.get('doi')]+=1
  if pid in catalog: issues[d].append('ALREADY_IN_CATALOG')
  vs={v['label']:v for v in m['versions']}
  for lab in ('v1','v2'):
    v=vs.get(lab)
    if not v: issues[d].append(f'NO_{lab}'); continue
    p=os.path.join(B,d,v['file'])
    if not os.path.isfile(p): issues[d].append(f'{lab}_FILE_MISSING')
    elif p.endswith('.pdf') and not pdfok(p): issues[d].append(f'{lab}_NOT_PDF')
    if not v.get('public_date'): issues[d].append(f'{lab}_NO_DATE')
  if 'v1' in vs and 'v2' in vs and vs['v1'].get('sha256')==vs['v2'].get('sha256'): issues[d].append('V1_EQ_V2')
  d1=vs.get('v1',{}).get('public_date'); d2=vs.get('v2',{}).get('public_date')
  if d1 and d2 and d2<=d1: issues[d].append('V2_NOT_AFTER_V1')
  rv=[r for r in m['reviews'] if r['on_version']=='v1']
  if not rv: issues[d].append('NO_V1_REVIEW')
  ans=C.defaultdict(list)
  for r in m['responses']:
    a=r['answers']; a=[a] if isinstance(a,str) else a
    for x in a: ans[x].append(r)
  paired=0
  for r in rv:
    if not r.get('date'): issues[d].append(f"{r['id']}_NO_DATE")
    for k in ('file','text_file'):
      if r.get(k) and not os.path.isfile(os.path.join(B,d,r[k])): issues[d].append(f"{r['id']}_{k}_MISSING")
    tf=r.get('text_file') or (r['file'] if r['file'].endswith('.txt') else None)
    if tf and os.path.isfile(os.path.join(B,d,tf)):
      n=len(open(os.path.join(B,d,tf),encoding='utf-8',errors='replace').read().split())
      if n<80: issues[d].append(f"{r['id']}_SHORT_TEXT({n}w)")
    if r.get('date') and d1 and r['date']<d1: issues[d].append(f"{r['id']}_BEFORE_V1")
    if r.get('date') and d2 and r['date']>d2: issues[d].append(f"{r['id']}_AFTER_V2")
    rs=ans.get(r['id'],[])
    if not rs: issues[d].append(f"{r['id']}_NO_RESPONSE"); continue
    paired+=1
    for x in rs:
      if x.get('date') and r.get('date') and x['date']<r['date']: issues[d].append(f"{r['id']}_RESPONSE_BEFORE_REVIEW")
      if not x.get('date'): issues[d].append(f"{x['id']}_NO_DATE")
      for k in ('file','text_file'):
        if x.get(k) and not os.path.isfile(os.path.join(B,d,x[k])): issues[d].append(f"{x['id']}_{k}_MISSING")
  rows.append(dict(dir=d,pid=pid,disc=m['discipline_oecd'],unc=m['discipline_uncertain'],v1=d1,v2=d2,nver=len(vs),v1rev=len(rv),paired=paired,lic=m.get('license'),title=m['title']))
for k,v in dois.items():
  if v>1: issues['DOI'].append(f'dup {k}')
json.dump(dict(rows=rows,issues=issues),open(sys.argv[3],'w'),ensure_ascii=False,indent=1)
print(len(rows),'papers;',sum(1 for r in rows if not issues[r['dir']]),'clean')
print(C.Counter(re.sub(r'R\d+_v1','Rk',i) for v in issues.values() for i in v).most_common())
print('paired dist',C.Counter(r['paired'] for r in rows)); print('lic',C.Counter(r['lic'] for r in rows))
