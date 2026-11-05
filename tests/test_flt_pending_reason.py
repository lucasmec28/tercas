"""Missing route domain must be distinguishable from missing lengths."""
import copy
import unittest
from io import BytesIO
from docx import Document
from tercas.application import defaults, calculate, rows
from tercas.report import word
from tercas.ux_inputs import whole_span


class FLTPendingReason(unittest.TestCase):
 def data(self):
  d=defaults(26)
  d.update(L_mm=5500.,q_uls=.9416,P_uls=0.,q_sls=0.,P_sls=0.,route_domain=False,
           segments=whole_span(5500.,5500.,5500.,5500.,'one','Comprimentos efetivos informados; sem crédito de travamento da telha'))
  return d

 def test_domain_missing_with_complete_lengths_has_specific_reason(self):
  d=self.data();before=copy.deepcopy(d);r=calculate(d);f=r['FLT_segments'][0]
  self.assertEqual(d,before)
  self.assertEqual(f['status'],'FLT_not_evaluated')
  self.assertEqual(f['flange_results'][0]['status'],'route_domain_not_declared')
  self.assertEqual(f['flange_results'][0]['Ly_used_mm'],5500.)
  self.assertEqual(f['flange_results'][0]['Lz_used_mm'],5500.)
  self.assertNotIn('index',f)
  self.assertIn('Domínio da expressão de Me',f['reason'])
  self.assertIn('Estabilidade, críticos e trechos',f['reason'])
  self.assertFalse(r['whole_member_approved'])

 def test_table_and_word_propagate_reason(self):
  r=calculate(self.data());row=next(x for x in rows(r) if x['Verificação'].startswith('FLT'))
  self.assertIn('Domínio da expressão de Me',row['Observação'])
  self.assertEqual(row['Situação'],'Não avaliado')
  doc=Document(BytesIO(word(r)))
  self.assertIn('Domínio da expressão de Me','\n'.join(p.text for p in doc.paragraphs))

 def test_global_pending_record_propagates_reason(self):
  from tercas.global_verification import build_global_verification
  r=calculate(self.data());g=build_global_verification(r)
  item=next(c for c in g['checks'] if c['id']=='ELU:DIRECT_ELU:FLT:1')
  self.assertEqual(item['status'],'pending')
  self.assertIn('Domínio da expressão de Me',item['reason'])
  self.assertIsNone(item['index'])

 def test_declared_domain_does_not_change_numeric_branch(self):
  d=self.data();d['route_domain']=True;f=calculate(d)['FLT_segments'][0]
  self.assertEqual(f['status'],'computed_from_supplied_effective_lengths')
  self.assertAlmostEqual(f['Me_Nmm'],993885.7123856952)
  self.assertAlmostEqual(f['FLT']['MRd_flt_Nmm'],903532.4658051775)
  self.assertAlmostEqual(f['index'],3.940561224689529)

 def test_missing_length_is_not_mislabeled_as_missing_domain(self):
  d=self.data();d['route_domain']=True;d['segments'][0]['Ly_top_effective_mm']=None
  f=calculate(d)['FLT_segments'][0]
  self.assertNotIn('Domínio da expressão de Me',f['reason'])
  self.assertEqual(f['flange_results'][0]['missing'],['Ly_effective_mm'])
  self.assertNotIn('index',f)

 def test_zero_demand_remains_not_applicable(self):
  d=self.data();d['q_uls']=0.
  self.assertEqual(calculate(d)['FLT_segments'][0]['status'],'not_applicable')

 def test_auxiliary_diagnostic_does_not_report_supplied_span_missing(self):
  r=calculate(self.data());aux=r['section_checks']['elastic_Me']
  self.assertEqual(aux['status'],'not_evaluated')
  self.assertNotIn('L_mm',aux['missing'])
  self.assertIn('restraint_load_contract',aux['missing'])
  self.assertNotIn('Me_Nmm',aux)
  self.assertEqual(aux['member_verification_path'],'FLT_segments')
  self.assertIn('não é a verificação de FLT da barra',aux['scope'])

 def test_auxiliary_scope_does_not_override_computed_member_flt(self):
  d=self.data();d['route_domain']=True;r=calculate(d)
  self.assertAlmostEqual(r['FLT_segments'][0]['index'],3.940561224689529)
  for key in ('elastic_Me','local_FLT_resistance'):
   aux=r['section_checks'][key]
   self.assertEqual(aux['status'],'not_evaluated')
   self.assertEqual(aux['member_verification_path'],'FLT_segments')
  self.assertNotIn('Me_Nmm',r['section_checks']['elastic_Me'])

 def test_standalone_section_diagnostic_still_reports_truly_missing_span(self):
  from tercas.core.selecao import evaluate as evaluate_section
  r=calculate(self.data())
  aux=evaluate_section(r['input_snapshot']['selected_section'])['elastic_Me']
  self.assertIn('L_mm',aux['missing'])
  self.assertIn('restraint_load_contract',aux['missing'])

 def test_reverse_bending_keeps_both_flange_causes(self):
  d=self.data();d.update(q_uls=1.,P_uls=-4000.,x_uls=500.)
  f=calculate(d)['FLT_segments'][0]
  self.assertEqual(len(f['flange_results']),2)
  self.assertIn('Domínio da expressão de Me',f['reason'])
  self.assertNotIn('index',f)

if __name__=='__main__':unittest.main()
