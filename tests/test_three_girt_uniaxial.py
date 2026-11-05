import copy,json,math,warnings
from io import BytesIO
from pathlib import Path
import numpy as np
import pytest
from docx import Document
from scipy.integrate import IntegrationWarning
from tercas.three_girt_uniaxial import application as a
from tercas.three_girt_warping import network
from tercas.three_girt_warping.application import calculate,current_configuration,attach_g81
from tercas.ue_family_reference import apply_geometry

@pytest.fixture(scope='module')
def demand():
 src=json.loads((Path(__file__).parent/'data/three_girt_normal_QA_input.json').read_text())
 d=apply_geometry(src['input_data'],1.5,6000.)
 return attach_g81(calculate(d,current_configuration(d,src['configuration']['three_girt'])))

def config(demand):
 c=a.configuration(demand);c.update(independent_members_declared=True,model_origin='Synthetic independent-beam QA');return c

@pytest.fixture(scope='module')
def result(demand):return a.attach(demand,config(demand))


def independent_integral(p,q):
 # Independent 128-point Gauss integration on analytic MSE transition cuts.
 L=p['L_mm'];Ig=p['Ig_mm4'];Ml=p['Ml_Nmm'];E=p['E_MPa'];z=L/2
 cuts=[0.,z,L];threshold=((1+math.sqrt(1-4*.22))/2)**2*Ml
 if q and abs(q)*L*L/8>threshold:
  root=math.sqrt(L*L-8*threshold/abs(q));cuts.extend(((L-root)/2,(L+root)/2))
 nodes,weights=np.polynomial.legendre.leggauss(128);out=0.
 for lo,hi in zip(sorted(set(cuts)),sorted(set(cuts))[1:]):
  x=(lo+hi)/2+(hi-lo)/2*nodes;m=q*x*(L-x)/2;lam=np.sqrt(abs(m)/Ml);rho=np.ones(len(x));active=lam>.673
  rho[active]=np.minimum(1.,(1-.22/lam[active])/lam[active])
  mu=np.where(x<=z,x/2,(L-x)/2)
  out+=(hi-lo)/2*float(weights@(m*mu/(E*Ig*rho)))
 return out

@pytest.mark.parametrize('q',[0.,.01,-.01,.25,-.25,1.,-1.,3.,-3.])
def test_gross_reduced_positive_negative_and_zero_against_independent_integral(demand,q):
 p=a.properties(demand['input_data']);r=a.beam_response(p,q,50.)
 assert not r['numerical_warnings']
 assert r['deflection_mm']==pytest.approx(independent_integral(p,q),rel=3e-10,abs=3e-8)
 assert r['x_mm']==pytest.approx(p['L_mm']/2 if q else 0.,abs=1e-7)
 assert abs(r['gross_uniaxial_deflection_mm'])<=abs(r['deflection_mm'])+1e-8
 assert abs(r['deflection_mm'])<=abs(r['constant_Ief_min_deflection_mm'])+1e-8


def test_reduced_half_load_is_not_half_displacement(demand):
 p=a.properties(demand['input_data']);full=a.beam_response(p,2.,50.);half=a.beam_response(p,1.,50.)
 assert full['Ief_min_over_Ig']<1 and half['Ief_min_over_Ig']<1
 assert full['deflection_mm']>2*half['deflection_mm']


def test_current_allocations_full_spans_original_demand_unchanged(demand,result):
 assert {k:v for k,v in result.items() if k!=a.FIELD}==demand
 c=a.saved_component(result);assert c['ELS_combinations']==7 and c['ELU_combinations_excluded']==12
 assert c['properties']['L_mm']==6000.
 assert all(c[k] is False for k in a.FALSE_FLAGS)
 for case,old in zip(c['cases'],[x for x in demand['cases'] if x['combination']['limit_state']=='ELS']):
  for name,load in zip(a.LEVELS,old['loads']):
   r=case['members'][name];assert r['q_Z_N_mm']==load['q_z_N_mm']
   assert r['original_distributed_load']==load
   assert r['max_abs_M_Nmm']==pytest.approx(abs(load['q_z_N_mm'])*6000.**2/8,rel=2e-15)
  assert case['members']['upper']['deflection_mm']==case['members']['lower']['deflection_mm']


def test_model_alternative_does_not_qualify_inconclusive_vlasov(demand,result):
 from tercas.three_girt_service import application as s
 cfg=s.configuration(result);cfg.update(nominal_intact_section_declared=True,model_origin='QA')
 r=s.attach(result,cfg);service=s.saved_component(r);uni=a.saved_component(r)
 assert any(not case['network_local_normal_gross_sufficient'] for case in service['cases'])
 assert any(m['isolated_component_index'] is not None for case in uni['cases'] for m in case['members'].values())
 assert all(case['members'][name]['qualified_complete_ELS_index'] is None for case in service['cases'] for name in a.LEVELS)


def test_no_solve_or_capacity_reuse(demand,monkeypatch):
 from tercas.three_girt_axial import application as nbr
 monkeypatch.setattr(network,'solve',lambda *x,**y:pytest.fail('No network solve'))
 monkeypatch.setattr(nbr,'_capacities',lambda *x,**y:pytest.fail('No resistance capacity'))
 assert a.calculate(demand,config(demand))['ELS_combinations']==7


