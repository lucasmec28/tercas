"""Lightweight saved-coordinate checks, no section reconstruction or LBA."""
import copy
import json
from pathlib import Path
import pytest
from tercas.roof_biaxial_geometry import ANCHORS,validate_geometry
from tercas import roof_top_load as roof,direct_roof_separated as separated,roof_biaxial as biaxial


@pytest.mark.parametrize('t',list(ANCHORS))
@pytest.mark.parametrize('line',['web_midplane','flange_midwidth'])
def test_pinned_coordinates_all_seven_sources_both_lines(t,line):
    a=ANCHORS[t];x=0. if line=='web_midplane' else (50.-t)/2;y=100.-t/2
    g=dict(coherent_torsion_section=True,section_profile_id=a['profile_id'],nodes_sha256=a['nodes_sha256'],
        CG_xy_mm=a['CG_xy_mm'],SC_xy_mm=a['SC_xy_mm'],h_mm=100.,bf_mm=50.,t_mm=t,
        load_line=line,load_x_from_web_midplane_mm=x,web_midplane_to_flange_midwidth_mm=(50.-t)/2,
        height_above_SC_mm=y-a['SC_xy_mm'][1],x_from_CG_mm=x-a['CG_xy_mm'][0],
        y_from_CG_mm=y-a['CG_xy_mm'][1],x_from_SC_mm=x-a['SC_xy_mm'][0])
    d=dict(properties=dict(h=100.,bf=50.,t=t),roof_top_load=dict(load_line=line))
    validate_geometry(g,d)
    g['SC_xy_mm']=[100.,g['SC_xy_mm'][1]];g['x_from_SC_mm']=x-100.
    with pytest.raises(ValueError):validate_geometry(g,d)


def test_anchors_match_exact_frozen_source_files_without_reconstructing():
    import hashlib
    root=Path(__file__).resolve().parents[1]/'tercas/data/torsion_profiles'
    for t,a in ANCHORS.items():
        raw=(root/f'ue100x50x17_t{t:.2f}.json').read_bytes();p=json.loads(raw)
        assert hashlib.sha256(raw).hexdigest()==a['source_file_sha256']
        assert p['profile_id']==a['profile_id']
        assert p['geometry_identity']['nodes_canonical_sha256']==a['nodes_sha256']
        assert p['own_properties']['centroid_xy_mm']==a['CG_xy_mm']
        assert p['own_properties']['shear_center_xy_mm']==a['SC_xy_mm']


def test_other_coherent_catalogue_contour_is_controlled_pending_not_exception():
    g=dict(coherent_torsion_section=True,section_profile_id='NEW_CATALOGUE_Ue83',
        nodes_sha256='different-contour',t_mm=2.,CG_xy_mm=[17.,49.],SC_xy_mm=[-25.,49.])
    acts=[dict(name='PP',kind='uniform',q_down_N_mm=.1,q_parallel_N_mm=.01,
        x_from_SC_mm=42.,height_above_SC_mm=0.)]
    assert biaxial.classify(acts,g)['applicable']
    scoped=biaxial.classify_for_roof(acts,g)
    assert not scoped['applicable'] and 'Não é proibição normativa' in scoped['reason']


def saved_negative():
    return json.loads((Path(__file__).parent/'fixtures/roof_axis_negative5_reader.json').read_text())


def resign_geometry(r):
    ev=r['roof_top_load_evidence']
    for row,combo in zip(ev['records'],roof.combination_inventory(r)):
        row['actions']=separated.actions(combo,ev['geometry'],include_parallel=True)[0]
        row['separate_axis_capacity_scope']=biaxial.classify_for_roof(row['actions'],ev['geometry'])
    ev['snapshot_sha256']=roof.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})


def test_reader_rejects_coherently_resigned_false_stabilizing_SC():
    r=saved_negative();assert roof.preserved(r)
    g=r['roof_top_load_evidence']['geometry']
    g['SC_xy_mm'][0]=100.;g['x_from_SC_mm']=g['load_x_from_web_midplane_mm']-100.
    resign_geometry(r)
    assert all(x['separate_axis_capacity_scope']['applicable'] for x in r['roof_top_load_evidence']['records'])
    with pytest.raises(ValueError,match='CG/CT'):roof.preserved(r)


