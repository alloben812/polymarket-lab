import re,html,sys,os
D=sys.argv[1]
def text(p):
    x=open(p,encoding='utf-8',errors='replace').read()
    x=re.sub(r'<script.*?</script>|<style.*?</style>','',x,flags=re.S)
    x=re.sub(r'<annotation[^>]*>.*?</annotation>','',x,flags=re.S)
    x=re.sub(r'<[^>]+>',' ',x); x=html.unescape(x); x=re.sub(r'\s+',' ',x); return x
Q={
'2610.13593v1':['184','20.7','54.96','50.71','102.98','order-book depth','11.2','2,189','8,544,732','11,924','0.23','f = 0.05','0.05','daily peak','June','July'],
'2610.23517v4':['491,827','125,095','2.50 million','3.5','11.1 million','854 addresses','78','1-second delay','22','2.9','6.3','semantic-inferred relations last','34','59','0.5% on capital','2.6'],
'2608.00666v1':['1.086','32 thousand','0.08 USDC','381,748','2,098','16.15','7.99','366','291,424','most profitable addresses','maker'],
'2610.36639v1':['one minute before','two minutes','208','51 ','337','62','1.4','1.2 million','0.10','0.32','release'],
'2609.12878v1':['19.3','0.83','72.40','14.84','12.63','16.34','46.15','1.826','clearest counterexample','24.74','25.15'],
'2605.31431v1':['3.06','48','88','Holding Rewards','0.96'],
'2607.26245v1':['347','16 ms','0.116','does not beat','No strategy iteration'],
'2606.31675v2':['821 wallets','243,000','8.2 million','7.6 million','3.1 million','one time in three','60-second'],
'2610.34754v1':['1,541,104','68.66','89.2','44.18','11.89','3.04','0.681','0.577','do not establish'],
'2606.19517v1':['5.6','214','6.46','287','Deribit','four hours','delta-hedged','2023'],
'2607.14430v1':['10–40 cents','1.31','1.22','0.991','24','settlement','close'],
'2605.00864v1':['290','101','76.9','14.8','210.19','3.6','final minutes'],
'2609.23969v1':['10 percent','four times','does not react'],
}
for k,qs in Q.items():
    t=text(os.path.join(D,k+'.html'))
    print('=====',k,len(t))
    for q in qs:
        i=t.find(q)
        n=t.count(q)
        if i<0: print('  MISSING:',q); continue
        print('  [%s] x%d: ...%s...'%(q,n,t[max(0,i-110):i+len(q)+110]))
