"""Closed section identity, explicit length derivation and historical output."""
import copy
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import pytest
from docx import Document
from tercas.homogeneous_reference import (load_reference, source, assess, evidence,
    calculate_reference, FIELD as REFERENCE_FIELD, REPORTING_VERSION as FIXED_VERSION)
from tercas.homogeneous_lengths import (FIELD, VERSION, REPORTING_VERSION, apply_lengths,
    configuration, global_criticals, SPAN_ORIGIN)


def direct(ref='U125', L=4500., **kw):
    data=load_reference(ref,5)
    data.update(load_mode='direct',q_uls=.4,q_sls=.2,q_parallel_uls=.03,q_parallel_sls=.02,
                P_uls=120.,P_sls=70.,x_uls=600.,x_sls=700.)
    return apply_lengths(data,L_mm=L,**kw)


@pytest.mark.parametrize('ref',('U100','U125','U150'))
@pytest.mark.parametrize('angle',(0,5,-5))
def test_fixed_mode_stays_opt_in_and_does_not_acquire_length_fields(ref,angle):
    fixed=load_reference(ref,angle);before=copy.deepcopy(fixed)
    assert FIELD not in fixed and fixed['L_mm']==3000.
    assert evidence(fixed)['reporting_version']==FIXED_VERSION
    assert 'global_length_derivation' not in evidence(fixed)
    changed=apply_lengths(fixed,L_mm=6000.)
    assert fixed==before and changed[REFERENCE_FIELD]==fixed[REFERENCE_FIELD]
    changed.pop(REFERENCE_FIELD)
    assert assess(changed)['eligible'] and not assess(changed)['active']
    with pytest.raises(ValueError):calculate_reference(changed)
    with pytest.raises(ValueError):apply_lengths(source(ref),L_mm=6000.)


@pytest.mark.parametrize('ref',('U100','U125','U150'))
@pytest.mark.parametrize('L',(1000.,2000.,3000.,4500.,6000.,12000.))
def test_span_mode_updates_all_derivatives_and_preserves_section_and_actions(ref,L):
    original=load_reference(ref);before=copy.deepcopy(original)
    updated=apply_lengths(original,L_mm=L)
    assert original==before and assess(updated)['calculable']
    assert updated['L_mm']==L and updated['properties']==original['properties']
    changed={'L_mm','segments','support_origin','weak_axis','ELS_limit_mm','ELS_origin',FIELD}
    assert {k:v for k,v in updated.items() if k not in changed}=={k:v for k,v in original.items() if k not in changed}
    assert updated['ELS_limit_mm']==L/180.
    segment=updated['segments'][0]
    assert len(updated['segments'])==1 and segment['start_mm']==0 and segment['end_mm']==L
    assert segment['Ly_top_effective_mm']==segment['Ly_bottom_effective_mm']==segment['Lz_effective_mm']==L
    assert segment['Cb_mode']=='one'
    vals=global_criticals(updated)
    for sign in ('positive','negative'):
        old=original['weak_axis'][sign];new=updated['weak_axis'][sign]
        assert new['Nex_N']==vals['Nex_N'] and new['Nez_N']==vals['Nez_N']
        assert {k:v for k,v in old.items() if k not in ('Nex_N','Nez_N','provenance')}=={k:v for k,v in new.items() if k not in ('Nex_N','Nez_N','provenance')}
        assert new['Nex_N']==pytest.approx(old['Nex_N']*(3000/L)**2,rel=5e-15)
        if L!=3000.:assert new['Nex_N']!=old['Nex_N'] and new['Nez_N']!=old['Nez_N']
    assert json.loads(json.dumps(updated))==updated
    assert assess(json.loads(json.dumps(updated)))['calculable']
    assert apply_lengths(updated,L_mm=L)==updated
    record=evidence(updated)['global_length_derivation']
    assert record['all_effective_lengths_equal_span'] and not record['physical_restraints_verified']
    assert not record['new_supports_created_in_demand_model'] and not record['whole_member_approved']
    assert record['ELS_criteria']['area_down_limit_mm']==L/180
    assert record['ELS_criteria']['area_up_limit_mm']==L/120


def test_declared_modes_are_algebraic_and_do_not_change_whole_span_demands_or_deflection():
    full=direct(L=6000.);declared=apply_lengths(full,L_mm=6000.,mode='declared',
        Lx_mm=4000.,Ly_mm=3000.,Lz_mm=5000.,origin='Distâncias sintéticas declaradas para ensaio; sem arranjo físico validado.')
    first=calculate_reference(full);second=calculate_reference(declared)
    one=evidence(declared)['global_length_derivation']
    assert not one['all_effective_lengths_equal_span']
    assert 'aplicação algébrica' in one['interpretation']
    assert one['effective_lengths_mm']=={'Lx':4000.,'Ly':3000.,'Lz':5000.}
    assert second['ELS']==first['ELS']
    for state in ('ELU','ELS'):
        assert second['inclination_evidence'][state]['states']==first['inclination_evidence'][state]['states']
    assert second['FLT_segments']!=first['FLT_segments']
    assert second['inclination_evidence']['ELU']['weak_axis_capacities']!=first['inclination_evidence']['ELU']['weak_axis_capacities']
    assert second['input_data']==declared and second['whole_member_approved'] is False
    assert second['sheet_restraint_credit'] is False


