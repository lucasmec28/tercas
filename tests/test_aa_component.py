"""AA integration: honest bounds, exact requests, fresh-only, no global release."""
import copy,json,math
from io import BytesIO
from fractions import Fraction
import pytest
from docx import Document
from tercas import ue_reference as ue,ue_family_reference as family
from tercas.aa_component import (MODE,LOCAL_MODE,POSITIVE_MODE,MODES,FIELD,ROW,GIRT_ROW,ROWS,
    activate,preserved_snapshot,presentation_rows,digest,_bundle)
from tercas.application import calculate,rows,defaults
from tercas.batch import calculate_batch,case_inputs
from tercas.study_completion import complete_result
from tercas.report import word,batch_word


def own(t=1.5,L=4000.):
    return ue.load_reference(angle=5.,L_mm=L) if t==1.2 else family.load_reference(t,L,5.)


def direct(t=1.5,L=4000.,**kw):
    d=own(t,L);d.update(load_mode='direct',q_sls=.1,q_parallel_sls=.03,P_sls=100.,P_parallel_sls=-20.,x_sls=1700.)
    d.update(kw);return d


def text(binary):
    d=Document(BytesIO(binary));return '\n'.join([p.text for p in d.paragraphs]+[c.text for t in d.tables for r in t.rows for c in r.cells])


@pytest.mark.parametrize('t',[1.2,*family.THICKNESSES])
def test_seven_sources_upper_bound_and_concurrent_axes(t):
    from tercas.biaxial_component import activate as gross
    d=direct(t);before=copy.deepcopy(d);r=complete_result(calculate(activate(d)))
    ev=preserved_snapshot(r);record=ev['records']['DIRECT_ELS'];raw=r['ELS']
    g=calculate(gross(d));exact=abs(g['ELS']['deflection_mm'])
    assert record['qualified_bound_component'] and record['response']['route']=='gross_full_section'
    assert raw['upper_bound_mm']>=exact*(1-1e-14)
    assert Fraction(raw['index'])>=Fraction(raw['upper_bound_mm'])/Fraction(d['ELS_limit_mm'])
    assert Fraction(math.nextafter(raw['index'],-math.inf))<Fraction(raw['upper_bound_mm'])/Fraction(d['ELS_limit_mm'])
    assert raw['index_kind']=='conservative_upper_bound_over_declared_limit'
    assert 'deflection_mm' not in raw and 'x_mm' not in raw
    assert record['request']['q_N_mm']==[d['q_sls'],d['q_parallel_sls']]
    assert record['request']['P_N']==[d['P_sls'],d['P_parallel_sls']]
    assert record['request']['a_mm']==d['x_sls']
    assert record['previous_scalar_component']==calculate(d)['ELS']
    assert len([x for x in rows(r) if x['Verificação'] in ROWS])==1
    assert all(r['global_verification'][k] is False for k in ('whole_member_approved','combined_ELS_approved'))
    assert r['global_verification']['by_limit_state']['ELS']['status']!='aprovado'
    assert d==before;json.dumps(r,allow_nan=False)


@pytest.mark.parametrize('mode',MODES)
def test_methods_explicit_and_only_requested_method_called(mode,monkeypatch):
    import tercas.aa_component as aa
    b=_bundle();called=[]
    class Only:
        def verify(self):return b.verify()
        def family_assess(self,q):called.append(MODE);return b.family_assess(q)
        def local_partition_assess(self,q,refinement_budget):called.append(LOCAL_MODE);return b.local_partition_assess(q,refinement_budget)
        def positive_ratio_assess(self,q):called.append(POSITIVE_MODE);return b.positive_ratio_assess(q)
    monkeypatch.setattr(aa,'_bundle',Only)
    r=calculate(activate(direct(),mode))
    assert called==[mode] and r[FIELD]['choice']==mode and r['ELS']['criterion_status']=='meets'


def test_reduced_web_and_all_other_walls_stay_guarded():
    r=calculate(activate(direct(q_sls=0.,q_parallel_sls=.305,P_sls=0.,P_parallel_sls=0.,x_sls=2000.)))
    s=r[FIELD]['records']['DIRECT_ELS'];a=s['response']
    assert a['route']=='web_control_hull' and a['sufficient']
    assert a['hull_evidence']['nonweb_and_material_sufficient']
    assert r['ELS']['upper_bound_mm']==pytest.approx(.07506424394,abs=1e-10)
    assert a['displacement_component_bounds'][1]['absolute_max_upper_mm']==pytest.approx(43.83557373533,abs=1e-9)
    assert not any('paralela' in x['Verificação'].lower() for x in rows(r))


