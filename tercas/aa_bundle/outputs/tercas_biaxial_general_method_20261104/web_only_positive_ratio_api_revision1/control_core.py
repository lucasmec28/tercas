"""Finite supplied-moment convex hull only. No beam/load builder or solver."""
from pathlib import Path
from fractions import Fraction
from decimal import Decimal,Context,localcontext,ROUND_FLOOR,ROUND_CEILING,ROUND_HALF_EVEN,MAX_EMAX,MIN_EMIN,InvalidOperation,DivisionByZero,Overflow
import json,hashlib,math,importlib.util,sys

def private_decimal_context(precision=80,rounding=ROUND_HALF_EVEN):
 return Context(prec=precision,rounding=rounding,Emin=MIN_EMIN,Emax=MAX_EMAX,capitals=1,clamp=0,
                flags=[],traps=[InvalidOperation,DivisionByZero,Overflow])

def json_binary64(token):
 with localcontext(private_decimal_context()):
  value=float(token)
  significand=token.lower().split('e',1)[0]
  nonzero=any(c in '123456789' for c in significand)
  if not math.isfinite(value) or (value==0 and nonzero):
   raise ValueError('JSON number cannot be represented as finite nonzero binary64')
  return value

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
MANIFEST_SHA='03f552f6d57c6e0f303bb1df78a0f57a83a580d96110716fc27eda35dcd7696a'
ALLOWED_SHA=('f74d3f941e59af0bceb3a2fdae414e8aa479b14b16cbe284c1dff3f3e816b005', '9a30115583275a30ab25eb8c782398a8aa5d547b8272743da9cd2f8342f880d4', 'fde5d287a73df9adf1b9ab3e392d7207c3423acb7a8894de5553d402cc7aef90', '8db5d3c4a037e01e665860c1ad8878bab01330cc07fc4165f74a40c0862ec562', '40aada8e49914bb1384c8ac205d8035225d5c033e1e76de8fa65f022ebdd99f1', 'e45b3298a2a95cca875b558269046090751e3bff2fa1b9dfae3cc0c1a2a97919', 'f1e9676c843459bcb7c14341a32ab10cc90c8ab6765e056fe9bcd47e3b58dd05')

PSI_EXTENSION_REVIEWED=True

def failure(status,reason):
 return dict(schema='aa_web_positive_ratio_control_hull_v1',scope='convex_hull_of_supplied_moment_vectors',status=status,sufficient=False,reason=reason,physical_ELS_approved=False,whole_member_approved=False,published=False)
def rational(x):
 if type(x) is bool:raise ValueError('bool is not a control value')
 if isinstance(x,Fraction):return x
 if type(x) is int:return Fraction(x)
 if type(x) is float and math.isfinite(x):return Fraction.from_float(x)
 raise ValueError('Control values must be finite exact int/Fraction or finite binary64')
def pair(x):return [str(x.numerator),str(x.denominator)]
def validate(req):
 if type(req) is not dict or set(req)!={'schema','geometry_sha256','material','controls'}:raise ValueError('Missing/extra fields; no q, P, L or case IDs')
 if req['schema']!='aa_web_positive_ratio_control_hull_v1' or req['geometry_sha256'] not in ALLOWED_SHA:raise ValueError('Source/schema identity')
 m=req['material']
 if type(m) is not dict or set(m)!={'E_MPa','nu','fy_MPa'}:raise ValueError('Material fields')
 for k,v in [('E_MPa',200000.),('nu',.3),('fy_MPa',250.)]:
  if type(m[k]) not in (int,float) or not math.isfinite(m[k]) or m[k]!=v:raise ValueError('Material outside pinned family')
 raw=req['controls']
 if type(raw) is not list or not raw:raise ValueError('Nonempty finite control list required')
 vals=[]
 for row in raw:
  if type(row) not in (list,tuple) or len(row)!=3:raise ValueError('Each control is [N,Mx,My]')
  r=tuple(rational(x) for x in row)
  if r[0]!=0:raise ValueError('N=0 component scope required')
  vals.append(r)
 unique=sorted(set(vals));canon=[[pair(x) for x in row] for row in unique]
 digest=hashlib.sha256(json.dumps(canon,separators=(',',':')).encode()).hexdigest()
 return unique,canon,digest

def load(geometry_sha256):
 raw=(HERE/'CORE_SOURCE_MANIFEST.json').read_bytes()
 if hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA:raise ValueError('Own fixed manifest changed')
 pins=json.loads(raw)['files']
 for p,sha in pins.items():
  if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=sha:raise ValueError('Pinned source changed: '+p)
 # These dependency modules define no dataclasses or relative imports. They
 # require no sys.modules registration and never emit cached bytecode.
 import types
 def mod(name,path):
  obj=types.ModuleType(name);obj.__file__=str(path)
  exec(compile(path.read_bytes(),str(path),'exec'),obj.__dict__)
  return obj
 core=mod('family_private_bound_core',HERE/'bound_core.py')
 source=mod('family_geometry_source',HERE/'geometry_source.py')
 return core,core.model(source,geometry_sha256),pins

