import copy
import json
import math
from pathlib import Path
import pytest
from tercas import three_girt_local_stability as b1
from tercas.three_girt_warping import application as w
from tercas.three_girt_axial import application as nbr
from tercas import three_girt_scope
from tercas.ue_family_reference import apply_geometry


def local_case(forces=(-100.,-100.),L=4000.):
    xs=[i*L/len(forces) for i in range(len(forces)+1)]
    nodes=[dict(id=i,xyz_CG_mm=[x,0.,0.]) for i,x in enumerate(xs)]
    beams=[dict(id='middle_'+str(i),girt='middle',x_start_mm=xs[i],x_end_mm=xs[i+1],
        normal_action_polynomials=dict(N_N=[n],My_strong_Nmm=[10.,20.,-20.],Mz_weak_Nmm=[-4.,1.]))
        for i,n in enumerate(forces)]
    model=dict(inputs=dict(L_mm=L,section=dict(E_MPa=200000.,I_strong_mm4=1e6,I_weak_mm4=2e5)),
        nodes=nodes,beams=beams,fixed_dofs=[dict(node=i,dof=d) for i in (0,len(forces)) for d in ('ux','uy','uz','rx')])
    return dict(combination=dict(id='synthetic',limit_state='ELU'),model=model)


@pytest.mark.parametrize('fraction',[0.,.001,.1,.5,.999])
def test_formula_uses_each_plane_euler_and_does_not_cap(fraction):
    E,I,L=200000.,234407.,4000.
    ne=math.pi**2*E*I/L**2
    out=b1.flexural_B1(compression_N=fraction*ne,E_MPa=E,I_mm4=I,L_mm=L)
    assert out['B1_reference']==pytest.approx(1/(1-fraction))
    assert out['K_flexural']==out['Cm']==1.
    assert out['effective_length_mm']==L


@pytest.mark.parametrize('fraction',[1.,1.001,2.])
def test_no_max_one_fallback_at_or_above_euler(fraction):
    ne=math.pi**2*200000*2e5/4000**2
    out=b1.flexural_B1(compression_N=fraction*ne,E_MPa=200000.,I_mm4=2e5,L_mm=4000.)
    assert out['B1_reference'] is None
    assert out['status']=='at_or_above_Euler'


@pytest.mark.parametrize('key', ['E_MPa','I_mm4','L_mm'])
@pytest.mark.parametrize('value',[0.,-1.,float('nan'),float('inf'),True])
def test_invalid_reference_data_fail_closed(key,value):
    args=dict(compression_N=100.,E_MPa=200000.,I_mm4=2e5,L_mm=4000.)
    args[key]=value
    with pytest.raises(ValueError):b1.flexural_B1(**args)


def test_uniform_reference_amplifies_only_separate_moment_polynomials():
    case=local_case();before=copy.deepcopy(case);r=b1._case(case)
    assert r['local_formula_reference_applicable']
    assert r['planes']['weak']['B1_reference']>r['planes']['strong']['B1_reference']>1
    assert r['supports']['Kt_classical_free_warping_reference']==1.
    assert r['physical_span_mm']==4000.
    for original,amplified in zip(case['model']['beams'],r['amplified_local_reference_moment_polynomials']):
        for plane,key,_,_,_ in b1.PLANS:
            assert amplified[key]==pytest.approx([v*r['planes'][plane]['B1_reference'] for v in original['normal_action_polynomials'][key]])
        assert 'N_N' not in amplified and 'B' not in amplified
    assert case==before
    assert r['global_redistribution_assessed'] is False and r['stability_criterion'] is None


@pytest.mark.parametrize('forces',[(0.,0.),(10.,100.),(0.,100.)])
def test_no_compression_has_unit_local_factor(forces):
    r=b1._case(local_case(forces))
    assert r['local_formula_reference_applicable']
    assert all(p['B1_reference']==1. for p in r['planes'].values())


