import json,sys,subprocess,os,collections,re
OUT='/home/user/polymarket-lab/data/datasets/_api'
def get(url,path):
    subprocess.run(['curl','-s','-L','--max-time','60',url,'-o',path],check=False)
for ds in sys.argv[1:]:
    safe=ds.replace('/','__')
    rd=f'{OUT}/{safe}.README.md'; tr=f'{OUT}/{safe}.tree.json'; inf=f'{OUT}/{safe}.info.json'
    if not os.path.exists(rd): get(f'https://huggingface.co/datasets/{ds}/raw/main/README.md',rd)
    if not os.path.exists(inf): get(f'https://huggingface.co/api/datasets/{ds}',inf)
    # paginated tree
    if not os.path.exists(tr):
        allr=[]; url=f'https://huggingface.co/api/datasets/{ds}/tree/main?recursive=true&limit=1000'
        for i in range(40):
            subprocess.run(['curl','-s','-L','--max-time','90','-D','/tmp/_hdr.txt','-o','/tmp/_body.json',url])
            hdr=open('/tmp/_hdr.txt').read()
            try: page=json.load(open('/tmp/_body.json'))
            except Exception as e: print('tree err',open('/tmp/_body.json').read()[:200]); break
            if isinstance(page,dict): print('tree msg',page); break
            allr+=page
            m=re.search(r'<([^>]+)>;\s*rel="next"',hdr)
            if not m: break
            url=m.group(1)
        else: print('TRUNCATED tree at 40 pages')
        json.dump(allr,open(tr,'w'))
    t=json.load(open(tr))
    files=[x for x in t if x.get('type')=='file']
    tot=sum(x.get('size',0) for x in files)
    ext=collections.Counter(os.path.splitext(x['path'])[1] for x in files)
    try: info=json.load(open(inf))
    except: info={}
    cd=info.get('cardData') or {}
    print('='*100); print(ds,'| files',len(files),'| total GB %.2f'%(tot/1e9),'| ext',dict(ext.most_common(6)),'| license',cd.get('license'),'| gated',info.get('gated'),'| mod',info.get('lastModified'),'| sha',(info.get('sha') or '')[:8])
    paths=sorted(x['path'] for x in files)
    show=paths[:8]+['...']+paths[-8:] if len(paths)>16 else paths
    sz={x['path']:x.get('size',0) for x in files}
    for p in show: print('   ',p, sz.get(p,''))
    tops=collections.Counter(p.split('/')[0] for p in paths)
    print('   top dirs:',dict(tops.most_common(12)))
