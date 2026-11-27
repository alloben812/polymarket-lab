"""Protocol run: V1 (aggregate makers), V2 (touch-maker, strict-through), V2o (touch-maker, at-price) markouts.
Writes per-fill table to data/gaps_maker_edge/fills.parquet and per-market sums to out/."""
import gzip, json, math, datetime as dt
import numpy as np, pandas as pd

D = "/home/user/polymarket-lab/data/gaps_maker_edge"
LAG, STALE_MID, STALE_Q, STEP, LAT, CLIP = 3, 3600, 900, 10, 2, 10.0
PB = [0, 0.05, 0.20, 0.40, 0.60, 0.80, 0.95, 1.0001]
PBL = ["<.05", ".05-.20", ".20-.40", ".40-.60", ".60-.80", ".80-.95", ">=.95"]
TB = [-1e18, 300, 3600, 6 * 3600, 86400, 3 * 86400, 1e18]
TBL = ["<5m", "5-60m", "1-6h", "6-24h", "1-3d", ">3d"]
EPS = 1e-6


def ts(s):
    if not s: return None
    s = s.replace(" ", "T").replace("+00", "+00:00") if "+00:00" not in s else s.replace(" ", "T")
    if s.endswith("Z"): s = s[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(s).timestamp()
    except ValueError:
        return None


class Mid:
    def __init__(self, tm, x, d, tres, pay0):
        a = d > 0
        self.ta, self.xa = tm[a], x[a]
        self.tb, self.xb = tm[~a], x[~a]
        self.tres, self.pay0 = tres, pay0

    def side(self, tt, xx, T, stale):
        i = np.searchsorted(tt, T, side="right") - 1
        ok = i >= 0
        i2 = np.where(ok, i, 0)
        val = np.where(ok, xx[i2] if len(xx) else np.nan, np.nan)
        age = np.where(ok, T - (tt[i2] if len(tt) else 0), np.inf)
        return np.where(age <= stale, val, np.nan)

    def mid0(self, T):
        m = (self.side(self.ta, self.xa, T, STALE_MID) + self.side(self.tb, self.xb, T, STALE_MID)) / 2
        return np.where(T >= self.tres, self.pay0, m)


def market(r):
    rows = [json.loads(l) for l in gzip.open(f"{D}/tapes/{r['conditionId']}.jsonl.gz", "rt")]
    if not rows: return None
    outs = json.loads(r["outcomes"]); tok0 = outs[0]
    pay0 = float(r["payout"][0])
    tres = ts(r.get("closedTime")) or ts(r.get("endDate"))
    tick = float(r.get("orderPriceMinTickSize") or 0.01)
    t = np.array([q["t"] for q in rows], float) - LAG
    is0 = np.array([q["o"] == tok0 for q in rows]); buy = np.array([q["s"] == "BUY" for q in rows])
    p = np.array([q["p"] for q in rows], float); z = np.array([q["z"] for q in rows], float)
    x = np.where(is0, p, 1 - p); d = np.where(is0 == buy, 1, -1)
    o = np.argsort(t, kind="stable"); t, x, d, z = t[o], x[o], d[o], z[o]
    M = Mid(t, x, d, tres, pay0)
    out = []

    def emit(var, tf, q, tokX, sh):
        # maker buys token X (0 or 1) at q, shares sh, at match time tf
        payX = np.where(tokX == 0, pay0, 1 - pay0)
        res = {"var": var, "tf": tf, "q": q, "sh": sh, "fin": payX - q}
        for h in (30, 300):
            m0 = M.mid0(tf + h)
            res[f"m{h}"] = np.where(tokX == 0, m0, 1 - m0) - q
        res["ttr"] = tres - tf
        out.append(pd.DataFrame(res))

    # V1: every print, maker opposite the taker
    tokX = np.where(d > 0, 1, 0); q = np.where(d > 0, 1 - x, x)
    emit("V1", t, q, tokX, z)
    # V2 / V2o: touch-maker on a 10 s grid
    if tres is None or len(t) == 0: return out
    tau = np.arange(t[0], tres, STEP)
    if len(tau) == 0: return out
    b = M.side(M.tb, M.xb, tau, STALE_Q); a = M.side(M.ta, M.xa, tau, STALE_Q)
    b = np.round(b / tick) * tick; a = np.round(a / tick) * tick
    live = np.isfinite(a) & np.isfinite(b) & (a > b + EPS) & (b > EPS) & (a < 1 - EPS)
    for var, strict in (("V2", True), ("V2o", False)):
        for sidev in (-1, 1):
            sel = d == sidev
            ts_, xs_, zs_ = t[sel], x[sel], z[sel]
            if len(ts_) == 0: continue
            u = ts_ - tau[0] - LAT
            k = np.ceil(u / STEP).astype(np.int64) - 1
            rem = u - k * STEP
            inwin = (k >= 0) & (k < len(tau)) & (rem > 0) & (rem <= STEP - LAT)
            k2 = np.where(inwin, k, 0)
            lvl = np.where(sidev < 0, b[k2], a[k2])
            if strict:
                hit = (xs_ < lvl - EPS) if sidev < 0 else (xs_ > lvl + EPS)
            else:
                hit = (xs_ <= lvl + EPS) if sidev < 0 else (xs_ >= lvl - EPS)
            hit &= inwin & live[k2]
            idx = np.nonzero(hit)[0]
            if len(idx) == 0: continue
            _, first = np.unique(k[idx], return_index=True)
            idx = idx[first]
            if sidev < 0:  # our bid for token0 at b filled
                qq = lvl[idx]; tok = np.zeros(len(idx), int)
            else:          # our offer of token0 at a = bid for token1 at 1-a
                qq = 1 - lvl[idx]; tok = np.ones(len(idx), int)
            sh = np.minimum(CLIP / qq, zs_[idx])
            emit(var, ts_[idx], qq, tok, sh)
    return out


def main():
    import sys
    sname = sys.argv[1] if len(sys.argv) > 1 else "sample.json"; oname = sys.argv[2] if len(sys.argv) > 2 else "fills.parquet"
    sel = json.load(open(f"{D}/{sname}"))
    frames = []
    for r in sel:
        try:
            parts = market(r)
        except FileNotFoundError:
            continue
        if not parts: continue
        f = pd.concat(parts, ignore_index=True)
        f["cid"] = r["conditionId"]; f["family"] = r["family"]; f["half"] = r["half"]
        frames.append(f)
    F = pd.concat(frames, ignore_index=True)
    F["pb"] = pd.cut(F.q, PB, labels=PBL, right=False).astype(str)
    F["tb"] = pd.cut(F.ttr, TB, labels=TBL, right=False).astype(str)
    F["wkend"] = pd.to_datetime(F.tf, unit="s").dt.dayofweek >= 5
    F.to_parquet(f"{D}/{oname}")
    print(F.groupby(["var", "half"]).size())


if __name__ == "__main__":
    main()
