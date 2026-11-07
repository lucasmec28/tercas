"""Synthetic physical point proofs; no private cases or global maximum claim."""
import copy
import json
from decimal import Decimal as D,localcontext
import pytest
from docx import Document
from tercas import isolated_en_ue125_300 as en
from tercas import en_ue125_300_normal_witness as witness
from tercas import isolated_en_ue125_300_ui as ui
from tercas.en_ue125_300_authority import read
from tercas.torsion_vlasov.vlasov import solve_member
from test_isolated_en_ue125_300 import summary


def make_point(scale=1.):
    s=en.section_reference()
    return solve_member(section=s,length_mm=4000.,E_MPa=200000.,G_MPa=77000.,
        actions=[dict(name='P',kind='point',force_xy_N=[1000.*scale,-10000.*scale],
            couple_Nmm=100.*scale,application_xy_mm=s['properties']['shear_center_xy_mm'],s_mm=2000.,origin='synthetic witness')],
        supports={side:dict(twist='fixed',warping='free_assumed',origin='synthetic witness') for side in ('left','right')},
        combination_id='SYNTHETIC_POINT',limit_state='ELU',member_id='QA',action_accounting_origin='synthetic',elements_per_interval=8)


@pytest.fixture(scope='module')
def source():return make_point()


@pytest.fixture(scope='module')
def check(source):return en.calculate(source,normal_snapshot=read(),model_origin='Synthetic witness')


def args(d):return dict(normal_snapshot=read(),source_sha256=en._sha(d),model_origin='Synthetic witness')


def decimal_sigma(d,w):
    with localcontext() as ctx:
        ctx.prec=70
        loc=w['location'];e=d['elements'][loc['element_index']];u=D(loc['longitudinal_parameter']);x=D(loc['x_mm'])
        ra=list(map(D,d['support_reactions']['left_force_xy_N']))
        mx=-ra[1]*x;my=ra[0]*x
        for a in d['loads']:
            if a['kind']=='uniform':mx-=D(a['q_xy_N_mm'][1])*x*x/2;my+=D(a['q_xy_N_mm'][0])*x*x/2
            elif a['s_mm']<=e['a_mm']:
                mx-=D(a['force_xy_N'][1])*(x-D(a['s_mm']));my+=D(a['force_xy_N'][0])*(x-D(a['s_mm']))
        b=sum(D(c)*u**k for k,c in enumerate(e['coefficients']['B_Nmm2']))
        s=d['section'];j=w['wall_segment'];node=j+int(w['wall_parameter']);p0,p1=s['nodes_xy_mm'][j:j+2]
        dx=D(p1[0])-D(p0[0]);dy=D(p1[1])-D(p0[1]);length=(dx*dx+dy*dy).sqrt();p=s['properties'];t=D(s['thickness_mm'])
        xx=D(s['nodes_xy_mm'][node][0])-D(p['centroid_xy_mm'][0])-D(w['face'])*t*dy/(2*length)
        yy=D(s['nodes_xy_mm'][node][1])-D(p['centroid_xy_mm'][1])+D(w['face'])*t*dx/(2*length)
        out=b*D(s['omega_nodes_mm2'][node])/D(p['Cw_mm6']);normal=read()
        for axis,value in [('Mx',mx),('My',my)]:
            key=w['selected_operators'][axis]
            if key:
                c0,cx,cy=map(D,normal['components'][key]['sigma_coefficients_c0_cx_cy']);out+=value*(c0+cx*xx+cy*yy)
        return out


def test_observed_point_decimal70_and_unchanged_upper(source,check):
    n=check['stress']['criteria']['normal'];assert n['observed_exceedance'] is True
    w=n['physical_witness'];exact=decimal_sigma(source,w)
    assert D(w['sigma_interval_MPa'][0])<=exact<=D(w['sigma_interval_MPa'][1])
    assert D(w['absolute_sigma_lower_MPa'])<=abs(exact) and w['absolute_sigma_lower_MPa']>300
    assert w['physical_maximum_claimed'] is False and w['first_order_analysis_qualified'] is False
    old=en._calculate(source,normal_snapshot=read(),model_origin='Synthetic witness',normal_witness=False)
    assert old['schema']==en.LEGACY_SCHEMA and old['stress']['criteria']['normal']['observed_exceedance'] is False
    assert all(old['stress']['criteria'][k]['index_upper_bound']==check['stress']['criteria'][k]['index_upper_bound'] for k in ('normal','shear','interaction'))
    assert old['mv']==check['mv'] and old['shear']==check['shear']
    assert check['source_demand']==source and not check['whole_member_approved']