@pytest.mark.parametrize('mutation',['CG','height','load_x','dimensions','identity'])
def test_reader_rejects_other_coherent_coordinate_mutations(mutation):
    r=saved_negative();g=r['roof_top_load_evidence']['geometry']
    if mutation=='CG':
        g['CG_xy_mm'][0]=-100.;g['x_from_CG_mm']=g['load_x_from_web_midplane_mm']+100.
    elif mutation=='height':g['height_above_SC_mm']+=1.
    elif mutation=='load_x':g['load_x_from_web_midplane_mm']+=1.
    elif mutation=='dimensions':g['h_mm']+=1.
    else:g['t_mm']=1.5  # Unrecognized identity must never preserve an active capacity.
    resign_geometry(r)
    if mutation=='identity':r['roof_top_load_evidence']['records'][0]['Me_Nmm']=1.;resign_geometry(r)
    with pytest.raises(ValueError):roof.preserved(r)


def test_pending_other_catalogue_contour_survives_reader_without_promoting():
    r=saved_negative();g=r['roof_top_load_evidence']['geometry']
    g.update(section_profile_id='NEW_CATALOGUE_Ue83',nodes_sha256='different-contour')
    resign_geometry(r)
    ev=roof.preserved(r)
    assert all(x['Me_Nmm'] is None and not x['separate_axis_capacity_scope']['applicable'] for x in ev['records'])
    assert all('Não é proibição normativa' in x['separate_axis_capacity_scope']['reason'] for x in ev['records'])


def test_geometry_reader_never_reopens_sources_or_calls_solver(monkeypatch):
    r=saved_negative();before=copy.deepcopy(r)
    from tercas import torsion_study
    from tercas.application import fingerprint
    def fail(*a,**k):raise AssertionError('Reader tried to reconstruct or reopen a source')
    monkeypatch.setattr(roof,'refined',fail);monkeypatch.setattr(roof,'geometry',fail)
    monkeypatch.setattr(torsion_study,'section_for',fail)
    monkeypatch.setattr(Path,'read_bytes',fail);monkeypatch.setattr(Path,'read_text',fail)
    assert roof.preserved(r)
    assert r==before


@pytest.mark.parametrize('catalog',[False,True])
@pytest.mark.parametrize('identity',['unknown_id','wrong_limit_state','duplicate'])
def test_rehashed_axis_record_identity_is_controlled_reader_error(catalog,identity,monkeypatch):
    """Read-only malformed area snapshots, using a public synthetic fixture."""
    from tercas.application import fingerprint
    r=saved_negative();ev=r['roof_top_load_evidence']
    combos=copy.deepcopy(roof.combination_inventory(r))
    r['schema']='tercas_batch_results_v1';r['input_data']['load_mode']='area'
    if catalog:r['input_data']['ue_catalog_reference']={}
    r['load_bundle']={'combinations':combos};r['cases']=[{'combination':c} for c in combos]
    ev['schema']='roof_top_load_evidence_v1'
    if identity=='unknown_id':ev['records'][0]['combination_id']='UNKNOWN'
    elif identity=='wrong_limit_state':ev['records'][0]['limit_state']='UNKNOWN'
    else:combos.append(copy.deepcopy(combos[0]));r['cases'].append({'combination':combos[-1]})
    r['input_fingerprint']=fingerprint(r['input_data']);ev['source_input_fingerprint']=r['input_fingerprint']
    ev['source_load_snapshot_sha256']=roof._source_snapshot(r,ev['schema'])
    ev['snapshot_sha256']=roof.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    def fail(*a,**k):raise AssertionError('Reader must not invoke solver/source')
    monkeypatch.setattr(roof,'refined',fail);monkeypatch.setattr(roof,'geometry',fail)
    with pytest.raises(ValueError,match='combinação única'):roof.preserved(r)
