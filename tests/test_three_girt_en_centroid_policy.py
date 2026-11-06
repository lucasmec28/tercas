"""EN6.1.3(3): bounds are not witnesses and old stress numbers do not move."""
import copy
import json
import math
from fractions import Fraction
from pathlib import Path
import pytest
from tercas.three_girt_en_normal import application as a
from tercas.three_girt_en_normal import centroid_policy as cp
from tercas.three_girt_en_normal import field_envelope as f
from tercas.three_girt_en_normal.en1993_normal_components import build_component_sections


@pytest.fixture(scope='module')
def certificates():
    root=Path(__file__).parents[1]/'tercas/data/torsion_profiles'
    return {t:build_component_sections(json.loads((root/f'ue100x50x17_t{t:.2f}.json').read_text()))
            for t in (1.2,1.5,2.65)}


def row_for(certificate,original,upper=.2,interaction=.3):
    _,reference=a._transport_polynomials(original,certificate)
    normal=dict(index_upper_bound=upper,index_lower_witness=None,witness=None,
        partial_index_upper_bound=None,criterion='within_1_by_full_interval_upper_bound',complete=True)
    shear=copy.deepcopy(normal);shear['index_upper_bound']=interaction
    return dict(combination_id='QA_ELU',girt='middle',segment_id='middle_0',x_start_mm=0.,x_end_mm=1000.,
        complete=True,normal_action_reference=reference,normal=normal,
        shear_interaction=dict(complete=True,shear=copy.deepcopy(normal),interaction=shear),pieces=[],
        complete_envelope=None,partial_maximum=None,normal_criterion=normal['criterion'],
        blocking_components=[])


def component_for(certificate,row):
    member=copy.deepcopy(row)
    member.update(ELU_segments=1,complete_segments=1,complete_sign_pieces=1,total_sign_pieces=1,
                  observed_normal_exceedance=False)
    return dict(schema=a.CENTRAL_SCHEMA,component_sections=certificate,rows=[row],per_member=dict(middle=member),
                content_sha256='test_component')


@pytest.mark.parametrize('thickness',[1.2,1.5,2.,2.25,2.65,3.,3.35])
def test_containing_rectangle_covers_every_pinned_exterior_vertex(thickness):
    path=Path(__file__).parents[1]/'tercas/data/torsion_profiles'/f'ue100x50x17_t{thickness:.2f}.json'
    profile=json.loads(path.read_text());nodes=profile['nodes_xy_mm']
    # Translation by Cg does not affect containment. No section/property solve.
    cert=dict(thickness_mm=thickness,profile_id=profile['profile_id'],
        nodes_sha256=profile['geometry_identity']['nodes_canonical_sha256'],gross_properties=dict(centroid_xy_mm=[0.,0.]))
    box=cp._box(cert)
    fibers=f.exterior_fibers(dict(nodes_xy_mm=nodes,omega_nodes_mm2=[0.]*len(nodes),thickness_mm=thickness,
        properties=dict(centroid_xy_mm=[0.,0.],Cw_mm6=1.)))
    assert len(fibers['xy_mm'])==832
    assert all(box[0][0]<=Fraction(x)<=box[0][1] and box[1][0]<=Fraction(y)<=box[1][1]
               for x,y in fibers['xy_mm'])


@pytest.mark.parametrize('mutation',[
    lambda certificate:certificate.update(thickness_mm=1.5),
    lambda certificate:certificate.update(nodes_sha256='changed'),
    lambda certificate:certificate.update(thickness_mm=1.21),
])
def test_containing_rectangle_requires_the_exact_thickness_geometry_pair(certificates,mutation):
    certificate=copy.deepcopy(certificates[1.2]);mutation(certificate)
    with pytest.raises(ValueError,match='pinned'):cp._box(certificate)


def sigma(polynomials,certificate,t,x,y):
    total=0.
    for axis,coefficients in polynomials.items():
        value=sum(v*t**i for i,v in enumerate(coefficients))
        if value:
            operator=certificate['components'][a._component_key(axis,1 if value>0 else -1)]['sigma_coefficients_c0_cx_cy']
            total+=value*(operator[0]+operator[1]*x+operator[2]*y)
    return total


