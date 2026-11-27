import json, urllib.request, datetime as dt
D="https://data-api.polymarket.com/v2"
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"}),timeout=60) as f: return json.loads(f.read())
for name,w in (("ColdMath","0x594edb9112f526fa6a80b8f858a6379c8a2c1c11"),("BeefSlayer","0x331bf91c132af9d921e1908ca0979363fc47193f"),("VibeTrader","0xcbbc5e035504421b084ad9248b660f6e9618b5d0")):
    pts=sorted(get(f"{D}/user-pnl?user={w}&interval=all&fidelity=1d")["data"]["points"],key=lambda x:x["timestamp"])
    print(name); prev=None
    for q in pts:
        d=dt.datetime.fromtimestamp(q["timestamp"],dt.timezone.utc)
        if d>=dt.datetime(2026,11,14,tzinfo=dt.timezone.utc) and prev:
            f=lambda k:(q.get(k) or 0)-(prev.get(k) or 0)
            print(f"  {d:%m-%d %H:%M} vol {f('volume_usdc'):>9,.0f} fees {f('fees'):>8,.1f} maker_reb {f('maker_rebate'):>7,.1f} taker_reb {f('taker_rebate'):>7,.1f} rewards {f('reward_income'):>6,.1f} net {f('economic_pnl'):>9,.0f}")
        prev=q
