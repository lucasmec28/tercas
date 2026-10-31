"""CBCA 2014, examples 07-09/S8: COMMON stages, not MLE=MSE validation.
The source inconsistencies are deliberately flagged, never calibrated away.
See docs/CBCA_COMPARATORS.md. All units converted to N/mm.
"""
import math
import unittest
from tercas.core.flt_vrd import vrd,chi_flt
from tercas.core.travamentos_nbr import moment,segment_moments
from tercas.core.envelope_mv import envelope
from tercas.core.contrato import me
from tercas.inclination import annex_e_critical,biaxial_interaction,weak_resistance

class CBCACommonStages(unittest.TestCase):
 def test_07_strong_elastic_critical(self):
  end=dict(lateral_displacement='fixed',twist='fixed',warping='free',weak_bending_rotation='free',evidence='CBCA example07 ideal fork comparator')
  c=dict(sheet_restraint_credit=False,topology='single_span_no_overhang',intermediate_braces=[],left=end,right=end,load_height_relative_CT_mm=0,bending_axis='strong_symmetry_axis',axial_force_N=0,weak_bending_Nmm=0,strong_axis_symmetry=True,actions=[dict(name='self_weight',torque_demonstrated_zero=True,evidence='isolated ideal elastic comparator; no load magnitude used')])
  actual=me(c,200000,77000,10.12e4,.013e4,246.61e6,4000)/1e4
  self.assertAlmostEqual(actual,71.1,delta=.1) # printed rounded kN.cm
 def test_07_chi_from_printed_me(self):
  chi,branch=chi_flt(math.sqrt(8.83e3*250/(71.1e4)))
  self.assertEqual(branch,'elastic');self.assertAlmostEqual(chi,.322,delta=.001)
 def test_08_annex_e_web_compressed(self):
  x=annex_e_critical(Nex_N=54.47e3,Nez_N=10.55e3,r0_mm=61.9,j_mm=60.6,Cs=1,Cm=1,provenance='CBCA2014 example08 p70 printed section/sign values')
  self.assertAlmostEqual(x['Me_Nmm']/1e4,692.,delta=.2)
  self.assertFalse(x['resistance_evaluated'])
 def test_08_mle_not_mse_complete(self):
  r=weak_resistance(W_mm3=3150,Wc_mm3=5650,fy_MPa=250,Me_Nmm=692e4,family='Ue',provenance='CBCA MLE example08; no MSE weak criticals supplied')
  self.assertEqual(r['status'],'not_evaluated')
 def test_09_point_load_moment(self):
  self.assertEqual(moment(2000,4000,0,1500,2000),150e4)
 def test_09_web_shear(self):
  r=vrd(95.2,1.2,250,200000)
  self.assertEqual(r['branch'],'intermediate')
  self.assertAlmostEqual(r['VRd_N']/1000,13.45,delta=.005)
 def test_09_mv_given_mle_capacity(self):
  # Capacity fixed FROM MLE reference, not produced/validated by MSE.
  r,_=envelope(4000,0,1500,2000,2000,195.45e4,13.45e3)
  self.assertAlmostEqual(r['index_squared'],.592,delta=.0005)
 def test_s8_cb_quarter_moments(self):
  r=segment_moments(3420,1,0,1710,0,1710)
  self.assertAlmostEqual(r['Cb_from_moments'],1.3,delta=.01)
 def test_s8_annex_e_printed_discrepancy_flagged(self):
  r=annex_e_critical(Nex_N=225.38e3,Nez_N=99.564e3,r0_mm=58.09,j_mm=68.79,Cs=-1,Cm=1,provenance='CBCA S8 pp168-169: known arithmetic discrepancy')
  value=r['Me_Nmm']/1e4
  self.assertAlmostEqual(value,227.50954340086187,places=8)
  # Regression guard for actual formula, NOT endorsement of printed224.57.
  self.assertGreater(abs(value/224.57-1),.01)
 def test_s8_web_height_discrepancy_flagged(self):
  actual=vrd(114.4,2.65,240,200000)['VRd_N']/1000
  self.assertAlmostEqual(actual,39.69,delta=.005)
  h_geometry=125-2*2.65-2*3.975
  self.assertNotEqual(h_geometry,114.4)
  self.assertEqual(h_geometry,111.75)
 def test_s8_biaxial_component_only(self):
  r=biaxial_interaction(230e4,10e4,382.82e4,66.89e4)
  # N=0 API does NOT represent full S8 axial compression case.
  self.assertAlmostEqual(r['index'],230/382.82+10/66.89)
  full_reference=r['index']+1.2/58.94
  self.assertAlmostEqual(full_reference,.77,delta=.005)
  self.assertFalse(r['whole_member_approved'])
if __name__=='__main__':unittest.main()
