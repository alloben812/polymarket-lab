"""Remote parquet peek over HTTP range requests (no full download).
usage: rpq.py <hf dataset id> <path in repo> [rowgroup index or 'last'] [maxwidth]"""
import sys, io, urllib.request, urllib.parse, pyarrow.parquet as pq, collections
class HttpFile(io.RawIOBase):
    def __init__(s,url):
        s.url=url; s.pos=0; s.bytes=0
        req=urllib.request.Request(url,method='HEAD'); r=urllib.request.urlopen(req,timeout=60)
        s.url=r.geturl(); s.size=int(r.headers['Content-Length'])
        if s.size<2000: raise SystemExit('too small / not a file: %d'%s.size)
    def seekable(s): return True
    def readable(s): return True
    def tell(s): return s.pos
    def seek(s,off,wh=0):
        s.pos = off if wh==0 else (s.pos+off if wh==1 else s.size+off); return s.pos
    def read(s,n=-1):
        if n<0: n=s.size-s.pos
        if n==0 or s.pos>=s.size: return b''
        end=min(s.pos+n,s.size)-1
        req=urllib.request.Request(s.url,headers={'Range':f'bytes={s.pos}-{end}'})
        b=urllib.request.urlopen(req,timeout=120).read(); s.pos+=len(b); s.bytes+=len(b)
        if s.bytes>400e6: raise SystemExit('range budget exceeded')
        return b
    def readinto(s,buf):
        b=s.read(len(buf)); buf[:len(b)]=b; return len(b)
def main():
    ds,path=sys.argv[1],sys.argv[2]; rg=sys.argv[3] if len(sys.argv)>3 else '0'; W=int(sys.argv[4]) if len(sys.argv)>4 else 110
    f=HttpFile(f'https://huggingface.co/datasets/{ds}/resolve/main/{urllib.parse.quote(path)}')
    pf=pq.ParquetFile(f)
    md=pf.metadata
    print('FILE',ds,path,'size',f.size,'rows',md.num_rows,'row_groups',md.num_row_groups,'cols',md.num_columns)
    for fld in pf.schema_arrow: print('   ',fld.name,':',str(fld.type)[:90])
    i=md.num_row_groups-1 if rg=='last' else int(rg)
    g=md.row_group(i); print('row group',i,'rows',g.num_rows,'bytes',g.total_byte_size)
    if g.total_byte_size>600e6: print('row group too big, skipping read'); return
    t=pf.read_row_group(i); n=t.num_rows
    for j in ([0,1,n//2,n-1] if n>3 else range(n)):
        print('  row',j,{c:str(t.column(c)[j].as_py())[:W] for c in t.column_names if t.column(c)[j].as_py() is not None})
    print('fetched MB',round(f.bytes/1e6,1))
    return t
if __name__=='__main__': main()
