"""Scope correction, not a resistance/new physical or mobile-envelope check."""
import copy,json
from io import BytesIO
import pytest
from docx import Document
from tercas.application import example
from tercas.batch import calculate_batch,area_bundle,case_inputs
from tercas.point_contact import FIELD,SCHEMA_V2,DECLARATIONS,blank_choice,reference_basis,saved_records
from tercas.point_limit import SCHEMA,SCOPE,contact_exclusion,saved_exclusion
from tercas.global_verification import build_global_verification,attach_global_verification


def combo():
    return dict(id='P_ELU_01_APOIO',limit_state='ELU',point_position='support_limit',
                x_mm=0.,P_N=1500.,P_vector=dict(normal=1500.,parallel=0.))


def valid():
    c=combo();return contact_exclusion(c,4000.),c,4000.,c['P_vector']


@pytest.mark.parametrize('mutation',[
    'old','bare','center','direct','x','force','parallel','span','id','state',
    'index','FRd_N','patch_mm','domain','physical_contact_checked',
    'physical_conditions_verified','connection_design_checked','unknown','bool','nan'])
def test_invalid_exclusions_never_requalify(mutation):
    raw,c,L,p=valid();p=copy.deepcopy(p)
    if mutation=='old':raw=dict(status='not_evaluated',position='support_limit',force_N=1500.,reason='old')
    elif mutation=='bare':raw=dict(status='not_applicable')
    elif mutation=='center':c['point_position']='center'
    elif mutation=='direct':c.pop('point_position')
    elif mutation=='x':c['x_mm']=20.
    elif mutation=='force':p['normal']=1.
    elif mutation=='parallel':p['parallel']=1e-300
    elif mutation=='span':L=4001.
    elif mutation=='id':c['id']='OTHER'
    elif mutation=='state':c['limit_state']='ELS'
    elif mutation in ('physical_contact_checked','physical_conditions_verified','connection_design_checked'):raw[mutation]=True
    elif mutation=='bool':raw['physical_contact_checked']=0
    elif mutation=='nan':raw['force_N']=float('nan')
    else:raw[mutation]=0.
    assert not saved_exclusion(raw,c,L,p)


def test_new_record_is_exact_exclusion_without_contact_or_capacity():
    raw,c,L,p=valid();before=copy.deepcopy((raw,c,p))
    assert saved_exclusion(raw,c,L,p)
    assert raw['schema']==SCHEMA and raw['scope']=='mathematical_limit'
    assert raw['force_N']==1500. and raw['a_limit']=='a→0+'
    assert not {'index','FRd_N','patch_mm','domain','c_mm'} & set(raw)
    assert 'não dispensa normativa' in raw['reason'] and 'P_CENTRO' in raw['reason']
    assert json.loads(json.dumps(raw,allow_nan=False))==raw and (raw,c,p)==before


@pytest.fixture(scope='module')
def batches():
    d=example();d.update(load_mode='area',selected_types=['ELU normal','ELS rara'],patch_mm=None,patch_origin='')
    absent=calculate_batch(d)
    cfg=blank_choice();cfg.update(schema=SCHEMA_V2,enabled=True,c_mm=40.,
        origin='Synthetic QA only: P and end webs',basis=reference_basis(d))
    cfg['declarations']={k:True for k in DECLARATIONS};d[FIELD]=cfg
    complete=calculate_batch(d)
    incomplete=copy.deepcopy(d);incomplete[FIELD]['c_mm']=None
    return absent,complete,calculate_batch(incomplete)


def support_checks(g):
    return [r for r in g['checks'] if r['id'].endswith(':point_introduction_scope') and '_APOIO:' in r['id']]


