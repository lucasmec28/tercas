"""Constant gross Euler-Bernoulli tensor response; no stiffness/ELS approval.

Physical section x points to the opening and y upwards. Component vectors are
[normal downwards (-y), parallel (+x)]. In these conjugate coordinates:
    K = E [[Ix, -Ixy], [-Ixy, Iy]], K v'''' = q, [Mx, My] = -K v''.
Ix=int(y² dA), Iy=int(x² dA), Ixy=int(x y dA), at the same centroid.

Inputs become exact rationals. Piecewise quartics, energy and equilibrium are
formed algebraically. Stationary roots are isolated by rational Sturm sequences;
their reported coordinates/response values are finite float approximations,
not certified intervals. There is no root grid or midpoint-only extremum.
"""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction as F
import hashlib
import json
import math

try:
    from .bounded_polynomial import real_roots_open_unit_interval as roots
except ImportError:
    from bounded_polynomial import real_roots_open_unit_interval as roots

SCHEMA = 'constant_gross_tensor_flexural_response_research_v1'

def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, F)):
        raise ValueError(name + ' must be a finite real number, not text/bool.')
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(name + ' must be finite.')
    if isinstance(value, Decimal) and not value.is_finite():
        raise ValueError(name + ' must be finite.')
    return F(value)

def vector(value, name):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(name + ' requires simultaneous [normal, parallel] components.')
    return tuple(number(x, name) for x in value)

def add(a, b):
    return tuple((a[i] if i < len(a) else F(0)) + (b[i] if i < len(b) else F(0))
                 for i in range(max(len(a), len(b))))

def scale(a, factor):
    return tuple(x*factor for x in a)

def derivative(a):
    return tuple(i*a[i] for i in range(1, len(a))) or (F(0),)

def multiply(a, b):
    out = [F(0)]*(len(a)+len(b)-1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i+j] += x*y
    return tuple(out)

def value(a, x):
    result = F(0)
    for coefficient in reversed(a):
        result = result*x + coefficient
    return result

def compose_affine(a, start, length):
    out = [F(0)]*len(a)
    for i, coefficient in enumerate(a):
        for j in range(i+1):
            out[j] += coefficient*math.comb(i, j)*start**(i-j)*length**j
    return tuple(out)

def integral_unit(a):
    return sum((x/F(i+1) for i, x in enumerate(a)), F(0))

def matvec(matrix, vec):
    return tuple(sum((matrix[i][j]*vec[j] for j in range(2)), F(0)) for i in range(2))

@dataclass(frozen=True)
class Piece:
    start: F
    end: F
    coefficients: tuple

@dataclass(frozen=True)
class Beam:
    L: F
    E: F
    Ix: F
    Iy: F
    Ixy: F
    q: tuple
    P: tuple
    position: object
    a: object
    K: tuple
    flexibility: tuple
    pieces: tuple

