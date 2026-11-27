"""Independent audit step 1: Binance 1s closes -> signal seconds (own implementation of the protocol rule), and
check of the yes/no -> Up/Down mapping of the dataset against Binance. Imports nothing from pmlab or the study."""
import glob, io, math, zipfile, sys
import numpy as np, pandas as pd
from statistics import NormalDist
R = "/home/user/polymarket-lab/"
ND = NormalDist()

def load_btc(days):
    T, C = [], []
    for d in days:
        f = f"{R}data/binance_1s/BTCUSDT-1s-{d}.zip"
        with zipfile.ZipFile(f) as z:
            df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), header=None, usecols=[0, 4])
        t = df[0].to_numpy(dtype=np.int64)
        t = np.where(t > 10**14, t // 10**6, t // 10**3)   # us -> s (2025+ dumps are microseconds)
        T.append(t); C.append(df[4].to_numpy(dtype=float))
    T = np.concatenate(T); C = np.concatenate(C)
    o = np.argsort(T); T, C = T[o], C[o]
    t_min, t_max = T[0], T[-1]
    dense = np.full(t_max - t_min + 1, np.nan); dense[T - t_min] = C
    # forward fill (gaps are rare)
    s = pd.Series(dense).ffill(limit=120).to_numpy()
    return t_min, s

t_min, S = load_btc([f"2026-08-{d}" for d in range(13, 23)])
print("binance secs", len(S), "nan", int(np.isnan(S).sum()), "first", pd.Timestamp(t_min, unit="s"))
lr = np.diff(np.log(S)); lr[~np.isfinite(lr)] = 0.0
csq = np.concatenate([[0.0, 0.0], np.cumsum(lr * lr)])
cs = np.concatenate([[0.0], np.cumsum(np.nan_to_num(S))])

def px(t): return S[int(t) - t_min]
def twap(t_end, L=60):  # mean of closes of seconds (t_end-L, t_end]
    j = int(t_end) - t_min; i = j - L
    return (cs[j + 1] - cs[i + 1]) / L
def mean_between(a, b):
    i, j = int(a) - t_min, int(b) - t_min
    return (cs[j + 1] - cs[i + 1]) / (j - i)
def sigma(t, lb=900):
    j = int(t) - t_min; i = j - lb
    return math.sqrt(max((csq[j + 1] - csq[i + 1]) / lb, 1e-18))

def gap(T, t0, D=300, L=60, mult=1.3):
    """(E[A]-K)/sd[A], A = settlement 60 s average, K = 60 s TWAP at t0; sd with sigma*1.3, driftless BM."""
    K = twap(t0, L); s = px(T); sg = sigma(T) * mult
    ta0, te = t0 + D - L, t0 + D
    if T <= ta0:
        mean = s; var = (sg * s) ** 2 * ((ta0 - T) + L / 3)
    else:
        e, r = T - ta0, te - T
        mean = (e / L) * mean_between(ta0, T) + (r / L) * s
        var = ((r / L) * sg * s) ** 2 * (r / 3)
    return (mean - K) / math.sqrt(max(var, 1e-12))

def signals(t0, D=300):
    out = []
    for T in range(t0 + D - 75, t0 + D - 15):
        g = gap(T, t0, D)
        if not np.isfinite(g) or g == 0: continue
        tail = "Down" if g > 0 else "Up"
        mv_up = (px(T) / px(T - 30) - 1) * 1e4
        mv = -mv_up if tail == "Down" else mv_up
        if abs(g) < 2.61 and mv >= 0.00122:
            out.append((T, tail, abs(g), mv))
    return out

if __name__ == "__main__":
    mk = pd.read_parquet(R + "data/gaps_btc5m_tail_sniper/mw/markets.parquet")
    mk["t0"] = mk.market_slug.str.rsplit("-", n=1).str[1].astype(int)
    mk = mk[(mk.t0 >= 1786665600) & (mk.t0 < 1787356800)].reset_index(drop=True)
    rows = []
    agree = tot = 0
    flip = 0
    for t0, w in zip(mk.t0, mk.winning_outcome):
        for T, tail, d, mv in signals(int(t0)):
            rows.append((int(t0), T, tail, d, mv))
        if w in ("yes", "no"):
            up_binance = twap(t0 + 300) >= twap(t0)
            tot += 1; agree += (up_binance == (w == "yes"))
    sig = pd.DataFrame(rows, columns=["t0", "T", "tail", "dist", "mv"])
    sig.to_parquet("/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/my_signals.parquet")
    print("markets", len(mk), "signal seconds", len(sig), "markets with signal", sig.t0.nunique())
    print("yes==Up agreement with Binance TWAP outcome:", agree, "of", tot, f"{agree/tot:.3f}")
    old = pd.read_parquet(R + "data/gaps_btc5m_tail_sniper/book_signals.parquet")
    a = set(zip(old.t0, old["T"])); b = set(zip(sig.t0, sig["T"]))
    print("author signal secs", len(a), "mine", len(b), "common", len(a & b))
