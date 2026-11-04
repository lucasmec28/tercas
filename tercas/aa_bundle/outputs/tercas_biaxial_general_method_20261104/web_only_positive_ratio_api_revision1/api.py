"""Pinned q+P component ceilings. Research only; never physical/global approval."""
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal, Context, localcontext, ROUND_HALF_EVEN, MAX_EMAX, MIN_EMIN, InvalidOperation, DivisionByZero, Overflow
import copy, hashlib, json, math, types, sys, uuid

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE=HERE.parent
MANIFEST_SHA='50c94fec4c24b44f012bd2a95993f964e93716133407617083b93dcf6286bce8'
ALLOWED_SHA=('f74d3f941e59af0bceb3a2fdae414e8aa479b14b16cbe284c1dff3f3e816b005', '9a30115583275a30ab25eb8c782398a8aa5d547b8272743da9cd2f8342f880d4', 'fde5d287a73df9adf1b9ab3e392d7207c3423acb7a8894de5553d402cc7aef90', '8db5d3c4a037e01e665860c1ad8878bab01330cc07fc4165f74a40c0862ec562', '40aada8e49914bb1384c8ac205d8035225d5c033e1e76de8fa65f022ebdd99f1', 'e45b3298a2a95cca875b558269046090751e3bff2fa1b9dfae3cc0c1a2a97919', 'f1e9676c843459bcb7c14341a32ab10cc90c8ab6765e056fe9bcd47e3b58dd05')
GEOMETRY_SHA=ALLOWED_SHA[0]  # Compatibility fixture default, never selection fallback.
SCHEMA='aa_web_positive_ratio_qp_component_v1'

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def pair(x):return [str(x.numerator),str(x.denominator)]
def key(c):return tuple((x.numerator,x.denominator) for x in c)
def flags():return dict(physical_ELS_approved=False,whole_member_approved=False,published=False)
def fail(status,reason):return dict(schema=SCHEMA,status=status,reason=reason,sufficient=False,result_kind='component_upper_bound',**flags())
def number(x,name):
    if type(x) not in (int,float) or not math.isfinite(x):raise ValueError(name+' must be finite int/float, not bool')
    return x

def validate(req):
    required={'schema_version','geometry_sha256','material','L_mm','q_N_mm','P_N','a_mm','N_N','bimoment_Nmm2','supports','stress_scope'}
    if type(req) is not dict or set(req)!=required:raise ValueError('Missing/extra fields; no case IDs or imported hull/bounds')
    if req['schema_version']!=SCHEMA or req['geometry_sha256'] not in ALLOWED_SHA:raise ValueError('Unsupported source/schema')
    m=req['material']
    if type(m) is not dict or set(m)!={'E_MPa','nu','fy_MPa'}:raise ValueError('Material fields')
    for k,v in [('E_MPa',200000),('nu',.3),('fy_MPa',250)]:
        if number(m[k],k)!=v:raise ValueError('Material outside pinned family')
    L=number(req['L_mm'],'L_mm')
    if L<=0:raise ValueError('L must be positive')
    for k in ('q_N_mm','P_N'):
        if type(req[k]) is not list or len(req[k])!=2:raise ValueError(k+' must have exactly two signed components')
        for x in req[k]:number(x,k)
    a=req['a_mm']
    if a is not None and not 0<number(a,'a_mm')<L:raise ValueError('Point coordinate must be strictly interior, never snapped to support')
    if any(req['P_N']) and a is None:raise ValueError('Nonzero P requires a_mm')
    for k in ('N_N','bimoment_Nmm2'):
        if number(req[k],k)!=0:raise ValueError('Bending component only requires mathematical N=B=0')
    if req['supports']!='simply_supported_bending' or req['stress_scope']!='bending_component_only':raise ValueError('Unsupported mechanics')
    canonical(req)

