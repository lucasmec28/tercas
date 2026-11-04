"""Integrated snapshots preserve mechanics and do not invent load lines."""
import copy
import json
import math
import pytest
from tercas import ue_family_reference as family, ue_reference as single
from tercas import torsion_study as torsion
from tercas.application import fingerprint
from tercas.deflection_scope import activate
from tercas.study_completion import complete_result


def data(t=1.5):
    return family.load_reference(t,4000.,5.) if t!=1.2 else single.load_reference(angle=5.)


def specified(d):
    d=copy.deepcopy(d);d[torsion.FIELD]=torsion.blank_choice()
    d[torsion.FIELD]['load_lines']={k:dict(declared=True,xy_from_CG_mm=[i*2.-3.,i-2.],
        origin='Synthetic independent line declaration, not a project') for i,k in enumerate(torsion.ROLES)}
    return d


def calculate(d):
    return family.calculate_reference(d) if family.claims_reference(d) else single.calculate_reference(d)


@pytest.mark.parametrize('t',[1.2,1.5,2.,2.25,2.65,3.,3.35])
def test_exact_own_contour_for_each_thickness(t):
    d=specified(data(t));s=torsion.section_for(d)
    assert s['thickness_mm']==t and len(s['nodes_xy_mm'])==209
    p=d['properties'];q=s['properties']
    for name,v in [('A_mm2',p['A_cm2']*100),('Ix_strong_mm4',p['Ix_cm4']*1e4),
                   ('Iy_weak_mm4',p['Iy_cm4']*1e4),('J_mm4',p['J_mm4']),('Cw_mm6',p['Cw_mm6'])]:
        assert math.isclose(q[name],v,rel_tol=2e-12)


def test_new_global_metadata_does_not_mutate_raw_mechanics():
    d=data();d.update(load_mode='direct');raw=calculate(d);before=copy.deepcopy(raw)
    out=complete_result(raw)
    assert raw==before
    assert all(out[k]==v for k,v in raw.items())
    assert not out['global_verification']['whole_member_approved']
    assert all(r['status']!='aprovado' for r in out['global_verification']['by_limit_state'].values())
    assert 'torsion_evidence' not in out


def test_missing_lines_are_pending_not_cg_or_zero():
    d=data();d[torsion.FIELD]=torsion.blank_choice();raw=calculate(d);out=complete_result(raw)
    assert all(out[k]==v for k,v in raw.items())
    ev=out['torsion_evidence']
    assert ev['computed_cases']==0 and ev['pending_model_cases']==58
    assert all(r['analysis'] is None for r in ev['records'])
    assert not ev['load_lines']


def test_declared_distinct_lines_concomitance_and_equilibrium():
    d=activate(specified(data()));raw=calculate(d);out=complete_result(raw)
    assert all(out[k]==v for k,v in raw.items())
    ev=out['torsion_evidence'];assert ev['computed_cases']==58 and ev['pending_model_cases']==0
    assert len(ev['records'])==len(raw['cases'])==58
    for row,case in zip(ev['records'],raw['cases']):
        assert row['combination_id']==case['combination']['id']
        a=row['analysis'];assert not a['resistance_qualified']
        assert a['analysis_domain']['order']==1
        assert abs(a['support_reactions']['torque_equilibrium_residual_Nmm'])<1e-3
        assert a['numerics']['relative_energy_error']<1e-8
        for field,env in a['field_envelopes'].items():
            if env:
                for kind,rec in env.items():
                    witness=a['witnesses'][rec['witness_index']]
                    assert witness[field]==rec['value']
                    assert witness['combination_id']==row['combination_id']
        if case['combination'].get('point_position')=='support_limit' and case['combination']['P_N']:
            assert a['support_limit_states'] and 'a->0+' in a['support_limit_states'][0]['position_limit']
    assert not out['whole_member_approved'] and not out['global_verification']['combined_ELS_approved']
    assert len(json.dumps(out,allow_nan=False))<4_000_000


def test_incomplete_declarations_remain_editable_and_pending():
    d=data();d[torsion.FIELD]=torsion.blank_choice()
    d[torsion.FIELD]['load_lines']['CP']=dict(declared=True,xy_from_CG_mm=[None,0.],origin='')
    assert family.assess(d)['calculable']
    out=complete_result(calculate(d))
    assert out['torsion_evidence']['pending_model_cases']==58


def test_choice_preserved_on_geometry_apply_and_json_roundtrip():
    d=activate(specified(data()));new=family.apply_geometry(d,3.35,4750.)
    assert new[torsion.FIELD]==d[torsion.FIELD]
    assert new['deflection_model']==d['deflection_model']
    assert family.assess(json.loads(json.dumps(new)))['calculable']
    assert new['properties']!=d['properties']


def test_direct_does_not_invent_decomposition_or_solve_area():
    d=specified(data());d['load_mode']='direct'
    out=complete_result(calculate(d));ev=out['torsion_evidence']
    assert ev['computed_cases']==0 and ev['records']==[] and 'diretas/3D' in ev['reason']


def test_stale_input_cannot_get_new_assessment():
    d=data();d['load_mode']='direct';raw=calculate(d);raw['input_data']['q_uls']+=.1
    with pytest.raises(ValueError,match='divergentes'):complete_result(raw)


@pytest.mark.parametrize('bad',[True,None,{},'Vlasov'])
def test_unknown_choice_never_silently_repaired(bad):
    d=data();d[torsion.FIELD]=bad
    assert not family.assess(d)['active']
    with pytest.raises(ValueError):torsion.configuration(d)


@pytest.mark.parametrize('bad',[True,float('nan'),float('inf'),'0'])
def test_invalid_offset_rejected(bad):
    d=specified(data());d[torsion.FIELD]['load_lines']['CP']['xy_from_CG_mm'][0]=bad
    assert not family.assess(d)['active']


def test_pp_cannot_be_moved_or_added_as_external_role():
    d=specified(data());d[torsion.FIELD]['load_lines']['PP']=dict(declared=True,xy_from_CG_mm=[10.,0.],origin='bad')
    with pytest.raises(ValueError):torsion.configuration(d)


def test_section_diagram_groups_coincident_lines_without_moving_points():
    import xml.etree.ElementTree as ET
    from tercas.torsion_study_ui import diagram
    d=data();s=torsion.section_for(d)
    records={role:dict(declared=True,xy_from_CG_mm=[0.,0.],origin='Synthetic QA') for role in torsion.ROLES}
    before=copy.deepcopy((s,records));svg=diagram(s,records);root=ET.fromstring(svg)
    assert len(root.findall('{http://www.w3.org/2000/svg}circle'))==2
    assert 'Pontos coincidentes declarados' in svg
    assert (s,records)==before
    assert all(role in svg for role in torsion.ROLES)


def test_section_diagram_preserves_distinct_points():
    import xml.etree.ElementTree as ET
    from tercas.torsion_study_ui import diagram
    d=specified(data());s=torsion.section_for(d)
    svg=diagram(s,d[torsion.FIELD]['load_lines']);root=ET.fromstring(svg)
    assert len(root.findall('{http://www.w3.org/2000/svg}circle'))==7
    assert 'Pontos coincidentes declarados' not in svg
