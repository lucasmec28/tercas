"""Requested fallback: isolated local component, never a biaxial ELS release."""
import copy
import json
import math
import warnings
from io import BytesIO
import numpy as np
import pytest
from docx import Document
from scipy.integrate import IntegrationWarning
from tercas.application import calculate, defaults, rows
from tercas.batch import calculate_batch
from tercas import ue_reference as ue, ue_family_reference as family
from tercas import deflection_scope as scope
from tercas.report import word, batch_word


def own(t=1.2, angle=5., L=4000.):
    return ue.load_reference(angle=angle, L_mm=L) if t == 1.2 else family.load_reference(t, L, angle)


def direct(t=1.2, **updates):
    data = own(t)
    data.update(load_mode='direct', q_uls=.3, q_sls=.1,
                q_parallel_uls=.025, q_parallel_sls=.05,
                P_parallel_uls=0., P_parallel_sls=0.)
    data.update(updates)
    return data


def text(binary):
    doc = Document(BytesIO(binary))
    return '\n'.join([p.text for p in doc.paragraphs] +
                     [c.text for table in doc.tables for row in table.rows for c in row.cells])


@pytest.mark.parametrize('t', [1.2, *family.THICKNESSES])
def test_explicit_mode_changes_scope_not_actions_or_resistance(t):
    source = direct(t)
    old = calculate(source)
    data = scope.activate(source)
    before = copy.deepcopy(data)
    result = calculate(data)
    assert data == before
    assert {k:v for k,v in data.items() if k != scope.FIELD} == source
    assert old['ELS'].get('index') is None
    assert result['ELS']['index'] == pytest.approx(abs(result['ELS']['deflection_mm']) / result['ELS']['limit_mm'])
    assert result['ELS']['deflection_mm'] == old['ELS']['deflection_mm']
    assert result['ELS']['x_mm'] == old['ELS']['x_mm']
    for key in ('NBR_branches', 'FLT_segments', 'section_checks'):
        assert result[key] == old[key]
    assert result['inclination_evidence']['ELU'] == old['inclination_evidence']['ELU']
    assert result['inclination_evidence']['ELS']['states'] == old['inclination_evidence']['ELS']['states']
    ev = result['ELS']['local_uniaxial_component']
    assert ev['actual_parallel_actions_zero'] is False
    assert ev['q_vector_N_mm']['parallel'] == .05
    for key in ('combined_stiffness_qualified','combined_ELS_approved','total_displacement_evaluated',
                'torsional_displacement_evaluated','whole_member_approved','parallel_actions_removed_from_strength'):
        assert ev[key] is False
    row = next(r for r in rows(result) if r['Verificação'] == scope.PURLIN_ROW)
    assert row['Índice'] == result['ELS']['index']
    assert 'critério uniaxial isolado' in row['Situação']
    assert 'Não é a flecha vertical global' in row['Observação']
    assert not any(r['Verificação'] == 'Flecha paralela à cobertura' for r in rows(result))


@pytest.mark.parametrize('t', [1.2, 1.5, 3.35])
@pytest.mark.parametrize('angle', [-5., 0., 5.])
def test_area_cases_preserve_vectors_and_only_keep_selected_ELS_component(t, angle):
    data = scope.activate(own(t, angle))
    result = calculate_batch(data)
    assert len(result['cases']) == 58
    from tercas.batch import area_bundle
    assert result['load_bundle'] == area_bundle(data)
    for case in result['cases']:
        c = case['combination']
        if c['limit_state'] != 'ELS':
            assert not any(r['Verificação'] in scope.ROWS for r in case['rows'])
            continue
        assert len(case['rows']) == 1
        assert case['rows'][0]['Verificação'] == scope.PURLIN_ROW
        block = case['evidence']['ELS']
        ev = block['local_uniaxial_component']
        assert ev['original_q_vector_N_mm'] == c['q_vector']
        assert ev['original_P_vector_N'] == c['P_vector']
        assert not ev['combined_ELS_approved']
        assert case['rows'][0]['Índice'] == block['index']
        if c.get('point_position') == 'support_limit':
            assert ev['P_vector_N'] == dict(normal=0., parallel=0.)
            assert c['P_vector']['normal'] > 0.
            assert case['evidence']['inclination']['P_vector'] == c['P_vector']
    assert not result['whole_member_approved']
    summary = next(r for r in result['summary'] if r['Verificação'] == scope.PURLIN_ROW)
    assert summary['Casos avaliados'] == 18
    assert summary['Casos pendentes'] == 0  # Only this selected component, not whole ELS.


