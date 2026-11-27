import json, collections
import sys; sys.path.insert(0, "/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/audit")
from a1 import *
conf=json.load(open(f"{D}/confirm.json"))
print("confirm move_off / busiest by release (sorted by T):")
for rel,c in sorted(conf.items(), key=lambda kv: kv[1]["T"]):
    print(f"  {rel:<19}{c['when']} tier {c['tier']} move_off={c['move_off']} ref={c['ref']} to={c['to']} busiest={c['busiest']} n={c['busiest_n']}/{c['n_1h']} -> {status[rel][:40]}")
res={m["cond"]: e4(rows_gaps(m), m, 30) for m in kept}
print("\nMarkets with +30 s fills:")
tot=0
for m in sorted(kept, key=lambda m:-res[m["cond"]]["net"]):
    r=res[m["cond"]]
    if not r["fills"]: continue
    tot+=r["net"]
    print(f"\n{m['release']} | {m['slug'][:70]} | vol {m['vol']:,.0f} | winner {m['winner']} | flag: {m['flag'][:40]!r} | closed +{(m['closed_ts']-m['T'])/3600:.1f}h | net {r['net']:.1f} cost {r['cost']:.0f}")
    print("   fills:", r["fills"][:14], "..." if len(r["fills"])>14 else "")
    w = 0 if m["winner"]=="Yes" else 1
    rows=sorted(rows_gaps(m), key=lambda r:r[0])
    seg=[(ts-3-m["T"], side, "W" if oi==w else "L", p, round(z,1), (wal or "")[:8]) for ts,side,oi,p,z,wal in rows if -900 <= ts-3-m["T"] <= 600]
    pre=[x for x in seg if x[0]<0][-5:]; post=[x for x in seg if x[0]>=0][:28]
    print("   last pre :", pre)
    print("   post     :", post)
print("total", tot)