@pytest.mark.parametrize('forces',[(-100.,-200.),(-100.,100.),(-100.,0.)])
def test_variable_N_uses_uniform_equivalent_compression_and_applies_moments(forces):
    r=b1._case(local_case(forces))
    assert r['N_compression_max_N']==-min(forces)
    assert not r['uniform_axial_force'] and r['local_formula_reference_applicable']
    assert r['amplified_local_reference_moment_polynomials'] is not None
    assert r['issues']==[]
    assert r['planes']['weak']['B1_reference']>1.


@pytest.mark.parametrize('kind',['end_translation_released','end_rotation_fixed','internal_support'])
def test_K_not_assumed_for_incompatible_supports(kind):
    case=local_case();fixed=case['model']['fixed_dofs']
    if kind=='end_translation_released':fixed.remove(dict(node=0,dof='uz'))
    elif kind=='end_rotation_fixed':fixed.append(dict(node=0,dof='ry'))
    else:fixed.append(dict(node=1,dof='uz'))
    r=b1._case(case)
    assert r['planes']['strong']['B1_reference'] is None
    assert r['supports']['planes']['strong']['K'] is None
    assert not r['local_formula_reference_applicable']
    assert r['planes']['weak']['effective_length_mm']==4000. # Never use the 2 m force interval.


def test_warping_restraint_not_mistaken_for_classical_free_warping():
    case=local_case();case['model']['fixed_dofs'].append(dict(node=0,dof='psi'))
    r=b1._case(case)
    assert r['supports']['Kt_classical_free_warping_reference'] is None
    assert r['planes']['strong']['K_flexural']==1.


@pytest.fixture(scope='module')
def integration():
    source=json.loads((Path(__file__).parent/'data/three_girt_normal_QA_input.json').read_text())
    data=apply_geometry(source['input_data'],3.35,4000.)
    cfg=w.current_configuration(data,source['configuration']['three_girt'])
    demand=w.calculate(data,cfg,verification_scope=three_girt_scope.SCHEMA)
    result=nbr.attach(demand,nbr.reference_configuration(demand))
    return demand,result


def test_current_concrete_QA_case_remains_inconclusive(integration):
    demand,result=integration;c=nbr.saved_component(result);out=b1.saved(c,demand=demand)
    assert out is not None,c.get('central_local_B1_error')
    assert out['verified_members']==['middle'] and out['ELU_combinations']==12
    assert out['maximum_B1_reference']['B1']==pytest.approx(1.0104961258712)
    r=next(r for r in out['cases'] if r['combination_id']=='ELUN_00021')
    assert r['N_compression_max_N']==pytest.approx(300.38359329827676)
    assert r['planes']['weak']['Ne_flexural_N']==pytest.approx(28918.904082128665)
    assert r['uniform_axial_force'] is False and r['amplified_local_reference_moment_polynomials'] is not None
    assert r['issues']==[]
    assert out['diagnostic_or_blocked_cases']==0 and out['local_formula_cases']==12
    assert out['local_NM_reference']['rows']
    assert out['local_NM_reference']['physical_concomitant_state'] is False
    assert out['local_NM_reference']['whole_member_approved'] is False
    assert all(out[k] is False for k in b1.SAFE_FALSE)
    assert result['cases']==demand['cases']
    assert {r['Travessa'] for r in b1.presentation_rows(c)}=={'Central'}
    from tercas.three_girt_assessment.application import assess
    item=next(x for x in assess(result)['checks'] if x['id']=='member_stability_and_analysis')
    assert item['status']=='pending' and 'foi quantificada' in item['reason']
    assert 'N variável' in item['reason']
    assert item['trace']['central_local_B1_component_sha256']==out['content_sha256']


def test_resistance_arithmetic_unchanged_and_old_scope_not_migrated(integration):
    demand,result=integration
    old=copy.deepcopy(demand);old.pop(three_girt_scope.FIELD)
    oldc=nbr.saved_component(nbr.attach(old,nbr.reference_configuration(old)))
    newc=nbr.saved_component(result)
    assert b1.saved(oldc) is None
    assert newc['rows']==oldc['rows'] and newc['capacities']==oldc['capacities']
    assert newc['per_member']==oldc['per_member']


