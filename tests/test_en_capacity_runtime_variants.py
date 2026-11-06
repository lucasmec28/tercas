"""Exact audited OpenBLAS variants; no tolerance-based certificate admission."""
import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest
from tercas import en_simplified_interaction as core, isolated_en_mv as isolated, three_girt_en_mv as three
from tercas.en_interaction_capacity_reference import REFERENCES, QUALIFIED_CERTIFICATE_VARIANTS, qualified_reference
from tercas.three_girt_en_normal import en1993_normal_components as normal
from tercas.three_girt_en_normal.application import _transport_polynomials

ROOT = Path(__file__).parents[1]


def fixture(t):
    profile = json.loads((ROOT/f'tercas/data/torsion_profiles/ue100x50x17_t{t:.2f}.json').read_text())
    cert = json.loads((ROOT/f'tests/data/en_normal_haswell_t{t:.2f}.json').read_text())
    return profile, cert


def seal(value):
    value['content_sha256'] = core._sha({k:v for k,v in value.items() if k!='content_sha256'})


@pytest.mark.parametrize('t', [1.2, 3.0])
def test_audited_complete_variant_rederives_all_six_unchanged_floors(t):
    profile, cert = fixture(t)
    before = copy.deepcopy(REFERENCES)
    normal.verify_component_sections(cert)
    assert cert['content_sha256'] in QUALIFIED_CERTIFICATE_VARIANTS[t]
    cap = core.capacities(profile, cert)
    assert cap['component_sections_sha256'] == cert['content_sha256']
    assert {k:v for k,v in cap.items() if k!='component_sections_sha256'} == {
        k:v for k,v in REFERENCES[t].items() if k!='component_sections_sha256'}
    # Independent endpoint/face first-yield arithmetic, not ULS normalization.
    nodes = np.array(profile['nodes_xy_mm']); delta = np.diff(nodes, axis=0)
    face_normal = np.column_stack([-delta[:,1],delta[:,0]])/np.linalg.norm(delta,axis=1)[:,None]
    points = np.concatenate([nodes[:-1]+side*t/2*face_normal for side in (-1,0,1)] +
                            [nodes[1:]+side*t/2*face_normal for side in (-1,0,1)])
    points -= cert['gross_properties']['centroid_xy_mm']
    for name, floor in cap['signed_capacity_floor'].items():
        coeff = np.array(cert['components'][name]['sigma_coefficients_c0_cx_cy'])
        assert floor == math.floor(250./np.max(np.abs(coeff[0]+points@coeff[1:])))
    cap['signed_capacity_floor']['Mx_positive'] = 0
    assert REFERENCES == before


@pytest.mark.parametrize('t', [1.2, 3.0])
@pytest.mark.parametrize('mutation', ['coefficient', 'material', 'eligibility', 'audit', 'nodes'])
def test_rehashed_unknown_certificate_rejected_even_with_same_capacity_floors(t, mutation):
    profile, cert = fixture(t)
    if mutation == 'coefficient':
        old = cert['components']['N_tension']['sigma_coefficients_c0_cx_cy'][0]
        new = math.nextafter(old, math.inf)
        # This 1-ULP corruption would pass a floor-only admission rule.
        assert math.floor(250./old) == math.floor(250./new)
        cert['components']['N_tension']['sigma_coefficients_c0_cx_cy'][0] = new
    elif mutation == 'material': cert['material']['fyb_MPa'] = 350.
    elif mutation == 'eligibility': cert['components']['N_tension']['eligible'] = False
    elif mutation == 'audit': cert['components']['Mx_positive']['ULS_pure_effort_signed'] += 1.
    else: cert['nodes_sha256'] = '0'*64
    seal(cert)
    normal.verify_component_sections(cert)  # A self-hash alone is insufficient.
    with pytest.raises(ValueError, match='referência resistente'):
        core.capacities(profile, cert)


@pytest.mark.parametrize('t', [1.2, 3.0])
def test_geometry_binding_and_hash_qualification_are_not_transferable(t):
    profile, cert = fixture(t)
    profile['geometry_identity']['nodes_canonical_sha256'] = '0'*64
    with pytest.raises(ValueError): core.capacities(profile, cert)
    other = 3.0 if t==1.2 else 1.2
    with pytest.raises(ValueError): qualified_reference(other, cert['content_sha256'])
    with pytest.raises(ValueError): qualified_reference(t, '0'*64)


def three_snapshot(t):
    profile, cert = fixture(t); cap = core.capacities(profile,cert)
    fields = dict(N=[-300.],Mx=[1e5,3e5,-3e5],My=[-3e4,4e4,-4e4])
    _, transport = _transport_polynomials(fields,cert)
    beam = dict(id='middle:0',girt='middle',length_mm=4000.,
        normal_action_polynomials=dict(N_N=fields['N'],My_strong_Nmm=[-x for x in fields['Mx']],
                                       Mz_weak_Nmm=[-x for x in fields['My']]))
    case = dict(combination=dict(id='QA',limit_state='ELU'),model=dict(beams=[beam]))
    demand = dict(cases=[case],input_data=dict(properties=dict(h=100.,bf=50.,lip=17.,t=t,ri_mm=t,fy_MPa=250.)))
    row = dict(combination_id='QA',girt='middle',segment_id='middle:0',normal_action_reference=transport)
    row['EN_bending_shear_component'] = three.calculate_row(demand,case,beam,row,cap,cap['shear_capacity_lower_N']['strong'])
    source = dict(component_sections=cert,rows=[row],EN_bending_shear_schema=three.COLLECTION_SCHEMA)
    return source,demand


