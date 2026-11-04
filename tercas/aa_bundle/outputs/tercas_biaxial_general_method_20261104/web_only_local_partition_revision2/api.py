"""Finite local certificates, exact subdivision, one original-span Green.
Research component ceilings only. No physical/global ELS approval.
"""
from pathlib import Path
from fractions import Fraction as F
from decimal import Context, localcontext, ROUND_HALF_EVEN, MAX_EMAX, MIN_EMIN, InvalidOperation, DivisionByZero, Overflow
import copy, hashlib, json, types, sys, uuid
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE=HERE.parent/'web_only_family_api_revision2'
MANIFEST_SHA='a8ba233933a7040b5cb5ef5860861822968ca99d9c8e109c935dbe7241fb9ba9'
SCHEMA='aa_web_family_qp_component_v1'
PARTITION_SCHEMA='aa_web_local_partition_v1'

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def pair(x):return [str(x.numerator),str(x.denominator)]
def failure(status,reason):return dict(schema=SCHEMA,status=status,reason=reason,sufficient=False,result_kind='component_upper_bound',physical_ELS_approved=False,whole_member_approved=False,published=False)
def verified_manifest():
    raw=(HERE/'SOURCE_MANIFEST.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA:raise ValueError('Partition manifest changed')
    m=json.loads(raw)
    for p,sha in m['files'].items():
        if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=sha:raise ValueError('Pinned dependency changed: '+p)
    return m

class Sources:
    def __enter__(self):
        self.names=[];self.prefix='_partition_'+uuid.uuid4().hex
        pkg=types.ModuleType(self.prefix);pkg.__path__=[];sys.modules[self.prefix]=pkg;self.names.append(self.prefix);return self
    def source(self,name,path):
        name=self.prefix+'.'+name;m=types.ModuleType(name);m.__file__=str(path);m.__package__=self.prefix
        sys.modules[name]=m;self.names.append(name);exec(compile(path.read_bytes(),str(path),'exec'),m.__dict__);return m
    def __exit__(self,*args):
        for name in reversed(self.names):sys.modules.pop(name,None)

def split(piece,fieldmod):
    """Rational midpoint de Casteljau: no amplitude or coordinate tolerance."""
    c0,c1,c2=piece.controls
    avg=lambda a,b:tuple((x+y)/2 for x,y in zip(a,b))
    d0,d1=avg(c0,c1),avg(c1,c2);mid=avg(d0,d1);z=(piece.left+piece.right)/2
    return (fieldmod.MomentPiece(piece.left,z,(c0,d0,mid)),fieldmod.MomentPiece(z,piece.right,(mid,d1,c2)))

def node_record(piece,node_id,parent,depth):
    return dict(id=node_id,parent=parent,depth=depth,left_fraction=pair(piece.left),right_fraction=pair(piece.right),
        exact_controls_N_Nmm=[[['0','1']]+[pair(x) for x in c] for c in piece.controls],status='pending',children=[])

def _assess(request,refinement_budget):
    if type(refinement_budget) is not int or refinement_budget<0:return failure('invalid_input','refinement_budget must be a nonnegative integer number of local hull calls')
    try:manifest=verified_manifest()
    except (OSError,ValueError,KeyError) as exc:return failure('source_mismatch',str(exc))
    try:
      with Sources() as mods:
        base=mods.source('base_api',BASE/'api.py')
        prior=base.assess(request)
        if prior.get('sufficient') or prior.get('status')!='inconclusive_domain':return prior
        req=copy.deepcopy(prior['request'])
        mods.source('bounded_polynomial_source',HERE.parent/'web_only_piecewise_field/bounded_polynomial_source.py')
        fm=mods.source('piecewise_field',HERE.parent/'web_only_piecewise_field/piecewise_field.py')
        core=mods.source('control_core',BASE/'control_core.py')
        field=fm.build_field(req['L_mm'],req['q_N_mm'],req['P_N'],req['a_mm'])
        if base.field_record(field)!=prior['field']:raise ValueError('Original mechanical field binding mismatch')
        nodes=[];pending=[];leaves=[];used=0
        def add(piece,parent=None,depth=0):
            i=len(nodes);nodes.append(node_record(piece,i,parent,depth));return (i,piece)
        pending=[add(p) for p in field.pieces]
        terminal_error=None
        # Breadth first, preserving every uncovered interval in the active frontier.
        while pending and used<refinement_budget:
            i,p=pending.pop(0);n=nodes[i];cs=[(F(0),)+c for c in p.controls]
            hull=core.assess(dict(schema='aa_web_family_control_hull_v1',geometry_sha256=req['geometry_sha256'],material=req['material'],controls=[list(c) for c in cs]));used+=1
            n['hull_evidence']=hull
            if hull.get('status') in ('invalid_input','source_mismatch','numerical_failure'):
                n['status']='failed';pending.insert(0,(i,p));terminal_error=hull;break
            mapping=base.hull_mapping(hull,cs,core,req['material'],req['geometry_sha256'])
            sufficient=all(hull.get(k) is True for k in ('sufficient','existence_sufficient','nonweb_and_material_sufficient'))
            if sufficient:
                n['status']='certified';n['local_domain_digest']=digest(dict(field_digest=prior['field_digest'],node={k:n[k] for k in ('id','left_fraction','right_fraction','exact_controls_N_Nmm')},hull_binding=hull['domain_binding_digest'],H=hull['common_H_compliance_diagnostic']))
                leaves.append((i,p,mapping))
            else:
                n['status']='split';n['reason']='Local existence/material/nonweb certificate insufficient; resource refinement only'
                children=[add(c,i,n['depth']+1) for c in split(p,fm)]
                n['children']=[j for j,c in children];pending.extend(children)
        leaves.sort(key=lambda item:item[1].left)
        frontier=sorted([(i,p) for i,p,m in leaves]+pending,key=lambda item:item[1].left)
        if not frontier or frontier[0][1].left!=0 or frontier[-1][1].right!=field.length or any(a.right!=b.left for (_,a),(_,b) in zip(frontier,frontier[1:])):raise ValueError('Incomplete frontier coverage')
        out=copy.deepcopy(prior)
        out.update(route='finite_local_partition',status='inconclusive_domain',sufficient=False,existence_sufficient=False,domain_sufficient=False,material_sufficient=False)
        out.pop('displacement_component_bounds',None)
        out['prior_attempt']=dict(status=prior['status'],route=prior['route'],binding_digest=prior['binding_digest'])
        out['partition']=dict(schema=PARTITION_SCHEMA,source_manifest_sha256=MANIFEST_SHA,source_pins=manifest['files'],original_field_digest=prior['field_digest'],nodes=nodes,
            certified_leaf_ids=[i for i,p,m in leaves],pending_leaf_ids=[i for i,p in pending],frontier_ids=[i for i,p in frontier],
            budget_requested=refinement_budget,budget_used=used,budget_units='Additional local control-core assessments, excluding original assessment',
            coverage_complete=not pending,frontier_covers_original_span=True,interfaces=[dict(coordinate_fraction=pair(b.left),left_leaf=a_id,right_leaf=b_id,original_field_continuous=a.controls[-1]==b.controls[0],additional_support=False) for (a_id,a),(b_id,b) in zip(frontier,frontier[1:])])
        if terminal_error:
            out['status']=terminal_error['status'];out['reason']=terminal_error.get('reason','Local hull failure')
        elif pending:out['reason']='Refinement resource budget exhausted; uncertified intervals remain; no usable ceiling'
        else:
            breaks=[F(0)]+[p.right for i,p,m in leaves];results=[]
            for k in range(2):
                # Mapping is intentionally PER LEAF, never keyed only by R globally.
                lower=[[m[base.key((F(0),)+c)][k][0] for c in p.controls] for i,p,m in leaves]
                upper=[[m[base.key((F(0),)+c)][k][1] for c in p.controls] for i,p,m in leaves]
                ceiling=fm.component_bound(breaks,lower,upper)
                for polys in (ceiling.lower_pieces,ceiling.upper_pieces):
                    if any(a.value(1,d)!=b.value(0,d) for a,b in zip(polys,polys[1:]) for d in (0,1)):raise ValueError('Global Green continuity failure')
                results.append(dict(component=k,leaf_ids=[i for i,p,m in leaves],break_fractions=[pair(x) for x in breaks],absolute_max_upper_mm=ceiling.upper_float(),absolute_max_upper_fraction=pair(ceiling.absolute_upper),lower_curvature_controls=[[pair(x) for x in row] for row in lower],upper_curvature_controls=[[pair(x) for x in row] for row in upper],lower_displacement_polynomials=[[pair(x) for x in p.coefficients] for p in ceiling.lower_pieces],upper_displacement_polynomials=[[pair(x) for x in p.coefficients] for p in ceiling.upper_pieces],extrema_root_enclosures=[[[i,[pair(x) for x in interval],[pair(x) for x in value]] for i,interval,value in ext.critical_intervals] for ext in (ceiling.lower_extrema,ceiling.upper_extrema)]))
            out.update(status='sufficient_finite_local_partition',sufficient=True,existence_sufficient=True,domain_sufficient=True,material_sufficient=True,displacement_component_bounds=results)
            out['partition']['global_Green_C1_verified']=True
        out['partition_digest']=digest(out['partition'])
        out['binding_digest']=digest(dict(request=out['request_digest'],field=out['field_digest'],manifest=MANIFEST_SHA,partition=out['partition_digest'],route=out['route']))
        canonical(out);return out
    except (ValueError,TypeError,ArithmeticError,KeyError,OverflowError,OSError) as exc:return failure('numerical_failure',str(exc))

def assess(request,refinement_budget=64):
    with localcontext(Context(prec=70,rounding=ROUND_HALF_EVEN,Emin=MIN_EMIN,Emax=MAX_EMAX,capitals=1,clamp=0,flags=[],traps=[InvalidOperation,DivisionByZero,Overflow])):
        return _assess(request,refinement_budget)

def assess_json(raw,refinement_budget=64):
    import math
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('Duplicate JSON key')
            d[k]=v
        return d
    def finite_float(token):
        x=float(token)
        significand=token.lower().split('e',1)[0]
        nonzero=any(c in '123456789' for c in significand)
        if not math.isfinite(x) or (x==0 and nonzero):raise ValueError('JSON float overflow/underflow')
        return x
    try:req=json.loads(raw,object_pairs_hook=pairs,parse_float=finite_float,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    except (ValueError,TypeError):return failure('invalid_input','Invalid strict JSON')
    return assess(req,refinement_budget)

def compare_component(request,component,criterion_mm,refinement_budget=64):
    import math
    flags=dict(physical_ELS_approved=False,whole_member_approved=False,published=False)
    try:
        valid=type(component) is int and component in (0,1) and type(criterion_mm) in (int,float) and math.isfinite(criterion_mm) and criterion_mm>0
    except (TypeError,ValueError,OverflowError):valid=False
    if not valid:return dict(status='invalid_input',**flags)
    result=assess(request,refinement_budget)
    if not result.get('sufficient'):return dict(status=result['status'] if result['status'] in ('invalid_input','source_mismatch','numerical_failure') else 'inconclusive',**flags)
    ceiling=result['displacement_component_bounds'][component]['absolute_max_upper_mm']
    return dict(status='sufficient_component_only' if F(ceiling)<=F(criterion_mm) else 'inconclusive',upper_bound_mm=ceiling,criterion_mm=criterion_mm,request_digest=result['request_digest'],binding_digest=result['binding_digest'],**flags)
