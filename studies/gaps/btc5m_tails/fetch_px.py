"""Binance 1-second dumps for the study period (data.binance.vision, one file per day, sequential) and a dense cache."""
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from pmlab import px  # noqa: E402

START, END = 1788220800, 1795737600
OUT = ROOT / "data" / "gaps_btc5m_tails"


def main() -> None:
    days = px.days_between(START - 86400, END)  # one day before for volatility lookbacks
    missing = []
    for d in days:
        p = px.download_day("BTCUSDT", d)
        if p is None:
            missing.append(d)
        time.sleep(0.3)
    print("days", len(days), "missing dumps", missing, flush=True)
    P = px.Px.load("BTCUSDT", days)
    np.savez_compressed(OUT / "px_dense.npz", t_min=P.t_min, p=P.p)
    print("dense", P.t_min, P.t_max, "nan share", float(np.isnan(P.p).mean()), flush=True)


if __name__ == "__main__":
    main()
