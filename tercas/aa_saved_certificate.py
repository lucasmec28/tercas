"""Algebraic checks of SAVED AA certificates, with no source reads or solvers.

No root search is run. Existing root intervals are checked by exact Sturm
counts; their saved Horner enclosures and extrema must reproduce the saved
ceiling. Green coefficients/continuity and hull-control links are identities.
This is consistency checking, not authentication or a new physical proof.
"""
from fractions import Fraction as F
from decimal import Decimal
import hashlib,json
from .biaxial_gross.bounded_polynomial import _trim,_value,_divide,_sturm,_variations


def _require(condition,message):
    if not condition:raise ValueError(message)


def _decimal(value):
    _require(isinstance(value,str) and len(value)<=4096,'Decimal salvo AA inválido.')
    d=Decimal(value)
    _require(d.is_finite(),'Decimal salvo AA não finito.')
    return F(d)


def _canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def _sha(value):return hashlib.sha256(_canonical(value).encode()).hexdigest()

def _interval(value):
    _require(isinstance(value,dict) and set(value)=={'lower_decimal','upper_decimal'},'Suporte AA salvo incompleto.')
    lo,hi=_decimal(value['lower_decimal']),_decimal(value['upper_decimal'])
    _require(lo<=hi,'Suporte AA salvo invertido.')
    return lo,hi


def _walls(walls,names,flag,slenderness):
    _require(isinstance(walls,list) and len(walls)==len(names),'Inventário de paredes AA incompleto.')
    _require(all(isinstance(w,dict) and w.get(flag) is True and isinstance(w.get('wall'),str) for w in walls),'Guarda detalhada de parede AA contradiz agregado.')
    _require({w['wall'] for w in walls}==set(names),'Paredes AA salvas ausentes/duplicadas.')
    for w in walls:
        lam=slenderness(w['lambda_local'])
        _require(0<=lam<=F(673,1000),'Esbeltez salva AA contradiz integralidade declarada.')


def _safe_flags(value):
    names={'physical_ELS_approved','combined_ELS_approved','whole_member_approved',
        'published','resistance_release','resistance_qualified','torsion_or_warping_qualified',
        'torque_or_warping_included','combined_stiffness_released','reduced_biaxial_law_qualified',
        'support_transfer_and_local_bearing_qualified','uniqueness_proved'}
    if isinstance(value,dict):
        for key,item in value.items():
            if key in names:_require(item is False,'Flag salva AA excede o escopo: '+key)
            _safe_flags(item)
    elif isinstance(value,list):
        for item in value:_safe_flags(item)


