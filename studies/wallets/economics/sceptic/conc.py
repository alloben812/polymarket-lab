"""Sceptic check 2: concentration. Per-market net (pmlab.wallet, resolved complete markets) with the three best
markets removed; economics only and all families; also clustered by event (slug prefix heuristics via fills pickle)."""
import json, sys, pickle, os, math, collections
def load(p): return json.load(open(p))
def tstat(xs):
    n=len(xs)
    if n<3: return None
    m=sum(xs)/n; v=sum((x-m)**2 for x in xs)/(n-1)
    return m/math.sqrt(v/n) if v>0 else None
def rep(label, path, pkl=None):
    d=load(path); ms=[m for m in d['_markets'] if m.get('resolved') and not m.get('incomplete') and m.get('turnover',0)>0]
    ev={}
    if pkl and os.path.exists(pkl):
        for r in pickle.load(open(pkl,'rb')): ev[r['condition_id']]=r.get('event_slug') or r.get('slug')
    for fam in ('economics', None):
        sel=[m for m in ms if fam is None or m['family']==fam]
        if not sel: continue
        nets=sorted((m['net'] for m in sel), reverse=True); tot=sum(nets)
        top=sorted(sel,key=lambda m:-m['net'])[:3]
        print(f"{label:14} {fam or 'all':9} markets={len(sel):4d} net={tot:9.0f} t_mkt={tstat(nets) and round(tstat(nets),2)} top3={sum(nets[:3]):8.0f} rest={tot-sum(nets[:3]):8.0f} t_rest={tstat(nets[3:]) and round(tstat(nets[3:]),2)} worst3={sum(nets[-3:]):8.0f} pos={sum(1 for x in nets if x>0)}/{len(nets)}")
        for m in top: print(f"      top: {m['slug'][:60]:60} net={m['net']:8.0f} turnover={m['turnover']:8.0f}")
        if ev:
            by=collections.defaultdict(float)
            for m in sel: by[ev.get(m['condition'], m['slug'])]+=m['net']
            xs=sorted(by.values(), reverse=True)
            print(f"      by event: events={len(xs)} t_event={tstat(xs) and round(tstat(xs),2)} top3={sum(xs[:3]):.0f} rest={sum(xs[3:]):.0f} t_rest={tstat(xs[3:]) and round(tstat(xs[3:]),2)} pos={sum(1 for x in xs if x>0)}/{len(xs)}")
T='/home/user/polymarket-lab/data/econ_tapes/'
rep('perfectnosta 88d','perfectnosta_88d.json',T+'fills_perfectnosta.pkl')
rep('perfectnosta JunAug','sceptic/perfectnosta_jun_aug.json')
rep('jozes 88d','jozeslemsek_88d.json',T+'fills_jozeslemsek.pkl')
rep('jozes JunAug','sceptic/jozes_jun_aug.json')
rep('Element JulAug','sceptic/element_jul_aug.json')
rep('Ahpo 88d','Ahpo_88d.json',T+'fills_Ahpo.pkl')
