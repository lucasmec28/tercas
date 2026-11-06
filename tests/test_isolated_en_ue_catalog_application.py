"""New route and readers: signed fields, all segments, same original authority."""
import copy
import json
import math
from io import BytesIO
import pytest
from docx import Document
from tercas import isolated_en_ue_catalog_application as en
from tercas import isolated_en_ue_catalog_ui as ui
from tercas import isolated_en_application as legacy
from tercas import ue_catalog_reference as own
from tercas import en_ue_bending_applicability as applicability
from tercas import en_ue_qualified_library as normal
from tercas.application import fingerprint
from en_ue_test_helpers import inputs,run


def declared(d):
    d[en.CHOICE]=en.choice(d,declared=True,origin='Seção nominal intacta declarada no ensaio.')
    return d


@pytest.fixture(scope='module')
def direct():
    d=declared(inputs(0));d.update(P_uls=12.,x_uls=1700.,q_parallel_uls=.002,P_parallel_uls=1.)
    return run(d)


@pytest.fixture(scope='module')
def tall():
    d=declared(inputs(82,angle=5.));return run(d)


def test_direct_pipeline_independent_signed_shear_and_material(direct):
    ev=en.preserved(direct);check=ev['records'][0]['check']
    assert ev['shear_computed_cases']==ev['mv_computed_cases']==1
    assert ev['mv_sufficient_cases']==1 and ev['ELS_cases_excluded']==1
    assert check['shear']['strong_ratio_upper']>check['shear']['weak_ratio_upper']>0
    assert check['source_analysis_material']=={'E_MPa':200000.,'G_MPa':77000.}
    assert check['capacity_reference']['material']==en.MATERIAL
    assert legacy.FIELD not in direct
    legacy.validate_saved_global(direct)
    global_row=next(x for x in direct['global_verification']['checks'] if x['id']=='torsion_warping')
    assert global_row['status']=='pending' and global_row['index'] is None
    assert 'dois cortantes calculados em 1' in global_row['reason'] and 'M–V calculada em 1' in global_row['reason']
    assert 'não verifica B/Tsv/Tw' in global_row['reason'] and 'EN6.1.6' in global_row['reason']
    assert all(check[k] is False for k in en.FLAGS)
    assert not direct['whole_member_approved']
    assert en.preserved(json.loads(json.dumps(direct)))==ev
    assert check['original_source_binding']['catalog_source_binding']==own.preserved(direct)['source_binding']
    assert 'NBR_capacities_used' in check and not check['NBR_capacities_used']


def test_tall_weak_shear_computed_mv_pending_without_index(tall):
    ev=en.preserved(tall);check=ev['records'][0]['check']
    assert ev['shear_computed_cases']==1 and ev['mv_pending_cases']==1 and not ev['mv_computed_cases']
    assert check['mv']['index_upper'] is None and 'Le' in check['mv']['reason']
    assert all(p['signed_interaction'] is None for p in check['pieces'])
    assert check['shear']['weak_ratio_upper']>0


def test_absent_and_disabled_do_not_activate_legacy():
    d=inputs(0);r=run(d)
    assert en.FIELD not in r and legacy.FIELD not in r
    d[en.CHOICE]=en.choice(d,enabled=False);r=run(d);assert en.FIELD not in r
    d[en.CHOICE]=en.choice(d);ev=en.preserved(run(d))
    assert ev['pending_demand_cases']==1 and 'intacta' in ev['reason']


def test_changed_profile_material_optin_and_any_input_invalidates(direct):
    for path,value in [(('q_uls',),.04),(('properties','fy_MPa'),300.),(('L_mm',),5000.),((en.CHOICE,'enabled'),False),
                       (('ue_catalog_reference','catalog_index'),1)]:
        r=copy.deepcopy(direct);x=r['input_data']
        for k in path[:-1]:x=x[k]
        x[path[-1]]=value
        with pytest.raises(ValueError):en.preserved(r)
    d=copy.deepcopy(direct['input_data']);d['properties']['fy_MPa']=300.
    assert en.reset_changed_declaration(d) and not d[en.CHOICE]['intact_section_model_declared']
    d=copy.deepcopy(direct['input_data']);d['catalog_index']=1;d=own.activate(d)
    assert en.reset_changed_declaration(d) and not d[en.CHOICE]['intact_section_model_declared']


def reseal(r):
    ev=r[en.FIELD]
    for row in ev['records']:
        if row['check']:row['check']['content_sha256']=en.digest({k:v for k,v in row['check'].items() if k!='content_sha256'})
    ev['snapshot_sha256']=en.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})