def _hull_mapping(hull,controls,request,contract,base,pair):
    _require(isinstance(hull,dict),'Certificado de hull AA ausente.')
    schema='aa_web_positive_ratio_control_hull_v1' if base=='positive_ratio' else 'aa_web_family_control_hull_v1'
    _require(hull.get('schema')==schema and hull.get('status')=='sufficient_control_hull','Esquema/status do hull AA incompatível.')
    _require(all(hull.get(k) is True for k in ('sufficient','existence_sufficient','nonweb_and_material_sufficient')),'Guardas agregadas AA incompletas.')
    _require(hull.get('source_manifest_sha256')==contract['core_manifest_sha256'] and hull.get('source_pins')==contract['core_source_pins'],'Fontes do hull AA salvo divergentes.')
    _require(hull.get('geometry_sha256')==request['geometry_sha256'] and hull.get('material')==request['material'],'Fonte/material do hull AA salvo divergentes.')
    unique=sorted(set(controls));raw=[[ [str(x.numerator),str(x.denominator)] for x in row] for row in unique]
    digest=hashlib.sha256(json.dumps(raw,separators=(',',':')).encode()).hexdigest()
    _require(hull.get('controls_digest')==digest,'Controles do hull AA não correspondem ao campo.')
    binding=dict(schema=schema,source_manifest=contract['core_manifest_sha256'],geometry_sha256=request['geometry_sha256'],controls_digest=digest,material=request['material'])
    if base=='positive_ratio':
        _require(hull.get('implementation_sha256')==contract['core_implementation_sha256'],'Implementação do hull AA salvo divergente.')
        binding['implementation_sha256']=contract['core_implementation_sha256']
    _require(hull.get('domain_binding_digest')==_sha(binding),'Vínculo de domínio AA salvo divergente.')
    eta=_decimal(hull['eta_common']);_require(0<=eta<=F(1,2),'Retenção AA salva fora da faixa.')
    _require(type(hull.get('constructive_full_section')) is bool and hull['constructive_full_section']==(eta==F(1,2)),'Retenção AA contradiz ramo integral.')
    rows=hull.get('controls');_require(isinstance(rows,list) and len(rows)==len(unique),'Controles do hull AA incompletos.')
    mapping={};old_flags=[];cone_flags=[]
    for row in rows:
        _require(isinstance(row,dict),'Controle do hull AA inválido.')
        exact=row['exact_resultants_N_Nmm'];R=tuple(pair(x) for x in exact)
        _require(len(R)==3 and R in unique and R not in mapping,'Controle do hull AA estranho/duplicado.')
        _require(row.get('control_digest')==hashlib.sha256(json.dumps(exact,separators=(',',':')).encode()).hexdigest(),'Digest do controle AA salvo divergente.')
        zero=not any(R)
        _require(row.get('zero_identity') is zero,'Identidade nula do controle AA contraditória.')
        _require(pair(row['normalization_scale_fraction'])==max(map(abs,R)),'Escala de controle AA divergente.')
        guards=row.get('guards');_require(isinstance(guards,dict) and guards.get('all_sufficient') is True,'Guardas detalhadas AA ausentes.')
        _walls(guards.get('walls'),('bottom_lip','bottom_flange','top_flange','top_lip'),'full_sufficient',_decimal)
        face=_decimal(guards['face_upper_MPa']);_require(0<=face<=F(request['material']['fy_MPa']),'Guarda material AA contraditória.')
        endpoints=row.get('web_endpoint_intervals_MPa');cones=row.get('cone_intervals_MPa')
        _require(isinstance(endpoints,list) and len(endpoints)==2 and isinstance(cones,list) and len(cones)==2,'Cones/extremidades AA ausentes.')
        e=[_interval(x) for x in endpoints];c=[_interval(x) for x in cones]
        old=zero or all(lo>0 for lo,hi in e);cone=zero or all(lo>0 for lo,hi in c)
        _require(row.get('two_positive_edges_sufficient') is old and row.get('psi_gt_minus0236_sufficient') is cone,'Existência detalhada AA contradiz intervalos salvos.')
        old_flags.append(old);cone_flags.append(cone)
        supports=row.get('curvature_supports_per_mm');_require(isinstance(supports,list) and len(supports)==2,'Dois suportes de curvatura AA exigidos.')
        mapping[R]=[_interval(x) for x in supports]
        if zero:_require(all(lo==hi==0 for lo,hi in mapping[R]),'Controle zero AA não pode receber curvatura.')
    _require(set(mapping)==set(unique),'Faltam controles do hull AA.')
    _require(hull.get('existence_positive_edges') is all(old_flags) and hull.get('existence_psi_cone') is all(cone_flags),'Existência agregada AA contraditória.')
    _require(eta==F(1,2) or all(old_flags) or (hull.get('psi_extension_reviewed') is True and all(cone_flags)),'Existência AA sem condição suficiente salva.')
    return mapping


def _interval_horner(coeff,interval):
    a,b=interval;lo=hi=F(0)
    for c in reversed(coeff):
        products=(lo*a,lo*b,hi*a,hi*b);lo,hi=min(products)+c,max(products)+c
    return lo,hi


