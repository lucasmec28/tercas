"""AISI nominal load-height capacity paired to the same ELU H4 field."""
import copy,json,math
from pathlib import Path
import pytest
from tercas import ue_family_reference as family,ue_reference as single
from tercas import roof_top_load as roof,aisi_torsion_component as a,aisi_roof_height as h
from tercas import torsion_study
from tercas.study_completion import complete_result
from tercas.aisi_torsion_ui import rows,text_lines,report


def data(t=2.,angle=0.,line='web_midplane'):
    d=single.load_reference(angle=angle) if t==1.2 else family.load_reference(t,4000.,angle)
    d['selected_types']=['ELU normal','ELS quase permanente'];d[roof.FIELD]=roof.choice(line)
    return d


def calculate(d):return complete_result(single.calculate_reference(d) if d['properties']['t']==1.2 else family.calculate_reference(d))


@pytest.fixture(scope='module')
def current():
    calls=[];original=a._aisi_demand
    def counted(source):
        calls.append(source['combination_id']);return original(source)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(a,'_aisi_demand',counted);result=calculate(data())
    assert len(calls)==40 and len(set(calls))==40
    return result


@pytest.fixture(scope='module',params=[1.5,2.25,2.65,3.,3.35])
def other(request):return calculate(data(request.param))


def check_all(result):
    ev=a.preserved(result)
    assert ev['schema']==h.SCHEMA and ev['H4_computed_cases']==ev['G81_computed_cases']==40
    assert ev['pending_cases']==0 and ev['strong_flexural_capacity'] is None and ev['weak_flexural_capacity'] is None
    assert not ev['physical_design_approved'] and not ev['whole_member_approved'] and not ev['NBR_capacities_used']
    assert 'não são automaticamente' in ev['load_basis']
    assert ev['roof_height_source']['first_order_model_adequacy']=='not_established'
    assert [r['combination_id'] for r in ev['records']]==[c['combination']['id'] for c in result['cases'] if c['combination']['limit_state']=='ELU']
    for r in ev['records']:
        rc=r['roof_height'];cap=rc['strong_capacity'];interaction=r['H4'];w=interaction['witness'];an=r['AISI_analysis']
        assert cap['phi_b']==.9 and cap['E_MPa']==203000 and cap['G_MPa']==78000
        assert cap['Ma_floor_Nmm']==.9*cap['Mn_floor_Nmm'] and cap['Mcre_Nmm']==rc['Mcre']['Me_Nmm']
        assert cap['Cb_applied_after_Mcre'] is False and rc['primary_torque_preserved']
        assert an['E_MPa']==182700 and an['G_MPa']==70200
        assert w['combination_id']==r['combination_id'] and w['My_physical_Nmm']==0.
        assert interaction['ratio']==pytest.approx(abs(w['Mx_physical_Nmm'])/cap['Ma_floor_Nmm']+abs(w['B_Nmm2'])/ev['bimoment_capacity']['Ba_Nmm2'])
        assert interaction['interpretation']==h.INTERPRETATION
    assert 'torsion_warping' in result['global_verification']['pending_ids'] and not result['whole_member_approved']
    assert a.preserved(json.loads(json.dumps(result)))==ev


def test_all_40_ELU_and_ELS_exclusion(current):check_all(current)
def test_other_five_sources(other):check_all(other)


def test_gravity_suction_and_P_have_different_same_combination_capacity(current):
    ev=current[a.FIELD];records={r['combination_id']:r for r in ev['records']}
    samples=[records[k] for k in ('ELUN_00001','ELUN_00019','P_ELU_01_CENTRO')]
    assert len({r['roof_height']['strong_capacity']['Ma_floor_Nmm'] for r in samples})==3
    assert [r['H4']['ratio'] for r in samples]==pytest.approx([2.0902353827923026,1.945173784,2.571922398],rel=1e-9)
    assert all(r['first_order_small_rotation_warning'] for r in samples)
    assert all(any(x['value']!=0 for x in r['roof_height']['Mcre']['primary_torque_by_action']) for r in samples)
    support=[r for r in ev['records'] if r['AISI_analysis']['source_combination'].get('point_position')=='support_limit']
    assert support and all(r['AISI_analysis']['support_limit_states_preserved'] for r in support)
    assert all('inconclusivo' in r['Parcela longitudinal'] for r in rows(ev) if r['H4 Mx/Max + My/May + B/Ba']>1)


def test_flange_load_line_changes_torque_not_nominal_linear_Mcre(current):
    flange=calculate(data(line='flange_midwidth'));ev=a.preserved(flange)
    for old,new in zip(current[a.FIELD]['records'],ev['records']):
        assert old['roof_height']['Mcre']['Me_Nmm']==new['roof_height']['Mcre']['Me_Nmm']
        assert old['roof_height']['strong_capacity']==new['roof_height']['strong_capacity']
    assert ev['records'][0]['H4']['ratio']!=current[a.FIELD]['records'][0]['H4']['ratio']


@pytest.mark.parametrize('t,angle,reason',[(1.2,0.,'críticos fortes'),(2.,5.,'Flexão fraca real')])
def test_missing_strong_or_biaxial_keeps_G81_pending_H4(t,angle,reason):
    r=calculate(data(t,angle));ev=a.preserved(r)
    assert ev['H4_computed_cases']==0 and ev['G81_computed_cases']==40
    assert all(reason in ' '.join(x['missing']) for x in ev['records'])
    assert all(x['H4'] is None for x in ev['records'])