def test_opposite_moment_signs_and_faces(source,check):
    d=make_point(-1.);r=en.calculate(d,normal_snapshot=read(),model_origin='Synthetic witness')
    n=r['stress']['criteria']['normal'];assert n['observed_exceedance']
    w=n['physical_witness'];exact=decimal_sigma(d,w)
    assert D(w['sigma_interval_MPa'][0])<=exact<=D(w['sigma_interval_MPa'][1]) and abs(exact)>300
    base=check['stress']['criteria']['normal']['bound_control']
    found=[]
    for face in (-1,1):
        c=copy.deepcopy(base);c['face']=face
        v=witness.observe(source,read(),c)
        if v:found.append(v);assert v['absolute_sigma_lower_MPa']>300
    assert len(found)==2


@pytest.mark.parametrize('key,value',[('longitudinal_control',1),('longitudinal_control',2),('wall_control',1),('longitudinal_control',False),('wall_control',False),('face',True)])
def test_fictitious_or_boolean_controls_are_not_points(source,check,key,value):
    c=copy.deepcopy(check['stress']['criteria']['normal']['bound_control']);c[key]=value
    assert witness.observe(source,read(),c) is None


def test_union_branch_and_its_sigma_are_never_used(source,check):
    c=copy.deepcopy(check['stress']['criteria']['normal']['bound_control'])
    expected=witness.observe(source,read(),c)
    c['signed_operator_superset']={'Mx':'My_negative','My':'Mx_positive'}
    c['sigma_interval_MPa']=[1e12,1e12]
    assert witness.observe(source,read(),c)==expected


@pytest.mark.parametrize('mutation',['face','coordinate','sign','interval','flag','source'])
def test_rehashed_witness_tampering_is_rejected(source,check,mutation):
    r=copy.deepcopy(check);w=r['stress']['criteria']['normal']['physical_witness']
    if mutation=='face':w['face']*=-1
    elif mutation=='coordinate':w['location']['x_mm']+=1
    elif mutation=='sign':w['selected_operators']['My']='My_positive'
    elif mutation=='interval':w['sigma_interval_MPa'][0]*=2
    elif mutation=='flag':r['stress']['criteria']['normal']['observed_exceedance']=False
    else:w['source_demand_sha256']='f'*64
    w['content_sha256']=en._sha({k:v for k,v in w.items() if k!='content_sha256'})
    r['stress']['content_sha256']=en._sha({k:v for k,v in r['stress'].items() if k!='content_sha256'})
    r['content_sha256']=en._sha({k:v for k,v in r.items() if k!='content_sha256'})
    with pytest.raises(ValueError):en.validate_saved(r,summary(source),**args(source))


def test_legacy_v1_remains_unchanged_and_rejects_injection(source,check,monkeypatch):
    old=en._calculate(source,normal_snapshot=read(),model_origin='Synthetic witness',normal_witness=False)
    before=json.dumps(old,sort_keys=True)
    def fail(*a,**k):raise AssertionError('A historical v1 must not be reclassified')
    monkeypatch.setattr(witness,'observe',fail)
    assert en.validate_saved(json.loads(before),summary(source),**args(source))
    assert json.dumps(old,sort_keys=True)==before
    old['stress']['criteria']['normal']=copy.deepcopy(check['stress']['criteria']['normal'])
    old['stress']['content_sha256']=en._sha({k:v for k,v in old['stress'].items() if k!='content_sha256'})
    old['content_sha256']=en._sha({k:v for k,v in old.items() if k!='content_sha256'})
    with pytest.raises(ValueError):en.validate_saved(old,summary(source),**args(source))


