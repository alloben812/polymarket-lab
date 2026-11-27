"""Audit diagnostics (post hoc, not a verdict): V1 with different entry timing, plus aggregated-rows depth."""
import sys; sys.path.insert(0,'.')
import recompute_v1 as R, collections
import json
# hack: parametrize window start via monkeypatch of run
def run_win(a_h,b_min,pick='first'):
    import gzip,os,re
    out=[]
    for e in R.evs:
        pass
    return out
# simplest: reuse run() but with different windows by editing function copy
import types, inspect
src=inspect.getsource(R.run)
src=src.replace("def run(","def run2(").replace("a,b=st-win_h*3600, st-300","a,b=st-win_h*3600, st-end_min*60").replace("verbose=False):","verbose=False, end_min=5, pick='first'):")
src=src.replace("            for r in sorted(rows,key=lambda r:r['t']):","            rr=sorted(rows,key=lambda r:r['t'])\n            if pick=='last': rr=rr[::-1]\n            for r in rr:")
ns=dict(R.__dict__); exec(src,ns); run2=ns['run2']
for name,kw in [('first in [-24h,-5m] (study)',dict()),
                ('first in [-24h,-6h]',dict(win_h=24,end_min=360)),
                ('first in [-6h,-5m]',dict(win_h=6)),
                ('first in [-1h,-5m]',dict(win_h=1)),
                ('LAST buyable row in [-24h,-5m] (earlier lead used last pre-start price)',dict(pick='last')),
                ('LAST buyable row in [-6h,-5m]',dict(win_h=6,pick='last')),
                ('first, fee 0.04',dict(rate=0.04)),
                ('first, wider price 0.30-0.97',dict(lo_px=0.30,hi_px=0.97)),
                ('first, price 0.50-0.80',dict(hi_px=0.80)),
                ('first, price 0.80-0.95',dict(lo_px=0.80)),
                ]:
    tr=run2(**kw)
    print(name); 
    R.summ(tr,'  all'); R.summ([t for t in tr if t['seg']=='S1'],'  S1'); R.summ([t for t in tr if t['seg']=='S2'],'  S2')
print('---- [-6h,-5m] first-row variant attacks')
import datetime as dt
tr=run2(win_h=6)
R.summ(tr,'all')
by=collections.defaultdict(float)
for t in tr: by[t['ev']]+=t['pnl']
best=set(sorted(by,key=lambda e:-by[e])[:3])
R.summ([t for t in tr if t['ev'] not in best],'drop 3 best events')
R.summ(run2(win_h=6,slip=0.01),'price +0.01')
R.summ(run2(win_h=6,rate=0.04),'fee 0.04')
wk=lambda t: dt.datetime.fromtimestamp(t['st'],dt.timezone.utc).weekday()>=5
R.summ([t for t in tr if wk(t)],'weekend'); R.summ([t for t in tr if not wk(t)],'weekday')
m=collections.defaultdict(list)
for t in tr: m[dt.datetime.fromtimestamp(t['st'],dt.timezone.utc).strftime('%Y-%m')].append(t)
for k in sorted(m): R.summ(m[k],'month '+k)
print('mean stake',sum(t['stake'] for t in tr)/len(tr),'trades/day',len(tr)/119)