@pytest.mark.parametrize('mutation',['index','weak','zero','sign','original','binding','normal_hash','identity','material','flags','coverage','piece','count','curling','lag','sha','missing'])
def test_rehashed_tampering_rejected_on_all_pieces(direct,mutation):
    r=copy.deepcopy(direct);ev=r[en.FIELD];row=ev['records'][0];c=row['check'];p=c['pieces'][len(c['pieces'])//3]
    if mutation=='index':c['mv']['index_upper']=0.
    elif mutation=='weak':c['shear']['weak_ratio_upper']=0.
    elif mutation=='zero':p['fields']['N']['lo'][0]=1e-300
    elif mutation=='sign':p['fields']['My']['lo'][0]*=-1
    elif mutation=='original':p['fields']['Mx_original']['lo'][0]*=.5
    elif mutation=='binding':row['original_source_binding']['catalog_source_binding']['nodes_sha256']='a'*64
    elif mutation=='normal_hash':row['original_source_binding']['qualified_normal_sha256']='b'*64
    elif mutation=='identity':row['original_source_binding']['normal_source_binding']=normal.qualified_reference(1)['source_binding']
    elif mutation=='material':c['capacity_reference']['material']['E_MPa']=200000.
    elif mutation=='flags':c['EN_6_1_6_qualified']=True
    elif mutation=='coverage':c['pieces'].pop(9)
    elif mutation=='piece':p['source_piece']['element_id']='OTHER'
    elif mutation=='count':ev['mv_sufficient_cases']=99
    elif mutation=='curling':c['applicability']['curling_panels']['weak_web']['ratio_upper']=0.
    elif mutation=='lag':c['applicability']['axes']['My']['zero_zones'][0]['Le_lower_mm']=99999.
    elif mutation=='sha':row['source_analysis_sha256']='f'*64;row['original_source_binding']['source_analysis_sha256']='f'*64
    elif mutation=='missing':p['missing_branches']=['My_positive']
    reseal(r)
    with pytest.raises(ValueError):en.preserved(r)


def test_saved_json_ui_word_no_solver_builder_or_source(direct,monkeypatch):
    from tercas import torsion_study,direct_torsion,en_ue_catalog_operators
    def fail(*a,**k):raise AssertionError('Saved reader must not solve or build a section')
    monkeypatch.setattr(torsion_study,'section_for',fail);monkeypatch.setattr(direct_torsion,'solve_member',fail)
    monkeypatch.setattr(own,'_source',fail);monkeypatch.setattr(en_ue_catalog_operators,'build_catalog_component_sections',fail)
    monkeypatch.setattr(normal,'build_qualified_component_sections',fail)
    before=copy.deepcopy(direct);ev=en.preserved(direct);doc=Document();ui.report(doc,direct)
    stream=BytesIO();doc.save(stream);text='\n'.join(p.text for p in Document(BytesIO(stream.getvalue())).paragraphs)
    assert ui.rows(ev)[0]['Teto M–V EN6.27']>0
    assert 'EN6.1.6' in text and 'NÃO estão resolvidos' in text and 'DIRECT_ELU' in text
    assert direct==before


def _source(index,L,q=(0.,1.),P=(0.,0.),a=1000.):
    from tercas.catalog_torsion_section import prepare
    s=prepare(index,arc_segments=32)['section']
    loads=[dict(kind='uniform',q_xy_N_mm=list(q))]
    if any(P):loads.append(dict(kind='point',force_xy_N=list(P),s_mm=a))
    return dict(length_mm=L,loads=loads,section=s)


@pytest.mark.parametrize('index',range(83))
def test_all_83_scalar_curling_is_source_specific(index):
    n=normal.qualified_reference(index)['source_binding'];s=_source(index,10000.,q=(.1,1.))
    e=applicability.assess(s,n)
    assert e['qualified']
    assert e['nodes_sha256']==s['section']['nodes_sha256']
    assert all(p['ratio_upper']<1 for p in e['curling_panels'].values())


def test_exact_zone_roots_opposed_loads_and_nonreversal_P():
    n=normal.qualified_reference(0)['source_binding']
    same=applicability.assess(_source(0,4000.,q=(0.,1.),P=(0.,1.),a=10.),n)
    assert len(same['axes']['Mx']['zero_zones'])==1 and same['axes']['Mx']['zero_zones'][0]['Le_lower_mm']==4000.
    opposite=applicability.assess(_source(0,4000.,q=(0.,1.),P=(0.,-2200.),a=2000.),n)
    zones=opposite['axes']['Mx']['zero_zones']
    assert len(zones)==3 and min(z['Le_lower_mm'] for z in zones)==400.
    assert not opposite['qualified']
    assert not same['axes']['My']['active']


def test_strict_Le_threshold_no_tolerance_and_tiny_action():
    n=normal.qualified_reference(0)['source_binding'];d=n['nominal_identity']['dimensions_mm']
    from fractions import Fraction as F
    edge=en.core._outward(50*(F(d['bf'])-F(d['t'])/2),1)
    for L,want in [(edge,False),(math.nextafter(edge,math.inf),True),(math.nextafter(edge,0.),False)]:
        e=applicability.assess(_source(0,L,q=(0.,1e-300)),n)
        assert e['axes']['Mx']['active'] and e['qualified'] is want


def test_all_segments_replayed_not_only_extreme_witnesses(direct):
    r=copy.deepcopy(direct);c=r[en.FIELD]['records'][0]['check']
    summary=r['torsion_evidence']['records'][0]['analysis']
    witnesses={w['element_id'] for w in summary['witnesses']}
    p=next(p for p in c['pieces'] if p['source_piece']['element_id'] not in witnesses)
    p['fields']['Vstrong']['lo'][0]=p['fields']['Vstrong']['hi'][0]=0.
    reseal(r)
    with pytest.raises(ValueError):en.preserved(r)


@pytest.mark.parametrize('weak,expected_missing',[(0.,False),(-1/512,False),(1/512,True)])
def test_absent_unused_sign_does_not_block_other_signed_branch(weak,expected_missing):
    d=declared(inputs(6,L=4096.));d['q_parallel_uls']=weak
    ev=en.preserved(run(d));c=ev['records'][0]['check']
    assert ev['shear_computed_cases']==1
    assert not c['capacity_reference']['eligible_components']['My_negative']
    assert ('My_negative' in c['mv']['missing_branches']) is expected_missing
    assert (c['mv']['index_upper'] is None) is expected_missing
    if weak==0.:
        for p in c['pieces']:
            assert p['fields']['My']['lo']==p['fields']['My']['hi']==[0.,0.,0.]
            assert p['signed_interaction']['identically_zero_by_exact_coefficients']['My']
            assert 'My_negative' not in p['required_branches']


def test_area_preserves_every_support_limit_and_both_sides_of_P():
    d=declared(inputs(0,angle=5.,mode='area'));d['selected_types']=['ELU normal']
    d['area_inputs'].update(permanent_kgf_m2=1.,live_kgf_m2=1.,wind_up_kgf_m2=1.,wind_down_kgf_m2=1.)
    r=run(d);ev=en.preserved(r)
    assert ev['shear_computed_cases']==ev['ELU_cases'] and not ev['pending_demand_cases']
    row=next(x for x in ev['records'] if any(p['source_piece']['kind']=='support_limit' for p in x['check']['pieces']))
    p=row['check']['pieces'][-1]
    assert p['source_piece']['kind']=='support_limit'
    assert p['fields']['Mx']['lo']==p['fields']['Mx']['hi']==[0.,0.,0.]
    corrupted=copy.deepcopy(r);e=corrupted[en.FIELD]
    changed=next(x for x in e['records'] if x['combination_id']==row['combination_id'])
    changed['check']['pieces'].pop()
    reseal(corrupted)
    with pytest.raises(ValueError):en.preserved(corrupted)


def test_non_dyadic_reactions_keep_exact_physical_support_zeros():
    from fractions import Fraction as F
    d=declared(inputs(6));d.update(q_parallel_uls=-.001,P_parallel_uls=-.7,P_uls=7.3,x_uls=1700.)
    r=run(d);ev=en.preserved(r);c=ev['records'][0]['check']
    assert c['mv']['index_upper'] is not None and not c['mv']['missing_branches']
    first,last=c['pieces'][0],c['pieces'][-1]
    assert first['field_controls'][0]['intervals']['My']==last['field_controls'][-1]['intervals']['My']==[0.,0.]
    assert first['field_controls'][0]['intervals']['Mx']==last['field_controls'][-1]['intervals']['Mx']==[0.,0.]
    proof=c['equilibrium_proof'];summary=r['torsion_evidence']['records'][0]['analysis']
    assert proof['source_left_force_xy_N']==summary['support_reactions']['left_force_xy_N']
    expected=-F(-.001)*4000/2-F(-.7)*(4000-1700)/4000
    saved=proof['rational_left_force_xy_N'][0]
    assert F(int(saved['numerator']),int(saved['denominator']))==expected
    assert r['input_data']==d and proof['original_demand_unchanged']


def test_rehashed_source_reaction_or_centroid_is_rejected(direct):
    for change in ('reaction','right_reaction','centroid','method','order','prismatic'):
        r=copy.deepcopy(direct);rec=r['torsion_evidence']['records'][0]
        if change=='reaction':rec['analysis']['support_reactions']['left_force_xy_N'][0]+=.01
        elif change=='right_reaction':rec['analysis']['support_reactions']['right_force_xy_N'][0]+=.01
        elif change=='method':rec['analysis']['method']='OTHER_MODEL'
        elif change=='order':rec['analysis']['analysis_domain']['order']=2
        elif change=='prismatic':rec['analysis']['analysis_domain']['prismatic_single_span']=False
        else:rec['analysis']['section']['properties']['centroid_xy_mm'][0]*=1.1
        ev=r[en.FIELD];ev['records'][0]['source_summary_record_sha256']=en.digest(rec)
        ev['source_torsion_snapshot_sha256']=en.digest(r['torsion_evidence']);reseal(r)
        with pytest.raises(ValueError):en.preserved(r)


def test_rebuilt_different_coherent_field_cannot_replace_original_inputs(direct):
    r=copy.deepcopy(direct);rec=r['torsion_evidence']['records'][0];s=rec['analysis']
    for a in s['loads']:
        key='q_xy_N_mm' if a['kind']=='uniform' else 'force_xy_N'
        a[key]=[2*v for v in a[key]]
    for key in ('left_force_xy_N','right_force_xy_N'):s['support_reactions'][key]=[2*v for v in s['support_reactions'][key]]
    ev=r[en.FIELD];row=ev['records'][0]
    row['check']=en._calculate(s,[p['source_piece'] for p in row['check']['pieces']],row['original_source_binding'])
    row['source_summary_record_sha256']=en.digest(rec)
    ev['source_torsion_snapshot_sha256']=en.digest(r['torsion_evidence']);reseal(r)
    with pytest.raises(ValueError,match='Cargas/vetores'):en.preserved(r)


def test_rehashed_PP_application_line_cannot_move_to_top(direct):
    r=copy.deepcopy(direct);rec=r['torsion_evidence']['records'][0];s=rec['analysis']
    pp=next(a for a in s['loads'] if a['name']=='PP');top=next(a for a in s['loads'] if a['name']=='EXTERNAL')
    pp['application_xy_mm']=top['application_xy_mm'].copy()
    ev=r[en.FIELD];row=ev['records'][0]
    row['check']=en._calculate(s,[p['source_piece'] for p in row['check']['pieces']],row['original_source_binding'])
    row['source_summary_record_sha256']=en.digest(rec);ev['source_torsion_snapshot_sha256']=en.digest(r['torsion_evidence']);reseal(r)
    with pytest.raises(ValueError,match='PP deve permanecer'):en.preserved(r)


def test_stale_catalog_choice_never_intercepts_a_legacy_result():
    from test_direct_torsion import inputs as legacy_inputs
    d=legacy_inputs();d[en.CHOICE]=en.choice(d,declared=True,origin='Stale catalogue choice')
    result=dict(input_data=d)
    assert en.finalize(result) is result and en.FIELD not in result


def test_independent_closed_form_q_P_reactions_and_shear_floors(direct):
    from fractions import Fraction as F
    d=direct['input_data'];L=F(d['L_mm']);c=direct[en.FIELD]['records'][0]['check']
    mass=F(d['properties']['mass_kg_m']*9.80665/1000.*1.25)
    # The action producer computes the characteristic PP then its factor;
    # this independent expression retains that documented operation order.
    qstrong=F(d['q_uls'])+mass;Pstrong=F(d['P_uls']);a=F(d['x_uls'])
    qweak=F(d['q_parallel_uls']);Pweak=F(d['P_parallel_uls'])
    for axis,q,P in [('strong',qstrong,Pstrong),('weak',qweak,Pweak)]:
        left=q*L/2+P*(L-a)/L;right=q*L/2+P*a/L
        exact=max(abs(left),abs(right))/F(c['capacity_reference']['shear_capacity_lower_N'][axis])
        assert c['shear'][axis+'_ratio_upper']>=float(exact)
        assert c['shear'][axis+'_ratio_upper']==pytest.approx(float(exact),rel=3e-15)
    assert c['capacity_reference']['shear_capacity_lower_N']['strong']!=c['capacity_reference']['shear_capacity_lower_N']['weak']
