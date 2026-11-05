"""The CT expression also covers stabilizing loads, without favorable credit."""
import copy
import math
import unittest
from io import BytesIO
from pathlib import Path

from docx import Document
from tercas.application import calculate, defaults, rows
from tercas.report import word
from tercas.ux_inputs import whole_span


class FLTLoadPosition(unittest.TestCase):
 def data(self):
  d=defaults(21)
  d.update(L_mm=5500.,q_uls=.94,P_uls=0.,q_sls=0.,P_sls=0.,route_domain=False,
           segments=whole_span(5500.,5500.,5500.,5500.,'one','Comprimentos efetivos informados; sem crédito de travamento da telha'))
  return d

 def test_unknown_or_other_position_keeps_pending(self):
  d=self.data();before=copy.deepcopy(d);r=calculate(d);f=r['FLT_segments'][0]
  self.assertEqual(d,before)
  self.assertEqual(f['status'],'FLT_not_evaluated')
  self.assertEqual(f['flange_results'][0]['status'],'route_domain_not_declared')
  self.assertNotIn('Me_Nmm',f)
  self.assertNotIn('index',f)
  self.assertIn('carga no CT ou estabilizante',f['reason'])
  self.assertIn('Carga desestabilizante exige tratamento específico',f['reason'])
  self.assertIn('todas as ações, combinações e trechos',f['reason'])
  self.assertFalse(r['whole_member_approved'])

 def test_declared_position_uses_unchanged_CT_expression(self):
  d=self.data();d['route_domain']=True;before=copy.deepcopy(d)
  f=calculate(d)['FLT_segments'][0];p=d['properties']
  me=math.pi/5500.*math.sqrt(p['E_MPa']*p['Iy_cm4']*1e4*(p['G_MPa']*p['J_mm4']+math.pi**2*p['E_MPa']*p['Cw_mm6']/5500.**2))
  self.assertEqual(d,before)
  self.assertAlmostEqual(f['Me_Nmm'],me)
  self.assertAlmostEqual(f['Me_Nmm'],855120.652259821)
  self.assertAlmostEqual(f['FLT']['MRd_flt_Nmm'],777382.4111452916)
  self.assertAlmostEqual(f['index'],4.572234911725695)
  self.assertFalse(f['whole_member_approved'])

 def test_favorable_load_height_never_inferred_from_force_sign(self):
  for q in (.94,-.94):
   with self.subTest(q=q):
    d=self.data();d['q_uls']=q
    f=calculate(d)['FLT_segments'][0]
    self.assertNotIn('index',f)
    self.assertEqual(f['flange_results'][0]['status'],'route_domain_not_declared')

 def test_primary_torsion_is_not_silently_qualified(self):
  d=self.data();r=calculate(d)
  self.assertIn('sem torção primária',r['FLT_segments'][0]['reason'])
  self.assertFalse(r['whole_member_approved'])
  self.assertEqual(r['section_checks']['elastic_Me']['status'],'not_evaluated')

 def test_table_word_and_global_keep_position_scope(self):
  from tercas.global_verification import build_global_verification
  r=calculate(self.data())
  row=next(x for x in rows(r) if x['Verificação'].startswith('FLT'))
  self.assertIn('carga no CT ou estabilizante',row['Observação'])
  self.assertIn('Carga desestabilizante',row['Observação'])
  self.assertEqual(row['Situação'],'Não avaliado')
  text='\n'.join(p.text for p in Document(BytesIO(word(r))).paragraphs)
  self.assertIn('carga no CT ou estabilizante',text)
  item=next(c for c in build_global_verification(r)['checks'] if c['id']=='ELU:DIRECT_ELU:FLT:1')
  self.assertEqual(item['status'],'pending')
  self.assertIn('Carga desestabilizante',item['reason'])

 def test_interface_documents_declaration_without_new_numeric_height(self):
  text=(Path(__file__).resolve().parents[1]/'app.py').read_text()
  self.assertIn('Eixo forte de simetria; cargas no CT ou estabilizantes, sem torção primária',text)
  self.assertIn('todas as ações, combinações e trechos calculados',text)
  self.assertIn('sem aproveitar seu efeito favorável',text)
  self.assertIn('Não exclui o giro do modo de FLT',text)
  self.assertNotIn('sem torção primária ou efeito de altura neste modelo',text)


if __name__=='__main__':unittest.main()
