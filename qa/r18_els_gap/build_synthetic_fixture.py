"""Explicit fixture regeneration only. Runs ONE 32-element ELS solve.

Never imported by tests or readers. All loads and dimensions here are synthetic;
no user project or private source is read. Requires coordinated singlethread QA.
"""
import gzip
import json
from pathlib import Path


def build():
    from tercas import ue_family_reference as family, ue_catalog_reference as own
    from tercas import direct_self_weight as pp, direct_roof_separated as split
    from tercas import direct_torsion as direct, roof_top_load as roof
    from tercas import isolated_service_mechanics as mechanics
    from tercas.isolated_service_component import _dimensions
    from tercas.torsion_vlasov.vlasov import solve_member
    data = pp.activate(family.load_reference(1.5, 4000., 5.))
    data.update(load_mode='direct', catalog_index=19, q_uls=.7, q_sls=.6*.7,
        q_parallel_sls=.02, P_uls=0., P_sls=0., x_uls=1700., x_sls=1700.,
        roof_top_load=roof.choice('web_midplane'))
    data = own.activate(data)
    section = own.section_for(data)
    p = data['properties']
    combo = split.combinations(data)[1]
    demand = solve_member(section=section, length_mm=data['L_mm'], E_MPa=p['E_MPa'], G_MPa=p['G_MPa'],
        actions=direct.actions(combo, roof.geometry(data)),
        supports={side: dict(twist='fixed', warping='free_assumed',
            origin='Synthetic ideal fork, no connection design') for side in ('left', 'right')},
        combination_id=combo['id'], limit_state='ELS', member_id='SYNTHETIC_PURLIN',
        action_accounting_origin='Synthetic regression only; external at selected top and automatic PP once at CG',
        elements_per_interval=32)
    cfg = {'point_xy_from_CG_mm': [0., 0.], 'projection_xy': [0., -1.]}
    dims = _dimensions(data)
    check = mechanics.calculate(demand, dims, p['fy_MPa'], cfg, 1000.)
    assert check['gross_screen']['elastic_field_sufficient']
    assert not check['gross_screen']['gross_local_normal_sufficient']
    assert check['index_lower'] is None and check['index_upper'] is None
    return dict(schema='synthetic_service_gap_fixture_v1', synthetic_only=True,
        source_commit='23de0dd535bf71f863c2ca9e2fba3ef8fa5032be',
        recipe=dict(catalog_index=19, inclination_deg=5., physical_span_mm=4000.,
            q_external_normal_ELS_N_mm=.6*.7, q_external_parallel_ELS_N_mm=.02,
            PP_factor_ELS=1., PP_mass_kg_m=p['mass_kg_m'], top_line='web_midplane'),
        source_combination=combo, configuration=cfg, dimensions=dims,
        fy_MPa=p['fy_MPa'], limit_mm=1000., demand=demand, comparison=check)


if __name__ == '__main__':
    packet = build()
    path = Path(__file__).resolve().parents[2] / 'tests/fixtures/isolated_service_reduced_gap_synthetic.json.gz'
    raw = json.dumps(packet, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()
    path.write_bytes(gzip.compress(raw, mtime=0))
    print(path)
    print(json.dumps({k: packet['comparison'][k] for k in ('criterion_status', 'index_upper', 'stored_linear_twist_max_rad')}))
