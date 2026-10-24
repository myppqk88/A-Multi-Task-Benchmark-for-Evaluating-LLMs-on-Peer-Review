import json,os,sys,re,collections as C
B=os.path.join(sys.argv[1],'intake/batch-01')
res={};tot=C.Counter()
pat=re.compile(r'"doi":"10\.(?:21956|5256)\\?/[a-z]+\.(\d+)\.r(\d+)".{0,400}?"dateCompleted":"([\d-]+)')
for d in sorted(os.listdir(B)):
  P=os.path.join(B,d)
  if not os.path.isdir(P) or d.startswith('fill_'): continue
  m=json.load(open(os.path.join(P,'metadata.json')))
  rep={}
  for sp in os.listdir(os.path.join(P,'source_pages')):
    if sp.endswith('.html'):
      h=open(os.path.join(P,'source_pages',sp),encoding='utf-8',errors='replace').read()
      for s,r,dt in pat.findall(h): rep[r]=(s,dt)
  v1=[r for r in m['reviews'] if r['on_version']=='v1']
  sets={rep[str(r.get('publisher_report_id'))][0] for r in v1 if str(r.get('publisher_report_id')) in rep}
  v1all={r:v for r,v in rep.items() if v[0] in sets}
  listed={str(r.get('publisher_report_id')) for r in v1}
  v2d=[v['public_date'] for v in m['versions'] if v['label']=='v2'][0]
  missing={r:v[1] for r,v in v1all.items() if r not in listed}
  before_v2={r:dt for r,dt in missing.items() if dt<=v2d}
  res[d]=dict(sets=sorted(sets),listed=sorted(listed),v1_all=sorted(v1all),missing_before_v2=before_v2,missing_after_v2={r:dt for r,dt in missing.items() if dt>v2d},unresolved_set=not sets)
  tot['papers']+=1; tot['complete' if not before_v2 and sets else ('noset' if not sets else 'missing')]+=1
print(tot)
for k,v in res.items():
  if v['missing_before_v2'] or v['unresolved_set']: print(k,v['listed'],v['missing_before_v2'],'noset' if v['unresolved_set'] else '')
json.dump(res,open(sys.argv[2],'w'),indent=1)