def _saved_roots(coeff,records,piece_index,pair):
    """Count roots only in the already saved intervals. Never isolate roots."""
    derivative=_trim([i*coeff[i] for i in range(1,len(coeff))])
    p=derivative
    while len(p)>1 and p[0]==0:p=p[1:]
    while len(p)>1 and sum(p)==0:
        p,rem=_divide(p,[F(-1),F(1)]);_require(rem==[0],'Fator de borda salvo incompatível.')
    if len(p)<2:
        _require(not records,'Extremos AA extras em polinômio constante.');return []
    sequence=_sturm(p)
    if len(sequence[-1])>1:
        p,rem=_divide(p,sequence[-1]);_require(rem==[0],'Fator repetido salvo incompatível.');sequence=_sturm(p)
    count=_variations(sequence,F(0))-_variations(sequence,F(1))
    _require(len(records)==count,'Inventário de raízes AA salvo incompleto/duplicado.')
    result=[];last=None
    for item in records:
        _require(isinstance(item,list) and len(item)==3 and type(item[0]) is int and item[0]==piece_index,'Estrutura de extremo AA inválida.')
        interval=item[1];value=item[2]
        _require(isinstance(interval,list) and len(interval)==2 and isinstance(value,list) and len(value)==2,'Enclosure de extremo AA incompleto.')
        l,r=map(pair,interval);lo,hi=map(pair,value)
        _require(0<=l<=r<=1 and (last is None or l>=last),'Raízes AA salvas sobrepostas/fora do trecho.')
        if last is not None and l==last:_require(_value(p,l)!=0,'Raiz AA compartilhada/duplicada entre enclosures.')
        if l==r:_require(0<l<1 and _value(p,l)==0,'Raiz singleton AA não é raiz do polinômio salvo.')
        else:_require(_value(p,l)!=0 and _variations(sequence,l)-_variations(sequence,r)==1,'Intervalo AA não isola uma raiz salva.')
        _require((lo,hi)==_interval_horner(coeff,(l,r)),'Enclosure do valor AA contradiz polinômio salvo.')
        result.append((lo,hi));last=r
    return result


def _green_bound(bound,breaks,component,pair,expected_controls=None):
    n=len(breaks)-1
    _require(isinstance(bound,dict) and type(bound.get('component')) is int and bound['component']==component,'Componente AA malformada.')
    required={'component','absolute_max_upper_mm','absolute_max_upper_fraction','lower_curvature_controls','upper_curvature_controls','lower_displacement_polynomials','upper_displacement_polynomials','extrema_root_enclosures'}
    if 'leaf_ids' in bound or 'break_fractions' in bound:required|={'leaf_ids','break_fractions'}
    _require(set(bound)==required,'Certificado Green AA incompleto ou desconhecido.')
    controls=[];polys=[]
    for prefix in ('lower','upper'):
        cc=bound[prefix+'_curvature_controls'];pp=bound[prefix+'_displacement_polynomials']
        _require(isinstance(cc,list) and len(cc)==n and isinstance(pp,list) and len(pp)==n,'Partição Green AA incompleta.')
        _require(all(isinstance(c,list) and len(c)==3 for c in cc) and all(isinstance(p,list) and len(p)==5 for p in pp),'Forma Green/curvatura AA inválida.')
        controls.append([list(map(pair,c)) for c in cc]);polys.append([list(map(pair,p)) for p in pp])
    _require(all(lo<=hi for cl,cu in zip(*controls) for lo,hi in zip(cl,cu)),'Curvaturas AA salvas invertidas.')
    if expected_controls is not None:_require(controls==expected_controls,'Curvaturas Green divergem dos suportes do mesmo controle/hull.')
    for cc,pp in zip(controls,polys):
        _require(pp[0][0]==0 and sum(pp[-1])==0,'Condições de apoio Green salvas divergentes.')
        for i,(c,p,u,v) in enumerate(zip(cc,pp,breaks,breaks[1:])):
            h=v-u;c0,c1,c2=c
            _require(p[2:]==[-h*h*c0/2,-h*h*2*(c1-c0)/6,-h*h*(c0-2*c1+c2)/12],'Equação Green salva não corresponde às curvaturas.')
            if i:
                last=pp[i-1];lh=breaks[i]-breaks[i-1]
                _require(sum(last)==p[0] and sum(j*last[j] for j in range(1,5))/lh==p[1]/h,'Continuidade Green d/d\' salva divergente.')
    records=bound['extrema_root_enclosures'];_require(isinstance(records,list) and len(records)==2,'Certificados de extremos AA ausentes.')
    extrema=[]
    for pp,saved in zip(polys,records):
        _require(isinstance(saved,list),'Lista de extremos AA inválida.')
        _require(all(isinstance(x,list) and len(x)==3 and type(x[0]) is int and 0<=x[0]<n for x in saved),'Índice do trecho extremo AA inválido.')
        _require([x[0] for x in saved]==sorted(x[0] for x in saved),'Extremos AA salvos fora da ordem.')
        values=[]
        for i,p in enumerate(pp):
            values.extend(((p[0],p[0]),(sum(p),sum(p))))
            values.extend(_saved_roots(p,[x for x in saved if x[0]==i],i,pair))
        extrema.append((min(x[0] for x in values),max(x[1] for x in values)))
    exact=max(F(0),extrema[1][1],-extrema[0][0])
    _require(pair(bound['absolute_max_upper_fraction'])==exact,'Teto AA contradiz os extremos e polinômios salvos.')
    return controls