def decimal_out(x,mp,upper):
 if not mp.isfinite(x):raise ArithmeticError('Nonfinite support')
 if not x:return '0'
 with localcontext(private_decimal_context(60,ROUND_CEILING if upper else ROUND_FLOOR)) as ctx:
  return str(+Decimal(mp.nstr(x,80)))
def interval_out(bounds,mp):
 return {'lower_decimal':decimal_out(bounds[0],mp,False),'upper_decimal':decimal_out(bounds[1],mp,True)}
def scalar_out(x,mp):return mp.nstr(x,60)
def _binary64_interval_impl(interval):
 try:
  values=[]
  for k,direction in [('lower_decimal',-math.inf),('upper_decimal',math.inf)]:
   exact=Decimal(interval[k]);f=float(exact)
   if not math.isfinite(f) or (f==0 and exact!=0):raise ArithmeticError('binary64 over/underflow; decimal support remains available')
   values.append(0. if exact==0 else math.nextafter(f,direction))
  if not all(math.isfinite(x) for x in values):raise ArithmeticError('outward binary64 conversion overflow')
  return dict(status='converted',interval=values)
 except (ValueError,TypeError,KeyError,ArithmeticError) as exc:return dict(status='numerical_conversion_failure',reason=str(exc))

def binary64_interval(interval):
 with localcontext(private_decimal_context()):
  return _binary64_interval_impl(interval)

def positive_ratio_fraction(core,g,H,nonzero,ends,vector,support,stress,S):
 mp=core.mp;zero=mp.mpf(0);one=mp.mpf(1)
 positive=all(stress(H,c,p)[0]>0 for c in nonzero for p in ends)
 if not positive:return zero,dict(eligible=False,reason='strict_positive_endpoint_support_failed',r_lower='0')
 v0,v1=map(vector,ends)
 def combined(r):return [support(H,c,w)[0] for c in nonzero for w in (v0-r*v1,v1-r*v0)]
 lo=zero;hi=one
 if min(combined(hi))>=0:lo=hi
 else:
  for _ in range(100):
   mid=(lo+hi)/2
   if min(combined(mid))>=0:lo=mid
   else:hi=mid
 r=lo*(1-core.PAD)
 lu=g['b']/g['t']/mp.mpf('.95')*mp.sqrt(S/(4*g['E']));ls=(1+mp.sqrt(mp.mpf('.12')))/2
 rho=one if lu<=ls*(1-core.PAD) else min(one,(1-mp.mpf('.22')/lu)/lu)*(1-core.PAD)
 floors=combined(r)
 if min(floors)<0:raise ArithmeticError('Final positive-ratio certificate failed')
 eta=rho/(3-r)*(1-core.PAD)
 return eta,dict(eligible=True,r_lower=mp.nstr(r,60),rho_lower=mp.nstr(rho,60),eta_ratio=mp.nstr(eta,60),combined_lower_MPa=[mp.nstr(x,60) for x in floors])

