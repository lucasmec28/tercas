import copy
import json
import math
from io import BytesIO
from pathlib import Path
import pytest
from docx import Document
from tercas.ue_family_reference import apply_geometry
from tercas.three_girt_warping.application import calculate as solve,current_configuration,attach_g81
from tercas.three_girt_en_normal import application as a
from tercas.three_girt_axial import application as nbr

FIXTURE=Path(__file__).parent/'data'/'three_girt_normal_QA_input.json'


def demand_for(t=2.65):
    source=json.loads(FIXTURE.read_text())
    if t==1.2:
        from tercas import ue_reference
        from tercas.ue_member_application import apply,editable
        data=apply(ue_reference.load_reference(angle=source['input_data']['inclination']['value'],L_mm=4000.),'wall_girt')
        for key in ue_reference.EDITABLE | editable(data):
            if key in source['input_data']:data[key]=copy.deepcopy(source['input_data'][key])
    else:
        data=apply_geometry(source['input_data'],t,4000.)
    data['project']=f'Synthetic EN normal QA t={t}; not a physical design'
    return attach_g81(solve(data,current_configuration(data,source['configuration']['three_girt'])))


def config(demand):
    c=a.reference_configuration(demand)
    c.update(intact_section_model_declared=True,section_model_origin='Synthetic QA intact nominal section')
    return c

@pytest.fixture(scope='module')
def demand():return demand_for()

@pytest.fixture(scope='module')
def result(demand):return a.calculate(demand,config(demand))


def test_current_case_closes_all_signed_integral_sections_without_global_approval(demand,result):
    assert len(result['rows'])==108
    assert result['ELU_combinations']==12 and result['ELS_combinations_excluded']==7
    assert result['section_fibers_checked']==832
    assert all(result[k] is False for k in a.FALSE_FLAGS)
    assert result['resistance_material_E_MPa']==210000 and result['demand_material_E_MPa']==200000
    for item in result['per_member'].values():
        assert item['complete'] is True and item['complete_envelope'] is not None
        assert item['partial_maximum'] is None
        assert item['blocking_components']==[]
    assert result['per_member']['middle']['complete_envelope']['concomitant_7DOF_state']['N_N']!=0


def test_witness_recomposition_at_same_exterior_fiber(result):
    props=result['component_sections']['gross_properties']
    for row in result['rows']:
        for piece in row['pieces']:
            if not piece['complete']:
                assert piece['maximum_absolute'] is None
                continue
            w=piece['maximum_absolute']
            if w is None:
                assert piece['normal']['index_lower_witness'] is None
                assert piece['normal']['index_upper_bound'] is not None
                assert piece['normal']['criterion']!='above_1_at_concomitant_state'
                continue
            s=w['concomitant_7DOF_state'];x,y=w['section_fiber']['fiber_xy_relative_to_gross_CG_mm']
            physical=s['N_N']/props['A_mm2']-s['My_strong_Nmm']*y/props['Ix_strong_mm4']+s['Mz_weak_Nmm']*x/props['Iy_weak_mm4']+w['stress_contributions_MPa']['B']
            assert physical==pytest.approx(w['sigma_MPa'],abs=2e-7)
            assert sum(w['stress_contributions_MPa'].values())==pytest.approx(w['sigma_MPa'],abs=2e-7)
            assert row['x_start_mm']<=w['x_mm']<=row['x_end_mm']
            assert s['x_mm']==w['x_mm']
            assert w['section_fiber']['thickness_face_sign'] in (-1,1)


def test_no_network_or_NBR_capacity_calculation(demand,monkeypatch):
    from tercas.three_girt_warping import network
    def forbidden(*args,**kwargs):raise AssertionError('Not part of the EN normal calculation')
    monkeypatch.setattr(network,'solve',forbidden)
    monkeypatch.setattr(nbr,'_capacities',forbidden)
    assert a.calculate(demand,config(demand))['schema']==a.SCHEMA