@pytest.mark.parametrize('n,thickness',[(0.,1.2),(1000.,1.2),(-1000.,2.65)])
def test_no_new_gate_for_zero_N_tension_or_zero_e(certificates,n,thickness):
    cert=certificates[thickness];row=row_for(cert,dict(N=[n],Mx=[-100.,300.],My=[200.,-400.]))
    before=copy.deepcopy(row);policy=cp.build(row,cert)
    assert not policy['required'] and policy['difference_bound'] is None
    assert policy['original_index_upper_bounds']==dict(normal=None,interaction=None)
    row[cp.FIELD]=policy;c=component_for(cert,row);cp.verify(c)
    assert cp.qualification(c,'middle','normal')['qualified']
    assert {k:v for k,v in row.items() if k!=cp.FIELD}==before


def test_bimoment_cancellation_can_make_larger_corrected_moment_favourable(certificates):
    cert=certificates[1.2];original=dict(N=[-1000.],Mx=[0.],My=[-1000.])
    row=row_for(cert,original);ref=row['normal_action_reference'];corrected=ref['corrected_polynomials_R01']
    assert abs(corrected['My'][0])>abs(original['My'][0])
    # Choose a concomitant B*omega/Cw cancelling corrected normal stress.
    # Magnitude-only moment selection misses the unshifted stress at this point.
    x,y=30.,0.;b=-sigma(corrected,cert,.5,x,y)
    corr=sigma(corrected,cert,.5,x,y)+b;orig=sigma(original,cert,.5,x,y)+b
    proof=cp.difference_bound(ref,cert)
    assert corr==0 and abs(orig)>0
    assert abs(orig-corr)<=proof['difference_upper_MPa']
    for tau in (0.,100.,-700.):
        assert math.hypot(orig,math.sqrt(3)*tau)<=math.hypot(corr,math.sqrt(3)*tau)+proof['difference_upper_MPa']
    row[cp.FIELD]=cp.build(row,cert)
    assert row[cp.FIELD]['original_scenario_witness'] is None
    assert row[cp.FIELD]['bound_is_not_a_concomitant_state']
    assert row['normal']['witness'] is None


@pytest.mark.parametrize('my',[[500.,100.],[-1000.,6000.,-4000.],[10000.,-40000.,40000.]])
def test_different_signed_operators_and_root_unions_are_enclosed(certificates,my):
    cert=certificates[1.2];row=row_for(cert,dict(N=[-1000.],Mx=[-1e5,4e5,-2e5],My=my))
    ref=row['normal_action_reference'];proof=cp.difference_bound(ref,cert)
    assert proof is not None
    assert proof['axis_difference_upper_MPa']['Mx']==0.
    if my==[500.,100.]:
        assert f.sign_intervals(ref['original_polynomials_R01'])[0]['signs']['My']==1
        assert f.sign_intervals(ref['corrected_polynomials_R01'])[0]['signs']['My']==-1
    # Independent dense evaluations are regression oracles, not the proof.
    for j in range(101):
        t=j/100
        for x,y in ((-15.,-45.),(30.,45.),(0.,0.)):
            original=sigma(ref['original_polynomials_R01'],cert,t,x,y)
            corrected=sigma(ref['corrected_polynomials_R01'],cert,t,x,y)
            assert abs(original-corrected)<=proof['difference_upper_MPa']+1e-10


def test_same_operator_exact_difference_and_outward_rounding(certificates):
    cert=certificates[1.5];row=row_for(cert,dict(N=[-1000.],Mx=[0.],My=[-10000.,-500.]))
    ref=row['normal_action_reference'];proof=cp.difference_bound(ref,cert)
    coef=list(map(Fraction,cert['components']['My_negative']['sigma_coefficients_c0_cx_cy']))
    box=cp._box(cert)
    max_operator=max(abs(coef[0]+coef[1]*x+coef[2]*y) for x in box[0] for y in box[1])
    delta=abs(Fraction(ref['original_polynomials_R01']['My'][0])-Fraction(ref['corrected_polynomials_R01']['My'][0]))
    assert Fraction(proof['difference_upper_MPa'])>=delta*max_operator
    assert proof['difference_upper_MPa']==pytest.approx(float(delta*max_operator),rel=1e-15)
    assert cp._up(Fraction(1,3))>=Fraction(1,3)