@pytest.mark.parametrize('angle', [-30., -5., 0., 5., 30.])
def test_local_not_global_axis_and_direct_loads_are_not_rotated(angle):
    data = scope.activate(direct())
    data['inclination']['value'] = angle
    result = calculate(data)
    p = data['properties']
    expected = 5 * data['q_sls'] * data['L_mm']**4 / (384*p['E_MPa']*p['Ix_cm4']*1e4)
    assert result['ELS']['deflection_mm'] == pytest.approx(expected, rel=1e-12)
    assert result['ELS']['local_uniaxial_component']['displacement_axis'] == 'local_normal_roof_vertical'
    assert result['inclination_evidence']['ELS']['q_vector']['normal'] == .1
    assert result['inclination_evidence']['ELS']['q_vector']['parallel'] == .05


def independent_scalar(data):
    """Independent Gauss integration and bisection, no core import."""
    L, q, P, a = (data[k] for k in ('L_mm','q_sls','P_sls','x_sls'))
    E = data['properties']['E_MPa']
    Ig = data['properties']['Ix_cm4']*1e4
    Ml = data['Ml_Nmm']
    nodes, weights = np.polynomial.legendre.leggauss(100)
    reaction = q*L/2 + P*(L-a)/L
    def moment(x):return reaction*x - q*x*x/2 - P*np.maximum(0.,x-a)
    # Include the exact clamp transition in the independent integration grid.
    threshold = ((1+math.sqrt(1-4*.22))/2)**2*Ml
    points = [0., a, L]
    for lo, hi, shift, R in ((0.,a,0.,reaction),(a,L,P*a,reaction-P)):
        for sign in (-1,1):
            coeff = [-q/2,R,shift-sign*threshold]
            roots = np.roots(np.trim_zeros(coeff,'f'))
            points.extend(float(r.real) for r in roots if abs(r.imag)<1e-9 and lo<r.real<hi)
    def calc(z, derivative=False):
        cuts=sorted(set(points+[z]));total=0.
        for lo,hi in zip(cuts,cuts[1:]):
            if hi==lo:continue
            x=(lo+hi)/2+(hi-lo)/2*nodes
            m=moment(x)
            lam=np.sqrt(np.abs(m)/Ml)
            rho=np.ones(len(x));active=lam>.673
            rho[active]=np.minimum(1.,(1-.22/lam[active])/lam[active])
            green=np.where(x<=z,-x/L,(L-x)/L) if derivative else np.where(x<=z,(L-z)*x/L,z*(L-x)/L)
            total+=(hi-lo)/2*float(weights@(m*green/(E*Ig*rho)))
        return total
    lo,hi=0.,L
    # Positive and negative actions share the peak location after sign removal.
    direction=1. if q>0 or P>0 else -1.
    for _ in range(60):
        mid=(lo+hi)/2
        if direction*calc(mid,True)>0:lo=mid
        else:hi=mid
    z=(lo+hi)/2
    return z,calc(z)


@pytest.mark.parametrize('q,P,a',[(.1,0.,2000.),(.1,100.,1333.),(.8,500.,1234.),(-.8,-500.,2800.)])
def test_gross_and_reduced_scalar_against_independent_integral(q,P,a):
    data=scope.activate(direct(q_sls=q,P_sls=P,x_sls=a))
    result=calculate(data)['ELS']
    z,v=independent_scalar(data)
    assert result['x_mm']==pytest.approx(z,abs=2e-7)
    assert result['deflection_mm']==pytest.approx(v,rel=2e-10,abs=2e-8)


@pytest.mark.parametrize('t',[1.2,1.5])
def test_opposite_actions_and_numerical_warning_are_not_promoted(t,monkeypatch):
    data=scope.activate(direct(t,P_sls=-100.))
    result=calculate(data)
    assert result['ELS'].get('index') is None
    assert result['ELS']['status']=='invalid_or_outside_implemented_domain'
    import tercas.core.especificacao_unica as core
    old=core.peak
    def warn(*args,**kwargs):
        warnings.warn('Intentional QA warning',IntegrationWarning)
        return old(*args,**kwargs)
    monkeypatch.setattr(core,'peak',warn)
    result=calculate(scope.activate(direct(t)))
    assert result['ELS']['criterion_status']=='not_evaluated_numerical_warning'
    assert result['ELS'].get('index') is None
    assert next(r for r in rows(result) if r['Verificação']==scope.PURLIN_ROW)['Índice'] is None


