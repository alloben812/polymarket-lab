"""Label each fill row as taker/maker by multiset difference between the full feed and the taker-only feed."""
import json,sys,collections
def load(p): return [json.loads(l) for l in open(p)]
def key(r): return (r['transaction_hash'], r['token_id'], r['side'], round(r['price'],8), round(r['size'],6), r['timestamp'])
allr=load(sys.argv[1]); tk=load(sys.argv[2]); out=sys.argv[3]
c=collections.Counter(key(r) for r in tk)
nt=nm=0
with open(out,'w') as f:
    for r in allr:
        k=key(r)
        if c[k]>0: c[k]-=1; r['role']='T'; nt+=1
        else: r['role']='M'; nm+=1
        f.write(json.dumps(r)+'\n')
left=sum(c.values())
print(f"rows all={len(allr)} taker_feed={len(tk)} labeled T={nt} M={nm} unmatched_taker_rows={left}")
