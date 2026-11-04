"""Bounded girt integration: orientation, combinations, gross-only diagnostics.
No numerical result here qualifies real ties, weak Ief or resistance.
"""
import copy,math,unittest
from io import BytesIO
from docx import Document
from tercas.application import defaults,calculate,build_spec,rows
from tercas.batch import calculate_batch,area_bundle,case_inputs
from tercas.load_combinations import COMBINATION_TYPES
from tercas.member_application import member_kind,validate,wall_els_config
from tercas.report import word,batch_word
from tercas.report_audit import technical_value

def fixture(mode='direct'):
 d=defaults(19)
 d.update(member_application='wall_girt',load_mode=mode,project='Teste Travessa — rigidez arbitrária, não projeto',L_mm=4000.,route_domain=True,
  q_uls=.2,q_sls=.1,P_uls=0.,P_sls=0.,q_parallel_uls=.15,q_parallel_sls=.1,P_parallel_uls=0.,P_parallel_sls=0.,
  x_uls=2000.,x_sls=2000.,inclination={'value':23.,'unit':'degrees'},selected_types=list(COMBINATION_TYPES))
 d['area_inputs'].update(spacing_m=1.5,permanent_kgf_m2=10.,live_kgf_m2=99.,wind_up_kgf_m2=120.,wind_down_kgf_m2=50.)
 d['segments']=[dict(start_mm=0.,end_mm=4000.,Ly_top_effective_mm=4000.,Ly_bottom_effective_mm=4000.,Lz_effective_mm=4000.,Cb_mode='one',restraint_provenance='Garfos ideais, sem crédito de tirantes; teste')]
 return d

def spring(k=10.,anchored=True):
 return dict(enabled=True,anchorage_confirmed=anchored,origin='Hipótese matemática de teste; não rigidez recomendada',springs=[dict(x_mm=2000.,k_N_mm=k,origin='Valor arbitrário para controle matemático')])

def doctext(data):
 doc=Document(BytesIO(data));return '\n'.join([p.text for p in doc.paragraphs]+[c.text for t in doc.tables for r in t.rows for c in r.cells])