def test_preserved_readers_no_source_reopen_curve_or_solver(current,monkeypatch):
    from tercas.aisi_research import adapter,aisi_candidate
    from docx import Document
    def fail(*args,**kwargs):raise AssertionError('Hidden recalculation')
    monkeypatch.setattr(h,'refined',fail);monkeypatch.setattr(a,'_aisi_demand',fail)
    monkeypatch.setattr(adapter,'verify_bundle',fail);monkeypatch.setattr(aisi_candidate,'flexural_floor',fail)
    monkeypatch.setattr(roof,'geometry',fail);monkeypatch.setattr(torsion_study,'section_for',fail)
    before=copy.deepcopy(current);ev=a.preserved(current);lines='\n'.join(text_lines(ev));rows(ev)
    doc=Document();report(doc,current)
    assert current==before
    assert 'adequação física da primeira' in lines and 'por combinação' in lines and 'não são automaticamente' in lines
    assert 'efeitos geométricos de altura/Wagner não estão incluídos' not in lines
    assert 'inconclusivo' in '\n'.join(x.text for x in doc.paragraphs)


def reseal(r):
    e=r[a.FIELD];e['snapshot_sha256']=a.digest({k:v for k,v in e.items() if k!='snapshot_sha256'})


@pytest.mark.parametrize('mutation',['swap','combo','material','phi','Ma','source','weak','scope','torque','ratio','count','record_shape','height_shape','Mcre_shape','cap_shape','position','actions','flag','downgrade','G81','rotation','warning','H4_shape','mode','pending','x','geometry','critical_flag','section_properties'])
def test_rehashed_snapshot_mutations_rejected(current,mutation):
    r=copy.deepcopy(current);e=r[a.FIELD];rec=e['records'][0];z=rec['roof_height'];cap=z['strong_capacity']
    if mutation=='geometry':e['roof_height_source']['geometry']['height_above_SC_mm']=0.
    if mutation=='critical_flag':z['Mcre']['production_resistance_authorized']=True
    if mutation=='section_properties':e['roof_height_source']['section']['properties']['Iy_weak_mm4']*=2
    if mutation=='H4_shape':rec['H4']='bad'
    if mutation=='mode':e['strong_capacity_mode']='single_CT'
    if mutation=='pending':z['missing']=['not_converged']
    if mutation=='x':rec['H4']['witness']['x_mm']=-1.
    if mutation=='downgrade':e['schema']=a.SCHEMA
    if mutation=='G81':rec['G81']['ratio']=0.
    if mutation=='rotation':rec['AISI_analysis']['max_abs_phi_rad']=0.
    if mutation=='warning':rec['first_order_small_rotation_warning']=False
    if mutation=='swap':rec['roof_height']=copy.deepcopy(e['records'][18]['roof_height'])
    if mutation=='combo':z['combination_sha256']='wrong'
    if mutation=='material':cap['E_MPa']=200000.
    if mutation=='phi':cap['phi_b']=1.
    if mutation=='Ma':cap['Ma_floor_Nmm']*=2
    if mutation=='source':e['roof_height_source']['strong_source']['exterior_moduli']['Wx_first_yield_mm3']*=2;e['roof_height_source']['strong_source_sha256']=a.digest(e['roof_height_source']['strong_source'])
    if mutation=='weak':rec['H4']['witness']['My_physical_Nmm']=1.
    if mutation=='scope':e['roof_height_source']['first_order_model_adequacy']='approved'
    if mutation=='torque':z['Mcre']['primary_torque_by_action'][0]['value']*=2
    if mutation=='ratio':rec['H4']['ratio']=0.
    if mutation=='count':e['H4_computed_cases']=1
    if mutation=='record_shape':e['records'][0]='bad'
    if mutation=='height_shape':rec['roof_height']='bad'
    if mutation=='Mcre_shape':z['Mcre']='bad'
    if mutation=='cap_shape':z['strong_capacity']='bad'
    if mutation=='position':rec['AISI_analysis']['source_combination']['x_mm']=1.
    if mutation=='actions':rec['AISI_analysis']['actions'][0]['q_xy_N_mm'][1]*=2
    if mutation=='flag':z['physical_design_approved']=True
    reseal(r)
    with pytest.raises(ValueError):a.preserved(r)


def test_zero_actions_no_matching_exception(current):
    d=data();raw=family.calculate_reference(d);section=torsion_study.section_for(d);ctx=h.prepare(raw,section)
    c=copy.deepcopy(raw['cases'][0]['combination']);c['coefficients']={};c['P_vector']={'normal':0.,'parallel':0.}
    r=h.capacity_for(ctx,c,{})
    assert r['status']=='no_nonzero_actions' and r['Mcre'] is None and r['strong_capacity'] is None


def test_failed_critical_does_not_fall_back_to_CT(current,monkeypatch):
    d=data();raw=family.calculate_reference(d);section=torsion_study.section_for(d);ctx=h.prepare(raw,section)
    rec=current[a.FIELD]['records'][0];source=copy.deepcopy(current['torsion_evidence']['records'][0]['analysis'])
    monkeypatch.setattr(h,'refined',lambda **kw:dict(numerically_converged=False,Me_Nmm=None,status='not_converged'))
    r=h.capacity_for(ctx,rec['AISI_analysis']['source_combination'],source)
    assert r['strong_capacity'] is None and r['missing'] and r['Mcre']['Me_Nmm'] is None