@pytest.mark.parametrize('t',[1.2,1.5])
def test_thin_effective_sections_and_complete_bending_coverage(t):
    d=demand_for(t);r=a.calculate(d,config(d))
    certificate=r['component_sections']['components']
    assert certificate['N_compression']['eligible'] is True
    assert certificate['N_compression']['moment_transport_required']
    assert certificate['N_compression']['sigma_coefficients_c0_cx_cy'][1:]==[0.,0.]
    assert 'N_compression' not in r['per_member']['middle']['blocking_components']
    assert all(record['eligible'] for record in certificate.values())
    assert certificate['My_negative']['section_status']=='effective_web_reduced_negative_My_ULS'
    assert all(item['complete'] and not item['blocking_components'] for item in r['per_member'].values())
    for item in r['per_member'].values():
        normal=item['normal'];lo=normal['index_lower_witness'];up=normal['index_upper_bound']
        assert up is not None and (lo is None or up>=lo)
        assert normal['criterion'] in ('within_1_by_full_interval_upper_bound','above_1_at_concomitant_state','unresolved_numerical_bound')
    if t==1.2:
        for name in ('Mx_positive','Mx_negative'):
            record=certificate[name]
            assert record['section_status']=='effective_local_flange_reduced_pure_Mx_ULS'
            assert record['effective_properties']['Ixy_mm4']!=0.
            assert record['sigma_coefficients_c0_cx_cy'][0]!=0.
            assert record['sigma_coefficients_c0_cx_cy'][1]!=0.
            assert not record['moment_transport_required']
    # Recompose every physical normal witness from its actual corrected signs,
    # including both c0 and Ixy-induced cx in the newly qualified Mx branches.
    checked=0
    for row in r['rows']:
        for piece in row['pieces']:
            w=piece['normal']['witness']
            if w is None:continue
            actions=w['normal_action_reference']['corrected_actions_R01']
            x,y=w['section_fiber']['fiber_xy_relative_to_gross_CG_mm']
            total=w['stress_contributions_MPa']['B']
            for axis,value in actions.items():
                if value==0.:
                    assert w['stress_contributions_MPa'][axis]==0.
                    continue
                record=certificate[a._component_key(axis,1 if value>0 else -1)]
                c0,cx,cy=record['sigma_coefficients_c0_cx_cy']
                contribution=value*(c0+cx*x+cy*y)
                assert contribution==pytest.approx(w['stress_contributions_MPa'][axis],abs=2e-7)
                total+=contribution
            assert total==pytest.approx(w['sigma_MPa'],abs=2e-7)
            checked+=1
    assert checked>0
    assert all(r[k] is False for k in a.FALSE_FLAGS)
    d[a.FIELD]=r;assert a.saved_component(d)==r
    from tercas.three_girt_en_normal import report
    doc=Document();report.append(doc,d);text='\n'.join(p.text for p in doc.paragraphs)
    assert 'redução distorcional exclusivamente' in text
    assert 'a testemunha é um estado físico concomitante' in text.lower()
    if t==1.5:assert 'majorante triangular 149' in text
    else:
        assert 'majorante misto 172→−43' in text
        assert 'Flexão forte com mesa localmente reduzida' in text
        assert 'Ixy =' in text


@pytest.mark.parametrize('change',[
    lambda d:d.pop('load_bundle'),
    lambda d:(d['cases'].pop(0),d['load_bundle']['combinations'].pop(0)),
    lambda d:d['cases'].reverse(),
    lambda d:d['cases'][0]['model']['beams'][0]['normal_action_polynomials']['N_N'].__setitem__(0,123.)])
def test_mutated_demand_rejected(demand,change):
    d=copy.deepcopy(demand);change(d)
    with pytest.raises((ValueError,KeyError)):a.calculate(d,config(d))

@pytest.mark.parametrize('change',[
    lambda c:c.update(intact_section_model_declared=False),
    lambda c:c.update(section_model_origin=''),
    lambda c:c.update(demand_input_fingerprint='bad'),
    lambda c:c.update(section_model='assumed_unchecked')])
def test_explicit_scope_required(demand,change):
    c=config(demand);change(c)
    with pytest.raises(ValueError):a.calculate(demand,c)


def test_saved_EN_and_NBR_hashes_coexist_without_recalculation(demand,result,monkeypatch):
    d=copy.deepcopy(demand);d[a.FIELD]=copy.deepcopy(result)
    d=nbr.attach(d,nbr.reference_configuration(d))
    from tercas.three_girt_warping import network,report
    def forbidden(*args,**kwargs):raise AssertionError('Saved display/export cannot recompute')
    monkeypatch.setattr(network,'solve',forbidden)
    monkeypatch.setattr(a,'calculate',forbidden)
    monkeypatch.setattr(a,'build_component_sections',forbidden)
    monkeypatch.setattr(nbr,'calculate',forbidden)
    assert a.saved_component(d)==result
    assert nbr.saved_component(d) is not None
    doc=Document(BytesIO(report.word(d)))
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Componente normal N Mx My B pela EN' in text
    assert 'sigma–tau' in text
    assert 'Campo majorante triangular' in text
    assert 'Não cobre modos acoplados com translação das junções' in text
    assert 'inventário de tração' not in text.lower()
    d[a.FIELD]['whole_member_approved']=True
    d[a.FIELD]['content_sha256']=a.fingerprint({k:v for k,v in d[a.FIELD].items() if k!='content_sha256'})
    with pytest.raises(ValueError):a.saved_component(d)


