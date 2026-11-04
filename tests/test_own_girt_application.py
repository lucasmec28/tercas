"""Explicit own-Ue girt contract; no redistribution or physical/global release."""
import copy,json,math
from io import BytesIO
import pytest
from docx import Document
from tercas import ue_reference as ue,ue_family_reference as family
from tercas.ue_member_application import apply,FIELD as APPLICATION_FIELD,token
from tercas.biaxial_component import activate,FIELD,GIRT_SCHEMA,GIRT_ROW,preserved_snapshot,presentation_rows,digest
from tercas.application import calculate,rows
from tercas.batch import calculate_batch,area_bundle
from tercas.study_completion import complete_result
from tercas.report import word,batch_word


def roof(t=1.5,L=4000.,angle=5.):
    return ue.load_reference(angle=angle,L_mm=L) if t==1.2 else family.load_reference(t,L,angle)


def module(t):return ue if t==1.2 else family


def girt(t=1.5,L=4000.):return apply(roof(t,L),'wall_girt')


def direct(t=1.5,L=4000.):
    d=girt(t,L);d.update(load_mode='direct',q_sls=.1,q_parallel_sls=.03,P_sls=-100.,P_parallel_sls=-15.,x_sls=1092.5)
    d['wall_els'].update(normal_reference_mm=3500.,normal_denominator=140.,origin='QA independente, 3500/140')
    return d


def doc_text(blob):
    d=Document(BytesIO(blob));return '\n'.join([p.text for p in d.paragraphs]+[c.text for t in d.tables for r in t.rows for c in r.cells])


@pytest.mark.parametrize('t',[1.2,*family.THICKNESSES])
def test_explicit_application_and_geometry_preserve_actions_and_criteria(t):
    d=roof(t);d.update(q_sls=.123,q_parallel_sls=-.044,P_sls=137.,P_parallel_sls=-17.,x_sls=901.)
    base=copy.deepcopy(d);w=apply(d,'wall_girt');assert d==base
    assert module(t).assess(w)['calculable'] and w[APPLICATION_FIELD]==token('wall_girt')
    assert w['properties']==d['properties'] and w['weak_axis']==d['weak_axis']
    for k in module(t).EDITABLE:assert w.get(k)==d.get(k)
    w['wall_els'].update(normal_reference_mm=3500.,normal_denominator=140.,vertical_reference_mm=1234.)
    changed=module(t).apply_span(w,4750.)
    assert changed['wall_els']==w['wall_els'] and changed['member_application']=='wall_girt'
    assert changed[APPLICATION_FIELD]==w[APPLICATION_FIELD]
    assert changed['x_sls']==901. and changed['P_parallel_sls']==-17.
    assert module(t).assess(changed)['calculable']
    if t!=1.2:
        other=family.apply_geometry(changed,2.65,4500.)
        assert other['member_application']=='wall_girt' and other['wall_els']==w['wall_els']
        assert other['x_sls']==901. and family.assess(other)['calculable']
    back=apply(w,'purlin')
    assert back['wall_els']==w['wall_els'] and back['properties']==d['properties']
    assert module(t).assess(back)['calculable']
    assert apply(back,'wall_girt')==w


@pytest.mark.parametrize('kind',['label_only','bad_token','numeric_false','three_d','spring'])
def test_unrequested_application_or_other_model_is_refused(kind):
    d=roof()
    if kind=='label_only':d['member_application']='wall_girt'
    else:
        d=girt()
        if kind=='bad_token':d[APPLICATION_FIELD]['member_application']='purlin'
        elif kind=='numeric_false':d[APPLICATION_FIELD]['three_girt_redistribution']=0
        elif kind=='three_d':d['three_girt_model']={'enabled':True}
        else:d['wall_tie_study']={'enabled':True,'springs':[],'anchorage_confirmed':True,'origin':'test'}
    before=copy.deepcopy(d);assert not family.assess(d)['calculable']
    with pytest.raises(ValueError):calculate(d)
    assert d==before