def test_read_export_does_not_recalculate_and_tamper_rejected(integration,monkeypatch):
    from docx import Document
    demand,result=integration;c=nbr.saved_component(result)
    monkeypatch.setattr(b1,'calculate_validated',lambda *a:(_ for _ in ()).throw(AssertionError('No recalculation')))
    monkeypatch.setattr(b1,'_local_interaction',lambda *a:(_ for _ in ()).throw(AssertionError('No interaction recalculation')))
    assert b1.saved(c)
    doc=Document();b1.append_report(doc,c)
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'A rede permanece inconclusiva' in text
    for key in b1.SAFE_FALSE:
        edited=copy.deepcopy(c);edited[b1.FIELD][key]=True
        edited[b1.FIELD]['content_sha256']=b1.fingerprint({k:v for k,v in edited[b1.FIELD].items() if k!='content_sha256'})
        with pytest.raises(ValueError):b1.saved(edited,demand=demand)
    edited=copy.deepcopy(c);edited[b1.FIELD]['cases'][0]['N_compression_max_N']+=1.
    with pytest.raises(ValueError):b1.saved(edited,demand=demand)
    edited=copy.deepcopy(c);edited['source_demand_sha256']='other'
    with pytest.raises(ValueError):b1.saved(edited,demand=demand)


def test_no_global_pass_even_for_uniform_small_B1():
    demand=dict(cases=[local_case()]);out=b1.calculate_validated(demand)
    assert out['local_formula_cases']==1 and out['maximum_B1_reference']['B1']<1.1
    assert out['status']=='inconclusive_network' and not out['network_stability_qualified']


def test_Euler_failure_remains_explicit_in_actual_case_structure():
    r=b1._case(local_case((-1e6,-1e6)))
    assert r['amplified_local_reference_moment_polynomials'] is None
    assert all(p['B1_reference'] is None for p in r['planes'].values())
    assert all('compression_at_or_above_Euler_'+name in r['issues'] for name in ('strong','weak'))


@pytest.mark.parametrize('edit',['empty','wrong_girt','wrong_combination','duplicate','wrong_count',
    'N_changed','uniform_claim','factor_changed','summary_changed','empty_amplified_fields'])
def test_resealed_snapshot_cannot_change_central_coverage_or_factors(integration,edit):
    demand,result=integration;c=copy.deepcopy(nbr.saved_component(result));out=c[b1.FIELD]
    if edit=='empty':out['cases']=[]
    elif edit=='wrong_girt':out['cases'][0]['girt']='upper'
    elif edit=='wrong_combination':out['cases'][0]['combination_id']='different'
    elif edit=='duplicate':out['cases'][0]=copy.deepcopy(out['cases'][1])
    elif edit=='wrong_count':out['ELU_combinations']+=1
    elif edit=='N_changed':out['cases'][0]['segments'][0]['N_tension_positive_N']+=1
    elif edit=='uniform_claim':out['cases'][0]['uniform_axial_force']=True
    elif edit=='factor_changed':out['cases'][0]['planes']['weak']['B1_reference']=1.
    elif edit=='summary_changed':out['maximum_B1_reference']['B1']=1.
    else:
        out['cases'][0]['issues']=[]
        out['cases'][0]['local_formula_reference_applicable']=True
        out['cases'][0]['amplified_local_reference_moment_polynomials']=[]
    out['content_sha256']=b1.fingerprint({k:v for k,v in out.items() if k!='content_sha256'})
    with pytest.raises(ValueError):b1.saved(c,demand=demand)


