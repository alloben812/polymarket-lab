import json, sys, glob, os, datetime as dt
rows=[]
for f in sorted(glob.glob(sys.argv[1]+"/*.v2.json")):
    d=json.load(open(f)); st=d["stats"]; p=st.get("all_time_pnl") or {}
    g=lambda k: p.get(k) or 0.0
    reb=g("taker_rebate")+g("maker_rebate")+g("reward_income")+g("referral_income")
    eco=g("economic_pnl"); vol=g("volume_usdc")
    ms={m["month"]:m for m in d["monthly"]}
    def mm(k, key="net"): return ms.get(k,{}).get(key,0)
    rows.append(dict(label=d["label"], wallet=d["wallet"], joined=dt.datetime.fromtimestamp(st["join_date"], dt.timezone.utc).strftime("%Y-%m-%d") if st.get("join_date") else "?",
        markets=st.get("trades"), fills=int(g("trade_count")), gross=g("trade_pnl"), fees_ch=g("fees"), refunded=g("fees_refunded"), fees_paid=g("fees_paid"), reb=reb,
        tr=g("taker_rebate"), mr=g("maker_rebate"), rw=g("reward_income"), ref=g("referral_income"), net=eco, net_nr=eco-reb, vol=vol,
        tt=(d.get("taker_tier") or {}).get("tier_name"), twv=(d.get("taker_tier") or {}).get("wv_30d"), mbps=(d.get("maker_tier") or {}).get("rebate_bps"), mwv=(d.get("maker_tier") or {}).get("wv_30d"),
        mon=[(k, mm(k), mm(k,"net_no_reb"), mm(k,"vol")) for k in ("2026-06","2026-07","2026-08","2026-09","2026-10","2026-11")]))
rows.sort(key=lambda r:-r["net_nr"])
json.dump(rows, open(sys.argv[1]+"/_table.json","w"))
for r in rows:
    print(f"{r['label']:18s} {r['wallet'][:8]} j{r['joined']} mk {r['markets']:>7} | gross {r['gross']/1e3:8.0f}K feesPaid {r['fees_paid']/1e3:7.0f}K (refunded {r['refunded']/1e3:5.0f}K) reb {r['reb']/1e3:6.0f}K (T{r['tr']/1e3:.0f}/M{r['mr']/1e3:.0f}/R{r['rw']/1e3:.0f}/ref{r['ref']/1e3:.0f}) NET {r['net']/1e3:7.0f}K noReb {r['net_nr']/1e3:7.0f}K rebShare {r['reb']/r['net']*100 if r['net'] else 0:4.0f}% vol {r['vol']/1e6:6.1f}M net/vol {r['net']/r['vol']*100 if r['vol'] else 0:+.2f}% | tier {r['tt']} wv {round(r['twv'] or 0)} / maker {r['mbps']}bps wv {round(r['mwv'] or 0)}")
    print("      Jun-Nov net(noReb): " + " ".join(f"{n/1e3:+.0f}({nn/1e3:+.0f})" for _,n,nn,_ in r["mon"]) + "   vol$M: " + " ".join(f"{v/1e6:.1f}" for *_,v in r["mon"]))