def test_upper_above_one_is_pending_not_physical_failure(certificates):
    cert=certificates[1.2];row=row_for(cert,dict(N=[-1000.],Mx=[0.],My=[-1000.]),upper=.999999,interaction=.999999)
    before=copy.deepcopy(row);row[cp.FIELD]=cp.build(row,cert);c=component_for(cert,row)
    for key in ('normal','interaction'):
        gate=cp.qualification(c,'middle',key)
        assert not gate['qualified'] and gate['original_index_upper_bound']>1
        assert cp.decision(c,'middle',key,'within_1_by_full_interval_upper_bound')==cp.PENDING
        assert cp.decision(c,'middle',key,'above_1_at_concomitant_state')=='above_1_at_concomitant_state'
    assert cp.qualification(c,'middle','shear')['qualified']
    assert {k:v for k,v in row.items() if k!=cp.FIELD}==before
    assert row['normal']['witness'] is None


def test_missing_original_only_signed_section_is_pending_without_fallback(certificates):
    cert=copy.deepcopy(certificates[1.2])
    row=row_for(cert,dict(N=[-1000.],Mx=[0.],My=[500.]))
    cert['components']['My_positive']['eligible']=False
    policy=cp.build(row,cert)
    assert row['complete'] is True
    assert policy['status']==cp.PENDING and policy['difference_bound'] is None
    assert policy['original_index_upper_bounds']==dict(normal=None,interaction=None)
    assert policy['original_scenario_witness'] is None


def test_older_zero_axial_sign_still_exempt_without_transport_metadata(certificates):
    cert=certificates[1.2]
    row=dict(pieces=[dict(required_signs=dict(N=[0]))])
    assert not cp.required(row,cert)
    row['pieces'][0]['required_signs']['N']=[-1]
    assert cp.required(row,cert)


@pytest.mark.parametrize('mutation',[
    lambda p:p.update(schema='forged'),
    lambda p:p.update(required=False),
    lambda p:p.update(source_section_certificate_sha256='forged'),
    lambda p:p['row_identity'].update(girt='upper'),
    lambda p:p['difference_bound'].update(difference_upper_MPa=0.),
    lambda p:p['original_index_upper_bounds'].update(normal=0.),
    lambda p:p.update(original_scenario_witness={'t':.5}),
])
def test_resealed_policy_and_scope_tampering_are_rejected(certificates,mutation):
    cert=certificates[1.2];row=row_for(cert,dict(N=[-1000.],Mx=[0.],My=[500.]))
    row[cp.FIELD]=cp.build(row,cert);c=component_for(cert,row);cp.verify(c)
    mutation(row[cp.FIELD]);row[cp.FIELD]['content_sha256']=cp._sha({k:v for k,v in row[cp.FIELD].items() if k!='content_sha256'})
    with pytest.raises(ValueError,match='centroid'):cp.verify(c)


def test_historical_indices_unchanged_and_display_does_not_promote(certificates):
    from tercas.three_girt_en_normal import ui
    cert=certificates[1.2];row=row_for(cert,dict(N=[-1000.],Mx=[0.],My=[500.]))
    c=component_for(cert,row)
    c.update(ELU_combinations=1,ELS_combinations_excluded=0,normal_limit_MPa=250.)
    before=copy.deepcopy(c);cp.verify(c)
    assert cp.qualification(c,'middle','normal')['criterion']==cp.PENDING
    assert 'Pendente' in ui.rows(c)[0]['Resultado']
    rows=ui.shear_rows(c)
    assert rows[0]['Resultado']=='Dentro do limite pelo limite superior'
    assert 'Pendente' in rows[1]['Resultado']
    summary=a.summary(c)['members']['middle']
    assert summary['normal_criterion']==cp.PENDING
    assert summary['normal']['criterion']==cp.PENDING
    assert summary['shear_interaction']['interaction']['criterion']==cp.PENDING
    assert summary['normal']['index_upper_bound']==row['normal']['index_upper_bound']
    assert c==before


