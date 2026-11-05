import copy,json
import pytest
from tercas.support_web import application as a
from tercas.support_web import mechanics as m


def source():
    return dict(schema='synthetic_source',input_fingerprint='immutable_input',P_uls=0.,q_uls=1.)

def extracted(result):
    return dict(schema='source_fixture',source_fingerprint=a.source_fingerprint(result),
        section=dict(family='Ue',H=100.,t=1.2,ri=1.2,fy=250.),scope='Synthetic test, not physical design',
        supports=[dict(support_id=side,label=side,combination_id=cid,limit_state='ELU',normal_N=force,
                       parallel_N=500.,moment_strong_Nmm=123.)
                  for cid,force in [('C1',-1000.),('C2',-10000.)] for side in ('left','right')],legacy_details={})

@pytest.fixture
def prepared(monkeypatch):
    monkeypatch.setattr(a.sources,'extract',extracted)
    src=source();cfg=a.reference_configuration(src)
    for d in cfg['details'].values():
        d.update(route='flange_contact',origin='Synthetic QA support',c_mm=40.,end_distance_mm=0.,
                 no_opposite_force=True,connected=False,normal_compressive_sign=-1,loaded_flange_orientation='Declared negative normal')
    return src,cfg

def test_reactions_checked_without_P_and_mixed_criteria(prepared):
    src,cfg=prepared;before=copy.deepcopy((src,cfg));out=a.calculate(src,cfg)
    assert (src,cfg)==before and src['P_uls']==0.
    assert out['summary']==dict(meets=2,fails=2,exempt=0,not_applicable=0,pending=0,records=4,
        all_local_records_decided=True,all_decided_local_checks_satisfied=False,whole_member_approved=False)
    assert all(out[k] is False for k in a.FALSE_FLAGS)
    assert a.saved_assessment(src,json.loads(json.dumps(out)))==out

def test_pending_and_web_exception_are_not_global_approval(prepared):
    src,cfg=prepared;cfg['details']['left']['route']=None;cfg['details']['right']['route']='web_connection'
    out=a.calculate(src,cfg);assert out['summary']['pending']==2 and out['summary']['exempt']==2
    assert out['whole_member_approved'] is False

@pytest.mark.parametrize('mutation',['source','config_source','missing_support','extra_support','detail_key'])
def test_configuration_is_bound_and_exact(prepared,mutation):
    src,cfg=prepared
    if mutation=='source':src['q_uls']=2.
    elif mutation=='config_source':cfg['source_fingerprint']='bad'
    elif mutation=='missing_support':cfg['details'].pop('left')
    elif mutation=='extra_support':cfg['details']['extra']=a.blank_detail()
    else:cfg['details']['left']['unknown']=1
    with pytest.raises(ValueError):a.calculate(src,cfg)

def test_read_and_word_never_extract_or_recalculate(prepared,monkeypatch):
    from tercas.support_web import report
    src,cfg=prepared;out=a.calculate(src,cfg)
    def no(*args,**kwargs):raise AssertionError('No source or resistance recalculation')
    monkeypatch.setattr(a.sources,'extract',no);monkeypatch.setattr(m,'evaluate_reaction',no)
    assert a.saved_assessment(src,out)==out
    assert report.word(src,out).startswith(b'PK')

@pytest.mark.parametrize('mutation',['hash','demand','index','force','normal','detail','global','summary','duplicate','domain'])
def test_saved_inconsistency_is_rejected_even_if_outer_digest_replaced(prepared,mutation):
    src,cfg=prepared;out=a.calculate(src,cfg)
    if mutation=='hash':out['content_sha256']='bad'
    elif mutation=='demand':src['q_uls']=2.
    elif mutation=='index':out['rows'][0]['local']['index']=0.
    elif mutation=='force':out['rows'][0]['local']['force_N']=1.
    elif mutation=='normal':out['rows'][0]['source_record']['normal_N']=1.
    elif mutation=='detail':out['rows'][0]['detail']['c_mm']=99.
    elif mutation=='global':out['whole_member_approved']=True
    elif mutation=='summary':out['summary']['meets']=999
    elif mutation=='duplicate':out['rows'].append(copy.deepcopy(out['rows'][0]))
    elif mutation=='domain':out['rows'][0]['local']['domain']['c_mm']=999.
    if mutation!='hash':out['content_sha256']=a.fingerprint({k:v for k,v in out.items() if k!='content_sha256'})
    with pytest.raises(ValueError):a.saved_assessment(src,out)
