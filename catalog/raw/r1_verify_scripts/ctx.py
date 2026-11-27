import re,html,sys,os
D=sys.argv[1]
def text(p):
    x=open(p,encoding='utf-8',errors='replace').read()
    x=re.sub(r'<script.*?</script>|<style.*?</style>','',x,flags=re.S)
    x=re.sub(r'<annotation[^>]*>.*?</annotation>','',x,flags=re.S)
    x=re.sub(r'<[^>]+>',' ',x); x=html.unescape(x); x=re.sub(r'\s+',' ',x); return x
Q=[('2610.36639v1','median of two minutes',500,300),('2610.36639v1','had a median volume',200,400),('2610.36639v1','first Web report',150,350),
('2610.23517v4','lose money at resolution',350,200),('2610.23517v4','Addresses',0,0),
('2607.14430v1','almost never',300,250),('2607.14430v1','0.30',200,200),('2607.14430v1','time to expiry',150,300),('2607.14430v1',' 5 928',10,200),
('2610.13593v1','approximately',250,250),('2610.13593v1','daily peak',100,400),('2610.13593v1','hours before',200,300),
('2608.00666v1','maker-acquired',300,200),('2608.00666v1','approximately one USDC',200,300),
('2607.26245v1','1% fee',200,200),('2606.31675v2','August',150,250),('2606.19517v1','marginal',200,200)]
cache={}
for k,q,b,a in Q:
    t=cache.setdefault(k,text(os.path.join(D,k+'.html')))
    idx=[m.start() for m in re.finditer(re.escape(q),t)][:2]
    if not idx: print('MISSING',k,q); continue
    for i in idx[:(2 if q in('approximately','hours before','first Web report','0.30','August') else 1)]:
        print('##',k,'[%s]'%q,':',t[max(0,i-b):i+len(q)+a]); print()
