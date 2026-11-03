import copy,json,math
import pytest
from pathlib import Path
from tercas.application import example,defaults as input_defaults,calculate as legacy_calculate
from tercas.batch import calculate_batch as legacy_batch
from tercas.three_girt_application import defaults,configuration,calculate,load_cases,enabled,SCHEMA
from tercas.three_girt_frame import solve_three_girts,topology,element_response
from tercas.catalog_scan import scan_catalog,inputs_for_section
from tercas.three_girt_report import word
from tercas.three_girt_ui import diagram
from docx import Document
from io import BytesIO


def ready(area=False):
 d=example();d.update(member_application='wall_girt',P_uls=0.,P_sls=0.,P_parallel_uls=0.,P_parallel_sls=0.,q_uls=.2,q_sls=.15,q_parallel_uls=.12,q_parallel_sls=.1)
 c=defaults();c.update(enabled=True,geometry_declared=True,axial_bars_declared=True,connections_declared=True,load_line_declared=True,
 origin='SYNTHETIC QA — declared, not verified physical system',sc_y_mm=17.,sc_z_mm=0.,sc_origin='SYNTHETIC shear-centre value for regression only',
 load_y_from_CG_mm=12.,load_z_from_CG_mm=5.,direct_pp_uls_N_mm=.04,direct_pp_sls_N_mm=.03,direct_brace_factor_uls=1.4,direct_brace_factor_sls=1.)
 d['three_girt_model']=c
 if area:
  d['load_mode']='area';d['selected_types']=['ELU normal','ELS rara','ELS frequente','ELS quase permanente']
  d['area_inputs'].update(permanent_kgf_m2=8.,wind_up_kgf_m2=60.,wind_down_kgf_m2=40.,live_kgf_m2=888.)
 return d


def test_no_implicit_enable_and_no_legacy_resistance():
 assert not enabled(input_defaults())
 d=ready()
 for fn in (legacy_calculate,legacy_batch,scan_catalog):
  with pytest.raises(ValueError,match='3D'):fn(d)
 d['member_application']='purlin';assert not enabled(d)
 # Hidden girt settings remain inactive when returning to the purlin route.
 a=copy.deepcopy(d);a.pop('three_girt_model');assert legacy_calculate(d)['section_checks']==legacy_calculate(a)['section_checks']


def test_direct_physical_contract_and_gates():
 d=ready();frozen=copy.deepcopy(d);r=calculate(d);assert d==frozen
 assert r['schema']==SCHEMA and r['status']=='conditional_elastic_diagnostic'
 assert all(r[k] is False for k in ('physical_conditions_verified','resistance_qualified','ELS_qualified','whole_member_approved','legacy_route_used'))
 for case in r['cases']:
  m=case['model'];assert m['status']=='conditional_elastic_diagnostic'
  assert all(m[k] is False for k in ('physical_conditions_verified','warping_qualified','resistance_qualified','whole_member_approved'))
  assert len(m['nodes'])==12 and len(m['beams'])==9 and len(m['bars'])==6
  assert all(not b['resistance_checked'] for b in m['bars'])
  assert any(b['axial_state']=='compression' for b in m['bars'])
  assert any(abs(v['N_N']['max_abs']['N_N'])>1e-6 for v in m['girt_envelopes'].values())
  fixed=m['boundary_conditions']['fixed_dofs'];assert len(fixed)==24
  assert set(v['dof'] for v in fixed)=={'ux','uy','uz','rx'}
  assert max(abs(v) for v in m['residuals']['global_force_N'])<1e-7
  for e in m['beams']:
   for state in e['critical_sections']:
    evaluated=element_response(e,state['x_mm'])
    for key in evaluated:assert evaluated[key]==state[key]
 assert 'NBR_branches' not in r and 'ELS' not in r
 assert json.loads(json.dumps(r,allow_nan=False))==r


@pytest.mark.parametrize('key',['geometry_declared','axial_bars_declared','connections_declared','load_line_declared'])
def test_declarations_do_not_default_to_approval(key):
 d=ready();d['three_girt_model'][key]=False;r=calculate(d)
 assert r['status']=='not_solved' and not r['cases'] and r['missing'] and not r['whole_member_approved']


@pytest.mark.parametrize('key',['sc_y_mm','sc_z_mm','direct_pp_uls_N_mm','direct_pp_sls_N_mm','direct_brace_factor_uls','direct_brace_factor_sls'])
def test_missing_required_data_fail_closed(key):
 d=ready();d['three_girt_model'][key]=None;r=calculate(d);assert not r['cases'] and r['status']=='not_solved'


@pytest.mark.parametrize('field',['P_uls','P_sls','P_parallel_uls','P_parallel_sls'])
def test_point_load_is_never_silently_dropped(field):
 d=ready();d[field]=1.
 with pytest.raises(ValueError,match='concentrada ativa'):calculate(d)
 d=ready(True);d[field]=123.;r=calculate(d);assert len(r['cases'])==19


def test_full_area_distribution_and_concomitance():
 d=ready(True);r=calculate(d);assert len(r['cases'])==19
 for c in r['cases']:
  coeff=c['combination']['coefficients'];pp=coeff.get('PP',0.)*d['properties']['mass_kg_m']*9.80665/1000
  q=c['combination']['q_vector'];assert c['brace_weight_factor']==coeff.get('PP',0.)
  assert 'SC' not in coeff and 'P' not in coeff
  for factor,load in zip((.5,1.,.5),c['loads']):
   assert load['q_y_N_mm']==pytest.approx(-(factor*(q['parallel']-pp)+pp))
   assert load['q_z_N_mm']==pytest.approx(-factor*q['normal'])
   assert load['distributed_torque_CG_N']==pytest.approx(12*(-factor*q['normal'])-5*(-factor*(q['parallel']-pp)))
   pp_component=load['components'][1];assert pp_component['y_from_CG_mm']==pp_component['z_from_CG_mm']==0.
   assert pp_component['q_y_N_mm']==pytest.approx(-pp)
  m=c['model'];expected_mass=sum(b['length_mm']/1000*b['material']['mass_kg_m'] for b in m['bars'])
  assert sum(b['self_weight_N'] for b in m['bars'])==pytest.approx(expected_mass*9.80665*coeff.get('PP',0.))


