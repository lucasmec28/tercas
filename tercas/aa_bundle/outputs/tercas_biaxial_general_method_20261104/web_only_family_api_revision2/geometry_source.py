"""Own seven-source registry and exact-segment Decimal geometry integration.

The registry is authority, never caller-derived. No interpolation or source
selection by label. Real coordinates, centroid and Ixy are never symmetrized.
"""
from decimal import Decimal as D, Context, localcontext, ROUND_HALF_EVEN, MAX_EMAX, MIN_EMIN, InvalidOperation, DivisionByZero, Overflow
from pathlib import Path
import hashlib
import json
import math

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
AUTHORITY='outputs/tercas_biaxial_general_method_20261104/gross_mle_domain/SOURCE_PINS.json'
AUTHORITY_SHA='8a6a3b64d98cc05909c791c33facf92fe07ae5a4df8f2f13774c73b1b857cc39'
PREFIX='outputs/tercas_biaxial_research_integration_20261104/candidate/tercas/data/torsion_profiles/'
REGISTRY={
 'f74d3f941e59af0bceb3a2fdae414e8aa479b14b16cbe284c1dff3f3e816b005':dict(path=PREFIX+'ue100x50x17_t1.20.json',t=1.20,D=17),
 '9a30115583275a30ab25eb8c782398a8aa5d547b8272743da9cd2f8342f880d4':dict(path=PREFIX+'ue100x50x17_t1.50.json',t=1.50,D=17),
 'fde5d287a73df9adf1b9ab3e392d7207c3423acb7a8894de5553d402cc7aef90':dict(path=PREFIX+'ue100x50x17_t2.00.json',t=2.00,D=17),
 '8db5d3c4a037e01e665860c1ad8878bab01330cc07fc4165f74a40c0862ec562':dict(path=PREFIX+'ue100x50x17_t2.25.json',t=2.25,D=17),
 '40aada8e49914bb1384c8ac205d8035225d5c033e1e76de8fa65f022ebdd99f1':dict(path=PREFIX+'ue100x50x17_t2.65.json',t=2.65,D=17),
 'e45b3298a2a95cca875b558269046090751e3bff2fa1b9dfae3cc0c1a2a97919':dict(path=PREFIX+'ue100x50x17_t3.00.json',t=3.00,D=17),
 'f1e9676c843459bcb7c14341a32ab10cc90c8ab6765e056fe9bcd47e3b58dd05':dict(path=PREFIX+'ue100x50x17_t3.35.json',t=3.35,D=17),
}

def context():
 return Context(prec=70,rounding=ROUND_HALF_EVEN,Emin=MIN_EMIN,Emax=MAX_EMAX,capitals=1,clamp=0,flags=[],traps=[InvalidOperation,DivisionByZero,Overflow])

def profile(sha):
 if type(sha) is not str or sha not in REGISTRY:raise ValueError('Unknown geometry SHA; only seven own pinned sources are admitted')
 raw=(ROOT/AUTHORITY).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=AUTHORITY_SHA:raise ValueError('Geometry authority changed')
 pins=json.loads(raw)
 for s,p in REGISTRY.items():
  if pins.get(p['path'])!=s:raise ValueError('Registry differs from pinned authority')
 p=dict(REGISTRY[sha])
 if hashlib.sha256((ROOT/p['path']).read_bytes()).hexdigest()!=sha:raise ValueError('Pinned geometry source changed')
 return p

def number(x):
 if type(x) not in (int,float) or not math.isfinite(x):raise ValueError('Geometry coordinate must be a finite number')
 return D(x)  # Preserve binary input exactly, just as the original R01 source.

def geometry(geometry_sha256):
 with localcontext(context()):return _geometry(geometry_sha256)

