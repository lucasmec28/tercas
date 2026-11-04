"""Practical current-input G8.1/H4, distinct from fixed PP controls."""
import copy
import hashlib
import json
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from docx import Document
from tercas import ue_family_reference as family,torsion_study as torsion
from tercas.study_completion import complete_result
from tercas import aisi_torsion_component as a
from tercas.torsion_vlasov.vlasov import solve_member,evaluate
from tercas.torsion_vlasov.adapter import attach_torsion_evidence,summarize_torsion_evidence


def inputs(angle=5.):
    d=family.load_reference(1.5,4000.,angle)
    d[torsion.FIELD]=torsion.blank_choice()
    d[torsion.FIELD]['load_lines']={r:dict(declared=True,xy_from_CG_mm=[0.,0.],
        origin='Synthetic QA declaration, not an actual project') for r in torsion.ROLES}
    return d


@pytest.fixture(scope='module')
def current():return complete_result(family.calculate_reference(inputs()))


@pytest.fixture(scope='module')
def analysis(current):
    record=current[a.FIELD]['records'][0]['AISI_analysis']
    return solve_member(section=torsion.section_for(current['input_data']),length_mm=4000.,
        E_MPa=record['E_MPa'],G_MPa=record['G_MPa'],actions=record['actions'],
        supports=record['support_hypotheses'],combination_id='QA',limit_state='ELU',
        member_id='PURLIN',action_accounting_origin='Current-combination QA')


def test_actual_combinations_and_all_40_uls_are_used(current):
    ev=a.preserved(current)
    assert ev['G81_computed_cases']==ev['H4_computed_cases']==40 and ev['pending_cases']==0
    assert [r['combination_id'] for r in ev['records']]==[c['combination']['id'] for c in current['cases'] if c['combination']['limit_state']=='ELU']
    assert ev['NBR_capacities_used'] is False and ev['whole_member_approved'] is False
    assert 'não são automaticamente' in ev['load_basis']
    assert ev['material']['E_MPa']==203000. and ev['analysis_material']['E_MPa']==182700.
    assert ev['original_analysis_material']['E_MPa']==200000.
    assert all(r['AISI_analysis']['source_combination']==next(c['combination'] for c in current['cases'] if c['combination']['id']==r['combination_id']) for r in ev['records'])


def test_g81_exact_first_yield_and_single_resistance_factor(current):
    c=current[a.FIELD]['bimoment_capacity'];s=torsion.section_for(current['input_data'])
    assert c['By_Nmm2']==pytest.approx(250.*s['properties']['Cw_mm6']/max(map(abs,s['omega_nodes_mm2'])))
    assert c['Ba_Nmm2']==.9*c['By_Nmm2']
    assert max(abs(c['By_Nmm2']*w/c['Cw_mm6']) for w in s['omega_nodes_mm2'])==pytest.approx(250.)
    assert c['Bp_required'] is False and c['Bcr_required'] is False


def test_nominal_strength_values_not_reduced_by_analysis_factor(current):
    ev=current[a.FIELD]
    assert ev['strong_flexural_capacity']['Ma_floor_Nmm']==pytest.approx(792540.7581669288)
    assert ev['weak_flexural_capacity']['web']['Ma_floor_Nmm']==pytest.approx(692901.4653543382)
    assert ev['weak_flexural_capacity']['lips']['Ma_floor_Nmm']==pytest.approx(375777.32129385107)
    assert ev['weak_flexural_capacity']['web']['F4_applicability']['mixed_field_waiver'] is False


@pytest.mark.parametrize('my,expected',[(10.,'lips'),(-10.,'web')])
def test_physical_weak_sign_not_fsm_sign(my,expected):
    state=dict(N_N=0.,Mx_physical_Nmm=0.,My_physical_Nmm=my,B_Nmm2=0.)
    caps={'web':20.,'lips':5.}
    assert a.h4_state(state,Max_Nmm=None,May_Nmm=caps,Ba_Nmm2=1.)['ratio']==abs(my)/caps[expected]


@pytest.mark.parametrize('n',[1.,-1.,1e-15])
def test_nonzero_axial_force_is_not_h4_n0(n):
    with pytest.raises(ValueError,match='N diferente'):
        a.h4_state(dict(N_N=n,Mx_physical_Nmm=0.,My_physical_Nmm=0.,B_Nmm2=0.),Max_Nmm=None,May_Nmm=None,Ba_Nmm2=1.)


def test_zero_demand_needs_no_missing_capacity():
    assert a.h4_state(dict(N_N=0.,Mx_physical_Nmm=0.,My_physical_Nmm=0.,B_Nmm2=2.),Max_Nmm=None,May_Nmm=None,Ba_Nmm2=4.)['ratio']==.5
    with pytest.raises(ValueError,match='ausente'):
        a.h4_state(dict(N_N=0.,Mx_physical_Nmm=1.,My_physical_Nmm=0.,B_Nmm2=0.),Max_Nmm=None,May_Nmm=None,Ba_Nmm2=4.)


