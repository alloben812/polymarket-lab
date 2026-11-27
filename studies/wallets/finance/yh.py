"""Yahoo chart API loader (the only intraday source with history that answered from the sandbox). 1-minute bars with
pre/post market, cached per ticker. Used as a PROXY for the Pyth candles the markets settle on."""
import json, os, time, bisect, math, statistics, urllib.request, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
MAP = {"SPX": "^GSPC", "DJIA": "^DJI", "NDX": "^NDX", "RUT": "^RUT", "NIK": "^N225", "XAUUSD": "GC=F", "XAGUSD": "SI=F", "WTI": "CL=F", "DXY": "DX-Y.NYB", "BRK.B": "BRK-B"}
T0, T1 = 1793232000, 1795795200       # 2026-10-29 00:00 .. 2026-11-27 16:00 UTC
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) research-client"}

def _get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except Exception as e:
            err = e; time.sleep(1.5 * (i + 1))
    raise err

def bars(tk):
    """dict(t=[...], o,h,l,c=[...]) 1-minute incl. pre/post; plus daily closes; None if Yahoo has nothing."""
    p = f"{HERE}/cache/yahoo/{tk.replace('^', '_').replace('=', '_')}.json"
    if os.path.exists(p): return json.load(open(p))
    sym = urllib.parse.quote(MAP.get(tk, tk)); out = dict(t=[], o=[], h=[], l=[], c=[])
    try:
        a = T0
        while a < T1:
            b = min(a + 7 * 86400, T1)
            j = _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1m&period1={a}&period2={b}&includePrePost=true")
            r = (j.get("chart", {}).get("result") or [None])[0]
            if r and r.get("timestamp"):
                q = r["indicators"]["quote"][0]
                for i, t in enumerate(r["timestamp"]):
                    if q["close"][i] is None: continue
                    out["t"].append(t); [out[k].append(q[n][i]) for k, n in (("o", "open"), ("h", "high"), ("l", "low"), ("c", "close"))]
            a = b; time.sleep(0.25)
        j = _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=6mo")
        r = j["chart"]["result"][0]; cl = [x for x in r["indicators"]["quote"][0]["close"] if x]
        rets = [math.log(cl[i] / cl[i - 1]) for i in range(1, len(cl))][-60:]
        out["sigma_d"] = statistics.pstdev(rets); out["n_daily"] = len(rets)
    except Exception as e:
        out = dict(error=str(e)[:100])
    json.dump(out, open(p, "w")); return out

# ---- US equity calendar for the window (ET = UTC-4 until 2026-11-01, UTC-5 after; Nov 26 closed, Nov 27 half day)
def session(day_epoch):
    """(open, close) UTC epochs of the regular session of the UTC calendar day starting at day_epoch, or None."""
    import datetime as dt
    d = dt.datetime.fromtimestamp(day_epoch, dt.timezone.utc)
    if d.weekday() >= 5 or (d.month, d.day) == (11, 26): return None
    off = 4 if (d.month, d.day) < (11, 1) else 5
    op = day_epoch + int((9.5 + off) * 3600); cl = day_epoch + (16 + off) * 3600
    if (d.month, d.day) == (11, 27): cl = day_epoch + (13 + off) * 3600
    return op, cl

def var_left(t, T, w_rth=0.7):
    """Remaining variance from t to T in units of one daily variance: RTH time carries w_rth, each gap between sessions 1-w_rth."""
    v = 0.0; day = (min(t, T) // 86400) * 86400 - 86400; prev_close = None
    while day <= T:
        s = session(day)
        if s:
            op, cl = s
            if prev_close is not None or True:
                # overnight gap ending at this open
                if op > t and op <= T + 1: v += (1 - w_rth) if (prev_close is None or prev_close < op) and t < op else 0
            a, b = max(t, op), min(T, cl)
            if b > a: v += w_rth * (b - a) / (cl - op)
            prev_close = cl
        day += 86400
    return v

def phi(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))

class Px:
    def __init__(self, tk):
        self.b = bars(tk); self.ok = bool(self.b.get("t")); self.sig = self.b.get("sigma_d")
    def last(self, t):
        i = bisect.bisect_right(self.b["t"], t - 60) - 1          # bar that CLOSED at or before t
        return (self.b["c"][i], t - 60 - self.b["t"][i]) if i >= 0 else (None, None)
    def rth_close(self, day_epoch):
        s = session(day_epoch)
        if not s: return None
        i = bisect.bisect_right(self.b["t"], s[1] - 60) - 1
        return self.b["c"][i] if i >= 0 and self.b["t"][i] >= s[1] - 600 else None
    def prev_close(self, t):
        day = (t // 86400) * 86400
        for k in range(0, 8):
            s = session(day - k * 86400)
            if s and s[1] <= t:
                c = self.rth_close(day - k * 86400)
                if c: return c, s[1]
        s = session(day)
        return (None, None)
    def extreme(self, a, b, hi=True):
        """max High (or min Low) of RTH 1-minute bars with a <= bar start and bar end <= b; and the time it was first reached at level asked later."""
        i0 = bisect.bisect_left(self.b["t"], a); i1 = bisect.bisect_right(self.b["t"], b - 60); best = None
        for i in range(i0, i1):
            t = self.b["t"][i]; s = session((t // 86400) * 86400)
            if not s or not (s[0] <= t < s[1]): continue
            x = self.b["h"][i] if hi else self.b["l"][i]
            if best is None or (x > best if hi else x < best): best = x
        return best
    def first_touch(self, a, b, K, hi=True):
        i0 = bisect.bisect_left(self.b["t"], a); i1 = bisect.bisect_right(self.b["t"], b)
        for i in range(i0, i1):
            t = self.b["t"][i]; s = session((t // 86400) * 86400)
            if not s or not (s[0] <= t < s[1]): continue
            if (self.b["h"][i] >= K) if hi else (self.b["l"][i] <= K): return t + 60     # end of the candle
        return None
