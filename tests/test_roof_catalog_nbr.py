"""Synthetic Ue125 certificate tests. No user project, actions or fixtures."""
import copy
import json
import math
from pathlib import Path

import pytest
from tercas import roof_top_load as roof,roof_top_nbr as nbr,roof_biaxial as biaxial
from tercas import roof_biaxial_geometry as anchors,ue_catalog_reference as own
from tercas import direct_self_weight as pp,direct_roof_separated as separated
from tercas.application import defaults,calculate,fingerprint


def inputs(*,parallel=.03,line='web_midplane',span=5000.):
    d=defaults(26);d['properties'].update(E_MPa=200000.,G_MPa=77000.,fy_MPa=300.,fu_MPa=400.)
    d.update(L_mm=span,q_uls=.2,q_sls=.1,P_uls=20.,P_sls=10.,x_uls=1800.,x_sls=2200.,
             q_parallel_uls=parallel,q_parallel_sls=parallel/2,P_parallel_uls=3.,P_parallel_sls=1.,
             roof_top_load=roof.choice(line),project='Synthetic catalogue height qualification')
    return own.activate(pp.activate(d))


def rehash(r):
    """Resign only container hashes, leaving arithmetic/source proof mandatory."""
    from tercas.ue_catalog_nbr_bending import FIELD
    r['input_fingerprint']=fingerprint(r['input_data'])
    ev=r['roof_top_load_evidence'];ev['source_input_fingerprint']=r['input_fingerprint']
    ev['snapshot_sha256']=roof.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    s=r[nbr.FIELD];s['source_input_fingerprint']=r['input_fingerprint'];s['source_roof_snapshot_sha256']=ev['snapshot_sha256']
    if s.get('source_section'):s['source_section']['source_reference_sha256']=roof.digest(r[FIELD])
    for row in s['records']:
        source=next(x for x in ev['records'] if x['combination_id']==row['combination_id'])
        row['source_roof_snapshot_sha256']=ev['snapshot_sha256'];row['source_me_record_sha256']=roof.digest(source)
    s['snapshot_sha256']=roof.digest({k:v for k,v in s.items() if k!='snapshot_sha256'})


@pytest.mark.parametrize('line',['web_midplane','flange_midwidth'])
def test_exact_ue125_anchor_distinct_from_t2_ue100(line):
    d=inputs(line=line);g=roof.geometry(d);a=anchors.CATALOG_UE125
    assert g['nodes_sha256']==a['nodes_sha256']!=anchors.ANCHORS[2.]['nodes_sha256']
    assert g['section_profile_id']==a['profile_id'] and anchors.supported_geometry(g)
    anchors.validate_geometry(g,d)
    assert g['height_above_SC_mm']==pytest.approx(62.5)
    assert g['x_from_SC_mm']>0


def test_individual_weak_position_rule_never_net_cancels():
    g=roof.geometry(inputs())
    actions=[dict(name='favorable',kind='uniform',q_parallel_N_mm=10.,x_from_SC_mm=23.),
             dict(name='unfavorable',kind='uniform',q_parallel_N_mm=-1.,x_from_SC_mm=23.)]
    c=biaxial.classify_for_roof(actions,g)
    assert not c['applicable'] and c['actions'][1]['position_classification']=='destabilizing'
    assert c['weak_favorable_height_used'] is False
    assert c['combined_buckling_eigenvalue'] is False


def test_catalogue_height_contour_analytical_uniform_moment():
    from tercas.ltb_load_height import solve
    d=inputs();p=d['properties'];L=d['L_mm'];E=p['E_MPa'];G=p['G_MPa']
    s=solve(L_mm=L,E_MPa=E,G_MPa=G,Iweak_mm4=p['Iy_cm4']*1e4,J_mm4=p['J_mm4'],
        Cw_mm6=p['Cw_mm6'],actions=[],constant_end_moment_Nmm=10000.,modes=4)
    exact=math.sqrt(math.pi**2*E*p['Iy_cm4']*1e4/L**2*(G*p['J_mm4']+math.pi**2*E*p['Cw_mm6']/L**2))
    assert s['Me_Nmm']==pytest.approx(exact,rel=2e-14)
    assert s['primary_torsion_resistance_included'] is False


@pytest.fixture(scope='module')
def result():
    return nbr.attach(roof.attach(calculate(inputs())))


