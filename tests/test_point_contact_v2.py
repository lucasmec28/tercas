"""Finite physical contact opt-in; synthetic fixtures, not a real design."""
import copy
from decimal import Decimal, localcontext
from io import BytesIO
import pytest
from docx import Document
from tercas.point_contact import *
from tercas.point_contact import _saved_digest
from tercas.application import example, calculate, build_spec
from test_point_contact import mechanics


def ready(x=20., family='Ue', ri=2.):
    d=example();d.update(load_mode='direct',x_uls=x,P_uls=1500.,P_parallel_uls=0.)
    d['properties']['ri_mm']=ri
    c=blank_choice();c.update(schema=SCHEMA_V2,enabled=True,c_mm=40.,origin='QA sintético: detalhe P e apoios A/B',basis=reference_basis(d))
    c['declarations']={k:True for k in DECLARATIONS};d[FIELD]=c
    s=build_spec(d);s['selected_section']['family']=family
    return d,s


@pytest.mark.parametrize('right',[False,True])
@pytest.mark.parametrize('x,expected',[(20.,'end'),(19.999999,None),(158.,'end'),(158.000001,'internal')])
def test_edges_and_exact_transition(right,x,expected):
    d,s=ready(x);d['x_uls']=d['L_mm']-x if right else x;d[FIELD]['basis']=reference_basis(d)
    b=evaluate(d,s)
    if expected is None:
        assert b['status']=='not_evaluated' and 'index' not in b
    else:
        assert b['status']=='computed' and b['domain']['table_location']==expected
        assert b['force_N']==1500. and b['patch_mm']==[d['x_uls']-20,d['x_uls']+20]


@pytest.mark.parametrize('family,loc,limit',[('U','end',2),('U','internal',1),('Ue','end',5),('Ue','internal',5)])
def test_radius_specific_row(family,loc,limit):
    d,s=ready(20. if loc=='end' else 2000.,family,ri=2.*limit)
    assert evaluate(d,s)['status']=='computed'
    s['selected_section']['fields']['ri_mm']['value']+=1e-9
    assert evaluate(d,s)['status']=='not_evaluated'


@pytest.mark.parametrize('family,coeff',[('Ue',('4.3','.14','.35','.02')),('U',('4.6','.40','.60','.03'))])
def test_independent_decimal_end_formula(family,coeff):
    d,s=ready(family=family);b=evaluate(d,s)
    with localcontext() as ctx:
        ctx.prec=60;D=Decimal;a,ar,ac,ah=map(D,coeff)
        oracle=a*D(2)**2*D(250)*(1-ar*(D(2)/D(2)).sqrt())*(1+ac*(D(40)/D(2)).sqrt())*(1-ah*(D(92)/D(2)).sqrt())/D('1.35')
        assert b['FRd_N']==pytest.approx(float(oracle),rel=2e-15)
        assert b['index']==pytest.approx(float(D(1500)/oracle),rel=2e-15)


@pytest.mark.parametrize('force,parallel,status',[(0.,0.,'not_applicable'),(-1.,0.,'not_evaluated'),(1.,1e-300,'not_evaluated'),(None,0.,'not_evaluated'),(1.,None,'not_evaluated')])
def test_force_signs_and_missing(force,parallel,status):
    d,s=ready();d.update(P_uls=force,P_parallel_uls=parallel)
    b=evaluate(d,s);assert b['status']==status and 'index' not in b


@pytest.mark.parametrize('missing',list(DECLARATIONS)+['origin','c_mm','basis'])
def test_missing_explicit_information(missing):
    d,s=ready()
    if missing in DECLARATIONS:d[FIELD]['declarations'][missing]=False
    else:d[FIELD][missing]='' if missing=='origin' else None
    assert evaluate(d,s)['status']=='not_evaluated'


def test_v1_stays_pending_and_never_migrates():
    d,s=ready();d[FIELD]['schema']=SCHEMA;before=copy.deepcopy(d)
    assert evaluate(d,s)['status']=='not_evaluated';assert d==before
    assert configuration(d)['schema']==SCHEMA
    assert blank_choice()['schema']==SCHEMA and not blank_choice()['enabled']


