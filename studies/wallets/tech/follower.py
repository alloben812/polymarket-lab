"""Rule F from protocol.md: buy the favoured side at 0.80-0.97 D minutes after the first sweep, hold to resolution."""
import bisect, collections, statistics as st
from common import *
from race import INFO, APP, groups, pw_rows, tape
for D in (600, 3600):
    per_ev = collections.OrderedDict(); n = wins = 0; rows_out = []
    for k in sorted((k for k in APP if APP[k]), key=lambda k: APP[k]):
        t0 = APP[k]
        for c in groups[k]:
            w = INFO[c]["winner"]; rows = tape(c)   # (t, price, size, outcome, side, wallet)
            ts = [r[0] for r in rows]; i = bisect.bisect_right(ts, t0 + D) - 1
            if i < 0: continue
            pyes = rows[i][1] if rows[i][3] == "Yes" else 1 - rows[i][1]
            fav = "Yes" if pyes >= 0.5 else "No"; pf = pyes if fav == "Yes" else 1 - pyes
            if not (0.80 <= pf < 0.97): continue
            entry = None
            for t, p, s, o, sd, wal in rows[i + 1:]:
                if t > k[1]: break
                bought = o if sd == "BUY" else ("No" if o == "Yes" else "Yes"); bp = p if sd == "BUY" else 1 - p
                if bought == fav and 0.80 <= bp < 0.97: entry = (t, bp, s); break
            if not entry: continue
            win = fav == w; pnl = 100 * ((1.0 if win else 0.0) - entry[1]) - 100 * 0.05 * entry[1] * (1 - entry[1])
            n += 1; wins += win; per_ev.setdefault(k, []).append(pnl); rows_out.append((fs(entry[0]), entry[1], win, entry[2], INFO[c]["q"][:70]))
    evs = list(per_ev.items()); half = len(evs) // 2
    tot = [sum(v) for _, v in evs]
    print(f"\nD = {D//60} min: entries {n} in {len(evs)} events, wins {wins}; net per 100-share unit: total ${sum(tot):.0f}, mean per market ${sum(tot)/n if n else 0:.2f}, mean per event ${st.mean(tot) if tot else 0:.1f} (se {st.stdev(tot)/len(tot)**.5 if len(tot)>1 else float('nan'):.1f}); events positive {sum(1 for x in tot if x>0)}/{len(tot)}")
    print(f"   earlier half ({half} events): ${sum(tot[:half]):.0f} on {sum(len(v) for _, v in evs[:half])} entries | later half: ${sum(tot[half:]):.0f} on {sum(len(v) for _, v in evs[half:])} entries; mean entry price {st.mean(r[1] for r in rows_out) if rows_out else 0:.3f}; median size of the print used as entry {st.median(r[3] for r in rows_out) if rows_out else 0:.0f} shares")
    for r in rows_out: print(f"     {r[0]} px {r[1]:.3f} {'WIN ' if r[2] else 'LOSS'} print {r[3]:6.0f} sh  {r[4]}")
