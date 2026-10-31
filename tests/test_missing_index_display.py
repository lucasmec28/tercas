import unittest,copy
from tercas.presentation import display_frame,display_records
class MissingIndexDisplay(unittest.TestCase):
 def test_none_and_number_only_presentation(self):
  records=[{'Índice':None,'Situação':'Não aplicável'}, {'Índice':.998765,'Situação':'Atende ao critério calculado'}, {'Índice':None,'Situação':'Pendente'}, {'Índice':1.00001,'Situação':'Não atende'}]
  frozen=copy.deepcopy(records);styler=display_frame(records)
  self.assertEqual(styler._display_funcs[(0,0)](styler.data.iloc[0,0]),'—')
  self.assertEqual(styler._display_funcs[(2,0)](styler.data.iloc[2,0]),'—')
  self.assertEqual(styler._display_funcs[(1,0)](styler.data.iloc[1,0]),'1,00 (<1,00)')
  self.assertEqual(styler._display_funcs[(3,0)](styler.data.iloc[3,0]),'1,00 (>1,00)')
  self.assertEqual(records,frozen)
  self.assertEqual(styler.data['Situação'].tolist(),[r['Situação'] for r in records])
  self.assertEqual(styler.data.iloc[1,0],'1,00 (<1,00)');self.assertEqual(records[1]['Índice'],.998765)
 def test_nullable_sentinels(self):
  import pandas as pd
  for missing in (None,float('nan'),pd.NA):
   styled=display_frame([{'Índice':missing}]);self.assertEqual(styled._display_funcs[(0,0)](styled.data.iloc[0,0]),'—')
 def test_text_records_preserve_absence(self):
  raw=[{'Índice':None,'Situação':'Não aplicável'}]
  self.assertEqual(display_records(raw)[0]['Índice'],'—');self.assertIsNone(raw[0]['Índice'])