def _assess_impl(req):
 try:controls,canonical,digest=validate(req)
 except (ValueError,TypeError,OverflowError) as exc:return failure('invalid_input',str(exc))
 try:core,g,pins=load(req['geometry_sha256'])
 except (ValueError,OSError,KeyError) as exc:return failure('source_mismatch',str(exc))
 try:
  mp=core.mp;r=mp.mpf('.236')
  def convert(f):return mp.mpf(f.numerator)/mp.mpf(f.denominator)
  prepared=[]
  for c,exact in zip(controls,canonical):
   scale=max(abs(c[1]),abs(c[2]));cn=[Fraction(0)]*3 if not scale else [x/scale for x in c]
   prepared.append(dict(exact=exact,scale=scale,s=convert(scale),Rn=mp.matrix([convert(x) for x in cn]),
    digest=hashlib.sha256(json.dumps(exact,separators=(',',':')).encode()).hexdigest()))
  def support(H,c,w):
   if not c['scale']:return (mp.mpf(0),mp.mpf(0))
   lo,hi=core.functional_bounds(g,H,c['Rn'],w)
   lo*=c['s'];hi*=c['s'];pad=core.PAD*max(abs(lo),abs(hi))
   return lo-pad,hi+pad
  def vector(pt):return g['E']*mp.matrix([1,pt[1]-g['yc'],-pt[0]])
  def stress(H,c,pt):return support(H,c,vector(pt))
  i,j=g['walls'][2][1:3];ends=[g['points'][z] for z in (i,j)]
  eta=mp.mpf(0);trace=[];nonzero=[c for c in prepared if c['scale']]
  if nonzero:
   for stage in range(12):
    H,low=core.compliance_difference(g,eta)
    S=max(mp.mpf(0),*(stress(H,c,p)[1] for c in nonzero for p in ends))
    improved,formula=core.guaranteed_edge_fraction(g,S)
    ratio_eta,ratio_evidence=positive_ratio_fraction(core,g,H,nonzero,ends,vector,support,stress,S)
    general_eta=improved
    if not all(mp.isfinite(z) and 0<=z<=mp.mpf('.5') for z in (eta,general_eta,ratio_eta)):raise ArithmeticError('Nonfinite or nonphysical retention candidate')
    improved=max(improved,ratio_eta)
    if not 0<=improved<=mp.mpf('.5'):raise ArithmeticError('Retained fraction outside physical range')
    trace.append(dict(stage=stage,eta_used=scalar_out(eta,mp),S_actual_MPa=scalar_out(S,mp),next_eta=scalar_out(max(eta,improved),mp),general_eta=scalar_out(general_eta,mp),ratio_evidence=ratio_evidence))
    next_eta=max(eta,improved)
    if not eta<=next_eta<=mp.mpf('.5'):raise ArithmeticError('Physical retained strips failed nesting')
    eta=next_eta
  else:eta=mp.mpf('.5')
  H,low=core.compliance_difference(g,eta)
  outputs=[];allguards=True;oldexist=True;newexist=True
  for c in prepared:
   zero=not c['scale'];endpoint=[stress(H,c,p) for p in ends]
   v0,v1=map(vector,ends);cone=[support(H,c,v0+r*v1),support(H,c,v1+r*v0)]
   old=zero or all(a>0 for a,b in endpoint);new=zero or all(a>0 for a,b in cone)
   oldexist &= old;newexist &= new;wallrows=[]
   for name,a,b,width,n in g['walls']:
    if name=='web':continue
    vals=[stress(H,c,[g['points'][z][k]+sign*g['t']/2*n[k] for k in (0,1)])[1] for z in (a,b) for sign in (-1,1)]
    S=max(mp.mpf(0),*vals)*(1+core.PAD);lp0=width/g['t']/mp.mpf('.623')*mp.sqrt(S/g['E']);Ia=Is=None
    if 'lip' in name:k=mp.mpf('.43');lp=width/g['t']/mp.mpf('.95')*mp.sqrt(S/(g['E']*k));full=lp<=mp.mpf('.673')*(1-core.PAD)
    elif lp0<=mp.mpf('.673')*(1-core.PAD):lp=lp0;full=True
    else:
     d=g['walls'][0 if name.startswith('bottom') else 4][3];ratio=g['D']/width;k=min(4,4 if ratio<=mp.mpf('.25') else mp.mpf('5.25')-5*ratio)
     Is=g['t']*d**3/12;Ia=min(g['t']**4*(56*lp0+5),399*g['t']**4*(mp.mpf('.487')*(lp0-mp.mpf('.673')))**3)
     lp=width/g['t']/mp.mpf('.95')*mp.sqrt(S/(g['E']*k));full=Is>=Ia*(1+core.PAD) and lp<=mp.mpf('.673')*(1-core.PAD)
    wallrows.append(dict(wall=name,sigma_upper_MPa=decimal_out(S,mp,True),lambda_local=scalar_out(lp,mp),full_sufficient=bool(full)))
   face=mp.mpf(0)
   for a,b in zip(g['points'][:-1],g['points'][1:]):
    le=mp.sqrt(sum((b[k]-a[k])**2 for k in (0,1)));n=(-(b[1]-a[1])/le,(b[0]-a[0])/le)
    for p in (a,b):
     for sign in (-1,1):face=max(face,*map(abs,stress(H,c,[p[k]+sign*g['t']/2*n[k] for k in (0,1)])))
   guards=all(w['full_sufficient'] for w in wallrows) and face<=250*(1-core.PAD);allguards &= guards
   curv=[]
   for k in (1,2):
    w=mp.matrix([0,0,0]);w[k]=1;curv.append(interval_out(support(H,c,w),mp))
   normalized_web=[(mp.mpf(0),mp.mpf(0)) if zero else core.functional_bounds(g,H,c['Rn'],vector(p)) for p in ends]
   normalized_cone=[(mp.mpf(0),mp.mpf(0)) if zero else core.functional_bounds(g,H,c['Rn'],w) for w in (v0+r*v1,v1+r*v0)]
   outputs.append(dict(control_digest=c['digest'],exact_resultants_N_Nmm=c['exact'],zero_identity=zero,
    normalized_web_supports_MPa=[interval_out(z,mp) for z in normalized_web],
    normalized_cone_supports_MPa=[interval_out(z,mp) for z in normalized_cone],
    normalization_scale_fraction=pair(c['scale']),normalization='R=scale*Rn, ||Rn||inf=1 when nonzero; fixed H, actual scale used in all bootstrap and final supports',
    web_endpoint_intervals_MPa=[interval_out(z,mp) for z in endpoint],cone_intervals_MPa=[interval_out(z,mp) for z in cone],
    two_positive_edges_sufficient=old,psi_gt_minus0236_sufficient=new,
    guards=dict(walls=wallrows,face_upper_MPa=decimal_out(face,mp,True),all_sufficient=bool(guards)),curvature_supports_per_mm=curv))
  full_section=(eta==mp.mpf('.5'))
  existence=full_section or oldexist or (PSI_EXTENSION_REVIEWED and newexist)
  sufficient=bool(allguards and existence)
  route='zero_identity' if not nonzero else 'constructive_full_section' if full_section else 'retained_subset_psi_cone' if PSI_EXTENSION_REVIEWED and newexist else 'retained_subset_positive_edges' if oldexist else 'inconclusive_existence'
  result=dict(schema='aa_web_positive_ratio_control_hull_v1',scope='convex_hull_of_supplied_moment_vectors',status='sufficient_control_hull' if sufficient else 'inconclusive_control_hull',sufficient=sufficient,
   implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),geometry_sha256=req['geometry_sha256'],source_pins=pins,source_manifest_sha256=MANIFEST_SHA,controls_digest=digest,material=dict(req['material']),controls=outputs,
   domain_binding_digest=hashlib.sha256(json.dumps(dict(schema='aa_web_positive_ratio_control_hull_v1',implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),source_manifest=MANIFEST_SHA,geometry_sha256=req['geometry_sha256'],controls_digest=digest,material=req['material']),sort_keys=True,separators=(',',':')).encode()).hexdigest(),
   coordinate_convention='Compression positive; b=[1,y,-x], resultants=[N,Mx,My]; core shifts y by gross yc only, N=0 leaves moments unchanged',
   common_internal_y_origin_mm=scalar_out(g['yc'],mp),
   common_H_compliance_diagnostic=[[scalar_out(H[i,j],mp) for j in range(3)] for i in range(3)],
   existence_route=route,constructive_full_section=bool(full_section),existence_sufficient=bool(existence),
   retention_method='general_and_correlated_positive_ratio_v1',stage_budget=12,ratio_bisection_budget=100,eta_common=scalar_out(eta,mp),bootstrap_trace=trace,nonweb_and_material_sufficient=bool(allguards),
   existence_positive_edges=bool(oldexist),existence_psi_cone=bool(newexist),psi_extension_reviewed=PSI_EXTENSION_REVIEWED,
   no_beam_field_asserted=True,no_beam_bound_returned=True,N_scope=0,bimoment_scope=0,
   numeric_context='Private 70-digit mpmath context, normalized functional PAD plus relative rescaling PAD; not formal interval arithmetic',
   exact_controls='Fraction input and canonical numerator/denominator pairs; no direction snapping; zero only exact',
   uniqueness_proved=False,physical_ELS_approved=False,whole_member_approved=False,published=False)
  json.dumps(result,allow_nan=False);return result
 except (ValueError,TypeError,ArithmeticError,OverflowError,ZeroDivisionError) as exc:return failure('numerical_failure',str(exc))


def assess(request):
 try:
  with localcontext(private_decimal_context()):
   return _assess_impl(request)
 except (ArithmeticError,ValueError,TypeError,OverflowError) as exc:
  return failure('numerical_failure',str(exc))

def assess_json(raw):
 def pairs(items):
  d={}
  for k,v in items:
   if k in d:raise ValueError('Duplicate JSON key')
   d[k]=v
  return d
 try:
  req=json.loads(raw,object_pairs_hook=pairs,parse_float=json_binary64,parse_int=int,parse_constant=lambda s:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
  for row in req['controls']:
   for i,x in enumerate(row):
    if type(x) is dict:
     if set(x)!={'numerator','denominator'} or any(type(x[k]) is not str for k in x):raise ValueError('Exact rational JSON requires integer strings')
     row[i]=Fraction(int(x['numerator']),int(x['denominator']))
  return assess(req)
 except (ValueError,TypeError,KeyError,ArithmeticError):return failure('invalid_input','Invalid strict rational JSON')
