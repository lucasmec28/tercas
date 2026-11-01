import copy,unittest,json
from experimental_fsm.custom_geometry_experimental import analyze
from experimental_fsm.app_integration.adapter import run,export_json
BASE={'geometry':{'h_mm':200,'b_mm':75,'lip_mm':20,'t_mm':2},'E_MPa':200000,'nu':.3,'axis':'y','moment_sign':1,'mesh_n':2,'halfwaves_mm':[15,50,150]}
class Domain(unittest.TestCase):
 def test_no_automatic_resistance_fields(self):
  r=run(BASE);j=json.loads(export_json(BASE,r));self.assertIsNone(j['local_Mcr_kNm']);self.assertIsNone(j['distortional_Mcr_kNm']);self.assertFalse(j['design_approved'])
 def test_operational_limits(self):
  for key,val in [('mesh_n',9),('halfwaves_mm',list(range(1,83)))]:
   q=copy.deepcopy(BASE);q[key]=val
   with self.assertRaises(ValueError):analyze(q)
 def test_nonfinite_and_bad_material(self):
  for key,val in [('E_MPa',float('inf')),('E_MPa',0),('nu',.5),('nu',-1)]:
   q=copy.deepcopy(BASE);q[key]=val
   with self.assertRaises(ValueError):analyze(q)
 def test_geometric_domain(self):
  for key,val in [('t_mm',0),('lip_mm',150),('h_mm',3),('b_mm',1)]:
   q=copy.deepcopy(BASE);q['geometry'][key]=val
   with self.assertRaises(ValueError):analyze(q)
 def test_no_unknown_physics(self):
  q=copy.deepcopy(BASE);q['corner_radius_mm']=2
  with self.assertRaises(ValueError):analyze(q)
 def test_explicit_axes_and_sign(self):
  for key,val in [('axis','strong'),('moment_sign',0),('moment_sign',True)]:
   q=copy.deepcopy(BASE);q[key]=val
   with self.assertRaises(ValueError):analyze(q)
if __name__=='__main__':unittest.main()
