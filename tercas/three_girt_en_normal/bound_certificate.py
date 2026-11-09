"""Replayable numerical rectangle proof, never an envelope search.

Outward binary64 operations enclose the saved binary64 field. The existing
field-construction magnitude guard is added separately. This is not a proof
of exact real-arithmetic section construction or normative applicability.
"""
import math
from numbers import Real
from functools import lru_cache

SCHEMA='EN_full_face_dyadic_taylor_bernstein_certificate_v2'
KEYS=('normal','shear','interaction')

def down(x):return math.nextafter(x,-math.inf)
def up(x):return math.nextafter(x,math.inf)
def point(x):return (float(x),float(x))
def add(a,b):return (down(a[0]+b[0]),up(a[1]+b[1]))
def mul(a,b):
    v=[x*y for x in a for y in b]
    return (down(min(v)),up(max(v)))
def div(a,b):
    assert b[0]>0
    return mul(a,(down(1/b[1]),up(1/b[0])))
def mag(a):return max(abs(a[0]),abs(a[1]))
def scale(a,b):return mul(a,point(b))

@lru_cache(maxsize=16384)
def hyperbolic(h,x):
    """Positive Taylor sums with a geometric tail; h*x in [0,10]."""
    if not 0<=h<=10 or not 0<=x<=1:raise ValueError('Certificate hyperbolic domain')
    xx=mul(point(x),point(x))
    # h*h itself is enclosed, including its binary64 rounding.
    z2=mul(xx,mul(point(h),point(h)))
    c=scale(xx,.5);s=point(x);ct=c;st=s
    for n in range(1,48):
        ct=div(mul(ct,z2),point((2*n+1)*(2*n+2)))
        st=div(mul(st,z2),point((2*n)*(2*n+1)))
        c=add(c,ct);s=add(s,st)
    # Next and all later term ratios are <=100/(96*97).
    ratio=up(100/(96*97))
    tailfactor=up(ratio/down(1-ratio))
    return ((max(0.,c[0]),up(c[1]+up(ct[1]*tailfactor))),
            (max(0.,s[0]),up(s[1]+up(st[1]*tailfactor))))

DEGREE=24

@lru_cache(maxsize=1)
def elevation_weights():
    return tuple(tuple(div(point(math.comb(k,j)),point(math.comb(DEGREE,j)))
                       for j in range(k+1)) for k in range(DEGREE+1))

@lru_cache(maxsize=16384)
def field_bernstein(h,B0,U,V,a,b):
    """Local Taylor polynomial plus rigorous geometric absolute tail.

    The two derivative parities obey q[n]=q[n-2]*(h*dx)^2/(n*(n-1)).
    Polynomial and torsion controls are combined before taking magnitudes,
    retaining mechanical cancellation without solving an extremum problem.
    """
    c,sh=hyperbolic(h,a);h2=mul(point(h),point(h))
    ch=add(point(1.),mul(h2,c));dx=add(point(b),point(-a))
    bm=add(point(B0),add(scale(c,U),scale(sh,V)))
    first=add(scale(sh,U),scale(ch,V))
    second=add(scale(ch,U),scale(mul(h2,sh),V))
    dx2=mul(dx,dx);factor=mul(h2,dx2)
    q=[bm,mul(first,dx),scale(mul(second,dx2),.5)]
    for n in range(3,DEGREE+3):q.append(div(mul(q[n-2],factor),point(n*(n-1))))
    # Every subsequent same-parity ratio is smaller than this one.
    ratio=up(max(0.,factor[1])/((DEGREE+1)*DEGREE))
    if ratio>=1:raise ValueError('Invalid Taylor certificate tail ratio')
    tail=up(up(mag(q[DEGREE+1])+mag(q[DEGREE+2]))/down(1-ratio))
    result=[]
    for weights in elevation_weights():
        value=point(0.)
        for j,weight in enumerate(weights):value=add(value,mul(q[j],weight))
        result.append(value)
    return tuple(result),tail


def controls(c,a,b):
    a=point(a);b=point(b);d=add(b,scale(a,-1))
    p=add(c[0],mul(a,add(c[1],mul(a,c[2]))))
    q=mul(d,add(c[1],scale(mul(a,c[2]),2)))
    r=mul(mul(d,d),c[2])
    return (p,add(p,scale(q,.5)),add(add(p,q),r))

def _stress_payload(row,pk,wk,field,x0,x1,u0,u1,scale_key,weight_scale):
    def number(value):
        if isinstance(value,bool) or not isinstance(value,Real) or not math.isfinite(value):
            raise ValueError('Finite real certificate arithmetic input required')
        return float(value)
    import struct
    polynomial=tuple(tuple(number(v) for v in r) for r in row[pk])
    weight=tuple(number(v) for v in row[wk])
    if len(polynomial)!=3 or any(len(r)!=3 for r in polynomial) or len(weight)!=3:
        raise ValueError('Certificate requires quadratic polynomial and wall fields')
    return struct.pack('!22d',*(v for r in polynomial for v in r),*weight,
        *(number(field[k]) for k in ('h','B0','U','V')),
        *(number(v) for v in (x0,x1,u0,u1,row[scale_key],weight_scale)))