@pytest.mark.parametrize('value',[None,True,False,{},[],1,'uniaxial','combined'])
def test_invalid_model_never_silently_enables(value):
    for data in (defaults(19), own(), own(1.5)):
        data[scope.FIELD]=value
        with pytest.raises(ValueError):calculate(data)


def girt(mode='direct'):
    data=defaults(19)
    data.update(member_application='wall_girt',L_mm=4000.,load_mode=mode,
                x_sls=2000.,x_uls=2000.,q_sls=.1,q_uls=.2,
                q_parallel_sls=.25,q_parallel_uls=.5,P_sls=0.,P_uls=0.,
                selected_types=['ELU normal','ELS rara','ELS frequente','ELS quase permanente'])
    data['area_inputs'].update(spacing_m=1.5,permanent_kgf_m2=10.,wind_up_kgf_m2=40.,wind_down_kgf_m2=30.)
    return data


@pytest.mark.parametrize('mode',['direct','area'])
def test_girt_only_horizontal_deflection_without_removing_vertical_loads(mode):
    data=scope.activate(girt(mode))
    result=calculate_batch(data) if mode=='area' else calculate(data)
    assert 'elastic_vertical' not in result and 'elastic_tie_study' not in result
    containers=[c for c in result.get('cases',[]) if c['combination']['limit_state']=='ELS']
    if not containers:containers=[dict(rows=rows(result),evidence=result)]
    for case in containers:
        ev=case['evidence']
        block=ev['ELS']
        assert block['local_uniaxial_component']['displacement_axis']=='local_normal_horizontal'
        assert 'elastic_vertical' not in ev and 'elastic_tie_study' not in ev
        names=[r['Verificação'] for r in case['rows']]
        assert scope.GIRT_ROW in names
        assert not any(name in ('Flecha vertical — eixo fraco','Flecha paralela à cobertura') for name in names)
        assert block['local_uniaxial_component']['q_vector_N_mm']['parallel'] != 0.
    rendered=text(batch_word(result) if mode=='area' else word(result))
    assert 'Flecha uniaxial local — escopo reduzido' in rendered
    assert 'Flecha vertical — diagnóstico elástico' not in rendered
    assert 'vertical é diagnóstico bruto separado' not in rendered


def test_existing_3d_guard_is_not_bypassed():
    data=scope.activate(girt())
    data['three_girt_model']=dict(enabled=True)
    with pytest.raises(ValueError):calculate(data)


@pytest.mark.parametrize('t',[1.2,1.5])
def test_input_result_roundtrip_and_source_snapshot_reports(t,monkeypatch):
    data=scope.activate(direct(t))
    result=calculate(data)
    assert calculate(json.loads(json.dumps(data)))==result
    assert json.loads(json.dumps(result))==result
    before=copy.deepcopy(result)
    source=ue if t==1.2 else family
    monkeypatch.setattr(source,'gate',lambda:(_ for _ in ()).throw(ValueError('Live files unavailable')))
    rendered=text(word(result))
    assert result==before
    assert scope.PURLIN_ROW in rendered
    assert 'O índice confronta somente a componente isolada' in rendered
    assert 'Estados biaxiais permanecem sem índice ELS' not in rendered
    assert 'somente q_parallel=P_parallel=0' not in rendered


def test_historical_result_not_requalified_by_adding_input_token():
    result=calculate(direct())
    result['input_data'][scope.FIELD]=scope.MODE
    assert not any(r['Verificação'] in scope.ROWS for r in rows(result))
    assert 'Flecha uniaxial local — escopo reduzido' not in text(word(result))
    assert result['ELS'].get('index') is None


def test_geometry_changes_preserve_explicit_mode_without_transfer_of_criticals():
    a=scope.activate(own())
    b=ue.apply_span(a,4750.)
    assert b[scope.FIELD]==scope.MODE and ue.assess(b)['calculable']
    a=scope.activate(own(1.5))
    b=family.apply_geometry(a,3.35,4750.)
    assert b[scope.FIELD]==scope.MODE and family.assess(b)['calculable']
    assert b['Ml_Nmm']!=a['Ml_Nmm']


def test_support_limit_metadata_does_not_call_original_external_P_zero():
    data=scope.activate(direct())
    zero=dict(normal=0.,parallel=0.)
    record=scope._description(data,zero,zero,zero,dict(normal=100.,parallel=50.))
    assert record['interior_bending_parallel_actions_zero'] is True
    assert record['actual_parallel_actions_zero'] is False
    assert record['original_P_vector_N']==dict(normal=100.,parallel=50.)