def test_local_partition_preserves_sign_reversal_and_original_span():
    d=direct(1.2,q_sls=0.,q_parallel_sls=.6,P_sls=0.,P_parallel_sls=-1200.,x_sls=2000.)
    old=calculate(activate(d));new=calculate(activate(d,LOCAL_MODE))
    assert old['ELS']['criterion_status']=='not_evaluated'
    a=new[FIELD]['records']['DIRECT_ELS']['response']
    assert a['route']=='finite_local_partition' and a['partition']['coverage_complete']
    assert len(a['partition']['certified_leaf_ids'])==6
    assert a['request']['L_mm']==4000. and a['request']['P_N']==[0.,-1200.]
    assert a['displacement_component_bounds'][0]['absolute_max_upper_mm']==pytest.approx(.0005621287530866161)
    assert not any(x['additional_support'] for x in a['partition']['interfaces'])


def test_positive_ratio_separate_and_improves_guard_not_physical_approval():
    d=direct(L=6000.,q_sls=0.,q_parallel_sls=.2024009036485318,P_sls=0.,P_parallel_sls=0.,x_sls=3000.)
    old=calculate(activate(d));r=complete_result(calculate(activate(d,POSITIVE_MODE)))
    assert old['ELS']['criterion_status']=='not_evaluated'
    assert r['ELS']['upper_bound_mm']==pytest.approx(.20330347585010872)
    assert r['ELS']['criterion_status']=='meets'
    assert r['global_verification']['by_limit_state']['ELS']['status']!='aprovado'


@pytest.mark.parametrize('limit,expected',[('.5','inconclusive_bound_above_limit'),('equal','meets'),('below','inconclusive_bound_above_limit')])
def test_criterion_boundary_no_failure_from_upper_bound(limit,expected):
    from tercas.ue_member_application import apply
    d=apply(direct(),'wall_girt');base=calculate(activate(d));u=base['ELS']['upper_bound_mm']
    value=u if limit=='equal' else math.nextafter(u,-math.inf) if limit=='below' else float(limit)
    d['wall_els']=dict(normal_reference_mm=value,normal_denominator=1.,vertical_denominator=180.,vertical_reference_mm=1000.,origin='Synthetic explicit boundary criterion')
    r=complete_result(calculate(activate(d)));raw=r['ELS']
    assert raw['criterion_status']==expected
    if expected!='meets':assert 'index' not in raw
    assert raw['criterion_status']!='fails'
    assert not any(x['id'].endswith('deflection') and x['status']=='fails' for x in r['global_verification']['checks'])


def test_area_support_limit_stays_pending_and_does_not_zero_original_P():
    d=activate(own());r=complete_result(calculate_batch(d));s=preserved_snapshot(r)
    assert s['total_cases']==18 and len(r['cases'])==58
    limits=0
    for entry in r['cases']:
        c=entry['combination']
        if c['limit_state']!='ELS':continue
        rec=s['records'][c['id']];raw=entry['evidence']['ELS']
        assert rec['case']['P_N']==[c['P_vector'][k] for k in ('normal','parallel')]
        assert rec['declared_limit']['value_mm']==case_inputs(d,c)['ELS_limit_mm']
        if c.get('point_position')=='support_limit':
            limits+=1;assert any(rec['case']['P_N'])
            assert rec['request'] is None and rec['response'] is None and 'index' not in raw
            assert entry['evidence']['inclination']['P_vector']==c['P_vector']
        assert len(entry['rows'])==1 and entry['rows'][0]['Verificação']==ROW
    assert limits==1
    summary=next(x for x in r['summary'] if x['Verificação']==ROW)
    assert summary['Casos pendentes']>=1


def test_isolated_girt_horizontal_limit_not_roof_limit():
    from tercas.ue_member_application import apply as apply_application
    d=apply_application(direct(),'wall_girt')
    d['wall_els']=dict(normal_denominator=120.,vertical_denominator=180.,normal_reference_mm=3500.,vertical_reference_mm=1000.,origin='Declared synthetic criterion')
    r=complete_result(calculate(activate(d)))
    assert r['ELS']['limit_mm']==3500./120.
    assert r[FIELD]['records']['DIRECT_ELS']['request']['q_N_mm']==[d['q_sls'],d['q_parallel_sls']]
    assert len([x for x in rows(r) if x['Verificação']==GIRT_ROW])==1
    assert not any(x['Verificação']=='Flecha vertical — eixo fraco' for x in rows(r))
    assert 'Teto de componente' in text(word(r))