def _geometry(sha):
 p=profile(sha);raw=(ROOT/p['path']).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('Pinned geometry changed during read')
 obj=json.loads(raw)
 if obj['schema']!='Ue100_family_geometry_preparation_v1':raise ValueError('Unreviewed schema')
 dims=obj['geometry_external_mm']
 if set(dims)!={'h','b','lip','t','ri'}:raise ValueError('Unexpected dimension fields')
 h,b,Dlip,t,ri=(number(dims[k]) for k in ('h','b','lip','t','ri'))
 if (h,b,Dlip,t,ri)!=(D(100),D(50),D(p['D']),D(p['t']),D(p['t'])):raise ValueError('Dimensions outside pinned family')
 if number(obj['thickness_mm'])!=t:raise ValueError('Thickness mismatch')
 mat=obj['declared_material_for_future_executor']
 if number(mat['E_MPa'])!=200000 or number(mat['nu'])!=D(.3):raise ValueError('Material outside fixed family')
 ident=obj['geometry_identity'];nf=ident['flat_segment_counts'];na=ident['arc_segment_counts']
 if nf!=[12,24,72,24,12] or na!=[16,16,16,16] or any(type(x) is not int for x in nf+na):raise ValueError('Unreviewed topology')
 pts=[tuple(number(v) for v in q) for q in obj['nodes_xy_mm']]
 if len(pts)!=209 or ident['node_count']!=209 or any(len(q)!=2 for q in pts):raise ValueError('Node topology mismatch')
 widths=(Dlip-ri-t,b-2*ri-2*t,h-2*ri-2*t,b-2*ri-2*t,Dlip-ri-t)
 directions=((0,-1),(-1,0),(0,1),(1,0),(0,-1));start=0;walls=[]
 for k in range(5):
  end=start+nf[k];a,z=pts[start],pts[end];delta=tuple(z[j]-a[j] for j in (0,1));width=sum(x*x for x in delta).sqrt()
  if width<=0 or abs(width-widths[k])>D('1e-11'):raise ValueError('Flat width mismatch')
  tangent=tuple(x/width for x in delta)
  if max(abs(tangent[j]-directions[k][j]) for j in (0,1))>D('1e-12'):raise ValueError('Wall direction mismatch')
  previous=D(-1)
  for q in pts[start:end+1]:
   dv=tuple(q[j]-a[j] for j in (0,1));along=sum(dv[j]*tangent[j] for j in (0,1));cross=dv[0]*tangent[1]-dv[1]*tangent[0]
   if abs(cross)>D('1e-11') or not D(0)<=along<=width or along<=previous:raise ValueError('Nonstraight or reordered wall')
   previous=along
  walls.append((start,end,width));start=end+(na[k] if k<4 else 0)
 i,j,width=walls[2]
 if any(q[0]!=0 for q in pts[i:j+1]):raise ValueError('Web removal requires x=0')
 A=Sx=Sy=Jx=Jy=Jxy=D(0)
 for a,z in zip(pts[:-1],pts[1:]):
  da=t*sum((z[k]-a[k])**2 for k in (0,1)).sqrt()
  if da<=0:raise ValueError('Degenerate segment')
  A+=da;Sx+=da*(a[0]+z[0])/2;Sy+=da*(a[1]+z[1])/2
  Jx+=da*(a[0]**2+a[0]*z[0]+z[0]**2)/3;Jy+=da*(a[1]**2+a[1]*z[1]+z[1]**2)/3
  Jxy+=da*(2*a[0]*a[1]+a[0]*z[1]+z[0]*a[1]+2*z[0]*z[1])/6
 xc,yc=Sx/A,Sy/A;Ix=Jy-Sy*Sy/A;Iy=Jx-Sx*Sx/A;Ixy=Jxy-Sx*Sy/A
 if min(Ix,Iy)<=0 or Ix*Iy-Ixy*Ixy<=0:raise ValueError('Non-SPD bending tensor')
 own=obj['own_properties']
 for value,key in ((A,'A_mm2'),(Ix,'Ix_strong_mm4'),(Iy,'Iy_weak_mm4')):
  if abs(value-number(own[key]))>abs(value)*D('1e-10'):raise ValueError('Own property mismatch '+key)
 if max(abs(v-number(own['centroid_xy_mm'][k])) for k,v in enumerate((xc,yc)))>D('1e-10'):raise ValueError('Centroid mismatch')
 # Tiny source binary64 Ixy has rounding noise: use tensor-scaled tolerance,
 # retain the full reintegrated nonzero value, never assign the source value.
 if abs(Ixy-number(own['Ixy_mm4']))>D('1e-10')*(Ix*Iy).sqrt():raise ValueError('Own Ixy mismatch')
 return dict(A0=A,Sx=Sx,Sy=Sy,Jx=Jx,Jy=Jy,Jxy=Jxy,t=t,b=width,Aw=t*width,yc=yc,xc=xc,
             Iy_gross=Iy,Ix_gross=Ix,Ixy_gross=Ixy,E=D(200000),D=Dlip,points=pts)
