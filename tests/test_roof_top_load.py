"""Automatic roof model uses existing actions once and never grants strength."""
import copy
import json
import math
import pytest
from tercas import roof_top_load as roof
from tercas import ue_family_reference as family
from tercas.application import example,build_spec,calculate
from tercas.batch import calculate_batch
from tercas.study_completion import complete_result


def generic(angle=None):
    d=example();d['load_mode']='area';d['selected_types']=['ELS frequente']
    d['area_inputs'].update(permanent_kgf_m2=8.,live_kgf_m2=25.,wind_up_kgf_m2=100.,wind_down_kgf_m2=50.)
    d[roof.FIELD]=roof.choice();return d


def own(t=2.,angle=0.):
    d=family.load_reference(t,4000.,angle);d['selected_types']=['ELS quase permanente']
    d[roof.FIELD]=roof.choice();return d


def test_absent_and_disabled_leave_legacy_mechanics_unchanged():
    d=example();r=calculate(d);assert roof.attach(r)==r
    d[roof.FIELD]=dict(roof.choice(),enabled=False)
    assert build_spec(d)['route_domain']=='strong_symmetry_CT_no_primary_torsion'
    r=calculate(d);assert roof.attach(r)==r


@pytest.mark.parametrize('bad',[None,True,{},dict(roof.choice(),load_line='guessed'),dict(roof.choice(),enabled=1)])
def test_malformed_choice_rejected_without_repair(bad):
    d=generic();d[roof.FIELD]=bad;before=copy.deepcopy(d)
    with pytest.raises(ValueError):build_spec(d)
    assert d==before


def test_active_scheme_suppresses_legacy_ct_without_changing_saved_choice():
    d=generic();before=copy.deepcopy(d);spec=build_spec(d)
    assert spec['route_domain'] is None and d==before and d['route_domain'] is True
    r=calculate_batch(d)
    # All values from the original calculation are left as-is by the attachment.
    out=roof.attach(r)
    assert all(out[k]==v for k,v in r.items())
    ev=roof.preserved(out)
    assert ev['computed_cases']==6 and not ev['resistance_qualified']
    assert not ev['whole_member_approved'] and not out['whole_member_approved']
    assert ev['manual_effective_lengths_used'] is False
    assert ev['geometry']['x_from_SC_mm'] is None
    assert all(t['value'] is None for rec in ev['records'] for t in rec['primary_torque_by_action'])


def test_actions_keep_pp_at_cg_and_suction_sign_per_case():
    r=calculate_batch(generic());out=roof.attach(r);ev=roof.preserved(out)
    for record,combo in zip(ev['records'],r['load_bundle']['combinations']):
        actions=record['actions'];names=[a['name'] for a in actions]
        assert len(names)==len(set(names)) and names.count('PP')==1
        pp=next(a for a in actions if a['name']=='PP')
        assert pp['height_above_SC_mm']==0.
        assert math.isclose(pp['q_down_N_mm'],combo['coefficients']['PP']*r['load_bundle']['case_vectors_N_mm']['PP']['normal'])
        assert math.isclose(sum(a.get('q_down_N_mm',0.) for a in actions),combo['q_vector']['normal'])
        for a in actions:
            if a['name']!='PP':assert a['height_above_SC_mm']==50.
    assert any(a['name']=='V_Cima' and a['q_down_N_mm']<0 for record in ev['records'] for a in record['actions'])
    # Same force line with reversed force must reverse its height stiffness term.
    assert any(t['value']<0 for record in ev['records'] for t in record['height_tangent_by_action'])


@pytest.mark.parametrize('t',[1.5,2.,2.25,2.65,3.,3.35])
def test_own_source_coordinates_derive_from_one_contour(t):
    d=own(t);g=roof.geometry(d)
    assert g['coherent_torsion_section']
    assert math.isclose(g['height_above_SC_mm'],50.,abs_tol=1e-10)
    assert math.isclose(g['x_from_CG_mm'],-g['CG_xy_mm'][0])
    assert math.isclose(g['x_from_SC_mm'],-g['SC_xy_mm'][0])
    d[roof.FIELD]=roof.choice('flange_midwidth');g2=roof.geometry(d)
    assert math.isclose(g2['x_from_CG_mm']-g['x_from_CG_mm'],(50-t)/2)


