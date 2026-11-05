"""Load-height Me is consumed per ELU, without changing M–V or AISI."""
import copy
import json
import math
import pytest
from tercas import roof_top_load as roof,roof_top_nbr as nbr
from tercas import ue_reference as single,ue_family_reference as family
from tercas.batch import calculate_batch
from tercas.global_verification import build_global_verification
from tercas.roof_top_nbr_ui import presentation_rows,ROW


@pytest.fixture(scope='module',params=[1.2,1.5,2.,2.25,2.65,3.,3.35])
def raw(request):
    t=request.param
    d=single.load_reference(angle=0.) if t==1.2 else family.load_reference(t,4000.,0.)
    d['selected_types']=['ELU normal','ELS quase permanente'];d[roof.FIELD]=roof.choice()
    return roof.attach(calculate_batch(d))


def oracle(W,fy,Ml,Me):
    l=math.sqrt(W*fy/Me);x=1. if l<=.6 else 1.11*(1-.278*l*l) if l<1.336 else 1/(l*l)
    p=math.sqrt(x*W*fy/Ml);r=1. if p<=.673 else (1-.22/p)/p
    return x*W*r*fy/1.1


def test_seven_sources_curve_per_ELU_and_pure_bending_minimum(raw):
    before=copy.deepcopy(raw);out=nbr.attach(raw);assert raw==before
    assert all(out[k]==v for k,v in raw.items())
    ev=nbr.preserved(out);s=ev['source_section'];me={r['combination_id']:r for r in raw['roof_top_load_evidence']['records']}
    assert ev['computed_cases']==40 and ev['pending_cases']==0 and ev['ignored_ELS_cases']==2
    for r in ev['records']:
        assert r['Me_Nmm']==me[r['combination_id']]['Me_Nmm']
        assert math.isclose(r['FLT']['MRd_flt_Nmm'],oracle(s['Wc_mm3'],s['fy_MPa'],s['Ml_Nmm'],r['Me_Nmm']),rel_tol=3e-15)
        assert r['MRd_bending_component_Nmm']==min(x for x in (r['FLT']['MRd_flt_Nmm'],r['MRd_section_effective_Nmm'],r['MRd_distortional_Nmm']) if x is not None)
        assert r['Cb_applied_after_Me'] is False and r['primary_torsion_assessed'] is False
        assert r['criterion_status']==('fails' if r['index']>1 else 'meets')
    assert s['strong_distortional_exempt']==(s['thickness_mm']==1.2)
    assert (s['MRd_distortional_Nmm'] is None)==(s['thickness_mm']==1.2)
    assert ev['M_V_denominators_changed'] is False and ev['AISI_capacities_changed'] is False
    assert ev['whole_member_approved'] is False


def test_only_FLT_and_coverage_change_in_global_and_torsion_remains(raw):
    old=build_global_verification(raw);out=nbr.attach(raw);new=build_global_verification(out)
    def rest(g):return [r for r in g['checks'] if ':FLT' not in r['id']]
    assert rest(old)==rest(new)
    rows=[r for r in new['checks'] if ':FLT_height' in r['id']]
    assert len(rows)==40 and all(r['status'] in ('fails','meets') for r in rows)
    assert any(r['status']=='fails' for r in rows)
    assert all(r['status']=='meets' for r in new['checks'] if ':FLT_coverage' in r['id'])
    assert 'torsion_warping' in new['pending_ids'] and new['whole_member_approved'] is False
    out['global_verification']=new;nbr.validate_saved_global(out)


def test_UI_replacement_changes_only_FLT_rows_not_raw(raw):
    out=nbr.attach(raw);before=copy.deepcopy(out);shown=presentation_rows(out,out['summary'])
    assert out==before
    assert [r for r in shown if r['Verificação']!=ROW]==[r for r in out['summary'] if not r['Verificação'].startswith('FLT — trecho ')]
    assert sum(r['Verificação']==ROW for r in shown)==1
    for c in out['cases']:
        shown=presentation_rows(out,c['rows'],c['combination']['id'])
        if c['combination']['limit_state']=='ELS':assert shown==c['rows']
        else:
            row=next(r for r in shown if r['Verificação']==ROW)
            saved=next(r for r in out[nbr.FIELD]['records'] if r['combination_id']==c['combination']['id'])
            assert row['Índice']==saved['index']


