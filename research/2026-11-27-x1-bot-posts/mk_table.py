import json, re, datetime as dt
T={r["label"].lower():r for r in json.load(open("data/x1/w2/_table.json"))}
alias={"gravia-0xbf5f":"gravia_0xbf5f","blue.birds":"blue.birds","0xb9587c37":"0xb9587c37"}
def W(l):
    l=l.lower(); return T.get(l) or T.get(alias.get(l,l))
RV=dict(l.split() for l in """2093781031870414955 almach
2093837003724837010 hot-garbage
2094175192268341694 pspspsps5
2094543744401805557 x-MoneyForWhiskas
2094909505322541455 trinity42
2095643258600730627 antsaslyku
2095920020953965000 0xAAAAA
2096003427956662759 bosona
2096366363723907562 BoneOhio
2096691577058148535 nj23adsknml3
2097082415533424979 std0
2097474803623923861 PBot-6
2097831263453196463 trinity42
2098196382599315480 Bonereaper
2099269744494862618 Polkadot-Frog
2100000224039071871 aswfadq1555
2100375324244447353 norm1e69
2100661635245359135 98euf98a
2101014760422547888 nagi777
2103259775131673007 0xAAAAA
2103609041070993458 x-MoneyForWhiskas
2103989964513869883 pspspsps5
2104339811486077290 nj23adsknml3
2104720599394156951 Jarvisen
2105082630823960896 almach
2105424635672281526 bosona
2105765969331151215 BoneOhio
2106128985570636277 flippingsharks
2106502269860552813 NIULAI4
2106843467431174326 mo-money
2107251346151768305 norm1e69
2107611711083573454 Bonereaper
2107960525506105457 std0
2108323995607052615 antsaslyku
2109048390885490966 aswfadq1555
2109384562753323278 98euf98a
2110131234492067928 Jarvisen
2110481171565990051 wzbbb
2110814975765717260 0xDB5
2111216247199171068 Polkadot-Frog
2111519327509770360 x-MoneyForWhiskas
2111893710380404811 pspspsps5
2112272129324450189 NIULAI4
2112627991364940066 almach
2112979037303759276 BoneOhio
2113695266075291847 bosona
2114121526257787056 trinity42
2114433452972122619 norm1e69
2114481659386966031 flippingsharks
2114776565984739357 std0
2115509401809203697 0xb55fa129
2115557297057603927 0xcE25E214
2115926237809942649 Polkadot-Frog
2116304157183254670 aswfadq1555
2116613743605944533 nj23adsknml3
2117354263928357300 pspspsps5
2118831801632182360 x-MoneyForWhiskas
2119195909061763101 norm1e69
2119530729243648311 flippingsharks
2119917714588238032 0xcE25E214
2120654549950103883 antsaslyku
2120940800884490261 almach
2121361485431755002 bosona
2121727181495709737 NIULAI4
2122090772442861958 mo-money
2122845563188027552 0x50f7
2123206692590563809 98euf98a
2123579117287170470 Polkadot-Frog
2124646951434219549 aswfadq1555
2125722897897439651 pspspsps5
2126065685079949412 antsaslyku""".splitlines())
DN=dict(l.split() for l in """2113352597121692101 ply-pm0
2113729503004672017 ply-pm2
2114081693434822835 norm1e69
2114434054829273385 dangerously-skip-permissions
2114785303365820543 x-MoneyForWhiskas
2115169743162548674 CrouchPredictions
2115505987347976492 FairValueMachine
2115879114905096655 Bonereaper
2116276054067405176 mo-money
2116637575431499792 bosona
2118796687590220281 CrouchPredictions
2119171022750470638 0xb55fa129
2119530691956543898 blue.birds
2120238742942441800 asdcaxz
2120927626273435797 0x50f7
2121347052093194306 antsaslyku
2121720344167981494 GoodFallen
2122054455721963958 bosona
2122402308201853324 ply-pm0
2122780501828313477 Polkadot-Frog
2123499200394731821 almach
2123872696606036265 blue.birds
2124620166893891891 dangerously-skip-permissions
2124962466140717069 FairValueMachine
2125289848432959520 asdcaxz
2126064396241899633 bosona""".splitlines())
refs=json.load(open("data/x1/profile_refs.json"))
slug2label={"0x5268527977f700f9bf9b6d5cd843859e4e70135d":"0x52685279","0x2e3ecedec4b004c61670f0dcda382ec0da1f0f92":"0x2e3ecede","0x0dbd0e1d5999a401263dc26cbf1597f2be0cfcd5":"0x0dbd0e1d","0xdde15ebd95330ce69136dc0ccd810d22382e02c5":"0xdde15ebd","0xdb976ec8f75771f7af08d13546fe3d000867eee8":"0xdb976ec8","0x76eca4109d0dfe8649d5e3861dfccac67ae7d630":"0x76eca410","mooseborzoiii":None}
def posts(path):
    return {json.loads(l)["id"]:json.loads(l) for l in open(path)}
