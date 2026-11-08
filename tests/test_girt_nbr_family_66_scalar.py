"""R21 own-girt resistance consumer: 66 exact sources, no FE/EN/UI execution.

Connection coverage is not acceptance of loads, complete design, or proof of all
method branches. Pending components must retain their actual method guards.
"""
import copy
import math
import pytest
from test_wall_girt_own_isolated import data
from tercas import nbr_ue_family_application as app, nbr_ue_family as provider
from tercas import ue_catalog_reference as own, wall_girt_isolated as girt
from tercas.application import fingerprint
from tercas.pierin_ue_registry import new_study_indices
from tercas.resistance_effective_lengths import declare, configuration
from tercas.direct_roof_separated import combinations

INDICES=tuple(new_study_indices())


@pytest.fixture
def no_solvers(monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('Scalar family coverage invoked a solver/EN/roof geometry')
    from tercas import roof_top_load,ltb_load_height,direct_torsion
    from tercas.torsion_vlasov import vlasov
    from tercas.three_girt_warping import network
    from tercas import isolated_en_ue_family_application as en
    monkeypatch.setattr(roof_top_load,'geometry',forbidden)
    monkeypatch.setattr(ltb_load_height,'refined',forbidden)
    monkeypatch.setattr(direct_torsion,'solve_member',forbidden)
    monkeypatch.setattr(vlasov,'solve_member',forbidden)
    monkeypatch.setattr(network,'solve',forbidden)
    monkeypatch.setattr(en,'attach_dense',forbidden)


def scalar_source(index,*,weak_sign=1,custom_material=False):
    d=data(index)
    # Both axes carry actual nonzero moment. Zero P avoids invoking Ritz and
    # deliberately selects the existing uniform documentary height branch.
    d.update(q_uls=.02,q_parallel_uls=.4*weak_sign,P_uls=0.,P_parallel_uls=0.,P_sls=0.)
    if custom_material:
        d['properties'].update(fy_MPa=345.,fu_MPa=450.)
        d['steel_name']='Personalizado'
        d=own.activate(d)
    L=d['L_mm'];d=declare(d,Lx_mm=L,Ly_mm=L,Lz_mm=L,
                          origin='Synthetic full-span resistance assumptions; no new support')
    r=dict(input_data=d,input_fingerprint=fingerprint(d),schema='NBR14762_one_span_v1',
           model_domain_evidence=dict(status='fixed_model_domain',conflict=False))
    return own.attach_source(r)


def assert_connected(source,index):
    before=copy.deepcopy(source);d=source['input_data'];out=app.attach(source);ev=out[app.FIELD]
    assert source==before
    assert ev['schema']==app.GIRT_SCHEMA
    assert ev['pending_reason'] is None and len(ev['records'])==1
    assert ev['application_source_binding']==own.source_binding(d)
    assert ev['application_source_binding']['schema']==own.GIRT_SCHEMA
    assert ev['application_source_binding']['catalog_index']==index
    assert ev['physical_span_mm']==d['L_mm']
    assert ev['whole_member_approved'] is False
    row=ev['records'][0];combo=next(c for c in combinations(d) if c['limit_state']=='ELU')
    assert row['combination']==combo
    assert row['actions']==girt.height_actions(d,None,combo)
    bind=row['height_source']['girt_action_binding']
    assert bind['eligible'] and bind['source_binding']==own.source_binding(d)
    assert bind['member_application']=='wall_girt' and not bind['roof_geometry_used']
    assert not bind['physical_supports_created'] and not bind['whole_member_approved']
    assert row['height_source']['actions']==row['actions']
    assert row['height_source']['normal_projection_only']
    assert row['height_source']['individual_parallel_actions_present']
    # Compare with the same provider, exact index, declared material and
    # resistance lengths. Never use a named profile or another branch's value.
    material=dict(E_MPa=d['properties']['E_MPa'],G_MPa=d['properties']['G_MPa'],
                  fy_MPa=d['properties']['fy_MPa'],nu=.3,gamma=1.1)
    expected=provider.assess(index,L_mm=d['L_mm'],material=material,
        lengths=configuration(d),load_position=row['load_position_by_axis']['normal']['classification'])
    actual=ev['sources']['own_rounded_contour']
    assert actual==expected
    assert actual['source_binding']['nodes_sha256']==own.source_binding(d)['nodes_sha256']
    assert actual['source_binding']['material']==material
    components={c['method']:c for c in row['components'] if c['route']=='own_rounded_contour'}
    assert components['local']['demand']['Msd_Nmm']>0
    weak_demand=max(c['demand']['Msd_Nmm'] for name,c in components.items() if name.startswith('weak_'))
    assert weak_demand>0
    branch_map={name:expected['strong'][name] for name in ('local','distortional','FLT_reference')}
    branch_map.update({'weak_'+sign+'_'+method:branches[method]
        for sign,branches in expected['weak'].items() for method in ('local','distortional','FLT_reference')})
    for name,branch in branch_map.items():
        component=components[name]
        assert component['capacity_Nmm']==branch.get('MRd_Nmm'),(index,name)
        if component['index'] is None:
            assert component['reason'].strip(),(index,name,'silent pending gate')
            assert component['status']!='component_index'
        else:
            assert branch['eligible'] and math.isfinite(component['index']) and component['index']>=0
            if component['demand']['Msd_Nmm']>0:assert component['index']>0
        assert not component['whole_member_approved']
    return out


def test_family_inventory_is_66_complete_rows():
    assert len(INDICES)==66 and set((79,80,81,82)).issubset(INDICES)


@pytest.mark.parametrize('index',INDICES)
def test_all_66_girts_reach_source_bound_resistance_consumer(no_solvers,index):
    out=assert_connected(scalar_source(index),index)
    if index in (79,80,81,82):
        branch=out[app.FIELD]['sources']['own_rounded_contour']['strong']['local']
        assert branch['eligible'] and branch['status']=='computed_conventional_MLE'
        component=next(c for c in out[app.FIELD]['records'][0]['components']
                       if c['route']=='own_rounded_contour' and c['method']=='local')
        assert component['capacity_Nmm']>0


def test_index79_MLE_negative_weak_and_changed_material(no_solvers):
    out=assert_connected(scalar_source(79,weak_sign=-1,custom_material=True),79)
    ev=out[app.FIELD]
    assert ev['application_source_binding']['material']['fy_MPa']==345.
    local=ev['sources']['own_rounded_contour']['strong']['local']
    assert local['eligible'] and local['status']=='computed_conventional_MLE'
    weak=next(c for c in ev['records'][0]['components']
              if c['route']=='own_rounded_contour' and c['method']=='weak_negative_local')
    assert weak['demand']['Msd_Nmm']>0
