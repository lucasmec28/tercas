"""Focused own Ue contract, numeric scope, ELS, source and persistence tests."""
import copy
import hashlib
import json
import math
from fractions import Fraction
from io import BytesIO
import pytest
from docx import Document
from tercas import ue_reference as ue
from tercas.application import calculate, defaults, rows
from tercas.batch import calculate_batch
from tercas.catalog_scan import scan_catalog, inputs_for_section


def mutations():
    base=ue.load_reference()
    for k in base['properties']:
        yield 'property '+k,lambda d,k=k:d['properties'].__setitem__(k,math.nextafter(d['properties'][k],math.inf))
    for k in ('property_origin','critical_origin','support_origin','patch_origin','steel_name','synthetic','route_domain','left_web','right_web','ELS_limit_mm','ELS_origin','patch_mm','Ml_Nmm','Mdist_Nmm'):
        yield k,lambda d,k=k:d.__setitem__(k,'changed')
    for side in ('positive','negative'):
        for k,v in base['weak_axis'][side].items():
            yield side+' '+k,lambda d,k=k,side=side,v=v:d['weak_axis'][side].__setitem__(k,not v if isinstance(v,bool) else v+1 if isinstance(v,(int,float)) else 'changed')
    for k in base['segments'][0]:yield 'segment '+k,lambda d,k=k:d['segments'][0].__setitem__(k,'changed')
    for k in base['ue_model']:yield 'model '+k,lambda d,k=k:d['ue_model'].__setitem__(k,'changed')
    for k in base['ue_source_documents']:yield 'source '+k,lambda d,k=k:d['ue_source_documents'].__setitem__(k,'changed')
    for k in base['active_numeric_reference']:yield 'numeric '+k,lambda d,k=k:d['active_numeric_reference'].__setitem__(k,'changed')
    for k,v in [('homogeneous_reference',{}),('homogeneous_lengths',{}),('weak_catalog',{}),('three_girt_model',{'enabled':False}),('wall_tie_study',{}),('member_application','wall_girt'),('N_N',1),('torque_Nmm',1),('model_domain','other'),('catalog_index',0),('L_mm',4500.)]:
        yield k,lambda d,k=k,v=v:d.__setitem__(k,v)
    yield 'bool t',lambda d:d['properties'].__setitem__('t',True)
    yield 'bool K',lambda d:d['ue_model'].__setitem__('Kx',True)
    yield 'bool Cs',lambda d:d['weak_axis']['positive'].__setitem__('Cs',True)
    yield 'missing weak',lambda d:d.pop('weak_axis')
    yield 'missing sources',lambda d:d.pop('ue_source_documents')
    yield 'parallel torque',lambda d:d['area_inputs'].__setitem__('torque',1)
    yield 'angle basis',lambda d:d['inclination'].__setitem__('live_basis','roof')

MUTATIONS=list(mutations())
@pytest.mark.parametrize('name,mutate',MUTATIONS,ids=[x[0] for x in MUTATIONS])
def test_protected_mutation_rejected_without_repair(name,mutate):
    d=ue.load_reference();mutate(d);before=copy.deepcopy(d)
    assert not ue.assess(d)['active'],name
    for call in (ue.calculate_reference,calculate,calculate_batch):
        with pytest.raises((ValueError,OSError)):call(d)
    assert d==before

@pytest.mark.parametrize('length',[True,False,None,'4000',math.inf,math.nan,2999.,6001.,math.nextafter(3000.,-math.inf),math.nextafter(6000.,math.inf),Fraction(3000)-Fraction(1,10**30),Fraction(6000)+Fraction(1,10**30)])
def test_length_is_strict_before_float_rounding(length):
    with pytest.raises(ValueError):ue.source(L_mm=length)
    with pytest.raises(ValueError):ue.apply_span(ue.load_reference(),length)

@pytest.mark.parametrize('length',[3000.,4000.,4750.,6000.,math.nextafter(3000.,math.inf),math.nextafter(6000.,-math.inf),4123.456])
def test_continuous_span_recomputes_all_derived_values(length):
    d=ue.apply_span(ue.load_reference(),length)
    assert ue.assess(d)['calculable']
    assert d['x_uls']==1500. and d['ELS_limit_mm']==length/180
    r=ue.reference(length);p=r['properties'];m=r['model']
    assert r['global_criticals']['Nex_N']==math.pi**2*m['E_MPa']*p['Ix_mm4']/length**2
    assert r['model']['stability_lengths']==dict(Lx_mm=length,Ly_mm=length,Lz_mm=length)
    assert d['weak_axis']['positive']['Nex_N']==r['global_criticals']['Nex_N']
    assert r['resistances_exterior_primary']['weak_web_compressed']['Mdist_Nmm'] is None
    assert d['weak_axis']['positive']['Mdist_Nmm']==850000.
    assert d['active_numeric_reference']['current_span_mm']==length