def test_independent_from_ties_eccentricity_and_parallel_loads(demand,result):
 d=copy.deepcopy(demand['input_data']);d['area_inputs']['permanent_kgf_m2']=16.
 oldcfg=copy.deepcopy(demand['configuration']['three_girt']);oldcfg.update(tie_count=1,connection_mode='concentric',connection_offsets={},load_y_from_CG_mm=30.,load_z_from_CG_mm=20.)
 other=attach_g81(calculate(d,current_configuration(d,oldcfg)));new=a.attach(other,config(other))
 baseline=a.saved_component(result);changed=a.saved_component(new)
 # Compare matching horizontal cases despite different vertical actions/model.
 assert len(baseline['cases'])==len(changed['cases'])
 for first,last in zip(baseline['cases'],changed['cases']):
  for name in a.LEVELS:
   assert first['members'][name]['q_Z_N_mm']==last['members'][name]['q_Z_N_mm']
   assert first['members'][name]['deflection_mm']==last['members'][name]['deflection_mm']


def test_above_gross_yield_keeps_math_not_pass(demand):
 p=a.properties(demand['input_data']);r=a.beam_response(p,20.,1e6)
 assert r['sigma_gross_max_MPa']>p['fy_MPa'] and r['deflection_mm'] is not None
 assert r['isolated_component_index'] is None and not r['isolated_limit_satisfied']
 assert r['comparison']=='gross_elastic_model_exceeded'


def test_numerical_warning_prevents_index(demand,monkeypatch):
 old=a.scalar.peak
 def warn(*x,**y):warnings.warn('Synthetic quadrature warning',IntegrationWarning);return old(*x,**y)
 monkeypatch.setattr(a.scalar,'peak',warn);r=a.attach(demand,config(demand));c=a.saved_component(r)
 assert all(m['isolated_component_index'] is None and m['deflection_mm'] is None and m['numerical_warnings'] for case in c['cases'] for m in case['members'].values())

@pytest.mark.parametrize('change',[lambda d:d['cases'][0]['loads'][0].update(q_z_N_mm=999.),lambda d:d['input_data'].update(Ml_Nmm=1.),lambda d:d['input_data']['wall_els'].update(normal_denominator=999.),lambda d:d['configuration']['three_girt'].update(tie_count=0)])
def test_source_change_rejected(result,change):
 d=copy.deepcopy(result);change(d)
 with pytest.raises(ValueError):a.saved_component(d)

@pytest.mark.parametrize('key',a.FALSE_FLAGS)
def test_no_scope_promotion_even_after_rehash(result,key):
 d=copy.deepcopy(result);c=d[a.FIELD];c[key]=True;c['content_sha256']=a.fingerprint({k:v for k,v in c.items() if k!='content_sha256'})
 with pytest.raises(ValueError):a.saved_component(d)

@pytest.mark.parametrize('change',[
 lambda c:c['criterion'].update(limit_mm=999.),lambda c:c['properties'].update(L_mm=1000.),
 lambda c:c['cases'][0]['members']['upper'].update(q_Z_N_mm=999.),
 lambda c:c['cases'][0]['members']['upper'].update(isolated_limit_satisfied=True),
 lambda c:c['cases'][0]['members']['upper'].update(Ief_min_mm4=1.),
 lambda c:c['configuration'].update(independent_members_declared=False),
 lambda c:c['cases'].pop(),lambda c:c['cases'][0]['members'].pop('middle'),
 lambda c:c.update(source_reference_id='other'),lambda c:c.update(scope='approved network'),
 lambda c:c['cases'][0]['members']['upper'].update(deflection_mm=0.,diagnostic_uniaxial_ratio=0.,isolated_component_index=0.,isolated_limit_satisfied=True,comparison='within_isolated_uniaxial_limit')])
def test_rehashed_scalar_and_inventory_changes_rejected(result,change):
 d=copy.deepcopy(result);c=d[a.FIELD];change(c);c['content_sha256']=a.fingerprint({k:v for k,v in c.items() if k!='content_sha256'})
 with pytest.raises(ValueError):a.saved_component(d)


def test_four_component_chain_and_saved_exports_without_recalculation(demand,result,monkeypatch):
 from tercas.three_girt_service import application as service
 from tercas.three_girt_en_normal import application as en
 from tercas.three_girt_axial import application as nbr
 from tercas.three_girt_warping.report import word
 sc=service.configuration(result);sc.update(nominal_intact_section_declared=True,model_origin='QA');r=service.attach(result,sc)
 ec=en.reference_configuration(r);ec.update(intact_section_model_declared=True,section_model_origin='QA');r=en.attach(r,ec)
 r=nbr.attach(r,nbr.reference_configuration(r));before=copy.deepcopy(r)
 def forbidden(*x,**y):raise AssertionError('Saved display/export must not recalculate')
 for module,name in ((network,'solve'),(a,'calculate'),(a.scalar,'peak'),(a.scalar,'deflection'),(service,'calculate'),(en,'calculate'),(nbr,'calculate')):monkeypatch.setattr(module,name,forbidden)
 assert a.saved_component(r) and service.saved_component(r) and en.saved_component(r) and nbr.saved_component(r)
 doc=Document(BytesIO(word(r)));text='\n'.join(p.text for p in doc.paragraphs)
 assert 'Alternativa uniaxial com Ix efetivo variável' in text and 'não a flecha total real' in text
 assert r==before and json.loads(json.dumps(r))==r


def test_missing_declaration_rejected(demand):
 with pytest.raises(ValueError):a.calculate(demand,a.configuration(demand))