def test_no_witness_required_for_sufficient_bound_in_panorama(certificates,monkeypatch):
    from tercas.three_girt_assessment import application as assessment
    cert=certificates[1.2];row=row_for(cert,dict(N=[-1000.],Mx=[0.],My=[500.]))
    row[cp.FIELD]=cp.build(row,cert);c=component_for(cert,row)
    monkeypatch.setattr(a,'verification_members',lambda component,demand:('middle',))
    monkeypatch.setattr(assessment,'members',lambda demand:('middle',))
    monkeypatch.setattr(assessment,'_beam_inventory',lambda demand,state:[('QA_ELU','middle','middle_0',0.,1000.)])
    checks=assessment._en({},c,None)
    assert len(checks)==3 and all(r['status']=='meets' for r in checks)
    assert all(r['trace']['witness'] is None for r in checks)
    assert checks[0]['index']==max(row['normal']['index_upper_bound'],row[cp.FIELD]['original_index_upper_bounds']['normal'])
    sidecar=dict(checks=copy.deepcopy(checks),groups=[dict(id='EN_section',checks=copy.deepcopy(checks))])
    with pytest.raises(ValueError,match='Panorama anterior'):cp.verify_assessment(c,sidecar,('middle',))
    sidecar[cp.ASSESSMENT_REVISION]=cp.SCHEMA
    cp.verify_assessment(c,sidecar,('middle',))
    sidecar['groups'][0]['checks'][0]['trace'].pop(cp.FIELD)
    with pytest.raises(ValueError,match='qualification'):cp.verify_assessment(c,sidecar,('middle',))
    row.pop(cp.FIELD)
    checks=assessment._en({},c,None)
    assert [r['status'] for r in checks]==['pending','meets','pending']
    assert all(r['trace']['witness'] is None for r in checks)


def test_old_panorama_without_affected_shift_keeps_its_scope(certificates):
    cert=certificates[2.65];row=row_for(cert,dict(N=[-1000.],Mx=[0.],My=[500.]))
    c=component_for(cert,row)
    cp.verify_assessment(c,{},('middle',))


def test_word_keeps_numbers_and_labels_uncovered_historical_centroid(certificates,monkeypatch):
    from docx import Document
    from tercas.three_girt_en_normal import report
    cert=certificates[1.2];row=row_for(cert,dict(N=[-1000.],Mx=[0.],My=[500.]))
    c=component_for(cert,row)
    c.update(configuration=dict(section_model_origin='Synthetic policy report QA'),
             demand_material_E_MPa=200000.,normal_limit_MPa=250.)
    before=copy.deepcopy(c)
    monkeypatch.setattr(report,'saved_component',lambda demand:c)
    doc=Document();report.append(doc,{})
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Decisão normal com cobertura normativa: pendente: cenário sem deslocamento' in text
    assert 'interação: pendente: cenário sem deslocamento' in text
    assert 'O teto adicional não é testemunha física' in text
    assert any(cell.text=='PENDENTE' for table in doc.tables for rr in table.rows for cell in rr.cells)
    assert any(cell.text=='0.20000' for table in doc.tables for rr in table.rows for cell in rr.cells)
    assert c==before


def test_ui_retires_old_cached_panorama_without_mechanical_recalculation(certificates,monkeypatch):
    from tercas.three_girt_assessment import application as assessment,ui
    cert=certificates[1.2];row=row_for(cert,dict(N=[-1000.],Mx=[0.],My=[500.]))
    c=component_for(cert,row);d={a.FIELD:c}
    old=dict(assessment_schema=assessment.SCHEMA,source_result_sha256=assessment.fingerprint(d),
             whole_member_approved=False,current_adapter_can_approve=False,numerical_results_changed=False,
             checks=[],groups=[])
    old['content_sha256']=assessment.fingerprint(old)
    monkeypatch.setattr(assessment,'_read',lambda *args:(c,None))
    def forbidden(*args,**kwargs):raise AssertionError('Saved panorama must not recalculate')
    monkeypatch.setattr(assessment,'assess',forbidden)
    class UI:
        session_state={ui.KEY:old}
        warnings=[]
        def caption(self,*args,**kwargs):pass
        def button(self,*args,**kwargs):return False
        def warning(self,text):self.warnings.append(text)
    st=UI();before=copy.deepcopy(d)
    assert ui.render(st,d) is None
    assert ui.KEY not in st.session_state
    assert any('Panorama anterior' in warning for warning in st.warnings)
    assert d==before
