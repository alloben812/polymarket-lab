"""Loader for Binance 1s klines (zip dumps) -> dense per-second close array, plus the TWAP binary fair-value model."""
import zipfile, io, glob, os, math
import numpy as np
class Btc:
    def __init__(self, folder, days=None):
        ts=[]; px=[]
        for p in sorted(glob.glob(os.path.join(folder,"BTCUSDT-1s-*.zip"))):
            day=os.path.basename(p)[len("BTCUSDT-1s-"):-4]
            if days and day not in days: continue
            with zipfile.ZipFile(p) as z:
                name=z.namelist()[0]
                raw=z.read(name).decode()
            a=np.genfromtxt(io.StringIO(raw), delimiter=",", usecols=(0,4))
            t=a[:,0]
            # dumps use microseconds since 2025; normalise to seconds
            t=np.where(t>1e14, t/1e6, t/1e3).astype(np.int64)
            ts.append(t); px.append(a[:,1])
        ts=np.concatenate(ts); px=np.concatenate(px)
        o=np.argsort(ts); ts=ts[o]; px=px[o]
        self.t_min=int(ts[0]); self.t_max=int(ts[-1])
        dense=np.full(self.t_max-self.t_min+1, np.nan)
        dense[ts-self.t_min]=px
        # forward-fill gaps (seconds without klines / missing days stay NaN across long gaps)
        idx=np.where(~np.isnan(dense), np.arange(len(dense)), 0); np.maximum.accumulate(idx, out=idx)
        gap=np.arange(len(dense))-idx
        filled=dense[idx]; filled[gap>120]=np.nan
        self.p=filled
        self.cs=np.nancumsum(np.where(np.isnan(filled),0,filled))  # prefix sums for fast TWAP
        self.ok=~np.isnan(filled)
        self.cok=np.cumsum(self.ok)
        lr=np.diff(np.log(filled)); lr[~np.isfinite(lr)]=0.0
        self.csq=np.concatenate([[0.0],np.cumsum(lr*lr)])
    def price(self,t):
        i=int(t)-self.t_min
        if i<0 or i>=len(self.p): return float('nan')
        return float(self.p[i])
    def twap(self,t_end,L=60):
        """average of closes over seconds (t_end-L, t_end]"""
        j=int(t_end)-self.t_min; i=j-L
        if i<0 or j>=len(self.p): return float('nan')
        n=self.cok[j]-self.cok[i]
        if n<L*0.8: return float('nan')
        return float((self.cs[j]-self.cs[i])/n)
    def sigma(self,t,look=900):
        """per-second log-return volatility over the trailing `look` seconds ending at t"""
        j=int(t)-self.t_min; i=j-look
        if i<0 or j>=len(self.csq): return float('nan')
        return math.sqrt(max((self.csq[j]-self.csq[i])/look,1e-18))
def ncdf(x): return 0.5*(1.0+math.erf(x/math.sqrt(2.0)))
def fair_up(btc,t,t0,K=None,L=60,dur=300,look=900,sig=None,sig_mult=1.0):
    """P(final L-second TWAP >= K) at time t for a window starting at t0 (settle TWAP over (t0+dur-L, t0+dur])."""
    if K is None: K=btc.twap(t0,L)
    S=btc.price(t)
    if sig is None: sig=btc.sigma(t,look)
    if not (K==K and S==S and sig==sig): return float('nan')
    sig*=sig_mult
    T_avg0=t0+dur-L; T_end=t0+dur
    if t>=T_end:
        A=btc.twap(T_end,L); return 1.0 if A>=K else 0.0
    if t<=T_avg0:
        tau1=T_avg0-t
        mean=S; var=(sig*S)**2*(tau1+L/3.0)
    else:
        e=t-T_avg0; r=T_end-t
        j=int(t)-btc.t_min; i=int(T_avg0)-btc.t_min
        n=btc.cok[j]-btc.cok[i]; sofar=(btc.cs[j]-btc.cs[i])/max(n,1)
        mean=(e/L)*sofar+(r/L)*S
        var=((r/L)*sig*S)**2*(r/3.0)
    sd=math.sqrt(max(var,1e-12))
    return ncdf((mean-K)/sd)