@pytest.mark.parametrize('t',[1.2,*family.THICKNESSES])
def test_wall_area_axes_seven_ELS_and_no_automatic_roof_actions(t):
    d=girt(t);d['area_inputs']['permanent_kgf_m2']=12.
    bundle=area_bundle(d);same=copy.deepcopy(d)
    same['inclination']['value']=-23.;same['area_inputs']['live_kgf_m2']=913.
    other=area_bundle(same)
    assert bundle['case_vectors_N_mm']==other['case_vectors_N_mm']
    assert [(x['id'],x['q_vector'],x['P_vector']) for x in bundle['combinations']]==[(x['id'],x['q_vector'],x['P_vector']) for x in other['combinations']]
    g=9.80665/1000.;v=bundle['case_vectors_N_mm']
    assert v['PP']=={'normal':0.,'parallel':d['properties']['mass_kg_m']*g}
    assert v['CP']=={'normal':0.,'parallel':12.*d['area_inputs']['spacing_m']*g}
    r=complete_result(calculate_batch(activate(d)));ev=preserved_snapshot(r)
    assert len(r['cases'])==19 and ev['total_cases']==7 and ev['schema']==GIRT_SCHEMA
    for c in r['cases']:
        assert 'SC' not in c['combination']['coefficients'] and not any(c['combination']['P_vector'].values())
        if c['combination']['limit_state']=='ELS':
            rec=ev['records'][c['combination']['id']]
            assert rec['case']['q_N_mm']==[c['combination']['q_vector'][x] for x in ('normal','parallel')]
            if rec['qualified_gross_flexural_component']:
                raw=c['evidence']['ELS'];assert raw['index']==abs(raw['deflection_mm'])/(d['L_mm']/120.)
    assert not r['global_verification']['whole_member_approved'] and not r['global_verification']['combined_ELS_approved']
    shown=presentation_rows(r,r['summary'])
    assert any(x['Verificação']==GIRT_ROW for x in shown)
    assert not any('Flecha vertical' in x['Verificação'] for x in shown)
    json.dumps(r,allow_nan=False)


@pytest.mark.parametrize('t',[1.2,1.5,3.35])
def test_direct_uses_wall_limit_not_stored_roof_or_vertical_limit(t):
    d=direct(t);r=complete_result(calculate(activate(d)));ev=preserved_snapshot(r)
    assert ev['records']['DIRECT_ELS']['declared_limit']['value_mm']==25.
    assert r['ELS']['limit_mm']==25. and r['ELS']['index']==abs(r['ELS']['deflection_mm'])/25.
    assert r['input_data']['ELS_limit_mm']!=25. and r['ELS']['component_schema']==GIRT_SCHEMA
    changed=copy.deepcopy(d);changed['wall_els'].update(vertical_reference_mm=123.,vertical_denominator=2000.)
    other=calculate(activate(changed))
    assert other['ELS']==r['ELS']
    assert not any('Flecha vertical' in row['Verificação'] for row in rows(r))
    txt=doc_text(word(r));assert 'Componente horizontal da flexão biaxial' in txt
    assert 'horizontal normal ao fechamento' in txt
    assert 'Flecha vertical — diagnóstico elástico do eixo fraco' not in txt


def test_torsion_choice_is_preserved_inactive_before_geometry_or_solver(monkeypatch):
    from tercas import torsion_study
    d=roof();d['torsion_model']=torsion_study.blank_choice();d=apply(d,'wall_girt');d=activate(d)
    original=copy.deepcopy(d['torsion_model'])
    def forbidden(*a,**k):pytest.fail('Purlin torsion must not run as isolated girt')
    monkeypatch.setattr(torsion_study,'section_for',forbidden)
    r=complete_result(calculate_batch(d))
    assert r['input_data']['torsion_model']==original
    assert r['torsion_evidence']['computed_cases']==0 and r['torsion_evidence']['status']=='pending_model_data'
    assert 'travessa isolada' in r['torsion_evidence']['reason']