def test_FLT_is_computed_but_distortion_and_biaxial_stay_pending(result):
    e=nbr.preserved(result);s=e['source_section'];r=e['records'][0]
    assert s['kind']=='own_catalog_Ue125_bending_components_v1'
    assert e['computed_cases']==1 and e['pending_cases']==0
    assert r['status']==nbr.COMPUTED and r['FLT']['MRd_flt_Nmm']>0
    assert s['strong_distortional_exempt'] is False and s['strong_bending_complete'] is False
    assert r['MRd_distortional_Nmm'] is None and r['MRd_bending_component_Nmm'] is None
    assert r['bending_component_index'] is None and r['governing_bending_components']==[]
    assert r['bending_component_status']=='pending_distortional'
    assert r['biaxial_pending']['index'] is None and 'biaxial' not in r
    assert e['domain']['end_mm']==5000. and not e['domain']['manual_effective_lengths_used']
    assert e['whole_member_approved'] is False
    assert nbr.preserved(json.loads(json.dumps(result,allow_nan=False)))==e


@pytest.mark.parametrize('mutation',['promote_D','minimum','biaxial','scope_removed','curve','capacity','kind','forged_legacy','source_kind','material','SC','height'])
def test_rehashed_promotion_or_source_substitution_rejected(result,mutation):
    from tercas.ue_catalog_nbr_bending import FIELD
    r=copy.deepcopy(result);e=r[nbr.FIELD];row=e['records'][0];s=e['source_section']
    if mutation=='promote_D':s['strong_distortional_exempt']=True;s['strong_bending_complete']=True
    elif mutation=='minimum':row['MRd_bending_component_Nmm']=row['FLT']['MRd_flt_Nmm'];row['bending_component_index']=row['index']
    elif mutation=='biaxial':row['biaxial']={'status':'computed_fixed_position','governing':{'index':0.}}
    elif mutation=='scope_removed':
        for me in r['roof_top_load_evidence']['records']:me.pop('separate_axis_capacity_scope',None)
        row.pop('biaxial_pending',None)
    elif mutation=='curve':
        row['FLT']['MRd_flt_Nmm']*=2;row['index']/=2;row['criterion_status']='meets' if row['index']<=1 else 'fails'
    elif mutation=='capacity':
        r[FIELD]['strong']['local']['MRd_local_Nmm']*=2;s['MRd_section_effective_Nmm']*=2;row['MRd_section_effective_Nmm']*=2
        ev=r[FIELD];ev['snapshot_sha256']=roof.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    elif mutation=='kind':s['kind']='own_Ue100_family'
    elif mutation=='forged_legacy':
        s['kind']='own_Ue100_family';s['strong_bending_complete']=True;s['strong_distortional_exempt']=True
        ev=r[FIELD];ev.update(reference_id=s['reference_id'],model={k:s[k] for k in ('E_MPa','G_MPa','fy_MPa')},
            signed_scalar_capacities={side:dict(W_mm3=s['W_mm3'],Wc_mm3=s['Wc_mm3'],Ml_Nmm=s['Ml_Nmm'],
                MRd_local_Nmm=s['MRd_section_effective_Nmm'],MRd_dist_Nmm=None) for side in ('strong_positive','strong_negative')})
    elif mutation=='source_kind':s['source_reference_field']='ue_family_reference_evidence'
    elif mutation=='material':r['input_data']['properties']['fy_MPa']=301.
    elif mutation=='height':r['roof_top_load_evidence']['geometry']['height_above_SC_mm']=0.
    else:
        g=r['roof_top_load_evidence']['geometry'];g['SC_xy_mm'][0]=-100.;g['x_from_SC_mm']=g['load_x_from_web_midplane_mm']+100.
        for source,combo in zip(r['roof_top_load_evidence']['records'],roof.combination_inventory(r)):
            source['actions']=separated.actions(combo,g,include_parallel=True)[0]
            source['separate_axis_capacity_scope']=biaxial.classify_for_roof(source['actions'],g)
    rehash(r)
    with pytest.raises(ValueError):nbr.preserved(r)


def test_reader_never_reopens_sources_or_resolves(result,monkeypatch):
    from tercas import ue_catalog_nbr_bending as qualification,torsion_study
    before=copy.deepcopy(result)
    def fail(*a,**k):raise AssertionError('Saved reader reopened/recalculated source')
    monkeypatch.setattr(qualification,'qualify',fail);monkeypatch.setattr(own,'_source',fail)
    monkeypatch.setattr(roof,'refined',fail);monkeypatch.setattr(nbr,'flt_mse',fail)
    monkeypatch.setattr(torsion_study,'section_for',fail)
    monkeypatch.setattr(Path,'read_text',fail);monkeypatch.setattr(Path,'read_bytes',fail)
    assert nbr.preserved(result)==result[nbr.FIELD] and result==before


def test_partial_report_never_calls_missing_D_exemption(result):
    from docx import Document
    from tercas.roof_top_nbr_ui import report
    doc=Document();report(doc,result);text='\n'.join(p.text for p in doc.paragraphs)
    assert 'MRd,FLT=' in text and 'Distorção forte pendente, sem dispensa' in text
    assert 'dispensa forte específica' not in text
