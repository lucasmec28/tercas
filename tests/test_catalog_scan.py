import copy
import unittest
from unittest.mock import patch
from tercas.application import example, defaults
from tercas.catalog_scan import inputs_for_section, summarize, scan_catalog
from tercas.catalogs import catalog_labels

class CatalogScanTests(unittest.TestCase):
 def test_preserve_general_replace_section(self):
  d=example();d.update(weak_catalog={'Lx_mm':2345,'geometry_mode':'explicit','mean_line':{'am_mm':123}},weak_axis={'positive':{'Ml_Nmm':123}})
  before=copy.deepcopy(d)
  for i in range(len(catalog_labels())):
   with self.subTest(i=i):
    out=inputs_for_section(d,i)
    for k in ('L_mm','segments','q_uls','P_uls','area_inputs','steel_name','selected_types'):
     self.assertEqual(out[k],d[k])
    self.assertEqual(out['properties']['mass_kg_m'],defaults(i)['properties']['mass_kg_m'])
    self.assertEqual(out['weak_catalog'],{'geometry_mode':'catalog','Lx_mm':2345})
    self.assertNotEqual(out['weak_axis'],d['weak_axis'])
  self.assertEqual(d,before)
 def test_derived_critical_respects_E_and_provenance(self):
  from tercas.core.local_table12 import local_critical
  from tercas.catalogs import catalog_entry
  d=example();d['properties']['E_MPa']=100000.
  for i in range(len(catalog_labels())):
   e=catalog_entry(i)
   if e['critical_values']['Ml_Nmm'] is not None:continue
   out=inputs_for_section(d,i);p=out['properties']
   expected=local_critical(e['family'],p['h'],p['bf'],p['t'],p['Wx_cm3']*1000,100000.,D_mm=p['lip'])
   self.assertAlmostEqual(out['Ml_Nmm'],expected['Ml_Nmm'])
   self.assertTrue(out['synthetic'])
 def test_malformed_weak_config_per_section_error(self):
  d=example();d['weak_catalog']=None
  r=scan_catalog(d,indices=[0]);self.assertEqual(r['rows'][0]['evaluated_checks'],0)
  self.assertFalse(r['rows'][0]['criteria_satisfied'])
 def test_summary(self):
  def r(idx,status='Atende ao critério calculado',name='Teste'):
   return {'Índice':idx,'Situação':status,'Verificação':name}
  self.assertTrue(summarize([r(.8)])['criteria_satisfied'])
  self.assertEqual(summarize([r(.8)])['utilization_percent'],80.)
  for rs in ([],[r(None)],[r(.9,'Parcial — atende')],[r(.9,'Atende — hipótese provisória')],[r(1.001)], [r(.8),r(None,'Pendente')]):
   self.assertFalse(summarize(rs)['criteria_satisfied'])
  self.assertFalse(summarize([r(.8)],['Aviso'])['criteria_satisfied'])
  self.assertTrue(summarize([r(.8),r(None,'Não aplicável')])['criteria_satisfied'])
  self.assertTrue(summarize([r(.8),r(None,'Pendente','Flecha paralela à cobertura')])['criteria_satisfied'])
 def test_cancel_and_limit(self):
  d=example()
  result=scan_catalog(d,indices=[1,2],cancelled=lambda:True)
  self.assertEqual(result['completed_count'],0);self.assertFalse(result['complete'])
  self.assertEqual(result['unprocessed_indices'],[1,2])
  with patch('tercas.catalog_scan.time.monotonic',side_effect=[0,2,3]):
   result=scan_catalog(d,indices=[1,2],max_seconds=1)
  self.assertEqual(result['stop_reason'],'time_limit')
 def test_bad_indices(self):
  for idx in ([1,1],[True],[-1],[999]):
   with self.assertRaises(ValueError):scan_catalog(example(),indices=idx)
 def test_direct_real(self):
  d=example();before=copy.deepcopy(d);progress=[]
  result=scan_catalog(d,indices=[0,82,100],progress=lambda n,t,r:progress.append((n,t)))
  self.assertEqual(d,before);self.assertTrue(result['complete']);self.assertEqual(len(progress),3)
  self.assertEqual([r['mass_kg_m'] for r in result['rows']],sorted(r['mass_kg_m'] for r in result['rows']))
  self.assertTrue(all(r['evaluated_checks']>0 for r in result['rows']))
  self.assertTrue(all(not r['whole_member_approved'] for r in result['rows']))
 def test_area_real(self):
  d=example();d['load_mode']='area';d['selected_types']=['ELS rara']
  # Catalogue-domain test: the synthetic example uses G=E/2.6, not the
  # original G=77000 configuration. Elastic-change blocking is tested separately.
  d['properties']['G_MPa']=77000.
  result=scan_catalog(d,indices=[0,82]);self.assertTrue(result['complete'])
  self.assertTrue(all(r['evaluated_checks']>0 for r in result['rows']))
 def test_no_shared_mutation(self):
  d=example();a=inputs_for_section(d,0);b=inputs_for_section(d,1)
  a['segments'][0]['end_mm']=1
  self.assertEqual(d['segments'],b['segments'])

if __name__=='__main__':unittest.main()

def test_batch_does_not_hide_non_governing_provisional_result():
 from tercas.batch import governing
 from tercas.catalog_scan import summarize
 rows=[]
 for idx,status in [(0.9,'Atende'),(0.5,'Parcial — hipótese provisória')]:
  rows.append({'combination':{'id':str(idx),'type':'ELU','q_kN_m':1.},'rows':[{'Verificação':'Flexão biaxial','Índice':idx,'Situação':status,'Observação':''}]})
 summary=governing(rows)
 assert summary[0]['Índice']==0.9
 assert summary[0]['Casos pendentes']==1
 assert 'Parcial' in summary[0]['Situação']
 assert summarize(summary)['criteria_satisfied'] is False
