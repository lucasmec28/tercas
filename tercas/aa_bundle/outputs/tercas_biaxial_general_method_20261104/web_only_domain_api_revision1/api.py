"""Pinned R01 q-only domain and component-bound API, no section solver/UI."""
from pathlib import Path
import hashlib, json, math, importlib.util, sys, copy
from decimal import Decimal, Context, localcontext, ROUND_HALF_EVEN, MAX_EMAX, MIN_EMIN, InvalidOperation, DivisionByZero, Overflow


def private_decimal_context(precision=80,rounding=ROUND_HALF_EVEN):
 return Context(prec=precision,rounding=rounding,Emin=MIN_EMIN,Emax=MAX_EMAX,capitals=1,clamp=0,
                flags=[],traps=[InvalidOperation,DivisionByZero,Overflow])

def json_binary64(token):
 with localcontext(private_decimal_context()):
  exact=Decimal(token);value=float(exact)
  if not math.isfinite(value) or (value==0 and exact!=0):
   raise ValueError('JSON number cannot be represented as finite nonzero binary64')
  return value

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
MANIFEST_SHA='48438848230163e4a4398a9732877c7f455de654b4d0d5fac755b2b9bc90f1cd'
GEOMETRY='outputs/tercas_biaxial_research_integration_20261104/candidate/tercas/data/torsion_profiles/ue100x50x17_t1.20.json'
GEOMETRY_SHA='f74d3f941e59af0bceb3a2fdae414e8aa479b14b16cbe284c1dff3f3e816b005'
_CACHE={}

def fail(status,reason):
    return dict(schema='aa_web_domain_bound_v1',status=status,reason=reason,
        sufficient=False,result_kind='component_upper_bound',physical_ELS_approved=False,
        whole_member_approved=False,published=False)

def number(x,name):
    if type(x) not in (int,float) or not math.isfinite(x):
        raise ValueError(name+' must be finite int/float, not bool/string')
    return x

def validate(request):
    required={'schema_version','geometry_sha256','material','L_mm','q_N_mm','N_N','bimoment_Nmm2','supports','stress_scope'}
    if type(request) is not dict or set(request)!=required:raise ValueError('Missing/extra input fields')
    if request['schema_version']!='aa_web_q_ray_v1':raise ValueError('Unsupported request version')
    if request['geometry_sha256']!=GEOMETRY_SHA:raise ValueError('Unrecognized geometry identity')
    material=request['material']
    if type(material) is not dict or set(material)!={'E_MPa','nu','fy_MPa'}:raise ValueError('Material fields')
    for k,expected in [('E_MPa',200000.),('nu',.3),('fy_MPa',250.)]:
        if number(material[k],k)!=expected:raise ValueError('Material outside pinned R01 source')
    L=number(request['L_mm'],'L')
    if L<=0:raise ValueError('L must be positive in mm')
    q=request['q_N_mm']
    if type(q) is not list or len(q)!=2:raise ValueError('q must contain two simultaneous N/mm components')
    for x in q:number(x,'q')
    for k in ('N_N','bimoment_Nmm2'):
        if number(request[k],k)!=0:raise ValueError(k+' outside bending-only scope')
    if request['supports']!='simply_supported_bending' or request['stress_scope']!='bending_component_only':raise ValueError('Unsupported mechanics')
    # Detect representability before expensive arithmetic; reject silently
    # lost nonzero moments. This is a numerical limit, not physical failure.
    for x in q:
        if x:
            with __import__('decimal').localcontext() as ctx:
                ctx.prec=80;m=Decimal(x)*Decimal(L)**2/8
            f=float(m)
            if not math.isfinite(f) or (f==0 and m!=0):raise ArithmeticError('Peak moment not representable as binary64')
    return L,q

def verified_manifest():
    raw=(HERE/'SOURCE_MANIFEST.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA:raise ValueError('Fixed authorized manifest changed')
    manifest=json.loads(raw)
    for path,expected in manifest['files'].items():
        actual=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
        if actual!=expected:raise ValueError('Pinned dependency changed: '+path)
    return manifest

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec);sys.modules[name]=obj;spec.loader.exec_module(obj)
    return obj

