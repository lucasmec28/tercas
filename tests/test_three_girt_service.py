import copy,json
from io import BytesIO
from pathlib import Path
import numpy as np
import pytest
from docx import Document
from tercas.three_girt_service import application as a
from tercas.three_girt_warping.application import calculate,current_configuration,attach_g81
from tercas.three_girt_warping import network
from tercas.ue_family_reference import apply_geometry
from tercas.three_girt_en_normal.application import _profile_and_section

FIXTURE=Path(__file__).parent/'data/three_girt_normal_QA_input.json'
@pytest.fixture(scope='module')
def demand():
 src=json.loads(FIXTURE.read_text());data=apply_geometry(src['input_data'],3.35,4000.)
 return attach_g81(calculate(data,current_configuration(data,src['configuration']['three_girt'])))
def config(demand):
 c=a.configuration(demand);c.update(nominal_intact_section_declared=True,model_origin='Synthetic QA');return c
@pytest.fixture(scope='module')
def component(demand):return a.calculate(demand,config(demand))

def test_all_service_and_spans_covered(demand,component):
 assert component['ELS_combinations']==7 and component['ELU_combinations_excluded']==12
 for c in component['cases']:
  assert c['combination']['limit_state']=='ELS' and len(c['segments'])==9
  assert set(c['members'])==set(a.LEVELS)
  assert c['network_local_normal_gross_sufficient']==all(s['section']['local_normal_gross_sufficient'] for s in c['segments'])
  assert all(len(s['section']['walls'])==5 and s['section']['all_exterior_fibers_checked']==832 for s in c['segments'])
 assert all(component[k] is False for k in a.FALSE_FLAGS)
 assert component['criterion']['horizontal_limit_mm']==pytest.approx(4000/120)

def test_saved_response_matches_fresh_network_response(demand):
 from tercas.three_girt_warping.application import _model
 for case in (demand['cases'][0],demand['cases'][-1]):
  model=case['model'];run=network.solve(_model(model['inputs']))
  for beam,rb in zip(model['beams'],run['beams']):
   field=a.horizontal_field(model,beam);fn=a.displacement_function(field)
   for t in (0.,.031,.25,.501,.78,1.):
    expected=network.response(run,rb,beam['x_start_mm']+t*beam['length_mm'])
    assert fn(t)==pytest.approx(expected['uz_CG_mm'],rel=5e-11,abs=1e-8)
   env=a.horizontal_extrema(field)
   grid=np.array([fn(float(t)) for t in np.linspace(0,1,151)])
   assert abs(env['maximum_absolute']['horizontal_CG_mm'])>=max(abs(grid))-1e-8

def test_classical_quartic_and_zero_gj():
 field=dict(polynomial_SC_mm=[0,2/3,0,-4/3,2/3],phi_factor_mm=0.,torsion=dict(L_mm=2.,GJ_Nmm2=0.,ECw_Nmm4=1.,m_SC_N=0.,nodal_phi_psi=[0.,0.,0.,0.]),x_start_mm=0.,length_mm=2.)
 env=a.horizontal_extrema(field)['maximum_absolute']
 assert env['t']==pytest.approx(.5) and env['horizontal_CG_mm']==pytest.approx(5*2**4/384)
 field['polynomial_SC_mm']=[0.]*5;field['phi_factor_mm']=3.
 field['torsion'].update(m_SC_N=1.,nodal_phi_psi=[0.,1/3,0.,-1/3])
 env=a.horizontal_extrema(field)['maximum_absolute']
 assert env['t']==pytest.approx(.5) and env['horizontal_CG_mm']==pytest.approx(3*5*2**4/384)

def test_normal_sign_tension_compression_and_yield(demand):
 profile,section=_profile_and_section(demand);beam=copy.deepcopy(demand['cases'][0]['model']['beams'][0]);s=section['properties']
 beam['torsion_state_parameters'].update(m_SC_N=0.,nodal_phi_psi=[0.,0.,0.,0.])
 for sign in (1.,-1.):
  beam['normal_action_polynomials'].update(N_N=[sign*10*s['A_mm2']],My_strong_Nmm=[0.],Mz_weak_Nmm=[0.])
  r=a.section_check(beam,section,profile,200000.,250.)
  assert r['local_normal_gross_sufficient']
  assert all(w['compression_upper_MPa']==pytest.approx(0 if sign>0 else 10) for w in r['walls'])
 beam['normal_action_polynomials']['N_N']=[251*s['A_mm2']]
 r=a.section_check(beam,section,profile,200000.,250.)
 assert not r['normal_elastic_sufficient'] and not r['local_normal_gross_sufficient']
 assert all(w['sufficient_integral'] for w in r['walls'])

def test_no_network_or_normative_capacity_resolve(demand,monkeypatch):
 from tercas.three_girt_axial import application as nbr
 monkeypatch.setattr(network,'solve',lambda *x,**y:pytest.fail('Network solve not permitted'))
 monkeypatch.setattr(nbr,'_capacities',lambda *x,**y:pytest.fail('NBR capacity not part of service'))
 assert a.calculate(demand,config(demand))['ELS_combinations']==7

