import copy
import io
import json
import pytest
from docx import Document
from tercas.application import example,calculate
from tercas import completion_requirements as req
from tercas.support_web import application as a, completion as c


def fixture():
    data=example();data.update(P_uls=0.,q_uls=1.,left_web=False,right_web=False,support_origin='')
    result=req.attach(calculate(data))
    config=a.reference_configuration(result)
    for d in config['details'].values():
        d.update(route='flange_contact',origin='Synthetic audit, no physical project',c_mm=40.,end_distance_mm=0.,
            no_opposite_force=True,connected=False,normal_compressive_sign=-1,loaded_flange_orientation='negative')
    return result,a.calculate(result,config)


@pytest.fixture(scope='module')
def baseline():return fixture()


def rehash(envelope):
    assessment=envelope['assessment']
    assessment['summary']=a.summary(assessment['rows'])
    assessment['content_sha256']=a.fingerprint({k:v for k,v in assessment.items() if k!='content_sha256'})
    envelope['snapshot_sha256']=a.fingerprint({k:v for k,v in envelope.items() if k!='snapshot_sha256'})


def test_complete_local_evidence_without_result_mutation_or_global_approval(baseline,monkeypatch):
    result,assessment=baseline;before=copy.deepcopy((result,assessment))
    def forbidden(*args,**kwargs):raise AssertionError('No member solver')
    monkeypatch.setattr('tercas.application.calculate',forbidden)
    env=c.build(result,assessment);got=c.saved(result,json.loads(json.dumps(env)))
    assert got==env and (result,assessment)==before
    records=got['completion']['records'];old=result[req.FIELD]['records']
    assert len(records)==len(req.REQUIRED_IDS)==19
    assert [r['id'] for r in records]==list(req.REQUIRED_IDS)
    assert [r for r in records if r['id']!='support_web']==[r for r in old if r['id']!='support_web']
    row=next(r for r in records if r['id']=='support_web')
    assert row['evidence_state']=='authenticated_local_support_components' and len(row['local_evidence'])==2
    assert all(got[k] is False and got['completion'][k] is False for k in c.FALSE_FLAGS)
    assert not row['complete_load_introduction_qualified']
    text=' '.join(p.text for p in Document(io.BytesIO(c.word(result,env))).paragraphs)
    assert c.PERSISTENCE in text
    assert c.SCOPE in text and 'Inventário de fechamento preservado' in text


@pytest.mark.parametrize('mutation',['capacity','demand','position','material','detail','omit','duplicate','exempt','authority','inventory','global'])
def test_deliberate_rehash_cannot_change_source_or_scalar_authority(baseline,mutation):
    result,assessment=baseline;env=c.build(result,assessment);r=env['assessment']['rows'][0];local=r['local']
    if mutation=='capacity':
        local['FRd_N']*=100;local['index']=local['force_N']/local['FRd_N'];local['criterion_status']='meets'
    elif mutation=='demand':
        r['source_record']['parallel_N']+=123;local['reaction']['parallel_N']+=123
    elif mutation=='position':r['source_record']['x_mm']+=1
    elif mutation=='material':env['assessment']['section']['fy']+=1
    elif mutation=='detail':
        env['assessment']['configuration']['details']['left']['end_distance_mm']=5
        r['detail']['end_distance_mm']=5;local['domain']['end_distance_mm']=5
    elif mutation=='omit':env['assessment']['rows'].pop()
    elif mutation=='duplicate':env['assessment']['rows'].append(copy.deepcopy(r))
    elif mutation=='exempt':
        # Replacing a computed resistance by an unbacked exclusion is refused.
        local.clear();local.update(status='not_applicable',reaction=copy.deepcopy(r['source_record']))
    elif mutation=='authority':env['authority']['core/anexo_d.py']='unknown'
    elif mutation=='inventory':env['completion']['records'].pop()
    else:env['whole_member_approved']=True
    rehash(env)
    with pytest.raises(ValueError):c.saved(result,env)


def test_pending_detail_and_declared_web_exception_remain_distinct(baseline):
    result,_=baseline;config=a.reference_configuration(result)
    config['details']['right'].update(route='web_connection',origin='User-declared hypothesis')
    env=c.build(result,a.calculate(result,config))
    row=next(r for r in env['completion']['records'] if r['id']=='support_web')
    assert row['local_summary']['pending']==1 and row['local_summary']['exempt']==1
    assert row['requirement_state']=='local_support_component_recorded_not_full_support_design'
    assert not env['normative_design_complete']