def test_B1_interaction_uses_combination_axial_envelopes(integration):
    demand,result=integration;c=nbr.saved_component(result);out=b1.saved(c,demand=demand)
    by_case={r['combination_id']:r for r in out['cases']}
    for row in out['local_NM_reference']['rows']:
        case=by_case[row['combination_id']]
        n=-case['N_compression_max_N'] if row['axial_branch']=='compression' else max(0.,case['N_max_tension_positive_N'])
        assert all(s['N_tension_positive_N']==n for s in row['states'])
        assert not row['physical_concomitant_state'] and row['girt']=='middle'
        old=next(r for r in c['rows'] if r['combination_id']==row['combination_id'] and r['segment_id']==row['segment_id'])
        if row['maximum'] is not None and old['maximum'] is not None and row['axial_branch']=='compression':
            # Compare only compressive source intervals; tensile capacity is separate.
            if old['states'][0]['N_tension_positive_N']<0:
                assert row['maximum']['numeric_index']>=old['maximum']['numeric_index']-1e-12


@pytest.mark.parametrize('edit',['index','axial','moment','missing_branch','capacity'])
def test_resealed_local_interaction_tamper_rejected(integration,edit):
    demand,result=integration;c=copy.deepcopy(nbr.saved_component(result));out=c[b1.FIELD]
    local=out['local_NM_reference']
    if edit=='index':local['rows'][0]['states'][0]['numeric_index']=1.
    elif edit=='axial':local['rows'][0]['states'][0]['N_tension_positive_N']+=1
    elif edit=='moment':out['cases'][0]['amplified_local_reference_moment_polynomials'][0]['My_strong_Nmm'][0]+=1
    elif edit=='missing_branch':local['rows'].pop()
    else:local['source_NBR_capacities_sha256']='changed'
    out['content_sha256']=b1.fingerprint({k:v for k,v in out.items() if k!='content_sha256'})
    with pytest.raises(ValueError):b1.saved(c,demand=demand)


def test_coherently_resealed_bending_fields_must_match_original_demand(integration):
    demand,result=integration;c=copy.deepcopy(nbr.saved_component(result));out=c[b1.FIELD]
    row=out['cases'][0];row['segments'][0]['moment_polynomials']['My_strong_Nmm'][0]+=10.
    row['amplified_local_reference_moment_polynomials'][0]['My_strong_Nmm'][0]+=10.*row['planes']['strong']['B1_reference']
    out['local_NM_reference']=b1._local_interaction(out,c)
    out['content_sha256']=b1.fingerprint({k:v for k,v in out.items() if k!='content_sha256'})
    with pytest.raises(ValueError):b1.saved(c,demand=demand)


def test_legacy_v1_reads_without_migration_or_new_interaction(integration):
    demand,result=integration;c=copy.deepcopy(nbr.saved_component(result));out=c[b1.FIELD]
    out['schema']=b1.LEGACY_SCHEMA
    out['applied_to_resistance']=out.pop('applied_to_original_resistance')
    out.pop('local_NM_reference')
    for row in out['cases']:
        row.pop('axial_reference')
        if row['N_compression_max_N']>0 and not row['uniform_axial_force']:
            row['issues'].append('nonuniform_axial_force_extension_not_qualified')
            row['local_formula_reference_applicable']=False
            row['amplified_local_reference_moment_polynomials']=None
            row['status']='estimate_or_inconclusive'
    out['local_formula_cases']=sum(r['local_formula_reference_applicable'] for r in out['cases'])
    out['diagnostic_or_blocked_cases']=len(out['cases'])-out['local_formula_cases']
    out['content_sha256']=b1.fingerprint({k:v for k,v in out.items() if k!='content_sha256'})
    before=copy.deepcopy(c)
    assert b1.saved(c,demand=demand)['schema']==b1.LEGACY_SCHEMA
    assert c==before and 'local_NM_reference' not in out
    from docx import Document
    doc=Document();b1.append_report(doc,c,demand=demand)
    assert any('históric' in p.text.lower() for p in doc.paragraphs)


