"""Independent force/moment accounting for the restricted EN axial reduction."""
import copy
import json
from pathlib import Path
import numpy as np
import pytest
from tercas.three_girt_en_normal import application as a
from tercas.three_girt_en_normal import en1993_normal_components as c
from tercas.three_girt_en_normal import field_envelope as f


def certificate(t):
    p=Path(__file__).parents[1]/'tercas/data/torsion_profiles'/f'ue100x50x17_t{t:.2f}.json'
    return c.build_component_sections(json.loads(p.read_text()))


@pytest.mark.parametrize('t',[1.2,1.5,2.,2.25])
def test_negative_N_transports_moment_once_and_changes_required_sign(t):
    cert=certificate(t);record=cert['components']['N_compression'];ex=record['centroid_shift_from_gross_mm'][0]
    raw=dict(N=[-1000.],Mx=[0.],My=[500.,100.])
    before=copy.deepcopy(raw);corrected,ref=a._transport_polynomials(raw,cert)
    assert raw==before and ref['available']
    assert corrected['My']==[500.-1000.*ex,100.]
    assert corrected['Mx']==[0.]
    assert ref['additional_My_Nmm']==-1000*ex
    assert record['sigma_coefficients_c0_cx_cy']==[1/record['effective_properties']['A_mm2'],0.,0.]
    assert all(p['signs']['My']==1 for p in f.sign_intervals(raw))
    assert all(p['signs']['My']==-1 for p in a._integral_sign_intervals(corrected,cert))
    assert corrected['My'][1:]==raw['My'][1:]
    assert ref['shear_derivatives_unchanged'] and ref['original_network_actions_and_rigidities_unchanged']
    state=dict(N_N=-1000.,My_strong_Nmm=0.,Mz_weak_Nmm=-525.)
    actions,witness=a._normal_action_state(state,ref)
    assert witness['original_actions_R01']['My']==525.
    assert actions['My']==pytest.approx(525.-1000*ex)
    assert witness['additional_moments_R01']['My']==pytest.approx(-1000*ex)


@pytest.mark.parametrize('t',[2.,2.25])
def test_component_resultants_close_in_gross_reference_without_double_count(t):
    cert=certificate(t);record=cert['components']['N_compression'];eff=record['effective_properties'];g=cert['gross_properties']
    n=-1000.;raw=dict(N=[n],Mx=[0.],My=[0.]);corrected,ref=a._transport_polynomials(raw,cert)
    ex,ey=record['centroid_shift_from_gross_mm']
    # Uniform axial component acts through Ceff. Its gross-origin moments are
    # N*ey and -N*ex. Pure-bending sections carry exactly the added moments.
    n_from_uniform=(n/eff['A_mm2'])*eff['A_mm2']
    mx_from_uniform=n*ey;my_from_uniform=-n*ex
    my_coefficient=cert['components']['My_negative']['sigma_coefficients_c0_cx_cy']
    my_from_bending=-corrected['My'][0]*my_coefficient[1]*g['Iy_weak_mm4']
    assert n_from_uniform==pytest.approx(n)
    assert mx_from_uniform+corrected['Mx'][0]==pytest.approx(0.,abs=1e-12)
    assert my_from_uniform+my_from_bending==pytest.approx(0.,abs=1e-10)
    assert abs(my_from_uniform)>500.
    # Applying the correction twice fails equilibrium visibly.
    assert abs(my_from_uniform+2*my_from_bending)>500.


def test_axial_tension_zero_and_integral_compression_have_no_fictitious_shift():
    for t,n in ((2.,0.),(2.,1000.),(2.65,-1000.)):
        raw=dict(N=[n],Mx=[1.,2.,3.],My=[-4.,5.,-6.])
        out,ref=a._transport_polynomials(raw,certificate(t))
        assert out==raw and ref['centroid_shift_from_gross_mm']==[0.,0.]
        assert ref['additional_Mx_Nmm']==0. and ref['additional_My_Nmm']==0.


def test_blocked_axial_section_never_receives_fabricated_reference():
    raw=dict(N=[-1000.],Mx=[0.],My=[0.]);cert=certificate(2.)
    cert['components']['N_compression']['eligible']=False
    out,ref=a._transport_polynomials(raw,cert)
    assert not ref['available'] and ref['centroid_shift_from_gross_mm'] is None
    assert ref['corrected_polynomials_R01'] is None
    assert out==raw
    with pytest.raises(ValueError):a._normal_action_state(dict(N_N=-1000.,My_strong_Nmm=0.,Mz_weak_Nmm=0.),ref)


@pytest.mark.parametrize('polys',[
    dict(N=[1.,2.],Mx=[0.],My=[0.]),
    dict(N=[True],Mx=[0.],My=[0.]),
    dict(N=[0.],Mx=[float('inf')],My=[0.])])