def test_saved_export_survives_other_components(demand,component,monkeypatch):
 from tercas.three_girt_en_normal import application as en
 from tercas.three_girt_axial import application as nbr
 from tercas.three_girt_warping.report import word
 d=copy.deepcopy(demand);d[a.FIELD]=copy.deepcopy(component)
 ec=en.reference_configuration(d);ec.update(intact_section_model_declared=True,section_model_origin='QA')
 d=en.attach(d,ec);d=nbr.attach(d,nbr.reference_configuration(d))
 def forbidden(*x,**y):raise AssertionError('Display/export cannot solve')
 monkeypatch.setattr(network,'solve',forbidden);monkeypatch.setattr(a,'calculate',forbidden)
 assert a.saved_component(d)==component and en.saved_component(d) and nbr.saved_component(d)
 doc=Document(BytesIO(word(d)));text='\n'.join(p.text for p in doc.paragraphs)
 assert 'Componente horizontal de serviço' in text and 'sigma–tau' in text

@pytest.mark.parametrize('change',[lambda d:d['cases'][0]['model']['nodes'][0]['displacements'].update(uz=3.),lambda d:d['cases'].pop(),lambda d:d['input_data']['wall_els'].update(normal_denominator=100.),lambda d:d['source_geometry'].update(content_sha256='bad')])
def test_mutated_source_rejected(demand,component,change):
 d=copy.deepcopy(demand);d[a.FIELD]=copy.deepcopy(component);change(d)
 with pytest.raises((ValueError,KeyError)):a.saved_component(d)

@pytest.mark.parametrize('name',a.FALSE_FLAGS)
def test_no_scope_promotion_after_rehash(demand,component,name):
 d=copy.deepcopy(demand);d[a.FIELD]=copy.deepcopy(component);c=d[a.FIELD];c[name]=True
 c['content_sha256']=a.fingerprint({k:v for k,v in c.items() if k!='content_sha256'})
 with pytest.raises(ValueError):a.saved_component(d)

@pytest.mark.parametrize('key,value',[('nominal_intact_section_declared',False),('model_origin',''),('demand_input_fingerprint','bad')])
def test_incomplete_configuration_rejected(demand,key,value):
 c=config(demand);c[key]=value
 with pytest.raises(ValueError):a.calculate(demand,c)

@pytest.mark.parametrize('change',[
 lambda c:c['criterion'].update(horizontal_limit_mm=1.),
 lambda c:c['criterion'].update(reference_mm=120.,horizontal_limit_mm=1.),
 lambda c:c['cases'][0]['segments'].pop(),
 lambda c:c['configuration'].update(nominal_intact_section_declared=False),
 lambda c:c['configuration'].update(model_origin=''),
 lambda c:c.update(sufficient_combinations=0),
 lambda c:c['cases'][0]['segments'][0]['section']['walls'][0].update(sufficient_integral=False),
 lambda c:c['cases'][0]['segments'][0]['section'].update(normal_elastic_sufficient=False),
 lambda c:c['cases'][0].update(network_local_normal_gross_sufficient=False),
 lambda c:c['cases'][0]['members']['upper'].update(diagnostic_gross_ratio=0.),
 lambda c:c['cases'][0]['members']['upper'].update(qualified_complete_ELS_index=0.),
])
def test_rehashed_scalar_contradictions_rejected(demand,component,change):
 d=copy.deepcopy(demand);d[a.FIELD]=copy.deepcopy(component);c=d[a.FIELD];change(c)
 c['content_sha256']=a.fingerprint({k:v for k,v in c.items() if k!='content_sha256'})
 with pytest.raises(ValueError):a.saved_component(d)


def test_service_calculation_preserves_entire_original_demand(demand):
 before=copy.deepcopy(demand);d=a.attach(demand,config(demand))
 assert demand==before and {k:v for k,v in d.items() if k!=a.FIELD}==before
 assert d[a.FIELD]['original_reactions_and_rigidities_unchanged'] is True


def test_all_seven_nominal_plate_limits_and_conservative_boundary():
 # All seven current Ue entries use identical topology with their own flats.
 for t in (1.2,1.5,2.,2.25,2.65,3.,3.35):
  p={'geometry_external_mm':{'h':100.,'b':50.,'lip':17.,'t':t,'ri':t},
     'geometry_identity':{'flat_segment_counts':[1]*5,'arc_segment_counts':[1]*4}}
  walls=a.plate_limits(p,200000.)
  assert len(walls)==5 and all(w['sigma_integral_MPa']>0 for w in walls)
  for w in walls:
   exact=(.673*.95)**2*w['k']*200000.*(t/w['b_mm'])**2
   assert w['sigma_integral_MPa']<exact
