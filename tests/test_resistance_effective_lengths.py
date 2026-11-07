"""Recovered scalar-only checks; not a claim that pre-loss tests cover new bytes."""
import copy
import json
import math
import types
from pathlib import Path
import pytest
from test_ue_catalog_nbr_weak_mle import data
from test_ue_catalog_nbr_weak_annex_e import reference_data
from tercas import resistance_effective_lengths as le
from tercas import ue_catalog_nbr_weak_annex_e as ae
from tercas import ue_catalog_nbr_weak_positive as positive


def declared_fields(data):
    out = copy.deepcopy(data)
    out.update(L_mm=4100.,weak_catalog={'Lx_mm':2050.},segments=[dict(
        start_mm=0.,end_mm=4100.,Ly_effective_mm=2050.,Lz_effective_mm=2050.,
        restraint_provenance='Synthetic declared resistance lengths; no physical supports')])
    return out


def test_independent_lengths_leave_all_other_inputs_unchanged(reference_data):
    before = copy.deepcopy(reference_data)
    d = le.declare(before,Lx_mm=2500.,Ly_mm=3000.,Lz_mm=4000.,origin='Synthetic hypothesis')
    assert before == reference_data
    assert {k:v for k,v in d.items() if k != le.FIELD} == before
    old, new = ae.qualify_reference(before), ae.qualify_reference(d)
    assert new['domain']['physical_span_mm'] == 5000.
    assert new['Nex_N'] == pytest.approx(old['Nex_N']*4)
    sec = new['section_constants']
    assert new['Nez_N'] == pytest.approx((77000*sec['J_mm4']+200000*sec['Cw_mm6']*(math.pi/4000)**2)/sec['r0_squared_mm2'])
    assert not new['actual_load_Me_qualified']
    assert new['real_action_applicability'] == 'not_assessed'
    assert ae.validate_saved(new,d) == new
    with pytest.raises(ValueError):ae.validate_saved(new,before)
    d[le.FIELD]['Ly_mm'] = 1234.
    assert ae.qualify_reference(d)['by_sign'] == new['by_sign']


@pytest.mark.parametrize('value',[0.,-1.,True,float('nan'),float('inf')])
def test_invalid_lengths(value):
    with pytest.raises(ValueError):
        le.declare({'L_mm':5000.},Lx_mm=value,Ly_mm=3000.,Lz_mm=4000.,origin='Synthetic')


def test_origin_required():
    with pytest.raises(ValueError):
        le.declare({'L_mm':5000.},Lx_mm=2500.,Ly_mm=3000.,Lz_mm=4000.,origin=' ')


def test_new_calculation_reads_existing_fields(reference_data):
    d = declared_fields(reference_data); before = copy.deepcopy(d)
    current = ae.qualify_reference(d)
    assert d == before
    assert current['domain']['physical_span_mm'] == 4100.
    assert current['domain']['Lx_used_mm'] == current['domain']['Lz_used_mm'] == 2050.
    historic = ae.qualify_reference(d,historical_span_policy=True)
    assert current['Nex_N'] == pytest.approx(4*historic['Nex_N'])
    assert ae.validate_saved(historic,d) == historic
    assert ae.validate_saved(current,d) == current


def test_positive_schema_dispatch(reference_data):
    d = declared_fields(reference_data)
    old = positive.qualify_reference(d,sign='positive',axial_force_N=0.,historical_span_policy=True)
    new = positive.qualify_reference(d,sign='positive',axial_force_N=0.)
    assert old['schema'] == positive.SCHEMA
    assert new['schema'] == positive.SCHEMA_EFFECTIVE
    assert old['domain']['Lx_used_mm'] == 4100.
    assert new['domain']['Lx_used_mm'] == 2050.
    assert positive.validate_saved(old,d) == old
    assert positive.validate_saved(new,d) == new


def test_flange_field_precedence(reference_data):
    d = declared_fields(reference_data);s = d['segments'][0]
    s.update(Ly_top_effective_mm=1234.,Ly_bottom_effective_mm=2345.)
    assert le.existing_declaration(d) is None
    s['Ly_bottom_effective_mm'] = 1234.
    assert le.existing_declaration(d)['Ly_mm'] == 1234.


def test_saved_note(reference_data):
    from tercas.resistance_effective_lengths_ui import saved_length_note
    cert = positive.qualify_reference(declared_fields(reference_data),sign='positive',axial_force_N=0.)
    note = saved_length_note({'source_section':{'weak_positive_reference':cert}})
    assert '2.050' in note or '2050' in note
    assert 'forte com altura continua usando o vão inteiro' in note
    assert saved_length_note({}) is None


def test_real_base_module_replay_bytes(reference_data):
    """Surviving git-show source, not current code's historical switch."""
    root = Path(__file__).parent/'fixtures/leff_baseline'
    modules = []
    for suffix in ('annex','positive'):
        path = root/(suffix+'_a5534ea.py')
        module = types.ModuleType('tercas._baseline_'+suffix)
        module.__package__ = 'tercas'
        exec(compile(path.read_text(),str(path),'exec'),module.__dict__)
        modules.append(module)
    modules[1].annex = modules[0]
    d = declared_fields(reference_data)
    original_annex = modules[0].qualify_reference(d)
    original_positive = modules[1].qualify_reference(d,sign='positive',axial_force_N=0.)
    canonical = lambda obj: json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False)
    assert canonical(ae.validate_saved(original_annex,d)) == canonical(original_annex)
    assert canonical(positive.validate_saved(original_positive,d)) == canonical(original_positive)
    assert original_annex['domain']['Lx_used_mm'] == 4100.
    assert ae.qualify_reference(d)['domain']['Lx_used_mm'] == 2050.
