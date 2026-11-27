import time,collections,re,datetime as dt,json
from pmlab import dataapi
W='0x0a0c42f6b1da5a633ec1a4d45ba76eb486c1a853'
now=int(time.time())
rows=list(dataapi.iter_trades(user=W,start=now-30*86400,end=now,taker_only=False))
print('rows',len(rows)); print(json.dumps(rows[0])[:700])
oc=collections.Counter(); usd=collections.Counter(); city=collections.Counter(); hb=collections.Counter(); hbu=collections.Counter()
MON={m:i+1 for i,m in enumerate(['january','february','march','april','may','june','july','august','september','october','november','december'])}
for r in rows:
    o=str(r.get('outcome')); s=r.get('side'); p=float(r['price']); sz=float(r['size'])
    oc[(s,o)]+=1; usd[(s,o)]+=p*sz
    slug=r.get('event_slug') or r.get('eventSlug') or r.get('slug') or ''
    m=re.search(r'highest-temperature-in-(.+?)-on-([a-z]+)-(\d+)(?:-(\d{4}))?',slug)
    if not m: city['?'+slug[:30]]+=1; continue
    city[m.group(1)]+=p*sz
    y=int(m.group(4) or 2026); end=dt.datetime(y,MON[m.group(2)],int(m.group(3)),12,tzinfo=dt.timezone.utc).timestamp()
    h=(end-float(r['timestamp']))/3600
    b='>48' if h>48 else '36-48' if h>36 else '24-36' if h>24 else '18-24' if h>18 else '12-18' if h>12 else '6-12' if h>6 else '0-6' if h>0 else 'after 12Z'
    hb[b]+=1; hbu[b]+=p*sz
print('side/outcome fills',dict(oc)); print('side/outcome usd',{k:round(v) for k,v in usd.items()})
print('cities usd',[(k,round(v)) for k,v in city.most_common(14)])
print('hours before 12:00 UTC of target date: fills',dict(hb)); print('usd',{k:round(v) for k,v in hbu.items()})
# xtx: last fills
X='0xad5353afe30c2da57709e2704ef3ccdcf67eef24'
c=collections.Counter(); n=0; u=collections.Counter()
for r in dataapi.iter_trades(user=X,start=now-6*3600,end=now,taker_only=False):
    slug=r.get('event_slug') or r.get('eventSlug') or r.get('slug') or ''
    k=re.sub(r'[-\d]+$','',re.sub(r'-on-.*$','',slug))[:40]; k='temperature' if 'temperature' in slug else k
    c[k]+=1; u[k]+=float(r['price'])*float(r['size']); n+=1
    if n>=6000: break
print('xtx last 6h fills',n,[(k,v,round(u[k])) for k,v in c.most_common(12)])
