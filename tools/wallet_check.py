#!/usr/bin/env python3
"""Truth-check a Polymarket account against the public Data API (read-only, no credentials).

  python3 -I tools/wallet_check.py <profile-name | 0xaddress> [--monthly] [--json]

Prints the all-time PnL decomposition. The number shown on a polymarket.com profile ("Profit/Loss")
is `trade_pnl`, i.e. BEFORE taker fees and before rebates. What the account really kept is `economic_pnl`:

    economic_pnl = trade_pnl + fees (negative) + taker_rebate + maker_rebate + reward_income (+ unrealized)

A strategy whose economic_pnl is mostly rebates only works for accounts in high volume tiers.
"""
import argparse, json, sys, time, urllib.parse, urllib.request, datetime as dt, collections

UA = "Mozilla/5.0"
GAMMA = "https://gamma-api.polymarket.com"
DATA = "https://data-api.polymarket.com/v2"


def get(url, data=None, tries=5):
    last = None
    for i in range(tries):
        try:
            headers = {"User-Agent": UA, "Accept": "application/json"}
            body = None
            if data is not None:
                body = json.dumps(data).encode()
                headers["Content-Type"] = "application/json"
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise SystemExit(f"fetch failed: {url}: {last}")


def resolve(ref):
    """profile name -> (name, proxy wallet); address passes through."""
    if ref.lower().startswith("0x") and len(ref) == 42:
        return ref, ref.lower()
    d = get(f"{GAMMA}/public-search?" + urllib.parse.urlencode({"q": ref, "search_profiles": "true", "limit_per_type": 10}))
    profs = d.get("profiles") or []
    exact = [p for p in profs if (p.get("name") or "").lower() == ref.lower()]
    pick = (exact or profs or [None])[0]
    if not pick:
        raise SystemExit(f"profile not found: {ref}")
    if not exact:
        sys.stderr.write(f"note: no exact name match, using closest: {pick.get('name')}\n")
    return pick.get("name"), pick.get("proxyWallet")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ref"); ap.add_argument("--monthly", action="store_true"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    name, wallet = resolve(a.ref)
    st = (get(f"{DATA}/user-stats?user={wallet}").get("data")) or {}
    p = st.get("all_time_pnl") or {}
    out = {"name": name, "wallet": wallet, "markets_traded": st.get("trades"), "join_date": st.get("join_date"), "all_time_pnl": p}
    try:
        out["taker_tier"] = (get(f"{GAMMA}/tiers", {"addresses": [wallet]}).get("tiers") or [None])[0]
        out["maker_tier"] = (get(f"{GAMMA}/v1/maker-tier/tiers", {"addresses": [wallet]}).get("tiers") or [None])[0]
    except SystemExit:
        pass
    months = None
    if a.monthly:
        pts = sorted(((get(f"{DATA}/user-pnl?user={wallet}&interval=all&fidelity=1d").get("data")) or {}).get("points") or [], key=lambda x: x["timestamp"])
        last = collections.OrderedDict()
        for q in pts:
            last[dt.datetime.fromtimestamp(q["timestamp"], dt.timezone.utc).strftime("%Y-%m")] = q
        months = []
        prev = {}
        for m, q in last.items():
            def dlt(k):
                return (q.get(k) or 0) - (prev.get(k) or 0)
            gross, fees = dlt("trade_pnl"), dlt("fees")
            reb = dlt("taker_rebate") + dlt("maker_rebate") + dlt("reward_income")
            months.append({"month": m, "gross": round(gross), "fees": round(fees), "rebates": round(reb), "net": round(gross + fees + reb),
                           "net_no_rebates": round(gross + fees), "volume_usdc": round(dlt("volume_usdc")), "fills": round(dlt("trade_count"))})
            prev = q
        out["monthly"] = months
    if a.json:
        print(json.dumps(out, indent=1))
        return
    g = lambda k: p.get(k) or 0.0  # noqa: E731
    reb = g("taker_rebate") + g("maker_rebate") + g("reward_income")
    vol = g("volume_usdc")
    jd = dt.datetime.fromtimestamp(st["join_date"], dt.timezone.utc).strftime("%Y-%m-%d") if st.get("join_date") else "?"
    print(f"{name}  {wallet}  joined {jd}  markets traded {st.get('trades')}  fills {int(g('trade_count'))}")
    print(f"  profile 'Profit/Loss' (trade_pnl, BEFORE fees): {g('trade_pnl'):>14,.0f}")
    print(f"  taker fees paid:                               {g('fees'):>14,.0f}")
    print(f"  = after fees, before rebates:                  {g('trade_pnl') + g('fees'):>14,.0f}")
    print(f"  rebates+rewards (taker {g('taker_rebate'):,.0f} / maker {g('maker_rebate'):,.0f} / rewards {g('reward_income'):,.0f}): {reb:>10,.0f}")
    print(f"  ECONOMIC PnL (what was really kept):           {g('economic_pnl'):>14,.0f}   unrealized {g('unrealized_pnl'):,.0f}")
    if vol:
        print(f"  volume ${vol:,.0f} ({g('volume'):,.0f} shares): gross {g('trade_pnl') / vol * 100:+.2f}% of volume, fees {g('fees') / vol * 100:.2f}%, net {g('economic_pnl') / vol * 100:+.2f}%")
    if g("economic_pnl"):
        print(f"  share of net that is rebates/rewards: {reb / g('economic_pnl') * 100:.0f}%")
    for k in ("taker_tier", "maker_tier"):
        if out.get(k):
            print(f"  {k}: {json.dumps(out[k])}")
    if months:
        print(f"  {'month':8s} {'gross':>10s} {'fees':>10s} {'rebates':>9s} {'NET':>10s} {'net w/o reb':>11s} {'volume$':>12s} {'fills':>9s}")
        for m in months:
            print(f"  {m['month']:8s} {m['gross']:>10,d} {m['fees']:>10,d} {m['rebates']:>9,d} {m['net']:>10,d} {m['net_no_rebates']:>11,d} {m['volume_usdc']:>12,d} {m['fills']:>9,d}")


if __name__ == "__main__":
    main()