def test_exact_limit_and_straddling_sign_never_prove_excess(source,check):
    # Operator-only fabricated exact-unit field. It is not submitted as a
    # qualified solved member; this isolates the strict interval inequality.
    d=copy.deepcopy(source);d['loads']=[];d['support_reactions']['left_force_xy_N']=[0.,0.]
    d['section']['properties']['Cw_mm6']=1.;d['section']['omega_nodes_mm2']=[1.]*134
    for e in d['elements']:e['coefficients']['B_Nmm2']=[300.];e['coefficients']['Tsv_Nmm']=[0.];e['coefficients']['Tw_Nmm']=[0.]
    c=copy.deepcopy(check['stress']['criteria']['normal']['bound_control'])
    assert witness.observe(d,read(),c) is None
    for e in d['elements']:e['coefficients']['B_Nmm2']=[301.]
    w=witness.observe(d,read(),c);assert w and w['absolute_sigma_lower_MPa']>300
    assert w['selected_operators']=={'Mx':None,'My':None}


def test_ui_word_distinguish_observed_excess(source,check,monkeypatch):
    ev=dict(configuration={'model_origin':'Synthetic witness'},computed_cases=1,pending_demand_cases=0,ELS_cases_excluded=0,ELU_cases=1,
        source_torsion_snapshot_sha256='a'*64,records=[dict(combination_id='SYNTHETIC_POINT',check=check,reason=None)])
    assert ui.rows(ev)[0]['Tensões EN6.1.6']=='Excesso normal observado no modelo linear'
    lines='\n'.join(ui.text_lines(ev));assert 'Excesso normal observado' in lines and 'não o máximo físico' in lines
    monkeypatch.setattr(ui.a,'_presentation_view',lambda result:ev)
    doc=Document();ui.report(doc,{})
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Excesso normal observado' in text and 'primeira ordem' in text and 'giro linear alto' in text


def test_ambiguous_interval_sign_and_false_union_excess_are_not_witnesses(source,check,monkeypatch):
    c=copy.deepcopy(check['stress']['criteria']['normal']['bound_control'])
    low=make_point(.1);c['sigma_interval_MPa']=[1e12,1e12]
    assert witness.observe(low,read(),c) is None
    original=witness._member_polynomials
    def ambiguous(d):
        p,ids=original(d);p['Mx']=en.I(p['Mx'].lo*0-1.,p['Mx'].hi*0+1.)
        return p,ids
    monkeypatch.setattr(witness,'_member_polynomials',ambiguous)
    assert witness.observe(source,read(),c) is None


def test_cold_reader_reproves_witness_and_keeps_upper(source,check,monkeypatch):
    with en._READ_LOCK:en._VERIFIED_READS.clear()
    calls=[];original=witness.observe
    def spy(*a,**k):calls.append(1);return original(*a,**k)
    monkeypatch.setattr(witness,'observe',spy)
    restored=json.loads(json.dumps(check))
    assert en.validate_saved(restored,summary(source),**args(source)) and calls==[1]
    assert restored==check


def test_ui_preserves_applicability_and_threshold_format(check):
    c=copy.deepcopy(check);c['applicability'].update(qualified=False,reason='Synthetic applicability pending')
    c['stress']['status']='pending_bending_applicability'
    c['stress']['criteria']['normal']['physical_witness']['absolute_sigma_lower_MPa']=300.0000001
    ev=dict(configuration={'model_origin':'Synthetic view only'},computed_cases=1,pending_demand_cases=0,ELS_cases_excluded=0,ELU_cases=1,
        records=[dict(combination_id='SYNTHETIC_POINT',check=c,reason=None)])
    row=ui.rows(ev)[0]
    assert 'Excesso normal observado' in row['Tensões EN6.1.6'] and 'aplicabilidade pendente' in row['Tensões EN6.1.6']
    assert 'Synthetic applicability pending' in row['Motivo']
    lines='\n'.join(ui.text_lines(ev))
    assert 'Aplicabilidade seccional pendente' in lines and ui.fmt(300.0000001,limit=300.) in lines
