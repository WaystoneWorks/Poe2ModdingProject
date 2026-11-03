#!/usr/bin/env python3
"""How well the grid line model predicts the next grid cell in the sprint frames of a poe-hook.log,
per line end candidate (waypoint, or N cells along the heading), for straight and turning frames.
Usage: sprint_line_fit.py <poe-hook.log>. Analysis only."""
import re,math,sys,collections
L=sys.argv[1]
CELL=250/23
rows=[];plan={}
cur_plans=[]
for l in open(L,errors='replace'):
    if 'PATHPLAN' in l:
        m=re.search(r'goal=(-?\d+),(-?\d+) start=(-?\d+),(-?\d+).* count=(\d+) path=(.*)',l)
        if m:
            pts=[tuple(map(int,p.split(','))) for p in m[6].split()]
            cur_plans.append(((int(m[3]),int(m[4])),(int(m[1]),int(m[2])),pts))
    m=re.search(r'frame #(\d+) dt=\S+ world \(([-\d.]+), ([-\d.]+)\) step \(([-\d.]+), ([-\d.]+)\) grid \((\d+), (\d+)\)',l)
    if m:
        rows.append(dict(f=int(m[1]),x=float(m[2])/CELL-.5,y=float(m[3])/CELL-.5,sx=float(m[4])/CELL,sy=float(m[5])/CELL,g=(int(m[6]),int(m[7])),plans_before=cur_plans))
        cur_plans=[]
def line(s,e,p):
    sf=s;ef=e
    if p is not None and p!=ef and (sf[0]-p[0])**2+(sf[1]-p[1])**2<4: pp=p
    else: pp=sf
    d=(ef[0]-pp[0],ef[1]-pp[1])
    if pp==sf: q=s
    else:
        l2=d[0]**2+d[1]**2; t=((sf[0]-pp[0])*d[0]+(sf[1]-pp[1])*d[1])/l2 if l2 else 0
        q=(math.floor(d[0]*t+pp[0]+.5),math.floor(d[1]*t+pp[1]+.5))
    ix,iy=abs(e[0]-q[0]),abs(e[1]-q[1])
    ym= ix<iy or (pp!=sf and ix==iy and abs(d[0])<abs(d[1]))
    if ym: pmaj,pmin,emin,qmaj,emaj=pp[1],pp[0],ef[0],q[1],e[1]
    else: pmaj,pmin,emin,qmaj,emaj=pp[0],pp[1],ef[1],q[0],e[0]
    df=abs(emaj-pmaj)
    if df<=0: return None
    sl=(emin-pmin)/df; off=abs(emaj-qmaj)-df; c=.49 if sl>0 else .5
    return dict(s=s,q=q,e=e,ym=ym,sl=sl,m0=pmin-sl*off+c)
def cell(li,pos):
    if li is None: return None
    if li['q']==li['e']: return li['s']
    pm,qm,em=(pos[1],li['q'][1],li['e'][1]) if li['ym'] else (pos[0],li['q'][0],li['e'][0])
    tot=abs(em-qm);rem=abs(em-pm);k=max(0,min(tot,math.floor(tot-rem+1e-4)))
    if k==0: return li['s']
    mj=qm+k*(1 if em>qm else -1); mn=math.floor(li['m0']+k*li['sl'])
    return (mn,mj) if li['ym'] else (mj,mn)
res=collections.defaultdict(lambda:[0,0])
ex=[]
for i in range(2,len(rows)-1):
    a,b=rows[i],rows[i+1]
    if b['f']!=a['f']+1 or rows[i-1]['f']!=a['f']-1: continue
    st=math.hypot(b['sx'],b['sy'])
    if not(1.7<st<2.0): continue
    if not a['plans_before'] and not b['plans_before']: pass
    ps=b['plans_before']  # plan logged between frame a and b: start == grid(b); so plan before a: start == grid(a)
    pa=a['plans_before']
    if not pa: continue
    s,goal,pts=pa[-1]
    if s!=a['g']: res['start!=grid'][1]+=1; continue
    wp=pts[0] if pts else goal
    tang=math.atan2(wp[1]-s[1],wp[0]-s[0]); hang=math.atan2(b['sy'],b['sx'])
    err=abs((tang-hang+math.pi)%(2*math.pi)-math.pi)
    cat='turn' if err>0.05 else 'straight'
    pos=(a['x'],a['y']); nxt=(b['x'],b['y'])
    for name,e in (('wp',wp),)+tuple((f'h{ln}',(s[0]+math.floor(math.cos(hang)*ln+.5),s[1]+math.floor(math.sin(hang)*ln+.5))) for ln in (10,25,50,100)):
        c=cell(line(s,e,pos),nxt)
        r=res[cat+':'+name]; r[1]+=1; r[0]+=c==b['g']
    c=cell(line(s,(s[0]+math.floor(math.cos(hang)*50+.5),s[1]+math.floor(math.sin(hang)*50+.5)),pos),nxt)
    if cat=='turn' and c!=b['g'] and len(ex)<12: ex.append((a['f'],s,round(pos[0],2),round(pos[1],2),round(nxt[0],2),round(nxt[1],2),'pred',c,'real',b['g'],'err',round(err,2)))
for k,v in sorted(res.items()): print(k,v, '%.0f%%'%(100*v[0]/v[1]) if v[1] else '')
for e in ex: print(e)