def verified_manifest():
    raw=(HERE/'SOURCE_MANIFEST.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA:raise ValueError('Own fixed manifest changed or pending final review')
    manifest=json.loads(raw)
    for p,sha in manifest['files'].items():
        if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=sha:raise ValueError('Pinned dependency changed: '+p)
    hull_path=HERE/'CORE_SOURCE_MANIFEST.json'
    hull=json.loads(hull_path.read_bytes())
    for path,expected in hull['files'].items():
        if manifest['files'].get(path)!=expected:raise ValueError('Missing/conflicting transitive hull pin: '+path)
    return manifest

class Modules:
    """Fresh source-only imports; no bytecode writes, cache, sys.path or precision changes."""
    def __init__(self):self.names=[];self.prefix='_qp_'+uuid.uuid4().hex
    def source(self,suffix,path,package=None):
        name=self.prefix+'.'+suffix;obj=types.ModuleType(name);obj.__file__=str(path);obj.__package__=package or self.prefix
        sys.modules[name]=obj;self.names.append(name)
        exec(compile(path.read_bytes(),str(path),'exec'),obj.__dict__)
        return obj
    def __enter__(self):
        pkg=types.ModuleType(self.prefix);pkg.__path__=[];sys.modules[self.prefix]=pkg;self.names.append(self.prefix);return self
    def __exit__(self,*args):
        for name in reversed(self.names):sys.modules.pop(name,None)

def field_record(field):
    return dict(L_fraction=pair(field.length),q_fractions=[pair(x) for x in field.q],P_fractions=[pair(x) for x in field.p],
        effective_position_fraction=None if field.position is None else pair(field.position),
        reaction_left_fractions=[pair(x) for x in field.reaction_left],reaction_right_fractions=[pair(x) for x in field.reaction_right],
        pieces=[dict(left_fraction=pair(p.left),right_fraction=pair(p.right),controls_N_Nmm=[[["0","1"]]+[pair(x) for x in c] for c in p.controls]) for p in field.pieces])

def hull_mapping(result,controls,core,material,geometry_sha256):
    if result.get('schema')!='aa_web_positive_ratio_control_hull_v1':raise ValueError('Hull schema binding mismatch')
    unique=sorted(set(controls));canon=[[pair(x) for x in row] for row in unique]
    # Match the core's ordered canonical JSON digest, then map by exact values.
    expected=hashlib.sha256(json.dumps(canon,separators=(',',':')).encode()).hexdigest()
    if result.get('geometry_sha256')!=geometry_sha256 or result.get('controls_digest')!=expected or result.get('material')!=material:raise ValueError('Hull request binding mismatch')
    if result.get('source_manifest_sha256')!=core.MANIFEST_SHA:raise ValueError('Hull source binding mismatch')
    expected_binding=digest(dict(schema='aa_web_positive_ratio_control_hull_v1',implementation_sha256=hashlib.sha256((HERE/'control_core.py').read_bytes()).hexdigest(),source_manifest=core.MANIFEST_SHA,geometry_sha256=geometry_sha256,controls_digest=expected,material=material))
    if result.get('implementation_sha256')!=hashlib.sha256((HERE/'control_core.py').read_bytes()).hexdigest():raise ValueError('Hull implementation binding mismatch')
    if result.get('domain_binding_digest')!=expected_binding:raise ValueError('Hull domain binding mismatch')
    expected_pins=json.loads((HERE/'CORE_SOURCE_MANIFEST.json').read_bytes())['files']
    if result.get('source_pins')!=expected_pins:raise ValueError('Hull dependency binding mismatch')
    mapped={}
    for row in result['controls']:
        raw=row['exact_resultants_N_Nmm'];c=tuple(F(int(n),int(d)) for n,d in raw)
        if raw!=[pair(x) for x in c] or c not in unique or key(c) in mapped:raise ValueError('Noncanonical, duplicate or foreign hull control')
        if row['control_digest']!=hashlib.sha256(json.dumps(raw,separators=(',',':')).encode()).hexdigest():raise ValueError('Control digest mismatch')
        vals=[(F(s['lower_decimal']),F(s['upper_decimal'])) for s in row['curvature_supports_per_mm']]
        if len(vals)!=2 or any(lo>hi for lo,hi in vals):raise ValueError('Invalid outward support')
        if not any(c) and any(lo or hi for lo,hi in vals):raise ValueError('Zero control must be exact identity')
        mapped[key(c)]=vals
    if set(mapped)!={key(c) for c in unique}:raise ValueError('Missing hull control')
    return mapped

def _assess(request):
    try:
        validate(request);req=copy.deepcopy(request)
    except (ValueError,TypeError,OverflowError) as exc:return fail('invalid_input',str(exc))
    def failed(status,reason):
        result=fail(status,reason);result.update(request=copy.deepcopy(req),request_digest=digest(req));return result
    try:manifest=verified_manifest()
    except (ValueError,OSError,KeyError) as exc:return failed('source_mismatch',str(exc))
    try:
        with Modules() as mods:
            mods.source('bounded_polynomial_source',BASE/'web_only_piecewise_field/bounded_polynomial_source.py')
            fieldmod=mods.source('piecewise_field',BASE/'web_only_piecewise_field/piecewise_field.py')
            field=fieldmod.build_field(req['L_mm'],req['q_N_mm'],req['P_N'],req['a_mm'])
            record=field_record(field);controls=[(F(0),)+c for p in field.pieces for c in p.controls]
            common=dict(schema=SCHEMA,implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),result_kind='component_upper_bound',request=req,request_digest=digest(req),
                source_manifest_sha256=MANIFEST_SHA,source_pins=manifest['files'],field=record,field_digest=digest(record),
                coordinate_convention='Signed q/P already in moment coordinates: b=[1,y,-x], R=[0,Mx,My], compression positive, -d_second=[kappa_x,kappa_y]. Internal shift y by gross yc leaves N=0 moments unchanged.',
                model_scope='Pinned Ue100x50x17 selected by request geometry_sha256; faceted midline dA=t ds, bends once, faces in stress guard. Prismatic simply-supported mathematical bending component. N=B=0 does not establish absence of physical torsion, warping or distortion.',
                numerical_limitations='Section supports use private 70-digit arithmetic and 1e-20 padding, not formal interval arithmetic. Decimal supports are parsed as exact rationals; global Green integration and Sturm extrema are rigorous conditional on those supports.',
                uniqueness_proved=False,**flags())
            if not any(any(c) for c in controls):
                route='zero_identity';mapping={key(c):[(F(0),F(0))]*2 for c in controls};sufficient=True
            else:
                core=mods.source('control_core',HERE/'control_core.py')
                bound=mods.source('bound_core',HERE/'bound_core.py')
                source=mods.source('source',HERE/'geometry_source.py')
                gm=mods.source('gross',BASE/'gross_mle_domain_revision2/gross_mle.py')
                g=bound.model(source,req['geometry_sha256']);mp=bound.mp
                profile=source.profile(req['geometry_sha256'])
                gd=gm.load_geometry(ROOT/profile['path'],req['geometry_sha256'])
                case=dict(q_N_mm=req['q_N_mm'],P_N=req['P_N'],point_position=None if req['a_mm'] is None else 'finite_interior')
                if req['a_mm'] is not None:case['a_mm']=req['a_mm']
                gross=gm.assess_case(gd,gm.model_for(gd,req['L_mm']),case);common['gross_evidence']=gross
                if gross['sufficient_full_section']:
                    route='gross_full_section';sufficient=True;mapping={}
                    for c in set(controls):
                        R=mp.matrix([mp.mpf(x.numerator)/x.denominator for x in c]);e=g['Cg']*R;vals=[]
                        for k in (1,2):
                            pad=bound.PAD*sum(abs(g['Cg'][k,j]*R[j]) for j in range(3))
                            vals.append((F(core.decimal_out(e[k]-pad,mp,False)),F(core.decimal_out(e[k]+pad,mp,True))))
                        mapping[key(c)]=vals
                    common['gross_Cg_reintegrated']=[[mp.nstr(g['Cg'][i,j],60) for j in range(3)] for i in range(3)]
                else:
                    hull=core.assess(dict(schema='aa_web_positive_ratio_control_hull_v1',geometry_sha256=req['geometry_sha256'],material=req['material'],controls=[list(c) for c in controls]))
                    common['hull_evidence']=hull
                    if hull.get('status') in ('invalid_input','source_mismatch','numerical_failure'):return failed(hull['status'],hull.get('reason','Hull failure'))
                    mapping=hull_mapping(hull,controls,core,req['material'],req['geometry_sha256'])
                    sufficient=all(hull.get(k) is True for k in ('sufficient','existence_sufficient','nonweb_and_material_sufficient'));route='web_control_hull'
            common.update(route=route,sufficient=sufficient,status='sufficient_'+route if sufficient else 'inconclusive_domain',existence_sufficient=sufficient,domain_sufficient=sufficient,material_sufficient=sufficient)
            if sufficient:
                breaks=[field.pieces[0].left]+[p.right for p in field.pieces];results=[]
                for k in range(2):
                    lower=[[mapping[key((F(0),)+c)][k][0] for c in p.controls] for p in field.pieces]
                    upper=[[mapping[key((F(0),)+c)][k][1] for c in p.controls] for p in field.pieces]
                    ceiling=fieldmod.component_bound(breaks,lower,upper)
                    results.append(dict(component=k,absolute_max_upper_mm=ceiling.upper_float(),absolute_max_upper_fraction=pair(ceiling.absolute_upper),
                        lower_curvature_controls=[[pair(x) for x in row] for row in lower],upper_curvature_controls=[[pair(x) for x in row] for row in upper],
                        lower_displacement_polynomials=[[pair(x) for x in p.coefficients] for p in ceiling.lower_pieces],upper_displacement_polynomials=[[pair(x) for x in p.coefficients] for p in ceiling.upper_pieces],
                        extrema_root_enclosures=[[[i,[pair(x) for x in interval],[pair(x) for x in value]] for i,interval,value in ext.critical_intervals] for ext in (ceiling.lower_extrema,ceiling.upper_extrema)]))
                common['displacement_component_bounds']=results
            common['binding_digest']=digest(dict(implementation_sha256=common['implementation_sha256'],request=common['request_digest'],field=common['field_digest'],manifest=MANIFEST_SHA,route=route))
            canonical(common);return common
    except (ValueError,TypeError,ArithmeticError,KeyError,OverflowError,OSError) as exc:return failed('numerical_failure',str(exc))

