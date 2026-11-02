#!/usr/bin/env python3
"""PATHPLAN lines and per-frame client positions of a poe-hook.log -> plans as JSON.

Usage: pathplans.py <poe-hook.log> <out.json>. Each plan has start, goal, params, level (from the
Positioned dump), path, prev/cur client positions (cells) and, with the +0x1e0..+0x290 dump, the
line state: active, current cell, point p (FUN_141ec83d0) and flag (FUN_141b87580). Runs: a
game-test scenario with [client_env] POE_HOOK_PATH_LOG = "1" and POE_HOOK_MOVEMENT_LOG = "1".
The tile hash in the output is the cliffs run (G1_1 seed 1); change it for another area."""
import json,re,sys
log=sys.argv[1]; out=sys.argv[2]
CELL=250/23
pos={}; plans=[]; seen=set()
for line in open(log,errors='replace'):
    m=re.search(r'frame #(\d+) dt=\S+ world \(([-\d.]+), ([-\d.]+)\).*grid \((\d+), (\d+)\)',line)
    if m:
        pos[int(m[1])]=(float(m[2])/CELL,float(m[3])/CELL,int(m[4]),int(m[5])); continue
    m=re.search(r'PATHPLAN #\d+ frame=(\d+) goal=(-?\d+),(-?\d+) start=(-?\d+),(-?\d+) params=(\S+) .*pos1e0=([0-9a-f]+) ok=\d reached=(\d) count=\d+ path=(.*)$',line)
    if m:
        pr=m[6].split('/'); b=bytes.fromhex(m[7])
        level=max(b[0x18],b[0x19]) if b[0x1f] else b[0x18]
        line=None
        if len(b)>=0xb0:
            import struct
            f=lambda o: struct.unpack_from('<f',b,o)[0]; i=lambda o: struct.unpack_from('<i',b,o)[0]
            active=b[0x89]==0 and f(0x94)!=0
            l2=0x70 if b[0x4e] else 0x68
            cx,cy=(i(0x6c),i(l2)) if b[0x4d] else (i(l2),i(0x6c))
            den=f(0x98) if b[0x88]==0 else f(0x94)
            r=(f(0xa4)/den if b[0x88]==0 else f(0xa8)/den) if den else 0.0
            r=min(max(r,0.0),1.0)
            c=[(i(0x5c+4*k)-f(0x34+4*k))*r+f(0x34+4*k) for k in range(3)]
            if b[0x4e]: c[0],c[2]=c[2],c[0]
            if b[0x4d]: c[0],c[1]=c[1],c[0]
            line=dict(active=active,cursor=[cx,cy],p=[c[0],c[1]],flag=active and [cx,cy]==[int(m[4]),int(m[5])])
        path=[[int(v) for v in c.split(',')] for c in m[9].split()]
        plans.append(dict(frame=int(m[1]),goal=[int(m[2]),int(m[3])],start=[int(m[4]),int(m[5])],
            min=int(pr[0],16),max=int(pr[1],16),radius=int(pr[2],16)-256 if int(pr[2],16)>127 else int(pr[2],16),
            level=level,line=line,reached=int(m[8]),path=path))
for p in plans:
    for k in ('prev','cur'):
        f=p['frame']-(1 if k=='prev' else 0)
        p[k]=list(pos[f][:2]) if f in pos else None
json.dump({'tile':3935790039,'plans':plans},open(out,'w'))
print(sum(1 for p in plans if p['line'] and p['line']['flag']),'flagged;',len(plans),'plans;', sum(p['prev'] is not None for p in plans),'with prev pos;',sum(p['cur'] is not None for p in plans),'with cur pos; levels',sorted({p['level'] for p in plans}))