def _stress_many_uncached(payloads):
    """Same interval operations, batched over faces sharing one field/box.

    Arithmetic is evaluated from the exact immutable payload used in the key.
    Vector dimensions do not change polynomial degree or operation ordering.
    """
    import numpy as np
    if not payloads:return []
    if any(len(p)!=176 or p[96:160]!=payloads[0][96:160] for p in payloads):
        raise ValueError('Batch requires the same actual field and box bytes')
    values=np.frombuffer(b''.join(payloads),dtype='>f8').astype(float).reshape(-1,22)
    if not np.isfinite(values).all():raise ValueError('Nonfinite certificate arithmetic input')
    p=values[:,:9].reshape(-1,3,3);weight=values[:,9:12]
    h,B0,U,V,x0,x1,u0,u1=map(float,values[0,12:20])
    def va(a,b):return (np.nextafter(a[0]+b[0],-np.inf),np.nextafter(a[1]+b[1],np.inf))
    def vm(a,b):
        vv=(a[0]*b[0],a[0]*b[1],a[1]*b[0],a[1]*b[1])
        return (np.nextafter(np.minimum.reduce(vv),-np.inf),np.nextafter(np.maximum.reduce(vv),np.inf))
    def vs(a,k):return vm(a,point(k))
    def vc(c0,c1,c2):
        a=point(u0);d=add(point(u1),scale(a,-1))
        pp=va(c0,vm(a,va(c1,vm(a,c2))))
        qq=vm(d,va(c1,vs(vm(a,c2),2)));rr=vm(mul(d,d),c2)
        return pp,va(pp,vs(qq,.5)),va(va(pp,qq),rr)
    uc=vc((p[:,0,:],p[:,0,:]),(p[:,1,:],p[:,1,:]),(p[:,2,:],p[:,2,:]))
    ul=np.stack([v[0] for v in uc],axis=1);uh=np.stack([v[1] for v in uc],axis=1)
    wc=vc((weight[:,0],weight[:,0]),(weight[:,1],weight[:,1]),(weight[:,2],weight[:,2]))
    wl=np.stack([v[0] for v in wc],axis=1);wh=np.stack([v[1] for v in wc],axis=1)
    c0=(ul[:,:,0],uh[:,:,0]);c1=(ul[:,:,1],uh[:,:,1]);c2=(ul[:,:,2],uh[:,:,2])
    dx=add(point(x1),point(-x0));a=point(x0)
    q0=va(c0,vm(a,va(c1,vm(a,c2))))
    q1=vm(dx,va(c1,vs(vm(a,c2),2)));q2=vm(mul(dx,dx),c2)
    shape=(len(payloads),3,DEGREE+1)
    lo=np.broadcast_to(q0[0][:,:,None],shape).copy();hi=np.broadcast_to(q0[1][:,:,None],shape).copy()
    weights=elevation_weights()
    for j,q in ((1,q1),(2,q2)):
        ew=np.asarray([v[j] for v in weights[j:]])
        lo[:,:,j:],hi[:,:,j:]=va((lo[:,:,j:],hi[:,:,j:]),vm((q[0][:,:,None],q[1][:,:,None]),(ew[:,0],ew[:,1])))
    bm,tail=field_bernstein(h,B0,U,V,x0,x1);bb=np.asarray(bm)
    lo,hi=va((lo,hi),vm((wl[:,:,None],wh[:,:,None]),(bb[:,0],bb[:,1])))
    remainder=np.nextafter(np.maximum(abs(wl),abs(wh))*tail,np.inf)
    upper=np.max(np.nextafter(np.maximum(abs(lo),abs(hi))+remainder[:,:,None],np.inf),axis=(1,2))
    # Preserve the scalar guard's nine/three upward-rounded additions exactly.
    ps=np.zeros(len(payloads));ws=np.zeros(len(payloads))
    for j in range(9):ps=np.nextafter(ps+abs(values[:,j]),np.inf)
    for j in range(3):ws=np.nextafter(ws+abs(weight[:,j]),np.inf)
    ps=np.maximum(values[:,20],ps);ws=np.maximum(values[:,21],ws)
    c,ss=hyperbolic(h,1.)
    fm=add(point(abs(B0)),add(scale(c,abs(U)),scale(ss,abs(V))))[1]
    guard=np.nextafter(128*2.220446049250313e-16*np.maximum(1.,np.nextafter(ps+np.nextafter(ws*fm,np.inf),np.inf)),np.inf)
    result=np.nextafter(upper+guard,np.inf)
    if not np.isfinite(result).all() or (result<0).any():raise ArithmeticError('Nonfinite certificate stress bound')
    return result.tolist()