P={"RetroValix":posts("data/x1/RetroValix.jsonl")}
for h in ["Dan1ro0","igor_mikerin","DextersSolab","rb_tweets","carverfomo"]: P[h]=posts(f"data/x1/tl/{h}.jsonl")
pairs=[]
MORE={}
for i,w in RV.items(): pairs.append(("RetroValix",i,w))
for i,w in DN.items(): pairs.append(("Dan1ro0",i,w))
for h in ["igor_mikerin","DextersSolab","carverfomo"]:
    for slug,lst in refs[h].items():
        lab=slug2label.get(slug, slug)
        if lab is None or not W(lab): continue
        ids=[]
        for d,i in lst:
            if i not in ids: ids.append(i)
        pairs.append((h,ids[0],lab)); MORE[(h,ids[0],lab)]=len(ids)-1
pairs.append(("rb_tweets","2095491180901630326","gravia_0xbf5f"))
def product(s):
    blob=json.dumps(s, ensure_ascii=False)
    out=[]
    for pat,name in [(r"join\.horizon\.trade/\w+","horizon.trade"),(r"t\.me/PolyGunSniperBot\?start=\w+","PolyGun TG bot"),(r"ratio\.you/r/\w+","ratio.you"),(r"kcex\.com/register\?inviteCode=\w+","KCEX"),(r"gravia\.trade/[^\s\"\\]*via=\w+","gravia.trade copy-trading"),(r"polymarket\.com/[^\s\"\\]*\?via=[\w\-]+","Polymarket referral"),(r"poly\.market/\w+","Polymarket referral (poly.market)")]:
        m=re.search(pat, blob)
        if m: out.append(f"{name} ({m.group(0)[:70]})")
    return "; ".join(out) or "none visible in text"
def claim(s):
    t=(s.get("text") or "")[:500]
    ms=re.findall(r"\+?\$[\d,]+(?:\.\d+)?[KkMm]?", t)
    def val(x):
        x=x.replace("+","").replace("$","").replace(",","")
        mult=1
        if x[-1:] in "Kk": mult=1e3; x=x[:-1]
        if x[-1:] in "Mm": mult=1e6; x=x[:-1]
        try: return float(x)*mult
        except: return 0
    big=[m for m in ms if val(m)>=10000]
    return (big[0] if big else (ms[0] if ms else "-"))
def k(x): return f"{x/1e3:,.0f}K"
lines=[]
pairs.sort(key=lambda p:(P[p[0]].get(p[1],{}).get("created_timestamp") or 0))
for h,i,lab in pairs:
    s=P[h].get(i); r=W(lab)
    if not s or not r: print("skip",h,i,lab); continue
    d=dt.datetime.fromtimestamp(s["created_timestamp"], dt.timezone.utc).strftime("%Y-%m-%d")
    mon=" / ".join(f"{n/1e3:+.0f}" for _,n,_,_ in r["mon"]); monnr=" / ".join(f"{nn/1e3:+.0f}" for _,_,nn,_ in r["mon"])
    rs=f"{r['reb']/r['net']*100:.0f}%" if r["net"] else "n/a"
    lines.append(f"| {d} | @{h} | [{i}](https://x.com/{h}/status/{i}) | {claim(s)}{(' (+%d later posts on same wallet)'%MORE[(h,i,lab)]) if MORE.get((h,i,lab)) else ''} | {lab} `{r['wallet']}` | {k(r['gross'])} | {k(r['fees_paid'])} | {k(r['reb'])} | **{k(r['net'])}** | {k(r['net_nr'])} | {rs} | {mon} | {monnr} | {r['markets']:,} | {product(s)} |")
open("data/x1/pairs_table.md","w").write("\n".join(lines)+"\n")
print(len(lines), "rows")
# unique wallet table
ul=[]
for r in sorted(T.values(), key=lambda r:-r["net_nr"]):
    mon=" / ".join(f"{n/1e3:+.0f}" for _,n,_,_ in r["mon"]); monnr=" / ".join(f"{nn/1e3:+.0f}" for _,_,nn,_ in r["mon"])
    rs=f"{r['reb']/r['net']*100:.0f}%" if r["net"] else "n/a"
    ul.append(f"| {r['label']} | `{r['wallet']}` | {r['joined']} | {r['markets']:,} | {k(r['gross'])} | {k(r['fees_ch'])} | {k(r['refunded'])} | {k(r['fees_paid'])} | {k(r['reb'])} | **{k(r['net'])}** | {k(r['net_nr'])} | {rs} | {r['vol']/1e6:.1f}M | {r['net']/r['vol']*100 if r['vol'] else 0:+.2f}% | {mon} | {monnr} | {r['tt']} {round(r['twv'] or 0):,} / {r['mbps']}bps {round(r['mwv'] or 0):,} |")
open("data/x1/unique_table.md","w").write("\n".join(ul)+"\n")
print(len(ul), "unique")