def build_beam(model, tensor, case):
    """Validate one explicit mechanics model. No geometry/source qualification."""
    if type(model) is not dict or set(model) != {'L_mm', 'E_MPa', 'supports', 'prismatic', 'scope'}:
        raise ValueError('Missing or unknown mechanics model fields.')
    if model['supports'] != 'simply_supported_bending' or model['prismatic'] is not True or model['scope'] != 'gross_flexural_component_only':
        raise ValueError('Only the explicit prismatic simply-supported flexural model is supported.')
    L, E = number(model['L_mm'], 'L'), number(model['E_MPa'], 'E')
    if L <= 0 or E <= 0:
        raise ValueError('L and E must be positive.')
    if type(tensor) is not dict or set(tensor) != {'Ix_mm4', 'Iy_mm4', 'Ixy_mm4'}:
        raise ValueError('Three centroidal tensor components are required; no unknown fields.')
    Ix, Iy, Ixy = (number(tensor[k], k) for k in ('Ix_mm4', 'Iy_mm4', 'Ixy_mm4'))
    det = Ix*Iy-Ixy*Ixy
    if Ix <= 0 or Iy <= 0 or det <= 0:
        raise ValueError('The centroidal inertia tensor must be positive definite.')
    if type(case) is not dict or not {'q_N_mm', 'P_N', 'point_position'} <= set(case) or set(case)-{'q_N_mm','P_N','point_position','a_mm','id','angle'}:
        raise ValueError('Missing or unknown action fields.')
    q, P = vector(case['q_N_mm'], 'q'), vector(case['P_N'], 'P')
    position = case['point_position']
    if position not in (None, 'center', 'finite_interior', 'support_limit'):
        raise ValueError('Unknown point-load position model.')
    a = case.get('a_mm')
    active_point = any(P)
    if position is None:
        if active_point or a is not None:
            raise ValueError('Nonzero P requires a position; an absent point cannot have a coordinate.')
        a = None
    elif position == 'center':
        if a is not None and number(a, 'a') != L/2:
            raise ValueError('Center position contradicts a_mm.')
        a = L/2
    elif position == 'finite_interior':
        a = number(a, 'a')
        if not 0 < a < L:
            raise ValueError('Finite point position must satisfy 0<a<L.')
    elif position == 'support_limit':
        if a is not None:
            raise ValueError('The analytic support limit is not a finite point coordinate.')
        a = F(0)
    K = ((E*Ix, -E*Ixy), (-E*Ixy, E*Iy))
    flexibility = ((Iy/(E*det), Ixy/(E*det)), (Ixy/(E*det), Ix/(E*det)))
    aq = tuple(x*L**4/24 for x in matvec(flexibility, q))
    ap = tuple(x*L**3/6 for x in matvec(flexibility, P))
    uniform = tuple((F(0), c, F(0), -2*c, c) for c in aq)
    pieces = []
    if active_point and position != 'support_limit':
        alpha, beta = a/L, 1-a/L
        for left, right, pbase in (
            (F(0), alpha, (F(0), beta*(1-beta*beta), F(0), -beta, F(0))),
            (alpha, F(1), (-alpha**3, alpha*(alpha*alpha+2), -3*alpha, alpha, F(0))),
        ):
            coefficients = tuple(compose_affine(add(uniform[i], scale(pbase, ap[i])), left, right-left) for i in range(2))
            pieces.append(Piece(left*L, right*L, coefficients))
    else:
        pieces.append(Piece(F(0), L, uniform))
    return Beam(L,E,Ix,Iy,Ixy,q,P,position,a,K,flexibility,tuple(pieces))

def _piece_state(beam, index, u):
    piece = beam.pieces[index]
    length = piece.end-piece.start
    derivatives = []
    for coeff in piece.coefficients:
        ds = [value(coeff,u)]
        for order in range(1,5):
            coeff = derivative(coeff)
            ds.append(value(coeff,u)/length**order)
        derivatives.append(ds)
    displacement = tuple(row[0] for row in derivatives)
    slope = tuple(row[1] for row in derivatives)
    curvature = tuple(row[2] for row in derivatives)
    moments = tuple(-x for x in matvec(beam.K,curvature))
    shears = tuple(-x for x in matvec(beam.K,tuple(row[3] for row in derivatives)))
    return dict(x_mm=piece.start+length*u,piece_index=index,u=u,
                side='right' if u==0 else 'left' if u==1 else 'interior',
                displacement_mm=displacement, slopes=slope,curvatures_mm_inv=curvature,
                moments_Nmm=moments,shears_N=shears,
                fourth_derivative=tuple(row[4] for row in derivatives))

