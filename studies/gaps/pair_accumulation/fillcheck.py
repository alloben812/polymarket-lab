"""Attack on the negative result (post-hoc, descriptive): price of the print that fills the bid, and the next
prints after it. For a sample of BTC 5m and BTC 15m markets, L = 0.45, conservative rule."""
import gzip, json
import numpy as np, pandas as pd
from common import BIG, DUR
from pmlab import updown
legs = pd.read_parquet(BIG / "legs_main.parquet")
out = []
for ser in ("btc-5m", "btc-15m", "eth-15m", "btc-1h"):
    x = legs[(legs.series == ser) & (legs.L == 0.45) & legs.placeable & legs.t_cons.notna()]
    x = x.sample(min(400, len(x)), random_state=1)
    fp, p10, wins = [], [], []
    for r in x.itertuples():
        m = json.loads((updown.META_DIR / r.asset / r.dur / f"{r.t0}.json").read_text())
        rows = updown.tape(m["condition"])
        s = [(t, p) for t, o, p, z in updown.sellable(rows) if o == r.X and r.t0 <= t < r.t0 + DUR[r.dur]]
        tf = r.t0 + r.t_cons
        first = [p for t, p in s if t == tf and p < 0.45 - 1e-9]
        later = [p for t, p in s if tf + 5 <= t < tf + 15]
        fp.append(first[0]); p10.append(np.mean(later) if later else np.nan); wins.append(r.won)
    out.append(f"{ser}: n {len(x)}, first through print mean {np.mean(fp):.3f} (median {np.median(fp):.3f}), "
               f"mean X price 5-15 s later {np.nanmean(p10):.3f}, win rate {np.mean(wins):.3f}")
print("\n".join(out)); open("out/fillcheck.txt", "w").write("\n".join(out) + "\n")
