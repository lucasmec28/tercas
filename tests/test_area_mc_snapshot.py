"""MC serialization regressions, not structural qualification or UI coverage."""
import copy,json,unittest
from io import BytesIO
from docx import Document
from tercas.application import defaults,calculate
from tercas.batch import calculate_batch,case_inputs
from tercas.report import batch_word,word
from tercas.presentation import fmt
from tercas.report_audit import technical_value

def text(blob):
 d=Document(BytesIO(blob))
 return '\n'.join([p.text for p in d.paragraphs]+[c.text for t in d.tables for r in t.rows for c in r.cells])

def specimen():
 d=defaults(19);d.update(load_mode='area',selected_types=['ELS quase permanente'],
   synthetic=True,project='Serialization sentinel, not a design',route_domain=True,
   property_origin='Synthetic sentinel values, not material certification',
   critical_origin='Synthetic independent manual sentinel, not qualified criticals',
   Ml_Nmm=1234567.,Mdist_Nmm=2345678.)
 d['properties'].update(E_MPa=198765.,G_MPa=76543.,fy_MPa=247.89,fu_MPa=402.34)
 d['area_inputs']['permanent_kgf_m2']=10.
 return d

class AreaMCSnapshot(unittest.TestCase):
 def test_snapshot_matches_direct_resolved_inputs(self):
  d=specimen();frozen=copy.deepcopy(d);r=calculate_batch(d)
  direct=calculate(case_inputs(d,r['cases'][0]['combination']))
  for key,value in r['common_input_snapshot'].items():
   self.assertEqual(value,direct['input_snapshot'][key])
  self.assertNotIn('ULS',r['common_input_snapshot']);self.assertNotIn('SLS',r['common_input_snapshot'])
  self.assertEqual(d,frozen)
 def test_all_properties_and_strong_criticals_exported(self):
  d=specimen();r=calculate_batch(d);s=text(batch_word(r))
  for value in d['properties'].values():
   if value is not None:self.assertIn(technical_value(value),s)
  for key in ('Ml_Nmm','Mdist_Nmm'):self.assertIn(fmt(d[key]),s)
  self.assertIn('Snapshot comum às combinações',s)
  self.assertIn('Ml declarado [N·mm]',s);self.assertIn('Mdist disponibilizado ao cálculo [N·mm]',s)
 def test_export_does_not_mutate_calculation_or_snapshot(self):
  r=calculate_batch(specimen());old=json.dumps(r,sort_keys=True,allow_nan=False)
  batch_word(r);self.assertEqual(json.dumps(r,sort_keys=True,allow_nan=False),old)
 def test_snapshot_is_detached_from_live_inputs(self):
  d=specimen();r=calculate_batch(d);d['properties']['E_MPa']=123.
  self.assertEqual(r['common_input_snapshot']['selected_section']['fields']['E_MPa']['value'],198765.)
 def test_incompatible_inherited_critical_remains_unused(self):
  d=defaults(19);d.update(load_mode='area',selected_types=['ELS quase permanente']);d['properties']['E_MPa']=100000.
  r=calculate_batch(d);s=text(batch_word(r))
  self.assertIsNone(r['common_input_snapshot']['Ml']['value'])
  self.assertIn(fmt(d['Ml_Nmm']),s)
  self.assertIn('Ml disponibilizado ao cálculo [N·mm]: Não informado / não utilizado',s)
  self.assertIn('E difere de 200000',s)
 def test_missing_property_is_not_invented(self):
  d=specimen();d['properties']['J_mm4']=None;r=calculate_batch(d);s=text(batch_word(r))
  self.assertIsNone(r['common_input_snapshot']['selected_section']['fields']['J_mm4']['value'])
  self.assertIn('Não informado',s)
 def test_old_result_exports_declared_only_without_recalculation(self):
  d=specimen();r=calculate_batch(d);r.pop('common_input_snapshot')
  s=text(batch_word(r));self.assertIn('Resultado anterior sem snapshot comum',s)
  self.assertIn('Nenhum recálculo',s);self.assertIn(technical_value(d['properties']['E_MPa']),s)
  self.assertIn('valor efetivamente disponibilizado não registrado',s)
 def test_no_structural_approval_added(self):
  r=calculate_batch(specimen());s=text(batch_word(r))
  self.assertFalse(r['whole_member_approved']);self.assertIn('NÃO É APROVAÇÃO GLOBAL',s)
  self.assertIn('não são certificação do perfil',s)
 def test_area_evidence_does_not_claim_direct_mode_or_missing_PP(self):
  r=calculate_batch(specimen());s=text(batch_word(r))
  self.assertNotIn('Modo direto: cargas já locais',s)
  for case in r['cases']:
   convention=case['evidence']['inclination']['convention']
   self.assertIn('Modo por área',convention);self.assertIn('PP incluído uma única vez',convention)
 def test_direct_property_table_header_repeats_and_rows_do_not_split(self):
  r=calculate_batch(specimen());direct=calculate(case_inputs(r['input_data'],r['cases'][0]['combination']))
  doc=Document(BytesIO(word(direct)))
  table=next(t for t in doc.tables if t.rows[0].cells[0].text=='Campo e unidade')
  self.assertTrue(table.rows[0]._tr.xpath('./w:trPr/w:tblHeader'))
  for row in table.rows[1:]:self.assertTrue(row._tr.xpath('./w:trPr/w:cantSplit'))

if __name__=='__main__':unittest.main(verbosity=2)