@pytest.mark.parametrize('schema',[SCHEMA,SCHEMA_V2])
def test_no_external_mechanics_change(schema):
    d,s=ready();d[FIELD]['schema']=schema
    legacy=copy.deepcopy(d);legacy.pop(FIELD)
    assert mechanics(calculate(d))==mechanics(calculate(legacy))


@pytest.mark.parametrize('key,value',[('x_uls',21.),('L_mm',4500.)])
def test_changed_position_or_span_requires_reconfirmation(key,value):
    d,s=ready();old=copy.deepcopy(d[FIELD]);d[key]=value
    assert evaluate(d,s)['status']=='not_evaluated' and d[FIELD]==old


@pytest.mark.parametrize('mutation',['location','negative_edge','radius','missing_digest','force','schema'])
def test_saved_corruption_rehashed_stays_pending(mutation):
    d,s=ready();r=calculate(d);b=r['NBR_branches']['point'];assert saved_records(r)[0]['status']=='computed'
    if mutation=='location':b['domain']['table_location']='internal'
    elif mutation=='negative_edge':b['domain']['contact_edges_mm'][0]=-1.
    elif mutation=='radius':b['domain']['ri_mm']=100.
    elif mutation=='force':b['force_N']+=1
    elif mutation=='schema':b['contact_contract']['schema']='future'
    if mutation=='missing_digest':b.pop('evidence_sha256')
    else:b['evidence_sha256']=_saved_digest(b)
    assert saved_records(r)[0]['status']=='pending'


def test_word_saved_end_has_no_solver(monkeypatch):
    import tercas.point_contact as contact
    from tercas.report import word
    d,s=ready();r=calculate(d);before=copy.deepcopy(r)
    def forbidden(*a,**kw):raise AssertionError('No solver in history')
    monkeypatch.setattr(contact,'evaluate',forbidden);monkeypatch.setattr(contact,'configuration',forbidden)
    text='\n'.join(p.text for p in Document(BytesIO(word(r))).paragraphs)
    assert 'Domínio v2' in text and 'extremidade' in text and str(r['NBR_branches']['point']['FRd_N']) in text
    assert r==before


def test_batch_support_limit_is_literal_and_center_unchanged():
    from tercas.batch import calculate_batch
    d,s=ready();d.update(load_mode='area',selected_types=['ELU normal']);d[FIELD]['basis']=reference_basis(d)
    old=copy.deepcopy(d);old[FIELD]['schema']=SCHEMA
    a=calculate_batch(old);b=calculate_batch(d)
    for ca,cb in zip(a['cases'],b['cases']):
        assert ca['combination']==cb['combination'] and ca['rows']==cb['rows']
        ea=copy.deepcopy(ca['evidence']);eb=copy.deepcopy(cb['evidence'])
        pa=ea['NBR_branches'].pop('point');pb=eb['NBR_branches'].pop('point')
        assert ea==eb
        if ca['combination'].get('point_position')=='support_limit':assert pa==pb and pb['status']=='not_applicable' and pb['scope']=='mathematical_limit'
        elif pa.get('status')=='computed':assert pa['FRd_N']==pb['FRd_N'] and pa['force_N']==pb['force_N']


def test_extreme_finite_inputs_return_serializable_pending():
    import json
    d,s=ready();d.update(L_mm=1.7e308,x_uls=1.6e308)
    d[FIELD].update(c_mm=1.7e308,basis=reference_basis(d))
    b=evaluate(d,s)
    assert b['status']=='not_evaluated' and 'domain' not in b and 'index' not in b
    json.dumps(b,allow_nan=False)


def test_fractional_right_contact_uses_same_saved_edges():
    d,s=ready();d['x_uls']=d['L_mm']-20.123456789
    d[FIELD].update(c_mm=40.01234567,basis=reference_basis(d))
    r=calculate(d);b=r['NBR_branches']['point']
    assert b['domain']['end_distance_mm']==min(b['patch_mm'][0],d['L_mm']-b['patch_mm'][1])
    assert saved_records(r)[0]['status']=='computed'


@pytest.mark.parametrize('flag',['physical_conditions_verified','connection_design_checked'])
def test_saved_v2_never_claims_physical_or_connection_verification(flag):
    d,s=ready();r=calculate(d);raw=r['NBR_branches']['point']
    raw[flag]=True;raw['evidence_sha256']=_saved_digest(raw)
    assert saved_records(r)[0]['status']=='pending'