def test_batch_local_only_never_changes_main_table_or_real_contacts(batches):
    absent,complete,incomplete=batches
    for r in batches:
        g=build_global_verification(r);sc=support_checks(g)
        assert len(sc)==4 and all(c['status']=='not_applicable' and c['index'] is None for c in sc)
        assert len(g['point_limit_exclusion_ids'])==4 and g['point_limit_scope_note']==SCOPE
        assert not g['whole_member_approved'] and not g['physical_conditions_verified']
        assert 'torsion_warping' in g['pending_ids']
        assert r['summary']==absent['summary']
        for a,b in zip(absent['cases'],r['cases']):
            assert a['combination']==b['combination'] and a['rows']==b['rows']
            ea=copy.deepcopy(a['evidence']);eb=copy.deepcopy(b['evidence'])
            if 'NBR_branches' in ea:
                pa=ea['NBR_branches'].pop('point');pb=eb['NBR_branches'].pop('point')
                if a['combination'].get('point_position')=='support_limit':assert pa==pb
            assert ea==eb
    for r in (absent,incomplete):
        g=build_global_verification(r)
        assert len([key for key in g['pending_ids'] if '_CENTRO:point_introduction_scope' in key])==4
    assert not [key for key in build_global_verification(complete)['pending_ids'] if '_CENTRO:point_introduction_scope' in key]
    records=saved_records(complete)
    limits=[r for r in records if '_APOIO' in r['combination_id']]
    assert len(limits)==4 and all(r['status']=='not_applicable' and r['c_mm'] is None and r['FRd_N'] is None and r['index'] is None for r in limits)


def test_old_snapshot_stays_pending_with_no_global_note(batches):
    r=copy.deepcopy(batches[1])
    for case in r['cases']:
        if case['combination'].get('point_position')=='support_limit' and case['combination']['limit_state']=='ELU':
            case['evidence']['NBR_branches']['point']=dict(status='not_evaluated',
                position='support_limit',force_N=case['combination']['P_N'],reason='old pending local transfer')
    before=copy.deepcopy(r);g=build_global_verification(r)
    assert all(c['status']=='pending' for c in support_checks(g))
    assert 'point_limit_scope_note' not in g
    assert all(v['status']=='pending' for v in saved_records(r) if '_APOIO' in v['combination_id'])
    assert r==before


@pytest.mark.parametrize('mutation',['center','vector','capacity','only_label','model_conflict','case_position','case_bool_position'])
def test_global_fails_closed_for_false_exclusion(batches,mutation):
    r=copy.deepcopy(batches[1]);case=next(c for c in r['cases'] if c['combination'].get('point_position')=='support_limit' and c['combination']['limit_state']=='ELU')
    raw=case['evidence']['NBR_branches']['point'];cid=case['combination']['id']
    if mutation=='center':
        target=next(c for c in r['cases'] if c['combination'].get('point_position')=='center' and c['combination']['limit_state']=='ELU')
        target['evidence']['NBR_branches']['point']=raw;cid=target['combination']['id']
    elif mutation=='vector':case['evidence']['inclination']['P_vector']['normal']+=1
    elif mutation=='capacity':raw['FRd_N']=100000.
    elif mutation=='only_label':case['evidence']['NBR_branches']['point']={'status':'not_applicable'}
    elif mutation=='case_position':case['combination']['point_position']='center'
    elif mutation=='case_bool_position':case['combination']['x_mm']=False
    else:r['model_domain_evidence']['conflict']='incompatible model'
    g=build_global_verification(r)
    assert 'ELU:'+cid+':point_introduction_scope' in g['pending_ids']
    assert not g['whole_member_approved']


def test_report_saved_only_no_reanalysis_and_no_legacy_migration(batches,monkeypatch):
    import tercas.point_contact as pc
    import tercas.batch as batch
    from tercas.report import batch_word
    r=attach_global_verification(batches[1]);before=copy.deepcopy(r)
    def forbidden(*a,**k):raise AssertionError('History must not solve or requalify')
    monkeypatch.setattr(pc,'evaluate',forbidden);monkeypatch.setattr(batch,'calculate_batch',forbidden)
    text='\n'.join(p.text for p in Document(BytesIO(batch_word(r))).paragraphs)
    assert 'Não aplicável — somente ao limite matemático' in text
    assert 'não dispensa normativa' in text and 'cobre somente o contato central' in text
    assert r==before