def test_resealed_missing_stationary_candidate_is_rejected(integration):
    demand,result=integration;c=copy.deepcopy(nbr.saved_component(result));out=c[b1.FIELD]
    local=out['local_NM_reference'];found=False
    for row in local['rows']:
        for state in row['states']:
            lo,hi=state['interval']
            if lo+1e-6<state['x_normalized']<hi-1e-6:
                # Remove all numerically coincident witnesses of this extremum,
                # not an endpoint-roundoff root or one harmless duplicate.
                u=state['x_normalized']
                row['states']=[v for v in row['states'] if v['interval']!=state['interval'] or abs(v['x_normalized']-u)>1e-7]
                row['maximum']=None if row['missing_capacity_keys'] else max(row['states'],key=lambda s:s['numeric_index'])
                found=True;break
        if found:break
    assert found,'QA must contain a non-endpoint component/interaction extremum'
    ready=[r for r in local['rows'] if r['maximum'] is not None]
    winner=max(ready,key=lambda r:r['maximum']['numeric_index']) if ready else None
    local['maximum_available']=None if winner is None else dict(combination_id=winner['combination_id'],segment_id=winner['segment_id'],
        axial_branch=winner['axial_branch'],state=winner['maximum'])
    out['content_sha256']=b1.fingerprint({k:v for k,v in out.items() if k!='content_sha256'})
    with pytest.raises(ValueError):b1.saved(c,demand=demand)


def test_uniform_axial_reference_is_conservative_for_both_signed_N_branches():
    from tercas.three_girt_axial import backend as a
    case=local_case((-200.,100.));out=b1.calculate_validated(dict(cases=[case]))
    originals=[]
    for beam in case['model']['beams']:
        binding=dict(section_id='synthetic_section',stability_member_id='middle_full_span',region_id=beam['id'])
        den={key:a.denominator(key=key,value=10000. if key in ('Nc','Nt') else 1000.,
            origin='Synthetic arithmetic oracle',**binding)
            for key in ('Nc','Nt','Mstrong_pos','Mstrong_neg','Mweak_pos','Mweak_neg')}
        p=beam['normal_action_polynomials']
        row=a.interaction_segment(N_coeff=p['N_N'],Mstrong_coeff=p['My_strong_Nmm'],
            Mweak_coeff=p['Mz_weak_Nmm'],capacities=den,combination_id='synthetic',
            segment_id=beam['id'],x_start_mm=beam['x_start_mm'],length_mm=beam['x_end_mm']-beam['x_start_mm'],
            origin='Synthetic arithmetic oracle',**binding)
        row.update(girt='middle',denominators=den,physical_member_length_mm=4000.);originals.append(row)
    ne_s=math.pi**2*200000.*1e6/4000.**2
    ne_w=math.pi**2*200000.*2e5/4000.**2
    parent=dict(rows=originals,capacities=dict(compression=dict(elastic=dict(Nex_N=ne_s,Ney_N=ne_w))),
        source_demand_sha256=out['source_demand_sha256'])
    ref=b1._local_interaction(out,parent)
    assert ref['complete'] and len(ref['rows'])==4
    for original in originals:
        branch='compression' if original['states'][0]['N_tension_positive_N']<0 else 'tension'
        equivalent=next(r for r in ref['rows'] if r['segment_id']==original['segment_id'] and r['axial_branch']==branch)
        assert equivalent['maximum']['numeric_index']>=original['maximum']['numeric_index']

    # Independent closed-form quadratic maximum, without the interaction backend.
    bs,bw=1./(1.-200./ne_s),1./(1.-200./ne_w)
    u=(20.*bs-bw)/(40.*bs)
    expected=.02+(bs*(10.+20.*u-20.*u*u)+bw*(4.-u))/1000.
    assert ref['maximum_available']['state']['numeric_index']==pytest.approx(expected,rel=1e-13)
    assert ref['maximum_available']['state']['x_normalized']==pytest.approx(u,rel=1e-13)
    assert ref['maximum_available']['axial_branch']=='compression'
    out['local_NM_reference']=ref
    out['content_sha256']=b1.fingerprint({k:v for k,v in out.items() if k!='content_sha256'})
    parent[b1.FIELD]=out
    assert b1.saved(parent,demand=dict(cases=[case]))['local_NM_reference']['complete']