@pytest.mark.parametrize('field',('L_mm','Lx_mm','Ly_mm','Lz_mm'))
@pytest.mark.parametrize('value',(None,True,False,0.,-1.,'3000',float('nan'),float('inf'),-float('inf')))
def test_bad_lengths_are_rejected_without_mutation(field,value):
    data=direct();before=copy.deepcopy(data)
    args=dict(L_mm=4500.,mode='declared',Lx_mm=4500.,Ly_mm=4500.,Lz_mm=4500.,origin='Teste')
    args[field]=value
    with pytest.raises((ValueError,ArithmeticError)):apply_lengths(data,**args)
    assert data==before


def mutations():
    yield 'old span',lambda d:d.update(L_mm=3000.)
    yield 'missing contract',lambda d:d.pop(FIELD)
    yield 'wrong schema',lambda d:d[FIELD].update(schema='other')
    yield 'empty origin',lambda d:d[FIELD].update(origin='')
    yield 'unrecorded origin',lambda d:d[FIELD].update(origin='another')
    yield 'Kx',lambda d:d[FIELD].update(Kx=.5)
    yield 'different declared length',lambda d:d[FIELD].update(Lx_effective_mm=2000.)
    yield 'bool L',lambda d:d.update(L_mm=True)
    yield 'segment end',lambda d:d['segments'][0].update(end_mm=3000.)
    yield 'segment Ly',lambda d:d['segments'][0].update(Ly_bottom_effective_mm=3501.)
    yield 'segment Lz',lambda d:d['segments'][0].update(Lz_effective_mm=3500.)
    yield 'segment Cb',lambda d:d['segments'][0].update(Cb_mode='auto')
    yield 'extra segment',lambda d:d['segments'].append(copy.deepcopy(d['segments'][0]))
    yield 'ELS old',lambda d:d.update(ELS_limit_mm=3000/180)
    yield 'ELS ratio',lambda d:d.update(ELS_down_denominator=200.)
    yield 'ELS origin',lambda d:d.update(ELS_origin='other')
    yield 'old support',lambda d:d.update(support_origin=source('U125')['support_origin'])
    yield 'unknown torque',lambda d:d.update(torque_Nmm=0.)
    yield 'catalogue mix',lambda d:d.update(weak_catalog={})
    yield '3D',lambda d:d.update(three_girt_model={'enabled':False})
    for key in source('U125')['properties']:
        yield 'property '+key,lambda d,key=key:d['properties'].__setitem__(key,math.nextafter(d['properties'][key],math.inf))
    for side in ('positive','negative'):
        for key in source('U125')['weak_axis'][side]:
            yield side+' '+key,lambda d,side=side,key=key:d['weak_axis'][side].__setitem__(key,'changed')
MUTATIONS=list(mutations())
@pytest.mark.parametrize('name,mutate',MUTATIONS,ids=[m[0] for m in MUTATIONS])
def test_changed_derivatives_or_frozen_physics_never_repaired_by_import_or_apply(name,mutate):
    data=direct(mode='declared',Lx_mm=4000.,Ly_mm=3500.,Lz_mm=4500.,origin='Teste sintético')
    mutate(data);before=copy.deepcopy(data)
    assert not assess(data)['eligible'],name
    with pytest.raises(ValueError):calculate_reference(data)
    with pytest.raises(ValueError):apply_lengths(data,L_mm=6000.)
    assert data==before


def test_absolute_point_load_coordinates_preserved_and_recoverable():
    data=direct();data.update(x_uls=3500.,x_sls=3900.,P_uls=200.,P_sls=-120.)
    smaller=apply_lengths(data,L_mm=2000.)
    assert smaller['x_uls']==3500. and smaller['x_sls']==3900.
    assert assess(smaller)['active'] and not assess(smaller)['calculable']
    with pytest.raises(ValueError):calculate_reference(smaller)
    smaller.update(x_uls=1600.,x_sls=1800.)
    assert assess(smaller)['calculable']
    assert smaller['P_uls']==200. and smaller['P_sls']==-120.
    assert calculate_reference(smaller)['input_data']==smaller
    smaller.update(load_mode='area',x_uls=3500.,x_sls=3900.)
    assert assess(smaller)['calculable']
    from tercas.batch import area_bundle
    bundle=area_bundle(smaller)
    centres=[c for c in bundle['combinations'] if c.get('point_position')=='center']
    assert centres and all(c['x_mm']==1000. for c in centres)
    assert smaller['x_uls']==3500. and smaller['x_sls']==3900.