def _stress_bound_uncached(row,pk,wk,field,x0,x1,u0,u1,scale_key,weight_scale):
    return _stress_many_uncached([_stress_payload(row,pk,wk,field,x0,x1,u0,u1,scale_key,weight_scale)])[0]


def stress_bound(row,pk,wk,field,x0,x1,u0,u1,scale_key,weight_scale):
    return _stress_bound_cached(SCHEMA,_stress_payload(row,pk,wk,field,x0,x1,u0,u1,scale_key,weight_scale))


def stress_many(rows,pk,wk,field,box,scale_key):
    values=[None]*len(rows);pending={}
    for index,row in enumerate(rows):
        weight_scale=sum(abs(row[wk])) if wk=='omega' else row['tw_roundoff_scale']
        payload=_stress_payload(row,pk,wk,field,*box,scale_key,weight_scale)
        key=_rc.key(SCHEMA,payload);saved=_ARITHMETIC_CACHE.get(key)
        if saved is not _rc.MISSING:values[index]=saved
        elif key in pending:pending[key][1].append(index)
        else:pending[key]=(payload,[index])
    computed=_stress_many_uncached([p for p,_ in pending.values()])
    for (key,(_,indices)),value in zip(pending.items(),computed):
        _ARITHMETIC_CACHE.put(key,value)
        for index in indices:values[index]=value
    return values


from . import replay_cache as _rc
_ARITHMETIC_CACHE=_rc.SuccessCache(196608)

def _stress_bound_cached(revision,payload):
    if revision!=SCHEMA:raise ValueError('Unknown certificate arithmetic revision')
    key=_rc.key(revision,payload);saved=_ARITHMETIC_CACHE.get(key)
    if saved is not _rc.MISSING:return saved
    result=_stress_many_uncached([payload])[0]
    _ARITHMETIC_CACHE.put(key,result)
    return result

_stress_bound_cached.cache_clear=_ARITHMETIC_CACHE.clear
_stress_bound_cached.cache_info=_ARITHMETIC_CACHE.info
_stress_bound_cached.retained_bytes=_ARITHMETIC_CACHE.retained_bytes


def boxes(paths,left,right):
    if not isinstance(paths,list) or not paths or any(not isinstance(p,str) or len(p)>128 or set(p)-{'0','1'} for p in paths):
        raise ValueError('Invalid certificate leaf paths')
    if paths!=sorted(set(paths)):raise ValueError('Duplicate/unordered certificate leaves')
    # A complete binary prefix code proves coverage without geometric tolerance.
    stack=[]
    for path in paths:
        if stack and path.startswith(stack[-1]):raise ValueError('Overlapping certificate leaves')
        stack.append(path)
        while len(stack)>1 and stack[-2].endswith('0') and stack[-1]==stack[-2][:-1]+'1':
            stack[-2:]=[stack[-2][:-1]]
    if stack!=['']:raise ValueError('Incomplete certificate leaf coverage')
    for path in paths:
        x0,x1,u0,u1=left,right,0.,1.
        for depth,bit in enumerate(path):
            a,b=(x0,x1) if depth%2==0 else (u0,u1);mid=(a+b)/2
            if mid in (a,b):raise ValueError('Degenerate certificate split')
            a,b=(a,mid) if bit=='0' else (mid,b)
            if depth%2==0:x0,x1=a,b
            else:u0,u1=a,b
        yield x0,x1,u0,u1

def verify(certificate,rows,tw,torsion,left,right,limit):
    if not isinstance(certificate,dict) or set(certificate)!={'schema','faces'} or certificate['schema']!=SCHEMA:
        raise ValueError('Missing/versioned interval bound certificate')
    faces=certificate['faces']
    if not isinstance(faces,list) or len(faces)!=len(rows):raise ValueError('Certificate face coverage')
    result=dict.fromkeys(KEYS,0.);groups={}
    for face,row in zip(faces,rows):
        if not isinstance(face,dict) or set(face)!={'segment_index','face','paths'} or (face['segment_index'],face['face'])!=(row['segment_index'],row['face']):
            raise ValueError('Certificate face identity')
        for box in boxes(face['paths'],left,right):groups.setdefault(box,[]).append(row)
    for box,group in groups.items():
        sigma=stress_many(group,'sigma','omega',torsion,box,'sigma_roundoff_scale')
        tau=stress_many(group,'tau','tw_weight',tw,box,'tau_roundoff_scale')
        for s,t in zip(sigma,tau):
            vals=(up(s/limit),up(up(t*up(math.sqrt(3)))/limit),
                  up(up(math.sqrt(up(up(s*s)+up(3*up(t*t)))))/down(1.1*limit)))
            for k,v in zip(KEYS,vals):
                if not math.isfinite(v) or v<0:raise ValueError('Nonfinite certificate bound')
                result[k]=max(result[k],v)
    return result
