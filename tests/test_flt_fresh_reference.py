"""Fresh selection of an existing reference, never migration or a new operator."""
import copy
import json
import pytest
from tercas import flt_height_effective as flt, ltb_load_height as ltb
from tercas import ue_catalog_reference as own, nbr_ue_family_application as app
from tercas import pierin_ue_registry as registry
from tercas.application import fingerprint
from test_flt_height_effective import data, uniform, point
from test_flt_combined_height import own_parallel_actions
from test_nbr_family_height_integration import source


def unmarked(index=26):
    return data(index, ly=4100., lz=4100.)


def result(index=26, length=4100.):
    r=source(index,Leff=length)
    r['input_data'].update(P_uls=500.,x_uls=1537.)
    r['input_fingerprint']=fingerprint(r['input_data'])
    return own.attach_source(r)


@pytest.mark.parametrize('index',registry.new_study_indices())
def test_fresh_unmarked_all66_same_defined_operator(index):
    d=unmarked(index);a=own_parallel_actions(d);before=copy.deepcopy((d,a))
    out=flt.qualify_family_fresh(d,a)
    assert out['schema']==flt.FRESH_SCHEMA and out['method']==flt.COMBINED_METHOD
    assert out['elastic_reference_eligible'] and out['numerical_critical']['numerically_converged']
    assert out['Me_Nmm']==out['numerical_critical']['Me_Nmm']
    assert out['authenticated_family_geometry']['action_positions_bound_to_same_contour']
    assert out['fresh_reference_selection']['input_method_marker'] is None
    assert not out['combined_method_declared']
    assert not out['fresh_reference_selection']['input_marker_added']
    assert not out['guaranteed_elastic_lower_bound'] and not out['physical_supports_created']
    assert not out['whole_member_approved'] and (d,a)==before


@pytest.mark.parametrize('ly,lz',[(2050.,2050.),(2050.,4100.),(4100.,2050.),(3000.,4100.)])
def test_short_lengths_still_use_floor_not_reinterpreted_solver(ly,lz,monkeypatch):
    monkeypatch.setattr(ltb,'refined',lambda **kw:pytest.fail('No effective-length solver'))
    d=data(ly=ly,lz=lz);a=[uniform(.7,50.),point()]
    out=flt.qualify_family_fresh(d,a)
    assert not out['elastic_reference_eligible'] and out['Me_Nmm'] is None
    from tercas.flt_height_energy_floor import qualify_family,POLICY_V2
    floor=qualify_family(d,a,method=POLICY_V2)
    assert floor['elastic_reference_eligible'] and floor['Me_lower_bound_Nmm']>0
    assert floor['Ly_used_mm']==ly and floor['Lz_used_mm']==lz


def test_pure_env_preserved_and_equivalent_factor_explained(monkeypatch):
    monkeypatch.setattr(ltb,'refined',lambda **kw:pytest.fail('Pure ENV must not solve'))
    d=data();a=[uniform(.7,50.)]
    legacy=flt.qualify_family(d,a);fresh=flt.qualify_family_fresh(d,a)
    assert fresh['method']==legacy['method']==flt.METHOD
    assert fresh['Me_Nmm']==legacy['Me_Nmm']
    assert fresh['C1']==legacy['C1'] and fresh['C2']==legacy['C2']
    assert 'equivalent kz/kw' in fresh['length_interpretation']
    assert 'proof or inference' in fresh['length_interpretation']
    assert flt.validate_saved(json.loads(json.dumps(legacy)),d,a)==legacy
    assert flt.validate_saved(json.loads(json.dumps(fresh)),d,a)==fresh


def test_explicit_v1_version_remains_explicit_and_pending():
    d=unmarked(53);d[flt.COMBINED_FIELD]=flt.LEGACY_COMBINED_METHOD
    out=flt.qualify_family_fresh(d,own_parallel_actions(d))
    assert out['method']==flt.LEGACY_COMBINED_METHOD
    assert not out['elastic_reference_eligible']
    assert out['fresh_reference_selection']['explicitly_declared_version_preserved']


@pytest.mark.parametrize('legacy_energy', [False,True])
def test_v3_v4_read_only_replay_stays_pending_without_marker(legacy_energy,monkeypatch):
    r=result();r[app.FIELD]=app._build(r,legacy_energy_floor=legacy_energy,legacy_height_selection=True)
    before=copy.deepcopy(r)
    monkeypatch.setattr(ltb,'refined',lambda **kw:pytest.fail('Historical replay cannot select Ritz'))
    assert app.preserved(json.loads(json.dumps(r)))==r[app.FIELD] and r==before
    assert not r[app.FIELD]['records'][0]['height_source']['elastic_reference_eligible']
    assert r[app.FIELD]['records'][0]['height_energy_floor']['resistance_floor_eligible']
    assert r[app.FIELD]['schema']==(app.LEGACY_SCHEMA_V3 if legacy_energy else app.LEGACY_SCHEMA_V4)