def test_unknown_horizontal_eccentricity_is_not_zero_torque():
    from tercas.ltb_load_height import solve
    result=solve(L_mm=3000,E_MPa=200000,G_MPa=77000,Iweak_mm4=50000,J_mm4=500,Cw_mm6=1e8,
        actions=[dict(name='q',kind='uniform',q_down_N_mm=1,height_above_SC_mm=50,x_from_SC_mm=None)])
    assert result['Me_Nmm']>0 and result['primary_torque_by_action'][0]['value'] is None


def test_direct_envelope_does_not_decompose_or_add_self_weight():
    d=generic();d['load_mode']='direct';raw=calculate(d);out=roof.attach(raw)
    assert all(out[k]==v for k,v in raw.items())
    ev=roof.preserved(out);assert ev['computed_cases']==2
    assert ev['self_weight_added'] is False and ev['self_weight_quantity_assumed'] is False
    assert all(t['value'] is None for rec in ev['records'] for t in rec['primary_torque_by_action'])


def test_destabilizing_weak_axis_is_pending_and_preserves_actions():
    d=own(angle=-5.);r=family.calculate_reference(d);out=roof.attach(r)
    ev=roof.preserved(out);assert ev['computed_cases']==0
    assert all(rec['status']=='pending_biaxial_model' and rec['actions'] for rec in ev['records'])
    assert all(out[k]==v for k,v in r.items())


def test_full_own_pipeline_automatic_torsion_and_no_h4_ct_substitution():
    d=own();d['selected_types']=['ELU normal']
    from tercas.torsion_study import FIELD,blank_choice
    d[FIELD]=blank_choice();d[FIELD]['enabled']=False
    before=copy.deepcopy(d);r=family.calculate_reference(d);out=complete_result(r)
    assert d==before and out['input_data'][FIELD]['enabled'] is False
    ev=out['torsion_evidence'];assert ev['computed_cases']==40
    assert ev['load_line_choice_source']=='automatic_selected_roof_scheme'
    assert ev['stored_manual_choice_preserved']==d[FIELD]
    assert out['aisi_torsion_component']['H4_computed_cases']==40
    assert out['aisi_torsion_component']['G81_computed_cases']==40
    assert out['roof_top_load_evidence']['computed_cases']==40
    assert out['global_verification']['whole_member_approved'] is False
    assert all(rec['roof_height']['strong_capacity']['nominal_Mcre_recalculated'] for rec in out['aisi_torsion_component']['records'])
    assert all(rec['roof_height']['strong_capacity']['NBR_MRd_used'] is False for rec in out['aisi_torsion_component']['records'])
    json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('field',['input','record','combination','flag'])
def test_preserved_rejects_stale_or_tampered_without_recalculation(field,monkeypatch):
    out=roof.attach(calculate_batch(generic()))
    monkeypatch.setattr(roof,'refined',lambda **kwargs: (_ for _ in ()).throw(AssertionError('recalc')))
    assert roof.preserved(out)
    if field=='input':out['input_data']['L_mm']+=1
    if field=='record':out['roof_top_load_evidence']['records'][0]['Me_Nmm']+=1
    if field=='combination':out['cases'][0]['combination']['q_N_mm']+=1
    if field=='flag':out['roof_top_load_evidence']['resistance_qualified']=True
    with pytest.raises(ValueError):roof.preserved(out)


def test_legacy_render_does_not_create_evidence():
    r=calculate(example());before=copy.deepcopy(r)
    assert roof.preserved(r) is None and r==before


@pytest.mark.parametrize('t',[1.2,2.])
def test_own_report_identifies_ct_comparators_separately(t):
    from docx import Document
    from tercas import ue_reference as single
    module=single if t==1.2 else family
    d=single.load_reference(angle=0.) if t==1.2 else own(t)
    d[roof.FIELD]=roof.choice();d['selected_types']=['ELS quase permanente']
    r=module.calculate_reference(d);doc=Document();module.report(doc,r)
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Comparador da referência no CT' in text
    assert 'não são a resistência da carga no topo' in text