def _state(beam, x, side='right'):
    if not isinstance(beam,Beam):raise ValueError('Expected a validated Beam.')
    x = number(x,'sample position')
    if not 0 <= x <= beam.L:raise ValueError('Sample position is outside the span.')
    if side not in ('left','right'):raise ValueError('Unknown side of the point load.')
    index = 0
    if len(beam.pieces)==2 and (x>beam.a or (x==beam.a and side=='right')):index=1
    piece = beam.pieces[index]
    return _piece_state(beam,index,(x-piece.start)/(piece.end-piece.start))

class Converter:
    def __init__(self):self.underflow=[]
    def convert(self,value,path='root'):
        if isinstance(value,F):
            try:out=float(value)
            except OverflowError as exc:raise ArithmeticError('Response cannot be represented as finite floats: '+path) from exc
            if not math.isfinite(out):raise ArithmeticError('Nonfinite response output: '+path)
            if value and out==0.:self.underflow.append(path)
            return out
        if isinstance(value,tuple) or isinstance(value,list):return [self.convert(x,path+'.'+str(i)) for i,x in enumerate(value)]
        if isinstance(value,dict):return {k:self.convert(v,path+'.'+k) for k,v in value.items()}
        return value

def evaluate(beam,x_mm,side='right'):
    """Read a field state. Physical deflection/ELS qualification is not implied."""
    converter=Converter();out=converter.convert(_state(beam,x_mm,side))
    out['numeric_output_resolution_limited']=bool(converter.underflow)
    return out

def _witness(beam,index,u,objective):
    state=_piece_state(beam,index,F(u))
    return dict(value=objective(state),state=state)

def _extrema(beam,kind,component=None):
    candidates=[]
    for index,piece in enumerate(beam.pieces):
        coeff=piece.coefficients
        if kind=='slope':coeff=tuple(scale(derivative(c),1/(piece.end-piece.start)) for c in coeff)
        if component is None:
            objective=add(multiply(coeff[0],coeff[0]),multiply(coeff[1],coeff[1]))
        else:objective=coeff[component]
        us=[0.,1.,*roots(derivative(objective))]
        for u in us:
            u=F(u)
            state=_piece_state(beam,index,u)
            values=state['slopes' if kind=='slope' else 'displacement_mm']
            scalar=sum((v*v for v in values),F(0)) if component is None else values[component]
            candidates.append(dict(value=scalar,state=state))
    low=min(candidates,key=lambda row:row['value']);high=max(candidates,key=lambda row:row['value'])
    absolute=max(candidates,key=lambda row:abs(row['value']))
    out=dict(minimum=low,maximum=high,maximum_absolute=absolute,
             boundary_and_stationary_candidates=len(candidates))
    if component is None:
        out['values_are_squared_norms']=True
    return out