def test_attach_order_is_explicit(demand):
    with_nbr=nbr.attach(demand,nbr.reference_configuration(demand))
    with pytest.raises(ValueError,match='before'):a.attach(with_nbr,config(with_nbr))


def test_saved_source_mutation_rejected(demand,result):
    d=copy.deepcopy(demand);d[a.FIELD]=copy.deepcopy(result)
    d['cases'][0]['model']['beams'][0]['states'][0]['N_N']=10.
    with pytest.raises(ValueError):a.saved_component(d)


def test_default_off_historical_word_still_exports(demand):
    from tercas.three_girt_warping.report import word
    old=nbr.attach(demand,nbr.reference_configuration(demand))
    assert a.saved_component(old) is None
    doc=Document(BytesIO(word(old)))
    assert not any('Componente normal N Mx My B pela EN' in p.text for p in doc.paragraphs)


def test_direct_central_N_M_B_complete_and_proportional():
    source=json.loads(FIXTURE.read_text());indices=[]
    for factor in (1.,20.):
        data=apply_geometry(copy.deepcopy(source['input_data']),2.65,4000.)
        data.update(load_mode='direct',q_uls=.1*factor,q_sls=.1*factor,
            q_parallel_uls=-.1*factor,q_parallel_sls=-.1*factor,
            actions_origin='Synthetic proportional QA, not real project')
        raw=copy.deepcopy(source['configuration']['three_girt'])
        raw.update(brace_self_weight=False,direct_pp_uls_N_mm=0.,direct_pp_sls_N_mm=0.)
        d=attach_g81(solve(data,current_configuration(data,raw)));r=a.calculate(d,config(d))
        central=r['per_member']['middle'];assert central['complete']
        w=central['complete_envelope'];s=w['concomitant_7DOF_state']
        assert all(s[k]!=0 for k in ('N_N','My_strong_Nmm','Mz_weak_Nmm','B_equilibrium_Nmm2'))
        indices.append(w['normal_index'])
        assert r['whole_member_approved'] is False
    assert indices[0]<1<indices[1]
    assert indices[1]/indices[0]==pytest.approx(20.,rel=1e-12)


def test_shear_interaction_witnesses_recompose_with_complete_section_coverage(result):
    for row in result['rows']:
        for piece in row['pieces']:
            shear=piece['shear_interaction']
            if not piece['complete']:
                assert shear is None
                continue
            assert shear['complete'] is True
            assert shear['checked_intervals']==piece['branch_count']==len(piece['branches'])>=1
            for key in ('normal','shear','interaction'):
                assert shear[key]['index_upper_bound']==max(branch['index_upper_bounds'][key] for branch in piece['branches'])
            for key in ('shear','interaction'):
                w=shear[key]['witness']
                if w is None:
                    assert shear[key]['index_lower_witness'] is None
                    assert shear[key]['index_upper_bound'] is not None
                    assert shear[key]['criterion']!='above_1_at_concomitant_state'
                    continue
                assert math.fsum(w['normal_contributions_MPa'].values())==pytest.approx(w['sigma_MPa'],abs=2e-7)
                assert math.fsum(w['shear_contributions_MPa'].values())==pytest.approx(w['tau_MPa'],abs=2e-7)
                assert w['equivalent_MPa']==pytest.approx(math.hypot(w['sigma_MPa'],math.sqrt(3)*w['tau_MPa']))
                assert w['concomitant_7DOF_state']['x_mm']==w['x_mm']
                assert 0<=w['u']<=1
                assert shear[key]['index_upper_bound']>=shear[key]['index_lower_witness']
    for member in result['per_member'].values():
        values=member['shear_interaction'];assert values['complete']
        for key in ('shear','interaction'):
            assert values[key]['index_upper_bound'] is not None
            assert values[key]['partial_index_upper_bound'] is None
            assert values[key]['criterion'] in ('within_1_by_full_interval_upper_bound','above_1_at_concomitant_state','unresolved_numerical_bound')


def test_historical_normal_only_snapshot_still_exports(demand,result,monkeypatch):
    old=copy.deepcopy(result);old['schema']=a.LEGACY_SCHEMA
    for row in old['rows']:
        row.pop('shear_interaction');row.pop('normal',None)
        for piece in row['pieces']:
            piece.pop('shear_interaction');piece.pop('normal',None)
    for member in old['per_member'].values():
        member.pop('shear_interaction');member.pop('normal',None)
    old['content_sha256']=a.fingerprint({k:v for k,v in old.items() if k!='content_sha256'})
    d=copy.deepcopy(demand);d[a.FIELD]=old
    def forbidden(*args,**kwargs):raise AssertionError('Historical export cannot requalify')
    monkeypatch.setattr(a,'calculate',forbidden)
    from tercas.three_girt_en_normal import report
    assert a.saved_component(d)==old
    doc=Document();report.append(doc,d)
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Snapshot histórico: cisalhamento' in text
    assert not any('Limite superior' in cell.text for table in doc.tables for row in table.rows for cell in row.cells)


