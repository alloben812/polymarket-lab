# Rule fixed before running (verification pass, one variant each):
#  A. negRisk long: event is executable if NOT negRiskAugmented, every open leg has bestAsk, and
#     sum(ask_i) + sum(rate_i*ask_i*(1-ask_i)) < 1.  Short: sum(bid_i) - sum(rate_i*bid_i*(1-bid_i)) > 1.
#     Universe: top 400 open events by volume24hr (gamma), negRisk with >=2 open legs.
#  B. weather rewards: all open events with tag weather; per market rewardsDailyRate, liquidityNum, spread.
import json,urllib.request,urllib.parse,gzip,statistics as st,time
def get(u):
    r=urllib.request.Request(u,headers={'Accept-Encoding':'gzip','User-Agent':'research-client'})
    b=urllib.request.urlopen(r,timeout=60).read()
    try: b=gzip.decompress(b)
    except Exception: pass
    return json.loads(b)
B='https://gamma-api.polymarket.com'
evs=[]
for off in range(0,400,100):
    evs+=get(B+f'/events?closed=false&active=true&order=volume24hr&ascending=false&limit=100&offset={off}'); time.sleep(0.3)
print('events',len(evs))
nr=[];
for e in evs:
    if not e.get('negRisk'): continue
    ms=[m for m in (e.get('markets') or []) if not m.get('closed') and m.get('active')]
    if len(ms)<2: continue
    nr.append((e,ms))
print('negRisk events >=2 open legs',len(nr))
full=0; sa=[]; sb=[]; longraw=[]; longnet=[]; shortraw=[]; shortnet=[]
for e,ms in nr:
    asks=[m.get('bestAsk') for m in ms]; bids=[m.get('bestBid') for m in ms]
    if any(a is None for a in asks) or any(b is None for b in bids): continue
    full+=1
    rate=[float((m.get('feeSchedule') or {}).get('rate') or 0) for m in ms]
    A=sum(map(float,asks)); Bd=sum(map(float,bids))
    fa=sum(r*float(a)*(1-float(a)) for r,a in zip(rate,asks)); fb=sum(r*float(b)*(1-float(b)) for r,b in zip(rate,bids))
    sa.append(A); sb.append(Bd)
    aug=bool(e.get('negRiskAugmented'))
    if A<1: longraw.append((e['slug'],len(ms),round(A,4),round(fa,4),aug))
    if A+fa<1 and not aug: longnet.append((e['slug'],len(ms),round(A,4),round(fa,4)))
    if Bd>1: shortraw.append((e['slug'],len(ms),round(Bd,4),round(fb,4),aug))
    if Bd-fb>1: shortnet.append((e['slug'],len(ms),round(Bd,4),round(fb,4),aug))
print('fully quoted',full,'median sum asks',round(st.median(sa),4),'median sum bids',round(st.median(sb),4))
print('long raw',len(longraw),'of which augmented',sum(1 for x in longraw if x[4])); 
for x in longraw: print('  ',x)
print('long net non-augmented',longnet)
print('short raw',len(shortraw)); 
for x in shortraw: print('  ',x)
print('short net',shortnet)
# B weather
w=[]
for off in range(0,600,100):
    try: page=get(B+f'/events?closed=false&active=true&tag_slug=weather&limit=100&offset={off}')
    except Exception as ex: print('weather page err',ex); break
    if not page: break
    w+=page; time.sleep(0.3)
print('open weather events',len(w))
tot=0;n=0;nrew=0;liqs=[];rates=[];temp=0
import collections
for e in w:
    if 'temperature' in (e.get('slug') or ''): temp+=1
    for m in e.get('markets') or []:
        if m.get('closed'): continue
        n+=1
        cr=m.get('clobRewards') or []
        d=sum(float(c.get('rewardsDailyRate') or 0) for c in cr)
        if d>0:
            nrew+=1; tot+=d; rates.append(d); liqs.append(float(m.get('liquidityNum') or 0))
print('temperature events',temp,'open markets',n,'with daily reward',nrew,'sum daily $',round(tot),'median rate',st.median(rates) if rates else None,'median liquidity of rewarded',round(st.median(liqs)) if liqs else None)
e=get(B+'/events?slug=highest-temperature-in-nyc-on-november-27-2026')[0]
m=e['markets'][0]; print('NYC DESC FULL:',m.get('description'))
print('event vol',e.get('volume'),'liq',e.get('liquidity'))
e=get(B+'/events?slug=democratic-presidential-nominee-2028')[0]
for m in e['markets']:
    if 'Newsom' in (m.get('groupItemTitle') or m.get('question') or ''):
        print('NEWSOM',m.get('bestBid'),m.get('bestAsk'),'min',m.get('rewardsMinSize'),'band',m.get('rewardsMaxSpread'),'daily',[c.get('rewardsDailyRate') for c in (m.get('clobRewards') or [])],'fee',(m.get('feeSchedule') or {}),'vol24',m.get('volume24hr'),'tick',m.get('orderPriceMinTickSize'))