def solve_response(beam,*,sample_positions_mm=()):
    """Continuous component and resultant extrema, reactions and exact checks."""
    if not isinstance(beam,Beam):raise ValueError('Expected a validated Beam.')
    fields={kind:{'normal':_extrema(beam,kind,0),'parallel':_extrema(beam,kind,1),
                  'resultant_squared':_extrema(beam,kind)} for kind in ('displacement','slope')}
    if beam.a is None:
        left=right=tuple(x*beam.L/2 for x in beam.q)
    else:
        left=tuple(beam.q[i]*beam.L/2+beam.P[i]*(1-beam.a/beam.L) for i in range(2))
        right=tuple(beam.q[i]*beam.L/2+beam.P[i]*beam.a/beam.L for i in range(2))
    force_residual=tuple(left[i]+right[i]-beam.q[i]*beam.L-beam.P[i] for i in range(2))
    moment_residual=tuple(right[i]*beam.L-beam.q[i]*beam.L**2/2-beam.P[i]*(beam.a or 0) for i in range(2))
    energy=work=F(0)
    equation=True
    for piece in beam.pieces:
        length=piece.end-piece.start
        c2=tuple(scale(derivative(derivative(c)),1/length**2) for c in piece.coefficients)
        for i in range(2):
            work+=beam.q[i]*length*integral_unit(piece.coefficients[i])
            for j in range(2):energy+=length*beam.K[i][j]*integral_unit(multiply(c2[i],c2[j]))/2
        c4=tuple(value(derivative(derivative(derivative(derivative(c)))),F(0))/length**4 for c in piece.coefficients)
        equation=equation and matvec(beam.K,c4)==beam.q
    if beam.a is not None:
        point=_state(beam,beam.a)
        work+=sum((beam.P[i]*point['displacement_mm'][i] for i in range(2)),F(0))
    continuity=True;point_jump=True
    if len(beam.pieces)==2:
        a,b=_state(beam,beam.a,'left'),_state(beam,beam.a,'right')
        continuity=all(a[k]==b[k] for k in ('displacement_mm','slopes','moments_Nmm'))
        point_jump=tuple(a['shears_N'][i]-b['shears_N'][i] for i in range(2))==beam.P
    endpoints=[_state(beam,0),_state(beam,beam.L)]
    supports=all(not any(s['displacement_mm']) and not any(s['moments_Nmm']) for s in endpoints)
    if not (equation and continuity and point_jump and supports and energy>=0 and work==2*energy and not any(force_residual) and not any(moment_residual)):
        raise ArithmeticError('An exact field, boundary, equilibrium or energy identity failed.')
    exact_inputs={k:[str(x.numerator)+'/'+str(x.denominator) for x in values] for k,values in
                  {'section':(beam.E,beam.Ix,beam.Iy,beam.Ixy),'loads':(*beam.q,*beam.P),
                   'length_position':(beam.L,beam.a or F(0))}.items()}
    exact_inputs['point_position']=beam.position
    out=dict(schema=SCHEMA,status='finite_gross_flexural_response',
        coordinate_order=['normal_down_minus_y','parallel_opening_plus_x'],
        source_tensor_mm4=dict(Ix=beam.Ix,Iy=beam.Iy,Ixy=beam.Ixy),
        source_E_MPa=beam.E,L_mm=beam.L,q_N_mm=beam.q,P_N=beam.P,
        point_position=beam.position,a_mm=beam.a,exact_numeric_inputs=exact_inputs,
        numeric_input_fingerprint=hashlib.sha256(json.dumps(exact_inputs,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        stiffness_matrix_Nmm2=beam.K,extrema=fields,
        reactions_N=dict(left=left,right=right),
        samples=[_state(beam,x) for x in sample_positions_mm],
        strain_energy_Nmm=energy,external_work_Nmm=work,
        exact_checks=dict(field_equation=equation,continuity=continuity,point_shear_jump=point_jump,
                          simply_supported_bending=supports,force_balance=True,moment_balance=True,
                          work_equals_twice_energy=True),
        first_order_and_shear_rigid_model=True,
        physical_ELS_approved=False,whole_member_approved=False,resistance_qualified=False,
        gross_stiffness_applicability_established=False,torque_or_warping_included=False,
        scope='Gross constant flexural response only. Applicability of gross stiffness is supplied separately; no limit or physical system approval.',
        numeric_contract='Exact rational algebra for supplied tensor/loads and piece fields; exact root counting/isolation, float stationary witnesses and outputs; not interval error certification.')
    if beam.position=='support_limit':
        out['support_transfer_limit']=dict(kind='a_to_zero_from_inside',x_mm=F(0),
            M_before_Nmm=(F(0),F(0)),V_before_N=left,V_after_N=tuple(x*beam.L/2 for x in beam.q),
            original_P_N=beam.P,interior_bending_P_contribution_zero=True,
            finite_point_on_support=False,local_transfer_or_resistance_qualified=False)
    converter=Converter();out=converter.convert(out)
    out['numeric_output_resolution_limited']=bool(converter.underflow)
    out['underflow_output_paths']=converter.underflow
    if converter.underflow:out['status']='numeric_output_resolution_limited'
    json.dumps(out,allow_nan=False)
    return out