def test_uniform_analysis_stiffness_factor_preserves_moments_and_bimoment(analysis):
    nominal=solve_member(section=analysis['section'],length_mm=4000.,E_MPa=203000.,G_MPa=78000.,
        actions=analysis['loads'],supports=analysis['support_hypotheses'],combination_id='QA',
        limit_state='ELU',member_id='PURLIN',action_accounting_origin='Nominal stiffness control')
    for i in range(len(analysis['elements'])):
        for u in (0.,.271,.5,1.):
            reduced=evaluate(analysis,i,u);full=evaluate(nominal,i,u)
            for field in ('Mx_physical_Nmm','My_physical_Nmm','B_Nmm2'):
                assert reduced[field]==pytest.approx(full[field],rel=2e-8,abs=1e-3)
            assert reduced['phi_rad']*.9==pytest.approx(full['phi_rad'],rel=2e-8,abs=1e-12)


def test_continuous_h4_envelope_matches_dense_independent_station_scan(analysis):
    caps=dict(Max_Nmm=792540.758,May_Nmm={'web':692901.465,'lips':375777.321},Ba_Nmm2=27996380.6369)
    env=a.h4_envelope(analysis,**caps)
    dense=max(a.h4_state(evaluate(analysis,i,float(u)),**caps)['ratio']
        for i in range(len(analysis['elements'])) for u in np.linspace(0,1,101))
    assert env['ratio']>=dense*(1-1e-12) and env['ratio']-dense<1e-4
    witness=env['witness']
    assert env['ratio']==pytest.approx(abs(witness['Mx_physical_Nmm'])/caps['Max_Nmm']+
        abs(witness['My_physical_Nmm'])/caps['May_Nmm']['web']+abs(witness['B_Nmm2'])/caps['Ba_Nmm2'])


def test_original_nbr_mechanics_and_torsion_snapshot_exact(current):
    base=family.calculate_reference(inputs())
    assert all(current[k]==v for k,v in base.items())
    source=current['torsion_evidence'];section=torsion.section_for(base['input_data'])
    dense=attach_torsion_evidence(base,section=section,load_lines=source['load_lines'],supports=source['supports'])
    expected=summarize_torsion_evidence(dense['torsion_evidence'])
    expected['choice_snapshot']=copy.deepcopy(base['input_data'][torsion.FIELD]);expected['scope_pt']=torsion.SCOPE
    assert current['torsion_evidence']==expected


def test_changed_current_actions_change_result_and_do_not_use_48_pp_controls(current):
    d=inputs();d['area_inputs']['permanent_kgf_m2']+=1.
    changed=complete_result(family.calculate_reference(d))
    assert changed[a.FIELD]['records'][0]['H4']['ratio']!=current[a.FIELD]['records'][0]['H4']['ratio']
    assert changed[a.FIELD]['source_input_fingerprint']!=current[a.FIELD]['source_input_fingerprint']


@pytest.mark.parametrize('mutation',['input','torsion','ratio','flag'])
def test_saved_snapshot_mutation_is_rejected(current,mutation):
    bad=copy.deepcopy(current)
    if mutation=='input':bad['input_data']['L_mm']+=1
    elif mutation=='torsion':bad['torsion_evidence']['records'][0]['analysis']['max_abs_phi']['phi_rad']+=1
    elif mutation=='ratio':bad[a.FIELD]['records'][0]['H4']['ratio']=0.
    else:bad[a.FIELD]['whole_member_approved']=True
    with pytest.raises(ValueError):a.preserved(bad)


def test_missing_lines_remain_specific_and_no_global_green():
    d=inputs();d[torsion.FIELD]['load_lines']={}
    result=complete_result(family.calculate_reference(d));ev=a.preserved(result)
    assert ev['G81_computed_cases']==ev['H4_computed_cases']==0 and ev['pending_cases']==40
    assert all(r['status']=='pending_demand' and r['missing'] for r in ev['records'])
    assert not result['whole_member_approved']


def test_capacity_can_be_shown_without_inventing_3d_bimoment():
    raw=family.calculate_reference(family.load_reference(1.5));raw['schema']='tercas_three_girt_results_v1'
    ev=a.finalize(raw)[a.FIELD]
    assert ev['bimoment_capacity']['Ba_Nmm2']>0 and ev['capacity_only']
    assert 'campo B requerido' in ev['reason'] and ev['records']==[]