def check_saved(response,request,base,contract,pair):
    _safe_flags(response)
    field=response['field'];pieces=field['pieces'];route=response['route']
    original_controls=[[tuple(pair(x) for x in row) for row in p['controls_N_Nmm']] for p in pieces]
    breaks=[pair(pieces[0]['left_fraction'])]+[pair(p['right_fraction']) for p in pieces]
    expected=None
    if route=='gross_full_section':
        gross=response.get('gross_evidence')
        _require(isinstance(gross,dict),'Crivo integral AA ausente.')
        _require(gross.get('status')=='sufficient_comparator_pass' and gross.get('sufficient_full_section') is True and gross.get('elastic_stress_sufficient') is True,'Crivo integral AA incompatível.')
        _require(gross.get('geometry_source_sha256')==request['geometry_sha256'],'Crivo integral AA de outra fonte.')
        _walls(gross.get('walls'),('bottom_lip','bottom_flange','web','top_flange','top_lip'),'full_wall_sufficient',F)
        for wall in gross['walls']:
            if 'flange' in wall['wall'] and (F(wall['lambda_p0'])>F(673,1000) or wall.get('Ia_monotone_upper_mm4') is not None):
                Is,Ia=wall.get('Is_mm4'),wall.get('Ia_monotone_upper_mm4')
                _require(type(Is) in (int,float) and type(Ia) in (int,float) and F(Is)>=F(Ia)>=0,'Enrijecedor salvo do crivo AA contradiz Is>=Ia.')
        _require(0<=F(gross['maximum_absolute_normal_stress_upper_MPa'])<=F(request['material']['fy_MPa']),'Guarda elástica integral AA contraditória.')
        C=response.get('gross_Cg_reintegrated')
        _require(isinstance(C,list) and len(C)==3 and all(isinstance(row,list) and len(row)==3 for row in C),'Tensor bruto AA salvo incompleto.')
        intervals=[]
        for row in C:
            intervals.append([])
            for x in row:
                value=_decimal(x);d=Decimal(x)
                # nstr(...,60): at most half a unit in its last requested place.
                radius=F(10)**(d.adjusted()-59)/2 if value else F(0)
                intervals[-1].append((value-radius,value+radius))
    elif route=='web_control_hull':
        mapping=_hull_mapping(response.get('hull_evidence'),[c for p in original_controls for c in p],request,contract,base,pair)
        expected=[[[[mapping[c][k][side] for c in p] for p in original_controls] for side in (0,1)] for k in (0,1)]
    elif route=='finite_local_partition':
        part=response['partition'];leaves=part['certified_leaf_ids'];nodes=part['nodes']
        _require(all(type(i) is int and 0<=i<len(nodes) for i in leaves),'IDs de folha AA inválidos.')
        expected=[[[],[]],[[],[]]];breaks=[F(0)]
        _require(type(part.get('budget_used')) is int and part['budget_used']==len(nodes) and 0<=len(nodes)<=part['budget_requested'],'Contagem de avaliações locais AA inconsistente.')
        interfaces=[]
        for position,i in enumerate(leaves):
            node=nodes[i];controls=[tuple(pair(x) for x in row) for row in node['exact_controls_N_Nmm']]
            u,v=pair(node['left_fraction']),pair(node['right_fraction'])
            sources=[(piece,cs) for piece,cs in zip(pieces,original_controls) if pair(piece['left_fraction'])<=u<v<=pair(piece['right_fraction'])]
            _require(len(sources)==1,'Folha AA não pertence a um trecho original.')
            original,cs=sources[0];a,b=pair(original['left_fraction']),pair(original['right_fraction'])
            def moment(z):
                t=(z-a)/(b-a)
                return tuple((1-t)**2*x+2*t*(1-t)*y+t*t*z for x,y,z in zip(*cs))
            t=(u-a)/(b-a);c0,c2=moment(u),moment(v)
            derivative=[2*((1-t)*(y-x)+t*(z-y))/(b-a) for x,y,z in zip(*cs)]
            c1=tuple(x+(v-u)*d/2 for x,d in zip(c0,derivative))
            _require(controls==[c0,c1,c2],'Controles de folha AA não representam o campo original.')
            if position:interfaces.append(dict(coordinate_fraction=node['left_fraction'],left_leaf=leaves[position-1],right_leaf=i,original_field_continuous=True,additional_support=False))
            h=node['hull_evidence']
            local_identity=dict(field_digest=response['field_digest'],node={k:node[k] for k in ('id','left_fraction','right_fraction','exact_controls_N_Nmm')},hull_binding=h['domain_binding_digest'],H=h['common_H_compliance_diagnostic'])
            _require(node.get('local_domain_digest')==_sha(local_identity),'Vínculo de domínio local AA salvo divergente.')
            mapping=_hull_mapping(h,controls,request,contract,base,pair)
            for k in (0,1):
                for side in (0,1):expected[k][side].append([mapping[c][k][side] for c in controls])
            breaks.append(pair(node['right_fraction']))
        _require(part['interfaces']==interfaces,'Interfaces Green AA salvas ausentes/incompatíveis.')
    elif route=='zero_identity':expected=[[[[F(0)]*3 for p in pieces] for side in (0,1)] for k in (0,1)]
    else:raise ValueError('Ramo de certificado AA desconhecido.')
    for k,bound in enumerate(response['displacement_component_bounds']):
        if route=='finite_local_partition':
            _require(bound.get('leaf_ids')==leaves and [pair(x) for x in bound.get('break_fractions',[])]==breaks,'Partição Green AA diverge das folhas certificadas.')
        else:_require('leaf_ids' not in bound and 'break_fractions' not in bound,'Partição local indevida no ramo AA salvo.')
        controls=_green_bound(bound,breaks,k,pair,None if expected is None else expected[k])
        if route=='gross_full_section':
            for p,low,high in zip(original_controls,*controls):
                for R,lo,hi in zip(p,low,high):
                    products=[(min(a*r,b*r),max(a*r,b*r)) for (a,b),r in zip(intervals[k+1],R)]
                    _require(lo<=sum(x[0] for x in products) and sum(x[1] for x in products)<=hi,'Suporte bruto AA contradiz o tensor salvo.')