def test_historical_sidecar_unchanged_and_missing_completion_not_created(baseline):
    result,assessment=baseline
    assert a.saved_assessment(result,assessment)==assessment
    raw=copy.deepcopy(result);raw.pop(req.FIELD)
    cfg=a.reference_configuration(raw);old=a.calculate(raw,cfg)
    with pytest.raises(ValueError,match='Inventário original'):c.build(raw,old)
    assert req.FIELD not in raw


def test_direct_PP_q_P_equilibrium_authenticated():
    from tercas import direct_self_weight as pp
    data=pp.activate(example());data.update(q_uls=.3,P_uls=123.,x_uls=700.,q_parallel_uls=.2,P_parallel_uls=31.)
    result=req.attach(calculate(data));config=a.reference_configuration(result)
    for detail in config['details'].values():detail.update(route='web_connection',origin='Declared only')
    env=c.build(result,a.calculate(result,config))
    rows=env['assessment']['rows'];total=pp.calculation_inputs(data);L=data['L_mm']
    assert sum(r['source_record']['normal_N'] for r in rows)==pytest.approx(-total['q_uls']*L-data['P_uls'])
    assert sum(r['source_record']['parallel_N'] for r in rows)==pytest.approx(-total['q_parallel_uls']*L-data['P_parallel_uls'])
    assert rows[1]['source_record']['normal_N']==pytest.approx(-total['q_uls']*L/2-data['P_uls']*data['x_uls']/L)
    assert total['q_uls']>data['q_uls']
    assert c.saved(result,env)==env


def test_empty_ELS_only_and_unknown_authority_are_not_consolidated(baseline,monkeypatch):
    result,assessment=baseline;env=c.build(result,assessment)
    empty=copy.deepcopy(env);empty['assessment']['rows']=[];rehash(empty)
    with pytest.raises(ValueError):c.saved(result,empty)
    els=copy.deepcopy(env)
    for row in els['assessment']['rows']:row['source_record']['limit_state']='ELS'
    rehash(els)
    with pytest.raises(ValueError):c.saved(result,els)
    monkeypatch.setattr(c,'_AUTHORITY',dict(c._AUTHORITY,**{'core/anexo_d.py':'unknown_revision'}))
    with pytest.raises(ValueError,match='Autoridade'):c.saved(result,env)


def test_zero_normal_excludes_only_normal_and_keeps_pending_connections():
    data=example();data.update(q_uls=0.,P_uls=0.,q_parallel_uls=.1,P_parallel_uls=0.,left_web=False,right_web=False,support_origin='')
    result=req.attach(calculate(data));cfg=a.reference_configuration(result)
    env=c.build(result,a.calculate(result,cfg))
    rows={r['id']:r for r in env['completion']['records']}
    assert rows['support_web']['local_summary']['not_applicable']==2
    assert all(e['status']=='not_applicable' for e in rows['support_web']['local_evidence'])
    assert rows['connections']['requirement_state']=='outside_member_design_scope'
    assert rows['support_model']['requirement_state']=='closure_not_qualified'
    assert not rows['support_web']['complete_load_introduction_qualified']
    assert not env['normative_design_complete']


def test_changed_authority_file_bytes_rejected(baseline,tmp_path,monkeypatch):
    from pathlib import Path
    result,assessment=baseline;env=c.build(result,assessment)
    original_root=Path(c.__file__).resolve().parents[1]
    for name in c._AUTHORITY:
        target=tmp_path/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((original_root/name).read_bytes())
    (tmp_path/'core/anexo_d.py').write_bytes(b'unknown formula revision')
    monkeypatch.setattr(c,'__file__',str(tmp_path/'support_web/completion.py'))
    with pytest.raises(ValueError,match='Autoridade'):c.saved(result,env)


@pytest.mark.parametrize('field',['source_schema','source_input_fingerprint','source_scope','source_metadata','legacy_detail_evidence','limits'])
def test_rehashed_metadata_cannot_contaminate_presentation(baseline,field):
    result,assessment=baseline;env=c.build(result,assessment)
    env['assessment'][field]='Forged presentation or provenance'
    rehash(env)
    with pytest.raises(ValueError,match='Metadados'):c.saved(result,env)