def finite_json(obj,mp):
    if isinstance(obj,mp.mpf):
        f=float(obj)
        if not math.isfinite(f) or (f==0 and obj!=0):raise ArithmeticError('Output over/underflow')
        return f
    if isinstance(obj,dict):return {k:finite_json(v,mp) for k,v in obj.items()}
    if isinstance(obj,(tuple,list)):return [finite_json(v,mp) for v in obj]
    if type(obj) is float and not math.isfinite(obj):raise ArithmeticError('Nonfinite result')
    return obj

def _assess_impl(request):
    """No ID-based acceptance; source validation is repeated even on cache hits."""
    try:L,q=validate(request)
    except (ValueError,TypeError,OverflowError) as exc:return fail('invalid_input',str(exc))
    except ArithmeticError as exc:return fail('numerical_failure',str(exc))
    try:manifest=verified_manifest()
    except (ValueError,OSError,KeyError) as exc:return fail('source_mismatch',str(exc))
    key=hashlib.sha256((MANIFEST_SHA+json.dumps(request,sort_keys=True,allow_nan=False)).encode()).hexdigest()
    if key in _CACHE:
        result=copy.deepcopy(_CACHE[key]);result['cache_hit']=True;return result
    try:
        # All own dependencies were verified above before any such import.
        core=module('aa_domain_revision1_core',HERE/'bound_core.py')
        gm=module('aa_domain_revision1_gross',HERE.parent/'gross_mle_domain_revision2/gross_mle.py')
        oracle=module('aa_domain_revision1_source',HERE.parent/'web_only_independent/pure_weak_oracle.py')
        mp=core.mp
        with mp.workdps(70):
            gd=gm.load_geometry(ROOT/GEOMETRY,manifest['files'][GEOMETRY])
            g=core.model(oracle)
            LL=mp.mpf(str(Decimal(L)));qq=[mp.mpf(str(Decimal(x))) for x in q]
            R=mp.matrix([0,qq[0]*LL*LL/8,qq[1]*LL*LL/8])
            common=dict(schema='aa_web_domain_bound_v1',result_kind='component_upper_bound',
                input_digest=key,source_manifest_sha256=MANIFEST_SHA,source_pins=manifest['files'],
                L_mm=L,q_N_mm=q,resultants_peak_N_Nmm=list(R),cache_hit=False,
                material=copy.deepcopy(request['material']),
                coordinate_convention=dict(compression='positive',section_basis='b=[1,y,-x]',
                    resultants='[N,Mx,My]=integral(b*sigma dA)',
                    load_components='q=[normal,parallel], M=[Mx,My]',
                    displacement_components='generalized [normal,parallel], -d_second=[kappa_x,kappa_y]',
                    geometry='Pinned faceted midline dA=t ds; bends retained once; external faces for material guard',
                    internal_origin_shift='PSD core shifts y by gross yc for conditioning; N=0 leaves moments unchanged'),
                model_scope=dict(N_N=0.,bimoment_Nmm2=0.,loading='uniform proportional q-only',
                    supports='simply_supported_bending',prismatic=True,
                    interpretation='Mathematical bending component only; N=B=0 does not establish physically absent torsion, warping or distortion'),
                numerical_limitations='70-digit arithmetic and 1e-20 padding are not formal interval arithmetic; binary64 published bounds are rounded outward. Physical application and global approval remain external.',
                uniqueness_proved=False,physical_ELS_approved=False,whole_member_approved=False,published=False,
                numeric_precision_digits=70,numerical_padding='1e-20')
            if all(x==0 for x in q):
                common.update(status='sufficient_zero_identity',sufficient=True,route='zero_identity',
                    existence_sufficient=True,material_sufficient=True,domain_sufficient=True,
                    stress_peak_MPa=0.,curvature_peak_intervals=[[0.,0.],[0.,0.]],
                    displacement_component_bounds=[{'absolute_max_upper_mm':0.,'midspan_interval_mm':[0.,0.] } for _ in range(2)])
            else:
                gross=gm.assess_case(gd,gm.model_for(gd,L),dict(q_N_mm=q,P_N=[0.,0.],point_position=None))
                if gross['sufficient_full_section']:
                    e=g['Cg']*R;factor=5*LL*LL/48
                    common.update(status='sufficient_gross_domain',sufficient=True,route='gross_full_section',
                        existence_sufficient=True,material_sufficient=True,domain_sufficient=True,gross_evidence=gross,
                        curvature_peak_intervals=[[e[i],e[i]] for i in (1,2)],
                        displacement_component_bounds=[dict(absolute_max_upper_mm=factor*abs(e[i])*(1+core.PAD),midspan_interval_mm=[factor*e[i],factor*e[i]]) for i in (1,2)])
                else:
                    bound=core.run_ray(g,R,LL)
                    sufficient=bool(bound['all_guards_sufficient'] and bound['exact_AA_law_section_existence_sufficient'])
                    common.update(bound)
                    common.update(status='sufficient_reduced_domain' if sufficient else 'inconclusive_domain',
                        sufficient=sufficient,route='retained_subset_psd_positive_web_existence',
                        existence_sufficient=bound['exact_AA_law_section_existence_sufficient'],
                        material_sufficient=bound['guards']['material_sufficient'],
                        domain_sufficient=bool(bound['all_guards_sufficient']),
                        gross_comparator_status=gross['status'])
                    if not sufficient:
                        common['diagnostic_only_component_bounds']=common.pop('displacement_component_bounds')
            result=finite_json(common,mp)
            # Decimal padding is smaller than a binary64 ulp. Public bounds
            # are rounded outward rather than silently losing that margin.
            if result['route']!='zero_identity':
                for bound_key in ('curvature_peak_intervals','web_endpoint_stress_intervals_MPa'):
                    for interval in result.get(bound_key,[]):
                        interval[0]=math.nextafter(interval[0],-math.inf)
                        interval[1]=math.nextafter(interval[1],math.inf)
                for bound_key in ('displacement_component_bounds','diagnostic_only_component_bounds'):
                    for item in result.get(bound_key,[]):
                        item['absolute_max_upper_mm']=math.nextafter(item['absolute_max_upper_mm'],math.inf)
                        item['midspan_interval_mm'][0]=math.nextafter(item['midspan_interval_mm'][0],-math.inf)
                        item['midspan_interval_mm'][1]=math.nextafter(item['midspan_interval_mm'][1],math.inf)
            json.dumps(result,allow_nan=False)
            _CACHE[key]=copy.deepcopy(result)
            return result
    except (ArithmeticError,ValueError,TypeError,KeyError,OverflowError,ZeroDivisionError) as exc:
        return fail('numerical_failure',str(exc))

