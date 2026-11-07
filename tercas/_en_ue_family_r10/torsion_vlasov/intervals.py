"""Small outward-rounded interval algebra for finite binary64 input fields.

Inputs are exact binary64 numbers. Every arithmetic operation is enclosed by
nextafter in both directions; no claim is made about FE discretization error.
"""
import math
import numpy as np


class Interval:
    __slots__=('lo','hi')
    def __init__(self,lo,hi=None):
        lo=np.asarray(lo,dtype=float);hi=lo if hi is None else np.asarray(hi,dtype=float)
        lo,hi=np.broadcast_arrays(lo,hi)
        if not (np.isfinite(lo).all() and np.isfinite(hi).all() and np.all(lo<=hi)):
            raise ValueError('Finite ordered interval required')
        self.lo=lo;self.hi=hi
    def __getitem__(self,key):return Interval(self.lo[key],self.hi[key])
    @staticmethod
    def cast(v):return v if isinstance(v,Interval) else Interval(v)
    @staticmethod
    def rounded(lo,hi):
        return Interval(np.nextafter(lo,-np.inf),np.nextafter(hi,np.inf))
    def __add__(self,other):
        b=self.cast(other)
        with np.errstate(over='raise',invalid='raise'):
            return self.rounded(self.lo+b.lo,self.hi+b.hi)
    __radd__=__add__
    def __neg__(self):return Interval(-self.hi,-self.lo)
    def __sub__(self,other):return self+-self.cast(other)
    def __rsub__(self,other):return self.cast(other)+-self
    def __mul__(self,other):
        b=self.cast(other)
        with np.errstate(over='raise',invalid='raise',under='ignore'):
            vals=np.stack(np.broadcast_arrays(self.lo*b.lo,self.lo*b.hi,self.hi*b.lo,self.hi*b.hi))
        return self.rounded(np.min(vals,axis=0),np.max(vals,axis=0))
    __rmul__=__mul__
    def __truediv__(self,other):
        b=self.cast(other)
        if np.any(b.lo<=0):raise ValueError('Positive interval denominator required')
        with np.errstate(over='raise',invalid='raise',under='ignore'):
            vals=np.stack(np.broadcast_arrays(self.lo/b.lo,self.lo/b.hi,self.hi/b.lo,self.hi/b.hi))
        return self.rounded(np.min(vals,axis=0),np.max(vals,axis=0))
    def square(self):
        lo=np.where((self.lo<=0)&(self.hi>=0),0.,np.minimum(np.abs(self.lo),np.abs(self.hi)))
        hi=np.maximum(np.abs(self.lo),np.abs(self.hi))
        with np.errstate(over='raise',invalid='raise',under='ignore'):
            low=np.maximum(0.,np.nextafter(lo*lo,-np.inf));high=np.nextafter(hi*hi,np.inf)
        return Interval(low,high)
    def sqrt(self):
        if np.any(self.lo<0):raise ValueError('Nonnegative radicand required')
        return Interval(np.maximum(0.,np.nextafter(np.sqrt(self.lo),-np.inf)),np.nextafter(np.sqrt(self.hi),np.inf))
    def abs(self):
        return Interval(np.where((self.lo<=0)&(self.hi>=0),0.,np.minimum(np.abs(self.lo),np.abs(self.hi))),
                        np.maximum(np.abs(self.lo),np.abs(self.hi)))


def stack(values,axis=0):
    return Interval(np.stack([v.lo for v in values],axis=axis),np.stack([v.hi for v in values],axis=axis))