@pytest.mark.parametrize('index',[0,26,53,79])
def test_fresh_recalculation_uses_reference_capacity_and_same_actions(index):
    r=result(index);before=copy.deepcopy(r)
    old=app._build(r,legacy_height_selection=True)
    new=app.attach(r);packet=app.preserved(json.loads(json.dumps(new)))
    row=packet['records'][0]
    assert packet['schema']==app.SCHEMA and new['input_data']==r['input_data']
    assert row['height_source']['method']==flt.COMBINED_METHOD
    assert row['height_capacity']['eligible'] and row['height_capacity']['MRd_Nmm']>0
    assert row['height_energy_floor'] is None
    assert row['actions']==old['records'][0]['actions']
    assert row['combination']==old['records'][0]['combination'] and r==before
    from tercas.nbr_family_panorama import apply
    checks,binding=apply(new,[])
    assert checks and binding and not binding['whole_member_approved']


def test_nonconvergence_preserved_and_floor_not_falsely_promoted(monkeypatch):
    monkeypatch.setattr(ltb,'refined',lambda **kw:dict(numerically_converged=False,Me_Nmm=None,reason='Synthetic resolution exhausted'))
    r=app.attach(result());row=r[app.FIELD]['records'][0]
    assert row['height_source']['status']=='pending_numerical_qualification'
    assert row['height_source']['reason']=='Synthetic resolution exhausted'
    assert not row['height_capacity']['eligible']
    assert row['height_energy_floor']['resistance_floor_eligible']
    component=next(c for c in row['components'] if c['method']=='FLT_height_energy_floor')
    assert component['capacity_lower_bound_only'] and not component['failure_proven']
    assert component['floor_exceeded_means']=='inconclusive_not_failed'


def test_unexpected_error_and_bad_marker_are_not_hidden(monkeypatch):
    def broken(**kw):raise RuntimeError('Synthetic programming error')
    monkeypatch.setattr(ltb,'refined',broken)
    with pytest.raises(RuntimeError,match='programming error'):app.attach(result())
    d=unmarked();d[flt.COMBINED_FIELD]='invented'
    with pytest.raises(ValueError,match='não reconhecido'):flt.qualify_family_fresh(d,[uniform(.7,50.),point()])


def test_bad_parallel_geometry_and_destabilizing_projection_keep_guards():
    d=unmarked(53);a=own_parallel_actions(d);a[-1]['x_from_SC_mm']+=1
    assert not flt.qualify_family_fresh(d,a)['elastic_reference_eligible']
    a=own_parallel_actions(d);a[-1]['P_parallel_N']=-50.
    assert not flt.qualify_family_fresh(d,a)['elastic_reference_eligible']


@pytest.mark.parametrize('field',['selection','critical','schema'])
def test_rehashed_current_reference_is_replayed(field):
    d=unmarked();a=own_parallel_actions(d);out=flt.qualify_family_fresh(d,a)
    if field=='selection':out['fresh_reference_selection']['input_marker_added']=True
    elif field=='critical':out['Me_Nmm']*=2
    else:out['schema']='unknown'
    out['snapshot_sha256']=own.digest({k:v for k,v in out.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):flt.validate_saved(out,d,a)


def test_current_reference_and_resistance_keep_variable_material():
    r=result(26);d=r['input_data']
    d['properties'].update(E_MPa=210000.,G_MPa=81000.,fy_MPa=345.,fu_MPa=450.)
    d=own.activate(d);r['input_data']=d;r['input_fingerprint']=fingerprint(d)
    r=own.attach_source(r);packet=app.attach(r)[app.FIELD];row=packet['records'][0]
    binding=row['height_source']['source_binding']
    assert binding['material']==dict(E_MPa=210000.,G_MPa=81000.,fy_MPa=345.)
    assert row['height_capacity']['eligible']
    source_material=packet['sources']['own_rounded_contour']['source_binding']['material']
    assert all(source_material[k]==v for k,v in binding['material'].items())
    assert binding['nodes_sha256']==packet['sources']['own_rounded_contour']['source_binding']['nodes_sha256']
    assert flt.COMBINED_FIELD not in d