def test_shear_results_are_visible_in_table_and_saved_word(demand,result):
    from tercas.three_girt_en_normal import ui,report
    rows=ui.shear_rows(result)
    assert len(rows)==6 and all(r['Cobertura']=='Completa no recorte' for r in rows)
    assert all(r['Índice_testemunha'] is not None for r in rows)
    d=copy.deepcopy(demand);d[a.FIELD]=copy.deepcopy(result);doc=Document();report.append(doc,d)
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Cisalhamento e interação normal–cisalhamento EN' in text
    assert 'tauSV = −face' in text
    assert '§6.1.5' in text and '§6.1.10' in text
    assert any('Limite superior' in cell.text for table in doc.tables for row in table.rows for cell in row.cells)


@pytest.mark.parametrize('t',[2.,2.25])
def test_web_reduced_N_and_negative_My_close_signed_envelope_with_explicit_transport(t):
    d=demand_for(t);r=a.calculate(d,config(d))
    cert=r['component_sections']['components']
    assert cert['My_negative']['eligible']
    assert cert['N_compression']['eligible']
    assert cert['N_compression']['moment_transport_required']
    assert all(item['complete'] for item in r['per_member'].values())
    assert all(not item['blocking_components'] for item in r['per_member'].values())
    compressed=0
    for row in r['rows']:
        reference=row['normal_action_reference']
        n=reference['original_polynomials_R01']['N'][0]
        if n<0:
            compressed+=1
            ex=cert['N_compression']['centroid_shift_from_gross_mm'][0]
            assert reference['additional_My_Nmm']==pytest.approx(n*ex)
            assert reference['additional_Mx_Nmm']==0.
        for piece in row['pieces']:
            assert piece['complete']
            w=piece['maximum_absolute']
            if w is None:
                assert piece['normal']['index_lower_witness'] is None
                assert piece['normal']['index_upper_bound'] is not None
                assert piece['normal']['criterion']!='above_1_at_concomitant_state'
                continue
            v=w['normal_action_reference'];actions=v['corrected_actions_R01']
            x,y=w['section_fiber']['fiber_xy_relative_to_gross_CG_mm']
            axial=cert['N_compression'] if actions['N']<0 else cert['N_tension']
            area=axial['effective_properties']['A_mm2'];g=r['component_sections']['gross_properties']
            sigma=actions['N']/area+actions['Mx']*y/g['Ix_strong_mm4']-actions['My']*x/g['Iy_weak_mm4']+w['stress_contributions_MPa']['B']
            assert sigma==pytest.approx(w['sigma_MPa'],abs=2e-7)
            assert v['original_actions_R01']['My']==-w['concomitant_7DOF_state']['Mz_weak_Nmm']
    assert compressed>0
    assert all(r[key] is False for key in a.FALSE_FLAGS)
    saved=copy.deepcopy(d);saved[a.FIELD]=copy.deepcopy(r)
    assert a.saved_component(saved)==r
    # Arithmetic contradictions are rejected even after recomputing the hash.
    saved[a.FIELD]['rows'][0]['normal_action_reference']['additional_My_Nmm']+=1.
    saved[a.FIELD]['content_sha256']=a.fingerprint({key:value for key,value in saved[a.FIELD].items() if key!='content_sha256'})
    with pytest.raises(ValueError,match='transport'):a.saved_component(saved)


@pytest.mark.parametrize('aggregate',['complete_envelope','partial_maximum','shear','interaction'])
def test_saved_row_aggregate_transport_is_verified_independently(demand,result,aggregate):
    saved=copy.deepcopy(demand);saved[a.FIELD]=copy.deepcopy(result)
    row=saved[a.FIELD]['rows'][0]
    if aggregate in ('complete_envelope','partial_maximum'):
        witness=copy.deepcopy(row['complete_envelope'] or row['partial_maximum'])
        row[aggregate]=witness
    else:
        witness=copy.deepcopy(row['shear_interaction'][aggregate]['witness'])
        row['shear_interaction'][aggregate]['witness']=witness
    witness['normal_action_reference']['additional_moments_R01']['My']+=1.
    saved[a.FIELD]['content_sha256']=a.fingerprint({key:value for key,value in saved[a.FIELD].items() if key!='content_sha256'})
    with pytest.raises(ValueError,match='transport'):a.saved_component(saved)