def power_to_bernstein(a):
    """Tensor transformation for power coefficients in the last two axes."""
    n,m=np.asarray(a.lo.shape[-2:])-1
    along=[]
    for i in range(n+1):
        row=Interval(np.zeros(a.lo.shape[:-2]+(m+1,)))
        for k in range(i+1):
            weight=Interval(float(math.comb(i,k)))/float(math.comb(n,k))
            row=row+a[...,k,:]*weight
        along.append(row)
    a=stack(along,axis=-2);out=[]
    for j in range(m+1):
        col=Interval(np.zeros(a.lo.shape[:-1]))
        for k in range(j+1):
            weight=Interval(float(math.comb(j,k)))/float(math.comb(m,k))
            col=col+a[...,k]*weight
        out.append(col)
    return stack(out,axis=-1)


def split_bernstein(a,axis):
    """Exact dyadic domain split, enclosed floating arithmetic, last axes only."""
    axis=axis if axis>=0 else a.lo.ndim+axis
    if axis not in (a.lo.ndim-2,a.lo.ndim-1):raise ValueError('A polynomial axis is required')
    temp=a;left=[];right=[]
    for _ in range(a.lo.shape[axis]):
        left.append(temp[tuple(0 if k==axis else slice(None) for k in range(temp.lo.ndim))])
        right.append(temp[tuple(-1 if k==axis else slice(None) for k in range(temp.lo.ndim))])
        if temp.lo.shape[axis]>1:
            before=tuple(slice(None,-1) if k==axis else slice(None) for k in range(temp.lo.ndim))
            after=tuple(slice(1,None) if k==axis else slice(None) for k in range(temp.lo.ndim))
            temp=(temp[before]+temp[after])*.5
    return stack(left,axis=axis),stack(list(reversed(right)),axis=axis)


def multiply_bernstein(a,b):
    """Tensor-product Bernstein multiplication with enclosed rational weights."""
    n,m=np.array(a.lo.shape[-2:])-1;p,q=np.array(b.lo.shape[-2:])-1
    rows=[]
    for k in range(n+p+1):
        cols=[]
        for ell in range(m+q+1):
            value=Interval(np.zeros(np.broadcast_shapes(a.lo.shape[:-2],b.lo.shape[:-2])))
            for i in range(max(0,k-p),min(n,k)+1):
                for j in range(max(0,ell-q),min(m,ell)+1):
                    numerator=math.comb(n,i)*math.comb(p,k-i)*math.comb(m,j)*math.comb(q,ell-j)
                    denominator=math.comb(n+p,k)*math.comb(m+q,ell)
                    weight=Interval(float(numerator))/float(denominator)
                    value=value+a[...,i,j]*b[...,k-i,ell-j]*weight
            cols.append(value)
        rows.append(stack(cols,axis=-1))
    return stack(rows,axis=-2)


def elevate_bernstein(a,axis,target_degree):
    """Degree elevation preserves the polynomial, using nonnegative weights."""
    axis=axis if axis>=0 else a.lo.ndim+axis
    if axis not in (a.lo.ndim-2,a.lo.ndim-1):raise ValueError('Polynomial axis required')
    while a.lo.shape[axis]-1<target_degree:
        n=a.lo.shape[axis]-1;rows=[]
        get=lambda i:a[tuple(i if k==axis else slice(None) for k in range(a.lo.ndim))]
        for i in range(n+2):
            if i==0:rows.append(get(0))
            elif i==n+1:rows.append(get(n))
            else:
                weight=Interval(float(i))/float(n+1)
                rows.append(get(i-1)*weight+get(i)*(Interval(1.)-weight))
        a=stack(rows,axis=axis)
    return a


def evaluate_bernstein(a,u,v):
    """u,v are exact dyadic local point coordinates in [0,1]."""
    if not (0<=u<=1 and 0<=v<=1):raise ValueError('Unit-square point required')
    temp=a;uc=Interval(1.)-u;vc=Interval(1.)-v
    while temp.lo.shape[-2]>1:temp=temp[...,:-1,:]*uc+temp[...,1:,:]*u
    temp=temp[...,0,:]
    while temp.lo.shape[-1]>1:temp=temp[...,:-1]*vc+temp[...,1:]*v
    return temp[...,0]
