# Rule fixed before running (one variant): KLGA, local days 2026-09-01..2026-11-26 (America/New_York).
# Settlement value = max over ROUTINE METARs (IEM report_type=3) of T-group temp, C*9/5+32 rounded half-up to whole F.
# "Feed" value = max over 5-minute HFMETAR obs (IEM report_type=1) of the same day, same conversion.
# Question: on what share of days does the 5-minute running max land in a different whole-F value / different
# 2F bucket (floor(F/2)) than the settlement value? (If often, "running max makes a bucket certain" is wrong.)
import urllib.request,csv,io,math,collections,sys
def fetch(rt):
    u=('https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=LGA&data=tmpf&data=metar'
       '&year1=2026&month1=9&day1=1&year2=2026&month2=11&day2=27&tz=America%2FNew_York&format=onlycomma'
       f'&latlon=no&missing=M&trace=T&direct=no&report_type={rt}')
    t=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'research-client'}),timeout=120).read().decode()
    return list(csv.DictReader(io.StringIO(t)))
def rhu(x): return math.floor(x+0.5)
import re
def tempF(row):
    m=re.search(r' T([01])(\d{3})\d{4}',row.get('metar') or '')
    if m:
        c=(-1 if m.group(1)=='1' else 1)*int(m.group(2))/10
        return c*9/5+32,'T'
    try: return float(row['tmpf']),'tmpf'
    except Exception: return None,None
out={}
for rt,name in ((3,'routine'),(1,'hf')):
    rows=fetch(rt); print(name,'rows',len(rows), 'sample:',rows[len(rows)//2] if rows else None)
    d=collections.defaultdict(list); src=collections.Counter()
    for r in rows:
        f,s=tempF(r)
        if f is None: continue
        src[s]+=1; d[r['valid'][:10]].append(f)
    print(name,'temp source counts',dict(src))
    out[name]={k:max(v) for k,v in d.items()}; out[name+'_n']={k:len(v) for k,v in d.items()}
days=sorted(set(out['routine'])&set(out['hf'])); days=[x for x in days if x<='2026-11-26']
difF=difB=hi=0; gaps=[]
for x in days:
    a=rhu(out['routine'][x]); b=rhu(out['hf'][x])
    if a!=b: difF+=1
    if a//2!=b//2: difB+=1
    if b>a: hi+=1
    gaps.append(out['hf'][x]-out['routine'][x])
print('days',len(days),'| different whole F',difF,'| different 2F bucket',difB,'| hf max above routine max (whole F)',hi)
import statistics as st
print('gap hf-routine F: median',round(st.median(gaps),2),'max',round(max(gaps),2),'min',round(min(gaps),2))
print('median obs/day routine',st.median(out['routine_n'].values()),'hf',st.median(out['hf_n'].values()))