@pytest.mark.parametrize('t', [1.2,3.0])
def test_three_saved_read_no_rebuild_and_known_hash_substitution_rejected(t,monkeypatch):
    source,demand = three_snapshot(t)
    before = copy.deepcopy(source)
    def forbidden(*args,**kwargs): raise AssertionError('Saved read must not rebuild')
    monkeypatch.setattr(core,'capacities',forbidden)
    monkeypatch.setattr(normal,'build_component_sections',forbidden)
    monkeypatch.setattr(three,'prepare',forbidden)
    monkeypatch.setattr(three,'calculate_row',forbidden)
    three.validate_component(source,demand)
    assert source == before
    out = source['rows'][0]['EN_bending_shear_component']
    out['capacity_reference'] = copy.deepcopy(REFERENCES[t]);seal(out)
    three.validate_internal(out)  # Each variant is qualified, but NOT interchangeable.
    with pytest.raises(ValueError,match='mesma barra/seção/caso'):
        three.validate_component(source,demand)


def isolated_snapshot(t):
    _, cert = fixture(t);cap = qualified_reference(t,cert['content_sha256'])
    source = dict(kind='element',element_id='e0',a_mm=0.,b_mm=100.)
    controls = []
    for j in range(3):
        intervals = {k:([-1e-320,1e-320] if k=='N' else [-1e-300,1e-300]) for k in core.ACTIONS}
        controls.append(dict(control=j,intervals=intervals,is_physical_state=False,
            **core.objective(intervals,cap,cap['shear_capacity_lower_N']['strong'])))
    maximum=max(c['index_upper'] for c in controls);shear=max(c['shear_ratio_upper'] for c in controls)
    verdict=core.verdict(maximum,shear,weak_zero=True,torsion_zero=True)
    piece=dict(source_piece=source,controls=controls,index_upper=maximum,shear_ratio_upper=shear,**verdict)
    out=dict(schema=isolated.SCHEMA,algorithm_schema=core.SCHEMA,source=core.SOURCE,scope=core.SCOPE,
        source_demand_sha256='a'*64,source_geometry_sha256=cert['nodes_sha256'],combination_id='QA',member_id='P',
        capacity_reference=cap,web_capacity_lower_N=cap['shear_capacity_lower_N']['strong'],pieces=[piece],
        full_member_field_covered=True,index_upper=maximum,shear_ratio_upper=shear,
        method='Concurrent degree-two Bernstein controls; signed-capacity minima; Mf/Mpl=0',
        normal_actions='N=0; physical Mx/My retained without total-stress cancellation; B checked separately by EN6.1.6',
        **verdict,**{k:False for k in core.FLAGS})
    seal(out)
    web=dict(capacity=dict(Vw_Rd_lower_N=out['web_capacity_lower_N']),pieces=[dict(source_piece=source,Vweb_end_intervals_N=[[0.,0.],[0.,0.]])])
    row=dict(source_analysis_sha256='a'*64,combination_id='QA',check=dict(component_sections_sha256=cert['content_sha256']))
    summary=dict(schema='saved_summary',member_id='P',section=dict(nodes_sha256=cert['nodes_sha256']),
        loads=[],support_reactions=dict(left_force_xy_N=[0.,0.]),witnesses=[],field_envelopes={
            k:{e:dict(value=0.) for e in ('minimum','maximum','maximum_absolute')}
            for k in ('B_Nmm2','Tsv_Nmm','Tw_Nmm','Mx_physical_Nmm','My_physical_Nmm','Vy_N','Vx_N')})
    return out,web,row,summary,dict(source_profile=dict(thickness_mm=t))


@pytest.mark.parametrize('t', [1.2,3.0])
def test_isolated_saved_read_no_rebuild_and_known_hash_substitution_rejected(t,monkeypatch):
    args=isolated_snapshot(t);before=copy.deepcopy(args)
    def forbidden(*args,**kwargs):raise AssertionError('Saved read must not rebuild')
    monkeypatch.setattr(core,'capacities',forbidden)
    monkeypatch.setattr(normal,'build_component_sections',forbidden)
    monkeypatch.setattr(isolated,'calculate',forbidden)
    isolated.validate_saved(*args)
    assert args==before
    args[0]['capacity_reference']=copy.deepcopy(REFERENCES[t]);seal(args[0])
    with pytest.raises(ValueError,match='Snapshot M–V EN incompatível'):
        isolated.validate_saved(*args)


def test_original_references_remain_exactly_selectable_without_new_fields():
    for t,ref in REFERENCES.items():
        assert qualified_reference(t,ref['component_sections_sha256'])==ref
    assert set(QUALIFIED_CERTIFICATE_VARIANTS)=={1.2,3.0}
    assert sum(map(len,QUALIFIED_CERTIFICATE_VARIANTS.values()))==2