def test_profile_change_removes_both_contracts_without_transferring_geometry():
    from tercas.catalog_scan import inputs_for_section
    data=direct();new=inputs_for_section(data,source('U150')['catalog_index'])
    assert FIELD not in new and REFERENCE_FIELD not in new
    assert 'Contorno próprio U125' not in new['property_origin']
    assert new['properties']!=data['properties']


def test_word_uses_recorded_length_evidence_and_leaves_historical_fixed_outputs_alone():
    from tercas.report import word
    result=calculate_reference(direct())
    saved=copy.deepcopy(result)
    # A stored result must not be recomputed or requalified while exporting.
    result['homogeneous_reference_evidence']['global_length_derivation']['origin']='ORIGEM HISTÓRICA REGISTRADA'
    before=copy.deepcopy(result)
    text='\n'.join(p.text for p in Document(BytesIO(word(result))).paragraphs)
    assert result==before and 'ORIGEM HISTÓRICA REGISTRADA' in text
    assert 'Vão e comprimentos de estabilidade' in text and 'não novas propriedades de seção' in text
    assert 'outputs/' not in text
    fixed=load_reference('U125',5);fixed['load_mode']='direct'
    old=calculate_reference(fixed);old_before=copy.deepcopy(old)
    old_text='\n'.join(p.text for p in Document(BytesIO(word(old))).paragraphs)
    assert 'Vão e comprimentos de estabilidade' not in old_text
    assert old==old_before and old['homogeneous_reference_evidence']['reporting_version']==FIXED_VERSION
    assert saved['homogeneous_reference_evidence']['reporting_version']==REPORTING_VERSION


ORACLE=json.loads((Path(__file__).parent/'data/homogeneous_lengths_oracle.json').read_text())
@pytest.mark.parametrize('row',ORACLE['records'],ids=lambda r:r['reference']+'_'+r['case'])
def test_independent_modal_or_algebraic_vectors_match_actual_backend(row):
    same=row['physical_equal_length_sine_mode']
    args={} if same else dict(mode='declared',origin='Vetor algébrico sintético independente, sem arranjo físico validado.',
        Lx_mm=row['Lx_mm'],Ly_mm=row['Ly_mm'],Lz_mm=row['Lz_mm'])
    data=direct(row['reference'],L=row['Lx_mm'] if same else 6000.,**args)
    values=global_criticals(data)
    for key,value in row['global_criticals'].items():assert values[key]==pytest.approx(value,rel=5e-13)
    result=calculate_reference(data)
    capacities=result['inclination_evidence']['ELU']['weak_axis_capacities']
    for sign in ('positive','negative'):
        assert capacities[sign]['annex_e']['Me_Nmm']==pytest.approx(row['directions']['weak_'+sign]['Me_matrix_Nmm'],rel=5e-13)
        assert capacities[sign]['MRd_Nmm']==pytest.approx(row['directions']['weak_'+sign]['MRd_Nmm'],rel=5e-13)
    strong=result['inclination_evidence']['ELU']['strong_capacity_Nmm']
    assert strong==pytest.approx(row['directions']['strong_positive']['MRd_Nmm'],rel=5e-13)
    assert strong==pytest.approx(row['directions']['strong_negative']['MRd_Nmm'],rel=5e-13)
    assert result['whole_member_approved'] is False

@pytest.mark.parametrize('value',(1e-250,1e250))
def test_stability_lengths_beyond_float_arithmetic_fail_without_partial_write(value):
    data=direct();before=copy.deepcopy(data)
    with pytest.raises((ValueError,ArithmeticError)):
        apply_lengths(data,L_mm=value)
    for field in ('Lx_mm','Ly_mm','Lz_mm'):
        args=dict(L_mm=4500.,mode='declared',Lx_mm=4500.,Ly_mm=4500.,Lz_mm=4500.,origin='Teste')
        args[field]=value
        with pytest.raises((ValueError,ArithmeticError)):apply_lengths(data,**args)
    assert data==before


def test_profile_adapter_does_not_transfer_own_origin_after_length_reference_exit():
    from tercas.catalog_scan import inputs_for_section
    data=apply_lengths(load_reference('U125'),L_mm=6000.)
    data.pop(REFERENCE_FIELD)
    before=copy.deepcopy(data)
    new=inputs_for_section(data,source('U150')['catalog_index'])
    assert data['property_origin'] not in new['property_origin']
    assert new['property_origin'].startswith('Geometria e propriedades seccionais do catálogo')
    assert FIELD not in new and REFERENCE_FIELD not in new
    assert new['properties']!=data['properties'] and data==before


def test_generic_catalog_scan_refuses_length_reference_even_after_opt_out():
    from tercas.catalog_scan import scan_catalog
    data=apply_lengths(load_reference('U125'),L_mm=6000.)
    data.pop(REFERENCE_FIELD)
    before=copy.deepcopy(data)
    with pytest.raises(ValueError,match='Referência própria'):
        scan_catalog(data,indices=[0])
    assert data==before