def test_saved_readers_do_not_reopen_sources_or_recalculate(raw,monkeypatch):
    out=nbr.attach(raw);out['global_verification']=build_global_verification(out)
    before=copy.deepcopy(out)
    def fail(*a,**k):raise AssertionError('Hidden calculation/source reopening')
    monkeypatch.setattr(roof,'refined',fail);monkeypatch.setattr(nbr,'flt_mse',fail)
    monkeypatch.setattr(family,'reference',fail);monkeypatch.setattr(single,'reference',fail)
    monkeypatch.setattr(family,'evidence',fail);monkeypatch.setattr(single,'evidence',fail)
    assert nbr.preserved(out)==out[nbr.FIELD]
    nbr.validate_saved_global(out);presentation_rows(out,out['summary'])
    from tercas.roof_top_nbr_ui import report
    from docx import Document
    doc=Document();report(doc,out)
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'MRd,FLT=' in text and 'Sem interação com torção' in text
    assert out==before and nbr.preserved(json.loads(json.dumps(out,allow_nan=False)))==out[nbr.FIELD]


def test_manual_legacy_segment_results_do_not_control_whole_span_component(raw):
    changed=copy.deepcopy(raw)
    for c in changed['cases']:
        if c['combination']['limit_state']=='ELU':c['evidence']['FLT_segments']=[]
    out=nbr.attach(changed);g=build_global_verification(out)
    assert len([r for r in g['checks'] if ':FLT_height' in r['id']])==40
    assert not any(':FLT:' in r['id'] or 'FLT_inventory' in r['id'] for r in g['checks'])
    assert all(r['status']=='meets' for r in g['checks'] if ':FLT_coverage' in r['id'])
    assert out[nbr.FIELD]['domain']==dict(start_mm=0.,end_mm=4000.,end_restraint='fork_free_warping',intermediate_restraints='none',manual_effective_lengths_used=False)


def test_source_evidence_staleness_is_not_silently_used(raw):
    altered=copy.deepcopy(raw)
    field='ue_family_reference_evidence' if 'ue_family_reference_evidence' in altered else 'ue_reference_evidence'
    altered[field]['signed_scalar_capacities']['strong_positive']['MRd_local_Nmm']*=2
    out=nbr.attach(altered);ev=nbr.preserved(out)
    assert ev['computed_cases']==0 and ev['pending_cases']==40
    assert all('diverge' in r['reason'] for r in ev['records'])


@pytest.fixture(scope='module')
def one():
    d=family.load_reference(2.,4000.,0.);d[roof.FIELD]=roof.choice();d['selected_types']=['ELU normal']
    return nbr.attach(roof.attach(calculate_batch(d)))


@pytest.mark.parametrize('mutation',['Me','source','source_removed','capacity','id','record_missing','record_duplicate','domain','approval','me_source_hash','gamma'])
def test_saved_tampering_rejected(one,mutation):
    r=copy.deepcopy(one);e=r[nbr.FIELD]
    if mutation=='Me':r['roof_top_load_evidence']['records'][0]['Me_Nmm']*=2
    if mutation=='source':r['ue_family_reference_evidence']['source_record']['profile_id']='other'
    if mutation=='source_removed':del r['ue_family_reference_evidence']
    if mutation=='capacity':e['records'][0]['FLT']['MRd_flt_Nmm']*=2
    if mutation=='id':e['records'][0]['combination_id']='other'
    if mutation=='record_missing':e['records'].pop()
    if mutation=='record_duplicate':e['records'].append(copy.deepcopy(e['records'][0]))
    if mutation=='domain':e['domain']['end_mm']=2000.
    if mutation=='approval':e['whole_member_approved']=True
    if mutation=='me_source_hash':e['source_roof_snapshot_sha256']='other'
    if mutation=='gamma':e['records'][0]['FLT']['gamma']=1.
    with pytest.raises(ValueError):nbr.preserved(r)


@pytest.mark.parametrize('mutation',['removed','altered','binding_removed','binding_null','binding_string','coverage_removed','summary_altered'])
def test_global_promotion_cannot_survive_sidecar_or_binding_loss(one,mutation):
    r=copy.deepcopy(one);r['global_verification']=build_global_verification(r)
    if mutation=='removed':del r[nbr.FIELD]
    if mutation=='altered':r[nbr.FIELD]['records'][0]['index']=0.
    if mutation=='binding_removed':del r['global_verification']['roof_top_nbr_binding']
    if mutation=='binding_null':r['global_verification']['roof_top_nbr_binding']=None
    if mutation=='binding_string':r['global_verification']['roof_top_nbr_binding']='invalid'
    if mutation=='summary_altered':r['global_verification']['display_summary']='Incorrect approval'
    if mutation=='coverage_removed':r['global_verification']['checks']=[x for x in r['global_verification']['checks'] if ':FLT_coverage' not in x['id']]
    with pytest.raises(ValueError):nbr.validate_saved_global(r)
    from tercas.study_completion import report_global
    from docx import Document
    doc=Document();report_global(doc,r)
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Panorama não exibido' in text
    assert 'Reprovado nos critérios calculados' not in text