class GirtBackend(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.d=fixture();cls.free=calculate(cls.d)
  cls.tied_d=copy.deepcopy(cls.d);cls.tied_d['wall_tie_study']=spring()
  cls.tied=calculate(cls.tied_d)
  cls.area_d=fixture('area');cls.batch=calculate_batch(cls.area_d)
 def close(self,a,b):self.assertAlmostEqual(a,b,delta=max(1e-8,abs(b)*1e-10))
 def test_default_legacy_kind_and_validation(self):
  self.assertEqual(member_kind(defaults()),'purlin')
  for x in ['girt',None,False,{},23]:
   d=fixture();d['member_application']=x
   with self.assertRaises(ValueError):validate(d)
 def test_area_global_to_local_exact_and_inactive_roof_inputs(self):
  b=self.batch['load_bundle'];g=9.80665/1000;v=b['case_vectors_N_mm']
  self.assertEqual(v['PP'],dict(normal=0.,parallel=2.13*g))
  self.assertEqual(v['CP'],dict(normal=0.,parallel=10*1.5*g))
  self.assertEqual(v['SC'],dict(normal=0.,parallel=0.))
  self.assertEqual(v['V_Cima'],dict(normal=-120*1.5*g,parallel=0.))
  self.assertEqual(v['V_Baixo'],dict(normal=50*1.5*g,parallel=0.))
  self.assertEqual(b['inactive_roof_inputs']['live_kgf_m2'],99.)
  self.assertEqual(b['inactive_roof_inputs']['inclination'],dict(value=23.,unit='degrees'))
  other=copy.deepcopy(self.area_d);other['inclination']={'value':-37.,'unit':'degrees'};other['area_inputs']['live_kgf_m2']=1234.
  b2=area_bundle(other)
  self.assertEqual(b['case_vectors_N_mm'],b2['case_vectors_N_mm'])
  self.assertEqual(b['combinations'],b2['combinations'])
 def test_19_combinations_independent_vector_sum_no_roof_SC_or_P(self):
  from collections import Counter
  cases=self.batch['cases'];self.assertEqual(len(cases),19)
  self.assertEqual(Counter(c['combination']['type'] for c in cases),{'ELU normal':12,'ELS rara':3,'ELS frequente':3,'ELS quase permanente':1})
  vectors=self.batch['load_bundle']['case_vectors_N_mm']
  for item in cases:
   c=item['combination'];self.assertNotIn('SC',c['coefficients']);self.assertNotIn('P',c['coefficients']);self.assertEqual(c['P_N'],0.)
   for axis in ('normal','parallel'):
    target=sum(coef*vectors[name][axis] for name,coef in c['coefficients'].items())
    self.close(c['q_vector'][axis],target)
   self.assertEqual(c['q_vector'],item['evidence']['inclination']['q_vector'])
   self.assertIn('Modo por área',item['evidence']['inclination']['convention'])
   self.assertNotIn('não há rotação nem PP automático',item['evidence']['inclination']['convention'])
 def test_criterion_rows_are_filtered_by_actual_limit_state(self):
  for item in self.batch['cases']:
   names=[r['Verificação'] for r in item['rows']]
   for name in ['Flecha horizontal — eixo forte','Flecha vertical — eixo fraco']:
    self.assertEqual(name in names,item['combination']['limit_state']=='ELS')
   self.assertNotIn('Flecha paralela à cobertura',names)
  self.assertFalse(self.batch['whole_member_approved'])
  for r in self.batch['summary']:
   if r['Verificação']=='Flecha vertical — eixo fraco':self.assertIsNone(r['Índice']);self.assertEqual(r['Casos pendentes'],7)
 def test_direct_local_actions_are_not_rotated_or_augmented(self):
  r=self.free
  for state in ('ELU','ELS'):
   ev=r['inclination_evidence'][state];suffix='uls' if state=='ELU' else 'sls'
   self.assertEqual(ev['q_vector'],dict(normal=self.d['q_'+suffix],parallel=self.d['q_parallel_'+suffix]))
   self.assertEqual(ev['angle']['degrees'],90.)
   self.assertIn('não há rotação nem PP automático',ev['convention'])
  self.assertEqual(r['input_data']['inclination']['value'],23.)
 def test_free_gross_deflection_matches_closed_form_but_no_ELS_index(self):
  v=self.free['elastic_vertical'];expected=5*.1*4000**4/(384*200000*101200)
  self.close(v['model']['deflection_max_down']['value_mm'],expected)
  self.close(v['model']['My_max']['value_Nmm'],.1*4000**2/8)
  self.assertEqual(v['status'],'gross_elastic_diagnostic');self.assertIsNone(v['index'])
  self.assertFalse(v['uses_effective_inertia']);self.assertFalse(v['usable_for_design_approval'])
  self.assertNotIn('elastic_tie_study',self.free)
 def test_finite_tie_satisfies_independent_flexibility_equation(self):
  t=self.tied['elastic_tie_study'];m=t['model'];EI=200000*101200;L=4000.;k=10.
  free=5*.1*L**4/(384*EI);f=L**3/(48*EI);R=free/(f+1/k)
  self.close(m['springs'][0]['reaction_up_N'],R)
  self.close(m['springs'][0]['displacement_down_mm'],R/k)
  self.assertEqual(t['status'],'conditional_elastic_tie_study');self.assertIsNone(t['index'])
  self.assertFalse(t['usable_for_design_approval']);self.assertTrue(t['strength_model_unchanged'])
  self.assertLess(m['deflection_max_abs']['value_mm'],free)
  for value in m['residuals'].values():self.assertLess(abs(value),1e-7)
 def test_ties_do_not_change_resistance_demands_FLT_or_normal_ELS(self):
  for key in ('NBR_branches','FLT_segments','section_checks','ELS','inclination_evidence','elastic_vertical','strong_critical_qualification'):
   self.assertEqual(self.free[key],self.tied[key],key)
  self.assertFalse(self.tied['whole_member_approved'])
 def test_tie_anchor_hypothesis_and_stiffness_gates(self):
  for cfg in [spring(anchored=False),dict(spring(),origin=''),dict(spring(),springs=[])]:
   d=fixture();d['wall_tie_study']=cfg;r=calculate(d)['elastic_tie_study']
   self.assertEqual(r['status'],'not_evaluated');self.assertNotIn('model',r)
  for key,value in [('k_N_mm',0),('k_N_mm',float('inf')),('k_N_mm',-1),('x_mm',0),('x_mm',4000),('origin','')]:
   d=fixture();d['wall_tie_study']=spring();d['wall_tie_study']['springs'][0][key]=value
   with self.assertRaises(ValueError):build_spec(d)
 def test_rigid_asymptote_is_not_two_released_half_spans(self):
  d=fixture();d['wall_tie_study']=spring(1e12);m=calculate(d)['elastic_tie_study']['model']
  self.close(m['springs'][0]['reaction_up_N'],5*.1*4000/8)
  self.close(m['My_min']['value_Nmm'],-.1*4000**2/32)
  self.assertNotEqual(m['My_min']['value_Nmm'],0.)
  self.assertTrue(any('Negative My' in s for s in m['warnings']))
 def test_three_lengths_stay_independent(self):
  d=fixture();d['wall_els']=dict(normal_reference_mm=1200.,vertical_reference_mm=1800.,normal_denominator=120.,vertical_denominator=180.,origin='Critérios arbitrários de teste')
  r=calculate(d)
  self.assertEqual(r['input_snapshot']['L_mm'],4000.)
  self.assertEqual(r['input_snapshot']['ELS_limit_mm']['value'],10.)
  self.assertEqual(r['elastic_vertical']['L_reference_mm'],1800.)
  self.assertEqual(r['elastic_vertical']['declared_limit_mm'],10.)
  self.assertEqual(r['elastic_vertical']['model'],self.free['elastic_vertical']['model'])
  self.assertEqual(r['FLT_segments'],self.free['FLT_segments'])
  self.close(r['ELS']['deflection_mm'],self.free['ELS']['deflection_mm'])
 def test_zero_vertical_and_unsupported_reverse_do_not_approve(self):
  d=fixture();d.update(q_parallel_sls=0.,P_parallel_sls=0.);r=calculate(d)
  self.assertEqual(r['elastic_vertical']['status'],'not_applicable')
  d['q_parallel_sls']=-.1;r=calculate(d)
  self.assertEqual(r['elastic_vertical']['status'],'not_evaluated');self.assertIsNone(r['elastic_vertical']['index'])
 def test_material_guard_stays_effective(self):
  d=fixture();d['properties']['E_MPa']=210000.;r=calculate(d)
  self.assertEqual(r['input_snapshot']['Ml']['value'],None)
  self.assertFalse(r['whole_member_approved'])
 def test_word_keeps_scopes_without_mutation(self):
  before=copy.deepcopy(self.tied);s=doctext(word(self.tied));self.assertEqual(before,self.tied)
  for token in ('Travessa lateral','boca para baixo','Sem índice ELS','Iy bruto','não se substitui L por L/n','não foi incorporada à resistência','10,00','NÃO É APROVAÇÃO GLOBAL'):
   self.assertIn(token,s)
 def test_word_retains_uplift_reactions_and_numerical_warnings(self):
  d=fixture();d.update(q_parallel_sls=0.,P_parallel_sls=100.,x_sls=100.)
  d['wall_tie_study']=spring(1e6);d['wall_tie_study']['springs'][0]['x_mm']=800.
  r=calculate(d);m=r['elastic_tie_study']['model'];self.assertLess(m['end_reactions_up_N'][1],0.)
  s=doctext(word(r))
  self.assertIn('Reações verticais dos apoios',s);self.assertIn('levantamento',s)
  self.assertIn('apoios bilaterais',s);self.assertIn('-0,31',s)
  injected=copy.deepcopy(r);injected['elastic_tie_study']['model']['warnings'].append('Novo aviso não conhecido pelo tradutor: NÃO OMITIR')
  self.assertIn('Novo aviso não conhecido pelo tradutor: NÃO OMITIR',doctext(word(injected)))
 def test_word_result_rows_cannot_split_across_pages(self):
  doc=Document(BytesIO(word(self.tied)))
  table=next(t for t in doc.tables if t.rows[0].cells[0].text=='Verificação')
  self.assertTrue(table.rows[0]._tr.xpath('./w:trPr/w:tblHeader'))
  for row in table.rows[1:]:self.assertTrue(row._tr.xpath('./w:trPr/w:cantSplit'))
 def test_area_MC_common_fields_and_inactive_inputs(self):
  d=fixture('area');d['selected_types']=['ELS quase permanente'];r=calculate_batch(d);before=copy.deepcopy(r);blob=batch_word(r);s=doctext(blob);self.assertEqual(before,r)
  for token in ('SC de cobertura armazenada e INATIVA','99,00','E_MPa','4590000,00','Flecha vertical','Não se adiciona P automática'):
   self.assertIn(token,s)
  table=next(t for t in Document(BytesIO(blob)).tables if t.rows[0].cells[0].text=='Campo e unidade')
  values={row.cells[0].text:row.cells[1].text for row in table.rows[1:]}
  self.assertEqual(values['E_MPa'],technical_value(d['properties']['E_MPa']))
  self.assertEqual(len(r['cases']),1)

if __name__=='__main__':unittest.main(verbosity=2)