@pytest.mark.parametrize('n',[0,1,2,3,7])
def test_variable_topology_and_custom_positions(n):
 d=ready();d['three_girt_model']['tie_count']=n
 c=configuration(d);assert len(c['resolved_positions_mm'])==n
 r=calculate(d);m=r['cases'][0]['model'];assert len(m['nodes'])==3*(n+2) and len(m['beams'])==3*(n+1)
 assert len(m['bars'])==(2*n+2 if n else 0)
 assert m['inputs']['attachment_x_mm']==c['resolved_positions_mm']
 assert '<svg' in diagram(d)
 if n:
  d['three_girt_model'].update(position_mode='custom',positions_mm=[d['L_mm']*(j/(n+1))**1.2 for j in range(1,n+1)])
  assert calculate(d)['cases'][0]['model']['status']=='conditional_elastic_diagnostic'


def test_invalid_configuration_and_profile_change():
 d=ready();old=copy.deepcopy(d);changed=inputs_for_section(d,20);assert d==old
 assert changed['three_girt_model']['sc_y_mm'] is None and not changed['three_girt_model']['connections_declared']
 for updates in [dict(tie_count=True),dict(tie_count=21),dict(position_mode='x'),dict(connection_mode='x'),dict(unknown=1),dict(enabled='yes'),dict(geometry_declared=1),dict(sc_y_mm=float('nan')),dict(direct_pp_uls_N_mm=-1),dict(direct_brace_factor_sls=-1),dict(position_mode='custom',positions_mm=[100,100]),dict(connection_mode='individual',connection_offsets={})]:
  x=copy.deepcopy(d);x['three_girt_model'].update(updates)
  with pytest.raises(ValueError):configuration(x)


def test_report_and_blocked_output_have_no_approval():
 r=calculate(ready());doc=Document(BytesIO(word(r)));text='\n'.join(p.text for p in doc.paragraphs)+'\n'+'\n'.join(c.text for t in doc.tables for row in t.rows for c in row.cells)
 assert 'não conclui atendimento de ELS' in text and 'não verifica resistência' in text
 assert 'NBR_branches' not in text and 'Atende' not in text
 assert 'SEM verificação de flambagem' in text and 'Cw_mm6' in text and 'não usado' in text
 d=ready();d['three_girt_model']['geometry_declared']=False;r=calculate(d);doc=Document(BytesIO(word(r)))
 assert any('Pendências' in p.text for p in doc.paragraphs)


def test_nonselected_failed_case_visible_in_word():
 r=calculate(ready());r['status']='not_solved';r['reason']='At least one diagnostic case failed.'
 r['cases'][1]['model']={'status':'not_solved','reason':'SYNTHETIC equilibrium failure'}
 doc=Document(BytesIO(word(r,0)));text='\n'.join(p.text for p in doc.paragraphs)+'\n'+'\n'.join(c.text for t in doc.tables for row in t.rows for c in row.cells)
 assert 'SYNTHETIC equilibrium failure' in text and 'COMBINAÇÃO NÃO RESOLVIDA: DIRETO_ELS' in text
 assert 'NÃO RESOLVIDO' in text and r['reason'] in text


def test_modified_bar_data_require_own_provenance():
 d=ready();d['three_girt_model']['blue']['A_mm2']*=.8
 with pytest.raises(ValueError,match='origem própria'):configuration(d)
 d['three_girt_model']['blue']['origin']='SYNTHETIC changed net-area assumption, no Gerdau attribution'
 assert configuration(d)['blue']['A_mm2']<defaults()['blue']['A_mm2']


def test_cladding_area_increment_does_not_half_profile_weight():
 d=ready(True);r0=calculate(d);d['area_inputs']['permanent_kgf_m2']+=10.;r1=calculate(d)
 dq=10.*d['area_inputs']['spacing_m']*9.80665/1000
 for a,b in zip(r0['cases'],r1['cases']):
  cp=b['combination']['coefficients'].get('CP',0.)
  assert a['combined_girt_PP_N_mm']==b['combined_girt_PP_N_mm']
  assert a['brace_weight_factor']==b['brace_weight_factor']
  for f,x,y in zip((.5,1.,.5),a['loads'],b['loads']):
   assert y['q_y_N_mm']-x['q_y_N_mm']==pytest.approx(-f*cp*dq)
   assert y['q_z_N_mm']==x['q_z_N_mm']
   assert y['distributed_torque_CG_N']-x['distributed_torque_CG_N']==pytest.approx(d['three_girt_model']['load_z_from_CG_mm']*f*cp*dq)
   assert y['components'][1]==x['components'][1]
  assert [v['self_weight_N'] for v in a['model']['bars']]==[v['self_weight_N'] for v in b['model']['bars']]
 doc=Document(BytesIO(word(r1)));text='\n'.join(p.text for p in doc.paragraphs)+'\n'+'\n'.join(c.text for t in doc.tables for row in t.rows for c in row.cells)
 assert 'telha/revestimento' in text and 'Ações características por área de influência' in text
 assert 'PP do perfil' in text and 'qY extrema' in text
