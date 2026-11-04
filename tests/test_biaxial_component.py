"""Own-Ue sufficient gross branch: fresh response, no physical/global ELS release."""
import copy,json,math
from io import BytesIO
import pytest
from docx import Document
from tercas import ue_reference as ue,ue_family_reference as family,deflection_scope
from tercas.application import calculate,rows,defaults
from tercas.batch import calculate_batch,case_inputs
from tercas.study_completion import complete_result
from tercas.biaxial_component import activate,FIELD,ROW,MODE,preserved_snapshot,presentation_rows
from tercas.report import word,batch_word


def own(t=1.5,L=4000.,angle=5.):
    return ue.load_reference(angle=angle,L_mm=L) if t==1.2 else family.load_reference(t,L,angle)


def direct(t=1.5,**kw):
    d=own(t);d.update(load_mode='direct',q_sls=.1,q_parallel_sls=.03,P_sls=100.,P_parallel_sls=-20.,x_sls=1700.)
    d.update(kw);return d


def text(binary):
    doc=Document(BytesIO(binary))
    return '\n'.join([p.text for p in doc.paragraphs]+[c.text for t in doc.tables for r in t.rows for c in r.cells])


@pytest.mark.parametrize('t',[1.2,*family.THICKNESSES])
def test_seven_own_sources_and_independent_new_response(t):
    d=activate(direct(t));before=copy.deepcopy(d);r=complete_result(calculate(d))
    assert d==before
    ev=preserved_snapshot(r);s=ev['records']['DIRECT_ELS']
    assert s['qualified_gross_flexural_component'] and r['ELS']['criterion_status']=='meets'
    assert s['screen']['sufficient_full_section']
    assert r['ELS']['index']==abs(r['ELS']['deflection_mm'])/d['ELS_limit_mm']
    assert s['case']['q_N_mm']==[d['q_sls'],d['q_parallel_sls']]
    assert s['case']['P_N']==[d['P_sls'],d['P_parallel_sls']]
    assert s['response']['source_tensor_mm4']['Ix']==s['screen']['computed_properties']['Ix_mm4']
    assert s['response']['source_tensor_mm4']['Ixy']==s['screen']['computed_properties']['Ixy_mm4']
    assert all(r['global_verification'][k] is False for k in ('whole_member_approved','combined_ELS_approved'))
    assert r['global_verification']['by_limit_state']['ELS']['status']!='aprovado'
    assert len([x for x in rows(r) if x['Verificação']==ROW])==1
    assert not any('Flecha paralela' in x['Verificação'] for x in rows(r))
    assert 'deflection_scope_evidence' not in r
    json.dumps(r,allow_nan=False)


def test_reversal_is_new_calculation_not_old_index_restoration():
    d=own(1.5,4750.,5.)
    d.update(load_mode='direct',q_sls=.1,q_parallel_sls=.03,P_sls=-500.,P_parallel_sls=-75.,x_sls=1092.5)
    old=calculate(d);new=calculate(activate(d))
    assert 'index' not in old['ELS'] and 'deflection_mm' not in old['ELS']
    assert new[FIELD]['records']['DIRECT_ELS']['previous_scalar_component']==old['ELS']
    assert new['ELS']['deflection_mm']==pytest.approx(-1.1141271565047324)
    assert new['ELS']['x_mm']==pytest.approx(1256.8254946364034)
    for key in ('NBR_branches','FLT_segments','section_checks'):
        assert new[key]==old[key]
    for state in ('ELU','ELS'):
        assert new['inclination_evidence'][state]['states']==old['inclination_evidence'][state]['states']