def test_sources_or_marker_never_suffice_and_roundtrip_preserves_inputs():
    d=ue.source();before=copy.deepcopy(d)
    assert ue.assess(d)['eligible'] and not ue.assess(d)['active']
    with pytest.raises(ValueError):calculate(d)
    a=ue.activate(d);assert d==before
    assert {k:v for k,v in a.items() if k!=ue.FIELD}==d
    assert ue.assess(json.loads(json.dumps(a)))['calculable']
    nominal=defaults(a['catalog_index']);nominal[ue.FIELD]=a[ue.FIELD]
    assert not ue.assess(nominal)['active']
    for call in (scan_catalog,inputs_for_section):
        with pytest.raises(ValueError):call(a,[] if call==scan_catalog else 0)

@pytest.mark.parametrize('filename',['sources.json','canonical.json','vector.json','length_decision.json','lips_decision.json','els_review.txt'])
def test_source_document_changes_deactivate_without_mutating_input(tmp_path,monkeypatch,filename):
    d=ue.load_reference();before=copy.deepcopy(d)
    import shutil
    shutil.copytree(ue.ROOT,tmp_path/'data')
    target=tmp_path/'data'/filename;target.write_bytes(target.read_bytes()+b' ')
    monkeypatch.setattr(ue,'ROOT',tmp_path/'data')
    assert not ue.assess(d)['active']
    with pytest.raises(ValueError):calculate(d)
    assert d==before


def test_scalar_reference_matches_all_twelve_reviewed_batches():
    summary=json.loads((ue.ROOT/'study_summary.json').read_text())
    for item in summary['batches']:
        r=ue.reference(item['L_mm']);caps=r['resistances_exterior_primary']
        assert r['global_criticals']==item['global_criticals']
        assert caps['strong_positive']['MRd_Nmm']==pytest.approx(item['strong_MRd_Nmm'],rel=1e-14)
        assert caps['weak_web_compressed']['MRd_Nmm']==pytest.approx(item['weak_web_MRd_Nmm'],rel=1e-14)
        assert caps['weak_lips_compressed']['MRd_Nmm']==pytest.approx(item['weak_lips_MRd_Nmm'],rel=1e-14)


def direct(**kwargs):
    d=ue.load_reference();d.update(load_mode='direct',q_sls=.1,q_uls=.2,**kwargs);return d

@pytest.mark.parametrize('angle',[0.,5.,13.25,-20.])
def test_uniaxial_els_depends_on_actual_local_actions_not_angle(angle):
    d=direct();d['inclination']['value']=angle
    r=calculate(d)
    assert r['ELS'].get('index') is not None
    assert r['ELS']['ue_ELS_scope']['strong_uniaxial_actions'] is True
    d['q_parallel_sls']=.0000001
    r=calculate(d)
    assert 'index' not in r['ELS'] and r['ELS']['diagnostic_only']
    assert r['ELS']['ue_ELS_scope']['strong_uniaxial_actions'] is False
    assert next(x for x in rows(r) if x['Verificação']=='Flecha — flexão')['Índice'] is None
    assert not r['whole_member_approved']


def test_parallel_point_alone_blocks_biaxial_els_and_sign_guards_survive():
    d=direct(P_parallel_sls=1.);r=calculate(d);assert 'index' not in r['ELS']
    d=direct();d.update(P_sls=-100.);r=calculate(d)
    assert r['ELS']['ue_ELS_scope']['strong_uniaxial_actions']
    assert r['ELS'].get('index') is None

@pytest.mark.parametrize('angle',[0.,5.,-5.])
def test_batch_source_floor_els_and_word(angle):
    d=ue.load_reference(angle=angle);before=copy.deepcopy(d);r=calculate_batch(d)
    assert d==before and r['input_data']==d and len(r['cases'])==58
    assert r['ue_reference_evidence']['source_ELS_evidence_transferred'] is False
    for case in r['cases']:
        assert not any(row['Verificação'] in ('Flecha paralela à cobertura','Cortante paralelo à cobertura') for row in case['rows'])
        if case['combination']['limit_state']!='ELS':continue
        c=case['combination'];uniaxial=c['q_vector']['parallel']==c['P_vector']['parallel']==0.
        assert case['evidence']['ELS']['ue_ELS_scope']['strong_uniaxial_actions']==uniaxial
        if not uniaxial:assert all(row['Índice'] is None for row in case['rows'])
    from tercas.report import batch_word
    doc=Document(BytesIO(batch_word(r)));text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Referência própria Ue100' in text and 'piso elástico conservador' in text
    assert 'Mdist identificado: não identificado' in text and 'Lx=Ly=Lz=L' in text
    assert 'Ml,y — referência oficial adotada: Pierin2013' not in text
    assert '900000' not in text and 'não é transferida' in text


def test_direct_word_uses_recorded_evidence_not_live_files(monkeypatch):
    r=calculate(direct())
    from tercas.report import word
    monkeypatch.setattr(ue,'gate',lambda:(_ for _ in ()).throw(ValueError('no live files')))
    text='\n'.join(p.text for p in Document(BytesIO(word(r))).paragraphs)
    assert 'Referência própria Ue100' in text and r['ue_reference_evidence']['input_sha256'] in text