def test_current_fy_recomputes_all_capacities_without_mutating_source():
    d=inputs();section=torsion.section_for(d)
    original=a._weak_capacities(d,section)[0]
    d['properties']['fy_MPa']=300.
    changed=a._weak_capacities(d,section)[0]
    assert changed['web']['Ma_floor_Nmm']!=original['web']['Ma_floor_Nmm']
    assert changed['lips']['M_esc_Nmm']==pytest.approx(1.2*original['lips']['M_esc_Nmm'])
    assert changed['web']['material']['Fy_MPa']==300.


def test_word_and_ui_render_saved_numbers_without_solving(current,monkeypatch):
    from tercas.aisi_torsion_ui import text_lines,rows
    from tercas.report import batch_word
    def forbidden(*args,**kwargs):raise AssertionError('Render/export must not solve')
    monkeypatch.setattr(a,'_aisi_demand',forbidden)
    before=copy.deepcopy(current)
    text='\n'.join(text_lines(a.preserved(current)))
    assert 'combinações LRFD AISI' in text and 'O fator de rigidez não é aplicado novamente' in text
    assert all('inconclusivo' in r['Parcela longitudinal'] for r in rows(current[a.FIELD]) if r['H4 Mx/Max + My/May + B/Ba']>1)
    doc=Document(BytesIO(batch_word(current)))
    words='\n'.join(p.text for p in doc.paragraphs)
    assert 'Verificação complementar de flexão e empenamento' in words and 'G8.1: By=' in words
    assert current==before


def test_historical_results_are_not_recalculated_or_added():
    old=family.calculate_reference(family.load_reference(1.5))
    assert a.preserved(old) is None


def test_frozen_research_and_weak_source_bytes_unchanged():
    from tercas.aisi_research.adapter import verify_bundle
    verify_bundle()
    root=Path(a.__file__).parent/'aisi_weak_sources'
    manifest=json.loads((root/'MANIFEST.json').read_text())
    assert hashlib.sha256((root/'MANIFEST.json').read_bytes()).hexdigest()=='f634a4809f1fbe97a93f973f0afecfd17b59eaa040f0689bce69740e40d5f835'
    assert all(hashlib.sha256((root/n).read_bytes()).hexdigest()==h for n,h in manifest['files'].items())


@pytest.mark.parametrize('L',[2999.,6001.])
def test_outside_capacity_span_keeps_g81(L):
    d=inputs();section=torsion.section_for(d);d['L_mm']=L
    assert a._strong_capacity(d,section)[0] is None
    assert a._weak_capacities(d,section)[0] is None
    assert a.g81_capacity(section,d['properties']['fy_MPa'])['Ba_Nmm2']>0


def test_t120_specific_capacity_absence_keeps_g81():
    from tercas import ue_reference
    d=ue_reference.load_reference();section=torsion.section_for(d)
    assert a._strong_capacity(d,section)[0] is None and a._weak_capacities(d,section)[0] is None
    assert a.g81_capacity(section,250.)['Ba_Nmm2']>0


def test_fy_outside_dsm_keeps_g81():
    d=inputs();section=torsion.section_for(d);d['properties']['fy_MPa']=656.
    assert a._strong_capacity(d,section)[0] is None and a._weak_capacities(d,section)[0] is None
    assert a.g81_capacity(section,656.)['Ba_Nmm2']>0


@pytest.mark.parametrize('n',[100.,-100.,True,False,None])
def test_separate_demand_cannot_erase_source_axial_force(analysis,n):
    bad=copy.deepcopy(analysis);bad['analysis_domain']['axial_force_in_this_model_N']=n
    with pytest.raises(ValueError):a._aisi_demand(bad)


def test_separate_demand_cannot_erase_state_axial_force(analysis):
    bad=copy.deepcopy(analysis);bad['critical_states'][0]['N_N']=1.
    with pytest.raises(ValueError):a._aisi_demand(bad)


@pytest.mark.parametrize('field',['NBR_design_check','physical_design_approved','whole_member_approved','NBR_capacities_used'])
def test_rehashed_false_approval_still_rejected(current,field):
    bad=copy.deepcopy(current);ev=bad[a.FIELD];ev[field]=True
    ev['snapshot_sha256']=a.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):a.preserved(bad)


@pytest.mark.parametrize('field',['load_basis','resistance_basis'])
def test_rehashed_changed_basis_still_rejected(current,field):
    bad=copy.deepcopy(current);ev=bad[a.FIELD];ev[field]='False reassignment'
    ev['snapshot_sha256']=a.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):a.preserved(bad)


def test_invalid_record_word_is_warning_not_false_numbers_or_export_crash(current):
    from tercas.aisi_torsion_ui import report
    bad=copy.deepcopy(current);bad['input_data']['project']='Changed'
    document=Document();report(document,bad)
    text='\n'.join(p.text for p in document.paragraphs)
    assert 'Registro do complemento AISI inválido' in text and 'Nenhum índice AISI' in text
    assert 'G8.1: By=' not in text