def compare_component(request,component,criterion_mm):
    """Reassess verified physical request; never trust caller-supplied bounds."""
    try:
        limit=number(criterion_mm,'criterion_mm')
        if limit<=0 or type(component) is not int or component not in (0,1):raise ValueError('Invalid criterion/component')
        result=assess(request)
        if result.get('status') in ('invalid_input','source_mismatch','numerical_failure'):
            return dict(status=result['status'],physical_ELS_approved=False)
        if result.get('sufficient') is not True:return dict(status='inconclusive',physical_ELS_approved=False)
        upper=result['displacement_component_bounds'][component]['absolute_max_upper_mm']
        return dict(status='sufficient_component_only' if upper<=limit else 'inconclusive',
                    upper_bound_mm=upper,criterion_mm=limit,physical_ELS_approved=False)
    except (ValueError,KeyError,TypeError,OverflowError):return dict(status='invalid_input',physical_ELS_approved=False)


def assess(request):
 try:
  with localcontext(private_decimal_context()):
   return _assess_impl(request)
 except (ArithmeticError,ValueError,TypeError,OverflowError) as exc:
  return fail('numerical_failure',str(exc))

def assess_json(raw):
    def unique_pairs(pairs):
        obj={}
        for k,v in pairs:
            if k in obj:raise ValueError('Duplicate JSON key')
            obj[k]=v
        return obj
    try:request=json.loads(raw,object_pairs_hook=unique_pairs,parse_float=json_binary64,parse_int=int,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON token')))
    except (ValueError,TypeError,ArithmeticError):return fail('invalid_input','Invalid strict JSON')
    return assess(request)
