"""Declared integrated reference, not a published whole-case MSE benchmark.

CBCA Ex07/09 strong properties/static stages + Pierin strong criticals.
Expected values are from a separate math-only oracle. MLE is not fitted.
"""
from pathlib import Path
import json,unittest,copy
from io import BytesIO
from docx import Document
from tercas.application import defaults,calculate,rows
from tercas.batch import calculate_batch
from tercas.report import batch_word,word
from tercas.report_audit import technical_value

ORACLE=json.loads((Path(__file__).parent/'fixtures/full_case_oracle_20261103.json').read_text())

def reference_input(J=130.,mode='area'):
 d=defaults(19)
 assert {k:d['properties'][k] for k in ('h','bf','lip','t')}==dict(h=100,bf=50,lip=17,t=1.2)
 d.update(project='Caso integrado declarado CBCA/Pierin — não é exemplo MSE integral publicado',
   load_mode=mode,selected_types=['ELU normal','ELS rara'],L_mm=4000.,x_uls=2000.,x_sls=2000.,
   q_uls=0.,P_uls=1500.,q_sls=0.,P_sls=1000.,route_domain=True,
   ELS_limit_mm=4000/180,ELS_origin='L/180 adotado para este exercício, não limite extraído do Ex09',
   actions_origin='Comparador Ex09: Pd=1500 N já de cálculo, sem PP somente neste comparador. Extensão ELS Pk=1000 N declarada.',
   property_origin='CBCA 2014 Ex07/09 pp62–71: propriedades e J130 mm4; variante J100 do catálogo explicitamente separada. Garfos/cargas no CT são idealizações, não vínculos físicos certificados.',
   inclination={'value':0.,'unit':'degrees'})
 d['properties']['J_mm4']=J
 d['segments']=[dict(start_mm=0.,end_mm=4000.,Ly_top_effective_mm=4000.,
    Ly_bottom_effective_mm=4000.,Lz_effective_mm=4000.,Cb_mode='one',
    restraint_provenance='Garfos ideais nas extremidades; sem tirantes intermediários ou telha. Cargas idealizadas no CT, sem torção primária.')]
 # Keep Pierin's original strong criticals and origin; never touch Mly or insert R04 data.
 assert d['Ml_Nmm']==4590000. and d['Mdist_Nmm']==4610000.
 return d

class FullCaseReference(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.batches={J:calculate_batch(reference_input(J)) for J in (130.,100.)}
 def close(self,x,y):self.assertAlmostEqual(x,y,delta=max(abs(y)*1e-10,1e-8))
 def main_case(self,J):return next(c for c in self.batches[J]['cases'] if c['combination']['id']=='P_ELU_01_CENTRO')
 def test_combinations_and_self_weight_counted_once(self):
  r=self.batches[130.];c=self.main_case(130.)['combination']
  self.assertEqual(len(r['cases']),50)
  self.close(r['load_bundle']['case_q_N_mm']['PP'],.0208881645)
  self.close(c['q_N_mm'],.026110205625);self.close(c['P_N'],1500.)
  self.assertEqual(c['coefficients'],dict(PP=1.25,CP=1.4,P=1.5))
 def test_simultaneous_static_state(self):
  c=self.main_case(130.);ev=c['evidence']['inclination'];p=next(s for s in ev['states'] if s['x_mm']==2000. and s['side']=='left')['normal']
  target=ORACLE['variants']['CBCA_J130']['loads']['PP_plus_P']
  self.close(p['M_Nmm'],target['Mmax_Nmm']);self.close(p['V_N'],750.);self.close(p['Rleft_N'],target['R_N'])
  self.assertNotEqual(p['V_N'],target['Vmax_N'])
 def test_local_and_shear_match_independent_oracle(self):
  e=self.main_case(130.)['evidence']
  self.close(e['NBR_branches']['local']['MRd_Nmm'],ORACLE['local']['M0Rd_Nmm'])
  self.close(e['section_checks']['shear']['VRd_N'],ORACLE['shear']['VRd_N'])
 def test_distortional_branch_uses_documented_gate_not_optional_capacity(self):
  d=self.main_case(130.)['evidence']['NBR_branches']['distortional']
  self.assertEqual(d['status'],'exempt_Table14');self.assertNotIn('MRd_Nmm',d)
 def test_flt_variants_keep_J_difference_visible(self):
  for J,key in ((130.,'CBCA_J130'),(100.,'catalog_J100')):
   c=self.main_case(J);f=c['evidence']['FLT_segments'][0];o=ORACLE['variants'][key]
   self.close(f['Me_Nmm'],o['Me_Nmm']);self.close(f['FLT']['MRd_flt_Nmm'],o['MRd_FLT_Nmm'])
   self.assertGreater(f['index'],2.3)
  self.assertNotEqual(self.main_case(100.)['evidence']['FLT_segments'][0]['Me_Nmm'],self.main_case(130.)['evidence']['FLT_segments'][0]['Me_Nmm'])
 def test_MV_below_one_does_not_override_failed_FLT(self):
  c=self.main_case(130.);b=c['evidence']['NBR_branches'];o=ORACLE['variants']['CBCA_J130']['loads']['PP_plus_P']['MV_max']
  self.close(b['MV']['result']['index_squared'],o['index']);self.assertLess(o['index'],1.)
  self.assertTrue(any(r['Verificação'].startswith('FLT') and r['Situação']=='Não atende' for r in c['rows']))
  self.assertFalse(self.batches[130.]['whole_member_approved'])
 def test_ELS_closed_form_when_effective_inertia_equals_gross(self):
  c=next(c for c in self.batches[130.]['cases'] if c['combination']['id']=='P_ELS_01_CENTRO')
  E=200000.;I=441500.;L=4000.;q=.0208881645;P=1000.
  self.assertLess((q*L**2/8+P*L/4)/4590000.,.673**2)
  delta=5*q*L**4/(384*E*I)+P*L**3/(48*E*I)
  self.close(c['evidence']['ELS']['deflection_mm'],delta)
  self.close(c['evidence']['ELS']['index'],delta/(L/180))
 def test_original_Ex09_loading_not_mistaken_for_MLE_MSE_identity(self):
  r=calculate(reference_input(130.,'direct'));b=r['NBR_branches']
  self.close(b['local']['Msd_Nmm'],1500000.)
  self.close(b['MV']['result']['index_squared'],ORACLE['variants']['CBCA_J130']['loads']['Ex09_P_only']['MV_max']['index'])
  self.assertGreater(abs(b['MV']['result']['index_squared']-.592103814),.01)
  self.assertFalse(r['whole_member_approved'])
 def test_MC_keeps_strong_inputs_failure_and_physical_scope(self):
  r=self.batches[130.];before=copy.deepcopy(r);doc=Document(BytesIO(batch_word(r)))
  s='\n'.join([p.text for p in doc.paragraphs]+[c.text for t in doc.tables for row in t.rows for c in row.cells])
  for token in ('J_mm4','4590000,00','4610000,00','Não atende','NÃO É APROVAÇÃO GLOBAL','sem travamento da telha'):
   self.assertIn(token,s)
  table=next(t for t in doc.tables if t.rows[0].cells[0].text=='Campo e unidade')
  values={row.cells[0].text:row.cells[1].text for row in table.rows[1:]}
  self.assertEqual(values['J_mm4'],technical_value(r['common_input_snapshot']['selected_section']['fields']['J_mm4']['value']))
  self.assertEqual(r,before)

if __name__=='__main__':unittest.main(verbosity=2)
