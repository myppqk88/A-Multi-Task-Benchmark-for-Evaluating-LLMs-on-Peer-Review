import json,os,sys,re,collections as C,datetime
B=os.path.join(sys.argv[1],'intake/batch-01'); out=json.load(open(sys.argv[2]))
tot=C.Counter()
for d in sorted(os.listdir(B)):
  if not d.startswith('F1000_'): continue
  P=os.path.join(B,d); m=json.load(open(os.path.join(P,'metadata.json')))
  h=open(os.path.join(P,'source_pages/v1.html'),encoding='utf-8',errors='replace').read()
  ids=C.defaultdict(set)
  for s,r in re.findall(r'f1000research\.(\d+)\.r(\d+)',h): ids[s].add(r)
  listed={str(r.get('publisher_report_id')) for r in m['reviews'] if r['on_version']=='v1'}
  sets=[s for s,v in ids.items() if v&listed]
  allv1=set().union(*[ids[s] for s in sets]) if sets else set()
  # dates: find 'Reviewer Report' blocks with date before each id occurrence
  v2d=[v['public_date'] for v in m['versions'] if v['label']=='v2'][0]
  miss={}
  for r in allv1-listed:
    i=h.find('.r'+r); seg=h[max(0,i-6000):i]
    ds=re.findall(r'(\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* 20\d\d)',seg)
    dt=None
    if ds:
      try: dt=datetime.datetime.strptime(ds[-1][:6].strip()+' '+ds[-1][-4:],'%d %b %Y').date().isoformat()
      except Exception: dt=None
    miss[r]=dt
  before={r:dt for r,dt in miss.items() if dt is None or dt<=v2d}
  out[d]=dict(sets=sets,listed=sorted(listed),v1_all=sorted(allv1),missing_before_v2=before,missing_after_v2={r:dt for r,dt in miss.items() if r not in before},unresolved_set=not sets)
  tot['noset' if not sets else ('missing' if before else 'complete')]+=1
  if before: print(d,sorted(listed),before)
print(tot); json.dump(out,open(sys.argv[2],'w'),indent=1)
