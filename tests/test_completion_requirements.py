import copy
import json
import pytest
from unittest.mock import patch
from tercas import completion_requirements as c
from test_serviceability_plan import fixture


def source():
    r=fixture();r['global_verification']={'checks':[
        {'id':'ELU:down:local','status':'meets'},
        {'id':'ELU:down:axial_scope','status':'not_applicable'},
        {'id':'ELS:down:combined_ELS_scope','status':'pending'}]}
    return r


def test_independent_inventory_present_when_no_checks_exist():
    r=source();r['global_verification']['checks']=[];x=c.attach(r)
    saved=c.saved(x)
    assert saved['required_ids']==list(c.REQUIRED_IDS) and len(saved['records'])==19
    assert all(row['evidence_state']=='not_consolidated' for row in saved['records'])
    assert not saved['whole_member_approved'] and not saved['normative_design_complete']
    assert c.FIELD not in r


def test_input_snapshot_and_json_roundtrip_without_member_solver():
    r=c.attach(source());before=copy.deepcopy(r)
    with patch('tercas.application.calculate',side_effect=AssertionError('no solver')):
        read=c.saved(json.loads(json.dumps(r)))
    assert read==r[c.FIELD] and r==before


@pytest.mark.parametrize('kind',['drop','duplicate','promote','source','plan','criterion','record','scope','normative_source','exclusions'])
def test_tampered_rehashed_inventory_still_rejected(kind):
    r=c.attach(source());s=r[c.FIELD]
    if kind=='drop':s['records'].pop()
    if kind=='duplicate':s['records'].append(copy.deepcopy(s['records'][0]))
    if kind=='promote':s['whole_member_approved']=True
    if kind=='scope':s['scope']='Tudo aprovado'
    if kind=='normative_source':s['normative_source_sha256']='unknown'
    if kind=='exclusions':s['exclusions']=[]
    if kind=='source':r['input_data']['L_mm']=4000
    if kind=='plan':s['service_preparation']['prepared_cases']=[]
    if kind=='criterion':s['service_preparation']['criteria'][1]['limit_mm']=999
    if kind=='record':s['records'][0]['requirement_state']='not_applicable'
    s['snapshot_sha256']=c.digest({k:v for k,v in s.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):c.saved(r)


def test_historical_result_has_no_inventory_synthesized():
    r=source()
    with patch.object(c,'build',side_effect=AssertionError('no builder')):
        assert c.saved(r) is None
    assert c.FIELD not in r


def test_frame_and_girt_not_substituted_by_purlin_inventory():
    for data in ({'schema':'tercas_three_girt_results_v1'},
                 {'input_data':{'L_mm':3000.,'member_application':'wall_girt'}}):
        r=source();r.update(data);assert c.build(r) is None


def test_only_saved_axial_scope_excluded_not_absent_supports():
    r=c.saved(c.attach(source()));rows={v['id']:v for v in r['records']}
    assert rows['axial_scope']['requirement_state']=='declared_N_zero_scope'
    assert rows['support_web']['evidence_state']=='not_consolidated'
    assert rows['support_web']['requirement_state']=='closure_not_qualified'
    assert rows['connections']['requirement_state']=='outside_member_design_scope'


def test_word_and_ui_use_saved_inventory_without_solver():
    from docx import Document
    class UI:
        def __init__(self):self.lines=[]
        def expander(self,*a,**kw):return self
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def caption(self,s):self.lines.append(s)
        def markdown(self,s):self.lines.append(s)
        def warning(self,s):self.lines.append(s)
    r=c.attach(source());st=UI();doc=Document()
    with patch.object(c,'build',side_effect=AssertionError('no builder')):
        c.show(st,r);c.report(doc,r)
    assert len(st.lines)>19 and any('nota f' in s for s in st.lines)
    assert any('nota f' in p.text for p in doc.paragraphs)


def test_completion_boundary_attaches_after_new_calculation_only():
    from contextlib import ExitStack
    from tercas.application import fingerprint
    from tercas.study_completion import complete_result
    r=source();r['input_fingerprint']=fingerprint(r['input_data']);before=copy.deepcopy(r)
    targets=['tercas.torsion_study.attach','tercas.ue_catalog_reference.attach_source',
             'tercas.aisi_torsion_component.finalize','tercas.isolated_en_application.finalize',
             'tercas.roof_top_load.attach','tercas.roof_top_nbr.attach',
             'tercas.nbr_ue_family_application.attach']
    with ExitStack() as stack:
        for target in targets:stack.enter_context(patch(target,side_effect=copy.deepcopy))
        stack.enter_context(patch('tercas.study_completion.build_global_verification',
                                 return_value=copy.deepcopy(r['global_verification'])))
        out=complete_result(r)
    assert r==before and out['completion_snapshot']['historical_results_requalified'] is False
    assert c.saved(out)['required_ids']==list(c.REQUIRED_IDS)