def test_domain_inconclusion_never_recovers_scalar_result():
    d=direct(1.2,q_sls=3.,q_parallel_sls=0.,P_sls=0.,P_parallel_sls=0.)
    old=calculate(d);r=complete_result(calculate(activate(d)))
    assert 'index' in old['ELS']
    assert 'index' not in r['ELS'] and 'upper_bound_mm' not in r['ELS']
    assert r['ELS']['criterion_status']!='fails'


@pytest.mark.parametrize('mode',[None,'local_uniaxial_component_v1','gross_biaxial_sufficient_component_v1'])
def test_no_AA_without_explicit_choice(monkeypatch,mode):
    import tercas.aa_component as aa
    monkeypatch.setattr(aa,'_bundle',lambda:pytest.fail('AA cannot run without explicit choice'))
    d=direct()
    if mode:d['deflection_model']=mode
    assert FIELD not in calculate(d)


def test_outside_geometry_or_system_rejected_without_source_repair():
    for d in (defaults(),dict(own(),member_application='wall_girt'),dict(own(),three_girt_model={'enabled':True})):
        d['deflection_model']=MODE
        with pytest.raises(ValueError):calculate(d)
    d=activate(direct());d['properties']['Ix_cm4']*=1.01
    with pytest.raises(ValueError):calculate(d)


def test_bundle_integrity_failure_blocks_whole_emission(monkeypatch):
    import tercas.aa_component as aa
    monkeypatch.setattr(aa,'LOADER_SHA','0'*64)
    with pytest.raises(ValueError,match='pin externo'):calculate(activate(direct()))


def test_history_and_word_read_no_live_source_or_solver(monkeypatch):
    import tercas.aa_component as aa
    r=complete_result(calculate(activate(direct())));before=copy.deepcopy(r)
    monkeypatch.setattr(aa,'_bundle',lambda:pytest.fail('No new AA calculation on read'))
    monkeypatch.setattr(aa,'_sources',lambda *a:pytest.fail('No live source on read'))
    monkeypatch.setattr(family,'gate',lambda:pytest.fail('No family gate on read'))
    assert preserved_snapshot(r) and rows(r)
    content=text(word(r));assert ROW in content and 'não é flecha exata' in content
    assert r==before


@pytest.mark.parametrize('change',['absent','null','raw','response','request','count','field','ratio','scope','input'])
def test_corrupted_history_rejected_even_with_rehashed_outer_record(change):
    r=complete_result(calculate(activate(direct())));s=r[FIELD];rec=s['records']['DIRECT_ELS']
    if change=='absent':r.pop(FIELD)
    elif change=='null':r[FIELD]=None
    elif change=='raw':r['ELS']['index']=0.
    elif change=='response':rec['response']['displacement_component_bounds'][0]['absolute_max_upper_mm']=0.
    elif change=='request':rec['request']['q_N_mm'][0]=.8
    elif change=='count':s['bounded_cases']=0
    elif change=='field':rec['response']['field']['reaction_left_fractions'][0]=['0','1'];rec['response_sha256']=digest(rec['response'])
    elif change=='ratio':r['ELS']['criterion_status']='fails'
    elif change=='scope':s['whole_member_approved']=True
    else:r['input_data']['project']='Different input'
    if isinstance(r.get(FIELD),dict):s['snapshot_sha256']=digest({k:v for k,v in s.items() if k!='snapshot_sha256'})
    before=copy.deepcopy(r)
    with pytest.raises((ValueError,TypeError,KeyError)):preserved_snapshot(r)
    show=presentation_rows(r,rows(r));row=next(x for x in show if x['Verificação']==ROW)
    assert row['Índice'] is None and 'inválido' in row['Situação']
    assert 'Registro do teto AA inválido' in text(word(r))
    assert r==before


def test_missing_declared_limit_and_ratio_subnormal_are_not_approval_shortcuts():
    from tercas.aa_component import _raw,_upper_ratio
    result=calculate(activate(direct()))
    record=copy.deepcopy(result[FIELD]['records']['DIRECT_ELS'])
    record['declared_limit']={'value_mm':None,'origin':None,'valid':False}
    raw=_raw(record)
    assert raw['criterion_status']=='missing_declared_limit' and 'index' not in raw
    ratio=_upper_ratio(math.ulp(0.),2.)
    assert ratio==math.ulp(0.) and Fraction(ratio)>=Fraction(math.ulp(0.))/2
    assert _upper_ratio(1e308,math.ulp(0.)) is None
