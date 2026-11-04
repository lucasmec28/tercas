"""Independent scalar Vlasov reference, not imported from the frame implementation.

N-mm units: S=GJ [N mm2], D=ECw [N mm4], q=[phi,psi] with psi=phi'.
uw=-omega psi; B=-D phi'' [N mm2]; T=S phi'-D phi''' [N mm].
The scalar reference makes NO statement about real support/connection warping.
"""
from dataclasses import dataclass, field
import numpy as np
from scipy.linalg import expm


@dataclass
class Problem:
    length: float = 6000.
    S: float = 77000. * 120.
    D: float = 200000. * 1.e8
    # m(x) = m0 + m1*x/length, units N mm/mm. No distributed bimoment.
    m0: float = .2
    m1: float = 0.
    # Each end fixes phi; warping chosen explicitly: free, restrained or spring.
    warping: tuple = ('free', 'free')
    springs: tuple = (0., 0.)  # physical k_psi [N mm3], Q_psi = -k_psi*psi
    end_bimoments: tuple = (0., 0.)  # external generalized loads H conjugate to psi
    # (x/L, applied torque, applied generalized bimoment H), interior only
    point_actions: tuple = field(default_factory=tuple)

    def __post_init__(self):
        if not (self.length > 0 and self.S >= 0 and self.D > 0):
            raise ValueError('L,D positive and S nonnegative required')
        for bc, k in zip(self.warping, self.springs):
            if bc not in ('free', 'restrained', 'spring') or k < 0:
                raise ValueError('Declare an admissible warping condition and nonnegative spring')
            if bc != 'spring' and k != 0:
                raise ValueError('Spring data require explicit spring boundary condition')
        if any(not 0 < t < 1 for t, _, _ in self.point_actions):
            raise ValueError('Point actions must be strictly interior')


def hermite(xi, L, order=0):
    """Derivatives w.r.t. physical x, computed from power coefficients."""
    coefficients = np.array([[1.,0.,-3.,2.], [0.,L,-2*L,L],
                             [0.,0.,3.,-2.], [0.,0.,-L,L]])
    for _ in range(order):
        coefficients = coefficients[:,1:] * np.arange(1, coefficients.shape[1]) / L
    return coefficients @ np.asarray(xi) ** np.arange(coefficients.shape[1])


def element_matrices(L, S, D, m_left=0., m_right=0.):
    """Gauss integration (5 points), independent of closed-form matrices."""
    K = np.zeros((4,4)); f = np.zeros(4)
    xi, weights = np.polynomial.legendre.leggauss(5)
    for t, w in zip((xi+1)/2, weights*L/2):
        N = hermite(t,L); dN = hermite(t,L,1); ddN = hermite(t,L,2)
        K += w*(S*np.outer(dN,dN)+D*np.outer(ddN,ddN))
        f += w*((1-t)*m_left+t*m_right)*N
    return K, f


def closed_form_matrix(L, S, D):
    a = np.array([[36.,3*L,-36.,3*L], [3*L,4*L*L,-3*L,-L*L],
                  [-36.,-3*L,36.,-3*L], [3*L,-L*L,-3*L,4*L*L]])
    b = np.array([[12.,6*L,-12.,6*L], [6*L,4*L*L,-6*L,2*L*L],
                  [-12.,-6*L,12.,-6*L], [6*L,2*L*L,-6*L,4*L*L]])
    return S*a/(30*L)+D*b/L**3


