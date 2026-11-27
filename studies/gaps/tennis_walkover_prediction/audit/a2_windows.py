import sys; sys.path.insert(0,'.')
from a1_recompute import *
for lo,hi in ((6,1),(24,6),(48,24),(12,1),(1,0.25),(3,0.5),(1,0),(100,0)):
    rows = run(lo,hi)
    stats(rows, label=f'window T-{lo}h..T-{hi}h')
print('--- price bands in protocol window')
rows = run(6,1)
for a,b in ((0.05,0.10),(0.10,0.15),(0.05,0.15),(0.15,0.30),(0.30,0.45)):
    stats([r for r in rows if a<=r[2]<b+1e-9], label=f'band {a}-{b}')
print('--- wider price band (any underdog print 0.02-0.499)')
stats(run(6,1,0.02,0.499), label='p 0.02-0.499')
print('--- fee 0.03')
stats(run(6,1), rate=0.03, label='fee rate 0.03')