@pytest.mark.parametrize('t,angle,qualified',[(1.2,5.,17),(1.2,-5.,17),(1.5,5.,18),(3.35,-5.,18)])
def test_area_cases_summary_and_support_limit_preserved(t,angle,qualified):
    d=activate(own(t,angle=angle));r=complete_result(calculate_batch(d));s=r[FIELD]
    assert s['total_cases']==18 and s['qualified_cases']==qualified
    assert len(r['cases'])==58
    for entry in r['cases']:
        c=entry['combination']
        if c['limit_state']!='ELS':
            assert not any(row['Verificação']==ROW for row in entry['rows']);continue
        e=s['records'][c['id']];raw=entry['evidence']['ELS'];local=case_inputs(d,c)
        assert len(entry['rows'])==1 and entry['rows'][0]['Verificação']==ROW
        assert e['declared_limit']['value_mm']==local['ELS_limit_mm']
        assert e['declared_limit']['origin']==local['ELS_origin']
        assert e['case']['q_N_mm']==[c['q_vector'][a] for a in ('normal','parallel')]
        if c.get('point_position')=='support_limit':
            p=[c['P_vector'][a] for a in ('normal','parallel')]
            assert e['case']['P_N']==p and any(p)
            response=e['response'];transfer=response['support_transfer_limit']
            assert transfer['original_P_N']==p and transfer['finite_point_on_support'] is False
            for i,a in enumerate(('normal','parallel')):
                assert response['reactions_N']['left'][i]==pytest.approx(c['q_vector'][a]*d['L_mm']/2+p[i])
            assert entry['evidence']['inclination']['P_vector']==c['P_vector']
        if not e['qualified_gross_flexural_component']:assert 'index' not in raw
    summary=next(x for x in r['summary'] if x['Verificação']==ROW)
    assert summary['Casos avaliados']==qualified and summary['Casos pendentes']==18-qualified
    assert r['global_verification']['by_limit_state']['ELS']['status']!='aprovado'


def test_strong_only_inconclusive_never_uses_scalar_ief_fallback():
    d=direct(1.2,q_sls=3.,q_parallel_sls=0.,P_sls=0.,P_parallel_sls=0.)
    old=calculate(d);r=complete_result(calculate(activate(d)))
    assert 'index' in old['ELS']
    assert not r[FIELD]['records']['DIRECT_ELS']['qualified_gross_flexural_component']
    assert 'index' not in r['ELS'] and 'deflection_mm' not in r['ELS']
    assert r['global_verification']['by_limit_state']['ELS']['status']!='aprovado'


@pytest.mark.parametrize('kind',['resolution','exception'])
def test_tensor_numeric_failure_is_pending_not_scalar_index(monkeypatch,kind):
    from tercas.biaxial_gross import tensor_beam
    original=tensor_beam.solve_response
    def fail(*a,**k):
        if kind=='exception':raise ArithmeticError('Injected numeric failure')
        v=original(*a,**k);v['status']='numeric_output_resolution_limited';v['numeric_output_resolution_limited']=True;return v
    monkeypatch.setattr(tensor_beam,'solve_response',fail)
    r=calculate(activate(direct(q_parallel_sls=0.,P_parallel_sls=0.)))
    assert 'index' not in r['ELS'] and not r[FIELD]['records']['DIRECT_ELS']['qualified_gross_flexural_component']
    json.dumps(r,allow_nan=False)


@pytest.mark.parametrize('mode',[None,'local_uniaxial_component_v1'])
def test_no_new_mode_does_not_call_screen_or_solver(monkeypatch,mode):
    from tercas.biaxial_gross import gross_mle,tensor_beam
    def forbidden(*a,**k):raise AssertionError('No new computation without explicit mode')
    monkeypatch.setattr(gross_mle,'assess_case',forbidden);monkeypatch.setattr(tensor_beam,'solve_response',forbidden)
    d=direct()
    if mode:d['deflection_model']=mode
    r=calculate(d)
    assert FIELD not in r
    assert (r['ELS'].get('index') is not None)==bool(mode)


def test_generic_girt_3d_unknown_and_incompatible_sources_refused():
    for d in (defaults(),dict(own(),member_application='wall_girt'),
              dict(own(),three_girt_model={'enabled':True})):
        d['deflection_model']=MODE
        with pytest.raises(ValueError):calculate(d)
    for update in ({'deflection_model':'unknown'},{'L_mm':6001.}):
        d=activate(direct());d.update(update)
        with pytest.raises(ValueError):calculate(d)
    d=activate(direct());d['properties']['Ix_cm4']*=1.01
    with pytest.raises(ValueError):calculate(d)