def test_unsupported_transport_input_rejected(polys):
    with pytest.raises(ValueError):a._transport_polynomials(polys,certificate(2.))


@pytest.mark.parametrize('t',[1.2,1.5])
def test_thin_axial_transport_selects_current_corrected_bending_branch(t):
    cert=certificate(t)
    raw=dict(N=[-1000.],Mx=[0.],My=[500.,100.])
    corrected,ref=a._transport_polynomials(raw,cert)
    assert ref['available'] and cert['components']['N_compression']['eligible']
    branch=cert['components']['My_negative']
    assert branch['eligible']
    assert branch['section_status']=='effective_web_reduced_negative_My_ULS'
    assert branch['sigma_coefficients_c0_cx_cy'][0]!=0.
    assert branch['sigma_coefficients_c0_cx_cy'][1]<0.
    assert not branch['moment_transport_required']
    for interval in a._integral_sign_intervals(corrected,cert):
        assert -1 in interval['required_signs']['My']
        missing=[a._component_key(axis,sign) for axis,signs in interval['required_signs'].items() for sign in signs if sign and not cert['components'][a._component_key(axis,sign)]['eligible']]
        assert 'My_negative' not in missing
        assert 'N_compression' not in missing
        assert missing==[]


@pytest.mark.parametrize('mx',[-200000.,200000.])
def test_t120_combined_N_Mx_My_closes_gross_resultants_once(mx):
    """Each pure section carries its own resultant; only axial Cg adds N*e."""
    cert=certificate(1.2);n=-1000.;raw=dict(N=[n],Mx=[mx],My=[500.])
    corrected,ref=a._transport_polynomials(raw,cert)
    profile=Path(__file__).parents[1]/'tercas/data/torsion_profiles/ue100x50x17_t1.20.json'
    xy=np.array(json.loads(profile.read_text())['nodes_xy_mm'])
    cg=np.array(cert['gross_properties']['centroid_xy_mm']);z,w=np.polynomial.legendre.leggauss(5)
    axial=cert['components']['N_compression'];ex=axial['centroid_shift_from_gross_mm'][0]
    assert corrected['My']==[500.+n*ex] and corrected['Mx']==[mx]
    assert ref['additional_My_Nmm']==n*ex
    chosen={'N':'N_compression','Mx':'Mx_positive' if mx>0 else 'Mx_negative','My':'My_negative'}
    total=np.zeros(3);parts={}
    for axis,key in chosen.items():
        r=cert['components'][key];co=np.array(r['sigma_coefficients_c0_cx_cy'])
        force=corrected[axis][0];result=np.zeros(3)
        intervals=r.get('effective_weighted_line_intervals') or [list(row)+[1.2] for row in r['effective_line_intervals']]
        for i,lo,hi,thickness in intervals:
            d=xy[i+1]-xy[i]
            for u,weight in zip((lo+hi)/2+(hi-lo)*z/2,w*(hi-lo)/2):
                point=xy[i]+u*d;stress=force*(co[0]+co[1:]@(point-cg))
                result+=weight*np.linalg.norm(d)*thickness*stress*np.array([1.,point[1]-cg[1],-(point[0]-cg[0])])
        parts[axis]=result;total+=result
        if axis!='N':
            assert not r['moment_transport_required']
            assert r['additional_Mx_per_N_mm']==r['additional_My_per_N_mm']==0.
            assert co[0]!=0.
            assert abs(result[0])<1e-8
    assert parts['N']==pytest.approx([n,0.,-n*ex],rel=0,abs=1e-8)
    assert parts['Mx']==pytest.approx([0.,mx,0.],rel=0,abs=1e-8)
    assert parts['My']==pytest.approx([0.,0.,corrected['My'][0]],rel=0,abs=1e-8)
    assert total==pytest.approx([n,mx,500.],rel=0,abs=2e-8)
    # Removing the My affine constant creates an axial force. Adding N*e
    # a second time would leave a moment error greater than 2 kN.mm.
    my=cert['components']['My_negative']
    omitted_c0_force=-corrected['My'][0]*my['sigma_coefficients_c0_cx_cy'][0]*my['effective_properties']['A_mm2']
    assert abs(omitted_c0_force)>10.
    assert abs(n*ex)>2000.


@pytest.mark.parametrize('mx',[-200000.,200000.])
def test_pure_t120_moments_c0_never_trigger_an_axial_transport(mx):
    cert=certificate(1.2);raw=dict(N=[0.],Mx=[mx],My=[-10000.])
    corrected,ref=a._transport_polynomials(raw,cert)
    assert corrected==raw
    assert ref['additional_Mx_Nmm']==ref['additional_My_Nmm']==0.
    assert ref['centroid_shift_from_gross_mm']==[0.,0.]