def assess(request):
    # A pristine context, not a copy of caller traps/exponent limits.
    with localcontext(Context(prec=70,rounding=ROUND_HALF_EVEN,Emin=MIN_EMIN,Emax=MAX_EMAX,capitals=1,clamp=0,flags=[],traps=[InvalidOperation,DivisionByZero,Overflow])):
        return _assess(request)

def assess_json(raw):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('Duplicate JSON key')
            d[k]=v
        return d
    def finite_float(token):
        x=float(token)
        # JSON grammar already guarantees a numeric token. Its significand
        # decides exact zero without constructing an unbounded Decimal exponent.
        significand=token.lower().split('e',1)[0]
        nonzero=any(c in '123456789' for c in significand)
        if not math.isfinite(x) or (x==0 and nonzero):raise ValueError('JSON float overflow/underflow')
        return x
    try:req=json.loads(raw,object_pairs_hook=pairs,parse_float=finite_float,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    except (ValueError,TypeError):return fail('invalid_input','Invalid strict JSON')
    return assess(req)

def compare_component(request,component,criterion_mm):
    try:
        limit=number(criterion_mm,'criterion_mm')
        if limit<=0 or type(component) is not int or component not in (0,1):raise ValueError('Invalid component/criterion')
        result=assess(request)
        if not result.get('sufficient'):return dict(schema='aa_web_positive_ratio_component_comparison_v1',status=result['status'] if result['status'] in ('invalid_input','source_mismatch','numerical_failure') else 'inconclusive',**flags())
        ceiling=result['displacement_component_bounds'][component]['absolute_max_upper_mm']
        return dict(schema='aa_web_positive_ratio_component_comparison_v1',status='sufficient_component_only' if F(ceiling)<=F(limit) else 'inconclusive',upper_bound_mm=ceiling,criterion_mm=limit,request_digest=result['request_digest'],**flags())
    except (ValueError,TypeError,OverflowError):return dict(schema='aa_web_positive_ratio_component_comparison_v1',status='invalid_input',**flags())