def test_fresh_source_gate_rejects_changed_geometry_pin(monkeypatch):
    import tercas.biaxial_component as component
    monkeypatch.setitem(component.PINS,1.5,'0'*64)
    with pytest.raises(ValueError,match='SHA256'):calculate(activate(direct()))


def test_history_and_export_read_without_live_solver_or_sources(monkeypatch):
    from tercas.biaxial_gross import gross_mle,tensor_beam
    r=complete_result(calculate(activate(direct())));before=copy.deepcopy(r)
    def forbidden(*a,**k):raise AssertionError('Reading is not recalculation')
    monkeypatch.setattr(gross_mle,'assess_case',forbidden);monkeypatch.setattr(gross_mle,'load_geometry',forbidden)
    monkeypatch.setattr(tensor_beam,'solve_response',forbidden);monkeypatch.setattr(family,'gate',forbidden)
    assert preserved_snapshot(r) and rows(r)
    content=text(word(r));assert ROW in content and 'não é uma expressão normativa geral' in content
    assert r==before


@pytest.mark.parametrize('alteration',['null','empty','raw','proof','input','count','row','absent','summary'])
def test_corrupt_saved_record_visible_without_solver(alteration,monkeypatch):
    from tercas.biaxial_gross import tensor_beam
    r=complete_result(calculate_batch(activate(own())))
    if alteration=='absent':r.pop(FIELD)
    elif alteration=='summary':next(x for x in r['summary'] if x['Verificação']==ROW)['Índice']=0.
    elif alteration=='null':r[FIELD]=None
    elif alteration=='empty':r[FIELD]={}
    elif alteration=='raw':next(c for c in r['cases'] if c['combination']['limit_state']=='ELS')['evidence']['ELS']['index']=0.
    elif alteration=='proof':next(iter(r[FIELD]['records'].values()))['qualified_gross_flexural_component']=False
    elif alteration=='input':r['input_data']['project']='Changed'
    elif alteration=='count':r[FIELD]['qualified_cases']=0
    else:next(c for c in r['cases'] if c['combination']['limit_state']=='ELS')['rows'][0]['Índice']=0.
    before=copy.deepcopy(r)
    monkeypatch.setattr(tensor_beam,'solve_response',lambda *a,**k:pytest.fail('No solver on read'))
    with pytest.raises((ValueError,KeyError,TypeError)):preserved_snapshot(r)
    shown=presentation_rows(r,r['summary']);normal=next(x for x in shown if x['Verificação']==ROW)
    assert normal['Índice'] is None and 'inválido' in normal['Situação']
    content=text(batch_word(r));assert 'Registro da componente biaxial inválido' in content
    assert r==before

@pytest.mark.parametrize('t',[1.2,1.5,3.35])
def test_explicit_geometry_and_span_changes_preserve_choice_without_weakening_source(t):
    d=activate(direct(t));before=copy.deepcopy(d)
    if t==1.2:
        changed=ue.apply_span(d,4500.);state=ue.assess(changed)
    else:
        changed=family.apply_geometry(d,2.65,4500.);state=family.assess(changed)
    assert d==before and state['calculable'] and changed['deflection_model']==MODE
    assert changed['q_parallel_sls']==d['q_parallel_sls'] and changed['P_sls']==d['P_sls']
    assert changed['x_sls']==d['x_sls'] and changed['L_mm']==4500.
    assert FIELD in calculate(changed)

@pytest.mark.parametrize('path',[('q_N_mm',),('L_mm',),('point_position',),('source_E_MPa',),('source_tensor_mm4','Ix'),('numeric_input_fingerprint',)])
def test_rehashed_response_still_cannot_change_its_case_or_tensor(path):
    from tercas.biaxial_component import digest
    r=calculate(activate(direct()));ev=r[FIELD];response=ev['records']['DIRECT_ELS']['response'];obj=response
    for k in path[:-1]:obj=obj[k]
    k=path[-1]
    obj[k]=([.9,.8] if k=='q_N_mm' else 'support_limit' if k=='point_position' else '0'*64 if k=='numeric_input_fingerprint' else obj[k]*1.01)
    ev['snapshot_sha256']=digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):preserved_snapshot(r)