def test_new_contract_history_reads_without_live_sources_and_wrong_axis_refused(monkeypatch):
    from tercas.biaxial_gross import gross_mle,tensor_beam
    d=activate(direct());r=complete_result(calculate(d));before=copy.deepcopy(r)
    def forbidden(*a,**k):pytest.fail('No mechanical/source computation on read')
    monkeypatch.setattr(gross_mle,'assess_case',forbidden);monkeypatch.setattr(gross_mle,'load_geometry',forbidden)
    monkeypatch.setattr(tensor_beam,'solve_response',forbidden)
    assert preserved_snapshot(r);assert GIRT_ROW in doc_text(word(r));assert r==before
    r[FIELD]['records']['DIRECT_ELS']['member_application']='purlin'
    r[FIELD]['snapshot_sha256']=digest({k:v for k,v in r[FIELD].items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):preserved_snapshot(r)
    assert next(x for x in rows(r) if x['Verificação']==GIRT_ROW)['Índice'] is None
    assert 'Registro da componente biaxial inválido' in doc_text(word(r))


def test_invalid_wall_limit_stays_editable_without_calculation():
    d=girt();d['wall_els']['normal_denominator']=None
    state=family.assess(d);assert state['active'] and not state['calculable']
    assert d['wall_els']['normal_denominator'] is None
    with pytest.raises(ValueError):calculate(activate(d))


@pytest.mark.parametrize('field',['tie_or_cladding_stiffness_credit','three_girt_redistribution'])
def test_saved_application_contract_requires_strict_boolean(field):
    r=complete_result(calculate(activate(direct())))
    r[FIELD]['application_contract'][field]=0
    r[FIELD]['snapshot_sha256']=digest({k:v for k,v in r[FIELD].items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError,match='Contrato isolado'):preserved_snapshot(r)
    assert 'Registro da componente biaxial inválido' in doc_text(word(r))

@pytest.fixture(scope='module')
def saved_context_pair():
    w=activate(direct())
    return {'wall_girt':complete_result(calculate(w)),
            'purlin':complete_result(calculate(apply(w,'purlin')))}

@pytest.mark.parametrize('kind',['wall_girt','purlin'])
@pytest.mark.parametrize('mutation',['source_kind','source_model','source_token_kind','source_token_zero','input_token_zero','input_token_kind'])
def test_saved_context_links_are_bound_to_application(saved_context_pair,kind,mutation):
    from tercas.application import fingerprint
    r=copy.deepcopy(saved_context_pair[kind]);s=r['ue_family_reference_evidence']
    other='purlin' if kind=='wall_girt' else 'wall_girt'
    if mutation=='source_kind':s['member_application']=other
    elif mutation=='source_model':s['model']['member_application']=other
    elif mutation=='source_token_kind':s['application_contract']['member_application']=other
    elif mutation=='source_token_zero':s['application_contract']['three_girt_redistribution']=0
    else:
        cfg=r['input_data'][APPLICATION_FIELD]
        if mutation=='input_token_zero':cfg['three_girt_redistribution']=0
        else:cfg['member_application']=other
        fp=fingerprint(r['input_data']);r['input_fingerprint']=fp;s['input_sha256']=fp
        r[FIELD]['source_input_fingerprint']=fp
        for item in r[FIELD]['records'].values():item['source_input_fingerprint']=fp
        r[FIELD]['snapshot_sha256']=digest({k:v for k,v in r[FIELD].items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):preserved_snapshot(r)
    assert 'Registro da componente biaxial inválido' in doc_text(word(r))

@pytest.mark.parametrize('mutation',['source_limit','source_convention','purlin_retains_girt'])
def test_saved_source_criterion_and_axes_cannot_drift(saved_context_pair,mutation):
    kind='purlin' if mutation=='purlin_retains_girt' else 'wall_girt'
    r=copy.deepcopy(saved_context_pair[kind]);s=r['ue_family_reference_evidence']
    if mutation=='source_limit':s['normal_component_limit']['value']=1.
    elif mutation=='source_convention':s['application_convention']='Normal vertical'
    else:s['normal_component_limit']={'value':1.,'origin':'foreign context'}
    with pytest.raises(ValueError):preserved_snapshot(r)


@pytest.mark.parametrize('remaining',['source_kind','source_model','source_limit','source_convention','input_wall_els'])
def test_removed_markers_do_not_reclassify_new_context_as_legacy(saved_context_pair,remaining):
    from tercas.application import fingerprint
    r=copy.deepcopy(saved_context_pair['purlin']);s=r['ue_family_reference_evidence']
    r['input_data'].pop(APPLICATION_FIELD)
    for k in ('application_contract','member_application','normal_component_limit','application_convention'):s.pop(k,None)
    s['model'].pop('member_application',None)
    if remaining!='input_wall_els':r['input_data'].pop('wall_els')
    if remaining=='source_kind':s['member_application']='wall_girt'
    elif remaining=='source_model':s['model']['member_application']='wall_girt'
    elif remaining=='source_limit':s['normal_component_limit']={'value':1.,'origin':'foreign'}
    elif remaining=='source_convention':s['application_convention']='foreign'
    fp=fingerprint(r['input_data']);r['input_fingerprint']=fp;s['input_sha256']=fp;r[FIELD]['source_input_fingerprint']=fp
    for item in r[FIELD]['records'].values():item['source_input_fingerprint']=fp
    r[FIELD]['snapshot_sha256']=digest({k:v for k,v in r[FIELD].items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):preserved_snapshot(r)
    assert 'Registro da componente biaxial inválido' in doc_text(word(r))


@pytest.mark.parametrize('key',['normal_denominator','normal_reference_mm','vertical_denominator','vertical_reference_mm'])
@pytest.mark.parametrize('value',[float('inf'),float('-inf'),float('nan'),10**400,2**53+1])
def test_nonrepresentable_wall_editor_value_is_inspection_only(key,value):
    d=girt();d['wall_els'][key]=value
    state=family.assess(d)
    assert not state['active'] and not state['calculable']
    assert any(key in text for text in state['reasons'])
    with pytest.raises(ValueError):calculate(activate(d))