def test_unconverged_and_empty_source_keep_specific_pending(one):
    r=copy.deepcopy(one);r.pop(nbr.FIELD);ev=r['roof_top_load_evidence'];ev['records'][0].update(Me_Nmm=None,numerically_converged=False,status='numerical_refinement_inconclusive')
    ev['snapshot_sha256']=roof.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    out=nbr.attach(r);assert out[nbr.FIELD]['computed_cases']==39 and out[nbr.FIELD]['pending_cases']==1
    ev['records']=[];ev['status']='pending_model_scope';ev['reason']='Source model not applicable.'
    ev['snapshot_sha256']=roof.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    out=nbr.attach(r);assert out[nbr.FIELD]['computed_cases']==0 and out[nbr.FIELD]['pending_cases']==40
    assert all(x['reason']=='Source model not applicable.' for x in out[nbr.FIELD]['records'])


def test_real_parallel_actions_remain_pending():
    d=family.load_reference(2.,4000.,5.);d[roof.FIELD]=roof.choice();d['selected_types']=['ELU normal']
    out=nbr.attach(roof.attach(calculate_batch(d)));ev=nbr.preserved(out)
    assert ev['computed_cases']==0 and ev['pending_cases']==40
    assert all('componentes paralelas' in r['reason'] for r in ev['records'])


def test_no_implicit_activation_or_historical_requalification():
    d=family.load_reference(2.,4000.,0.);d['selected_types']=['ELS quase permanente'];r=calculate_batch(d)
    assert nbr.attach(r)==r and nbr.preserved(r) is None
    assert presentation_rows(r,r['summary'])==r['summary']


def test_catalog_source_stays_pending_without_changing_Me():
    from tercas.application import example
    d=example();d['load_mode']='area';d['selected_types']=['ELU normal'];d[roof.FIELD]=roof.choice()
    raw=roof.attach(calculate_batch(d));out=nbr.attach(raw)
    assert out['roof_top_load_evidence']==raw['roof_top_load_evidence']
    assert out[nbr.FIELD]['computed_cases']==0 and out[nbr.FIELD]['pending_cases']==40
    assert all('não é proibição normativa' in r['reason'] for r in out[nbr.FIELD]['records'])


def test_ELSonely_selection_does_not_create_ELU():
    d=family.load_reference(2.,4000.,0.);d['selected_types']=['ELS quase permanente'];d[roof.FIELD]=roof.choice()
    out=nbr.attach(roof.attach(calculate_batch(d)));ev=nbr.preserved(out)
    assert ev['records']==[] and ev['status']=='no_ELU_selected' and ev['ignored_ELS_cases']==2
    assert 'missing_limit_state:ELU' in build_global_verification(out)['pending_ids']


def test_full_completion_keeps_AISI_and_old_MV_exactly():
    from tercas.study_completion import complete_result
    from tercas.torsion_study import attach
    from tercas.aisi_torsion_component import finalize,preserved as aisi_saved
    d=family.load_reference(2.,4000.,0.);d['selected_types']=['ELU normal'];d[roof.FIELD]=roof.choice()
    raw=calculate_batch(d);old=finalize(attach(raw));out=complete_result(raw)
    assert out['aisi_torsion_component']==old['aisi_torsion_component'] and aisi_saved(out)
    assert out['aisi_torsion_component']['H4_computed_cases']==0
    assert all(out[k]==v for k,v in raw.items())
    assert out[nbr.FIELD]['computed_cases']==40 and out['whole_member_approved'] is False
    nbr.validate_saved_global(out)


@pytest.mark.parametrize('mutation',['ratio','local','Wc','material','minimum','torque','curve_parameter'])
def test_resigned_internally_inconsistent_values_rejected(one,mutation):
    out=copy.deepcopy(one);ev=out[nbr.FIELD]
    if mutation=='ratio':ev['records'][0].update(index=0.,criterion_status='meets')
    if mutation=='local':ev['records'][0]['MRd_section_effective_Nmm']*=2
    if mutation=='Wc':ev['source_section']['Wc_mm3']*=2
    if mutation=='material':ev['source_section']['fy_MPa']*=2
    if mutation=='minimum':ev['records'][0]['MRd_bending_component_Nmm']*=2
    if mutation=='torque':ev['records'][0]['primary_torque_by_action'][0]['value']=0.
    if mutation=='curve_parameter':ev['records'][0]['FLT']['chi_flt']=-1.
    ev['snapshot_sha256']=roof.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):nbr.preserved(out)


@pytest.mark.parametrize('mutation',['section','row','curve'])
def test_malformed_saved_objects_fail_with_validation_error(one,mutation):
    out=copy.deepcopy(one);ev=out[nbr.FIELD]
    if mutation=='section':ev['source_section']='invalid'
    if mutation=='row':ev['records'][0]=None
    if mutation=='curve':ev['records'][0]['FLT']='invalid'
    ev['snapshot_sha256']=roof.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):nbr.preserved(out)
