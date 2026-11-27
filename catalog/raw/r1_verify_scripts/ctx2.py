import re,html,sys,os
def text(p):
    x=open(p,encoding='utf-8',errors='replace').read()
    if p.endswith('.html'):
        x=re.sub(r'<script.*?</script>|<style.*?</style>','',x,flags=re.S); x=re.sub(r'<annotation[^>]*>.*?</annotation>','',x,flags=re.S)
        x=re.sub(r'<[^>]+>',' ',x); x=html.unescape(x)
    return re.sub(r'\s+',' ',x)
D=sys.argv[1]; L='/home/user/polymarket-lab/data/papers/'
Q=[(D+'/2608.00666v1.html','all-taker',400,250,2),(D+'/2606.31675v2.html','disappeared from the five-minute',300,300,1),(D+'/2606.31675v2.html','TWAP',200,250,2),(D+'/2606.31675v2.html','Bloomberg',150,200,1),
(L+'nber_f243677.txt','1.91',250,150,1),(L+'nber_f243677.txt','0.82',200,150,1),(L+'nber_f243677.txt','75,754',200,150,1),(L+'nber_f243677.txt','41.6',100,150,1),(L+'nber_f243677.txt','overbet',150,200,1),
(L+'full/2610.06412v1.txt','Kalshi leads',300,150,1),(L+'full/2609.14267v1.txt','Kalshi',100,300,1),
(D+'/2609.12878v1.html','fees',150,250,2),(D+'/2610.36639v1.html','0.5 one minute',200,200,1),(D+'/2610.36639v1.html','minute',200,250,3),
(D+'/2610.13593v1.html','peak',150,250,4),(D+'/2605.31431v1.html','holding',200,250,2)]
c={}
for p,q,b,a,n in Q:
    if not os.path.exists(p): print('NOFILE',p); continue
    t=c.setdefault(p,text(p))
    idx=[m.start() for m in re.finditer(re.escape(q),t)]
    if not idx: print('MISSING',os.path.basename(p),q); continue
    for i in idx[:n]: print('##',os.path.basename(p),'[%s] x%d'%(q,len(idx)),':',t[max(0,i-b):i+len(q)+a]); print()