class ExactStateReference:
    """Exact piecewise constant-coefficient ODE propagation, NOT Hermite FE.

    Dimensionless state y=[phi,L*psi,B*L²/D,T*L³/D,mu,dmu/dt].
    y'=[p,-b,tau-lambda²*p,-mu,mu1,0]. Exponential is exact to roundoff.
    This is a bounded-magnitude benchmark oracle, not a large-lambda solver.
    """
    def __init__(self, problem):
        self.p = p = problem
        self.A = np.zeros((6,6)); self.A[0,1] = 1.; self.A[1,2] = -1.
        self.A[2,1] = -p.S*p.length**2/p.D; self.A[2,3] = 1.
        self.A[3,4] = -1.; self.A[4,5] = 1.
        self.particular = np.r_[np.zeros(4), p.m0*p.length**4/p.D, p.m1*p.length**4/p.D]
        self.points = sorted(p.point_actions)
        end0 = self._propagate(self.particular, 1.)[:4]
        F = np.column_stack([self._propagate(self.particular+np.eye(6)[i],1.)[:4]-end0 for i in range(4)])
        C = []; rhs = []
        for end in (0,1):
            linear = np.eye(4) if end == 0 else F
            shift = np.zeros(4) if end == 0 else end0
            C.append(linear[0]); rhs.append(-shift[0])
            bc = p.warping[end]
            if bc == 'restrained':
                row = np.array([0.,1.,0.,0.]); target=0.
            else:
                row = np.array([0., p.springs[end]*p.length/p.D, 1. if end==0 else -1., 0.])
                target = p.end_bimoments[end]*p.length**2/p.D
            C.append(row@linear); rhs.append(target-row@shift)
        self.y0 = self.particular.copy()
        self.y0[:4] = np.linalg.solve(np.asarray(C),rhs)
        self.boundary_residual = float(np.max(np.abs(np.asarray(C)@self.y0[:4]-rhs)))

    def _propagate(self, y0, t, side='right'):
        y = y0.copy(); previous=0.
        for position, torque, H in self.points:
            if position>t or (position==t and side=='left'): break
            y = expm(self.A*(position-previous))@y
            y[2] += H*self.p.length**2/self.p.D
            y[3] -= torque*self.p.length**3/self.p.D
            previous=position
        return expm(self.A*(t-previous))@y

    def at(self, x, side='right'):
        p=self.p; t=x/p.length
        if not -1.e-13<=t<=1.+1.e-13: raise ValueError('Outside member')
        y=self._propagate(self.y0,float(t),side)
        psi=y[1]/p.length; B=y[2]*p.D/p.length**2; T=y[3]*p.D/p.length**3
        return dict(phi=float(y[0]),psi=float(psi),B=float(B),T=float(T),
                    Tsv=float(p.S*psi),Tw=float(T-p.S*psi))

    def reactions(self):
        p=self.p; left=self.at(0.); right=self.at(p.length)
        # Reactions at restrained DOFs exclude explicitly applied H.
        H=[left['B'],-right['B']]
        return dict(torque=[-left['T'],right['T']],
                    generalized_warping_action=H,
                    essential_warping_reaction=[H[i]-p.end_bimoments[i] if p.warping[i]=='restrained' else 0. for i in (0,1)],
                    spring_warping_reaction=[-p.springs[i]*[left,right][i]['psi'] for i in (0,1)])


class HermiteReference:
    def __init__(self, problem, elements):
        self.p = p = problem; self.elements=[]
        # Include every point action in mesh, even if not on regular grid.
        self.nodes=np.unique(np.r_[np.linspace(0,p.length,elements+1),[t*p.length for t,_,_ in p.point_actions]])
        nd=2*len(self.nodes); self.K=np.zeros((nd,nd)); self.f=np.zeros(nd)
        for j,(x0,x1) in enumerate(zip(self.nodes[:-1],self.nodes[1:])):
            ids=np.arange(2*j,2*j+4); m0=p.m0+p.m1*x0/p.length; m1=p.m0+p.m1*x1/p.length
            ke,fe=element_matrices(x1-x0,p.S,p.D,m0,m1)
            self.K[np.ix_(ids,ids)]+=ke; self.f[ids]+=fe
            self.elements.append(dict(x0=x0,x1=x1,ids=ids,K=ke,f=fe,m0=m0,m1=m1))
        for t,M,H in p.point_actions:
            j=int(np.argmin(abs(self.nodes-t*p.length)))
            self.f[2*j]+=M; self.f[2*j+1]+=H
        fixed=[0,nd-2]
        for end,node in ((0,0),(1,len(self.nodes)-1)):
            psi=2*node+1; self.f[psi]+=p.end_bimoments[end]
            if p.warping[end]=='restrained': fixed.append(psi)
            elif p.warping[end]=='spring': self.K[psi,psi]+=p.springs[end]
        self.fixed=np.array(sorted(fixed)); self.free=np.setdiff1d(np.arange(nd),self.fixed)
        k=self.K[np.ix_(self.free,self.free)]; scale=1./np.sqrt(np.diag(k))
        self.q=np.zeros(nd); self.q[self.free]=scale*np.linalg.solve(k*scale[:,None]*scale[None,:],scale*self.f[self.free])
        self.residual=self.K@self.q-self.f
        self.scale_free=scale

    def at_element(self, j, xi):
        e=self.elements[j]; L=e['x1']-e['x0']; d=self.q[e['ids']]
        derivatives=[float(hermite(xi,L,k)@d) for k in range(4)]
        phi,psi,d2,d3=derivatives; B=-self.p.D*d2; T=self.p.S*psi-self.p.D*d3
        r=e['K']@d-e['f']; x=xi*L; slope=(e['m1']-e['m0'])/L
        Teq=-r[0]-e['m0']*x-slope*x*x/2
        Beq=r[1]-r[0]*x-e['m0']*x*x/2-slope*x**3/6-self.p.S*(phi-d[0])
        return dict(x=e['x0']+x,phi=phi,psi=psi,B=B,T=T,Tsv=self.p.S*psi,Tw=-self.p.D*d3,
                    B_equilibrated=float(Beq),T_equilibrated=float(Teq),
                    Tw_equilibrated=float(Teq-self.p.S*psi))

    def actions(self, j):
        e=self.elements[j]
        return e['K']@self.q[e['ids']]-e['f']
