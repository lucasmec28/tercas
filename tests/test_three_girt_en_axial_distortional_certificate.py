"""Thin uniform axial steps1-2: independent weighted geometry and safety guards."""
import copy
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from tercas.three_girt_en_normal import en1993_normal_components as en


class ThinAxialCertificateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths=(Path(__file__).resolve().parents[1]/'tercas/data/torsion_profiles').glob('ue*.json')
        cls.profiles={p['thickness_mm']:p for p in map(lambda p:json.loads(p.read_text()),paths)}
        cls.cert={t:en.build_component_sections(p) for t,p in cls.profiles.items()}

    def test_independent_geometric_quadrature_and_axial_resultants(self):
        # Rebuild widths, cuts and physical As from independent projected
        # coordinates. Do not consume implementation's weighted intervals.
        for t in (1.2,1.5):
            c=self.cert[t];r=c['components']['N_compression']
            n=np.array(self.profiles[t]['nodes_xy_mm']);cg=np.array(c['gross_properties']['centroid_xy_mm'])
            J=np.zeros((3,3)); result=np.zeros(3); z,w=np.polynomial.legendre.leggauss(4)
            bounds=(0,20,60,148,188,208); strips=[]
            for group,(start,end) in enumerate(zip(bounds,bounds[1:])):
                axis=1 if group%2==0 else 0
                lower=np.min(n[start:end+1,axis]);width=np.ptp(n[start:end+1,axis])
                if group in (1,2,3):
                    scr=4*math.pi**2*210000/(12*(1-.3**2))*(t/width)**2
                    lam=math.sqrt(250/scr);rho=1 if lam<=.5+math.sqrt(.03) else (lam-.22)/lam**2
                else:rho=1.
                self.assertAlmostEqual(r['local_panels'][group]['rho'],rho,places=14)
                for i in range(start,end):
                    d=n[i+1]-n[i]; cuts={0.,1.}
                    for fraction in (rho/2,1-rho/2):
                        if d[axis]!=0:
                            cut=(lower+width*fraction-n[i,axis])/d[axis]
                            if 0<cut<1:cuts.add(float(cut))
                    for lo,hi in zip(sorted(cuts),sorted(cuts)[1:]):
                        frac=(n[i,axis]+(lo+hi)/2*d[axis]-lower)/width
                        if rho<1 and rho/2<frac<1-rho/2:continue
                        is_as=group in (0,4) or (group in (1,3) and frac>1-rho/2)
                        chi=r['stiffeners'][0 if group<2 else 1]['chi_d'] if is_as else 1.
                        strips.append((i,lo,hi,t*chi))
                        for u,wt in zip((lo+hi)/2+(hi-lo)*z/2,w*(hi-lo)/2):
                            pt=n[i]+u*d;da=wt*np.linalg.norm(d)*t*chi
                            J+=da*np.outer(np.r_[1,pt],np.r_[1,pt])
                            result+=da*r['sigma_coefficients_c0_cx_cy'][0]*np.array([1,pt[1]-cg[1],-(pt[0]-cg[0])])
            eff=r['effective_properties'];center=J[0,1:]/J[0,0]
            tensor=J[1:,1:]-np.outer(J[0,1:],J[0,1:])/J[0,0]
            np.testing.assert_allclose([eff['A_mm2'],eff['Ix_strong_mm4'],eff['Iy_weak_mm4']],
                                       [J[0,0],tensor[1,1],tensor[0,0]],rtol=2e-13)
            np.testing.assert_allclose(center,eff['centroid_xy_mm'],atol=2e-12,rtol=0)
            ex,ey=r['centroid_shift_from_gross_mm']
            np.testing.assert_allclose(result,[1.,0.,-ex],atol=2e-12,rtol=0)
            self.assertEqual(ey,0.);self.assertEqual(eff['Ixy_mm4'],0.)
            self.assertEqual(r['sigma_coefficients_c0_cx_cy'],[1/eff['A_mm2'],0.,0.])
            self.assertAlmostEqual(r['ULS_pure_effort_signed'],-250*eff['A_mm2'],places=9)
            self.assertLess(abs(r['symmetry_audit']['raw_ey_mm']),1e-12)
            self.assertLess(r['symmetry_audit']['retained_thickness_mirror_max_error_mm'],1e-12)
            self.assertTrue(r['moment_transport_required'])
            self.assertFalse(r['distortional_reduction_audit']['step3_optional_refinement_used'])

    def test_reference_values_and_single_physical_As_reduction(self):
        for t,A,ex,chi in ((1.5,284.09912019149783,2.1094423081341382,.940014383056851),
                           (1.2,205.83476874899458,2.663223728219851,.8775838865789389)):
            r=self.cert[t]['components']['N_compression']
            self.assertAlmostEqual(r['effective_properties']['A_mm2'],A,places=10)
            self.assertAlmostEqual(r['centroid_shift_from_gross_mm'][0],ex,places=11)
            loss=0
            for st in r['stiffeners']:
                self.assertAlmostEqual(st['chi_d'],chi,places=12)
                self.assertAlmostEqual(st['t_red_mm'],t*chi,places=12)
                self.assertFalse(st['integral_fixed_point'])
                self.assertEqual(st['sigma_com_Ed_MPa'],250.)
                loss+=(1-st['chi_d'])*st['As_mm2']
            self.assertAlmostEqual(r['local_only_properties']['A_mm2']-loss,A,places=10)
            if t==1.2:self.assertLess(r['local_panels'][1]['rho'],1.)
            else:self.assertEqual(r['local_panels'][1]['rho'],1.)
            # Internal web always retains original t, not chi*t.
            for i,a,b,tt in r['effective_weighted_line_intervals']:
                if 60<=i<148:self.assertEqual(tt,t)

    def test_partition_rejects_outside_overlap_and_invalid_factors(self):
        refs=[(0,0.,.4),(0,.6,1.),(1,0.,1.)]
        for st in ([dict(chi_d=.9,line_intervals=[[0,.3,.7]])],
                   [dict(chi_d=.9,line_intervals=[[1,0.,.7]]),dict(chi_d=.8,line_intervals=[[1,.5,1.]])],
                   [dict(chi_d=1.01,line_intervals=[[1,0.,1.]])]):
            with self.assertRaises(ValueError):en._weighted_retained_intervals(refs,st,1.2)
        with self.assertRaises(ValueError):en._weighted_retained_intervals([(0,0.,.6),(0,.5,1.)],[],1.2)
        self.assertEqual(en._weighted_retained_intervals([(0,0.,1.)],
                         [dict(chi_d=.8,line_intervals=[[0,.5,1.]])],1.),[[0,0.,.5,1.],[0,.5,1.,.8]])

    def test_asymmetry_fails_closed_and_new_thin_bending_is_qualified(self):
        original=en._stiffener
        def asymmetric(*args):
            st=original(*args)
            if st['flange']=='upper_flange':st['Is_mm4']*=.99
            return st
        with patch.object(en,'_stiffener',side_effect=asymmetric):
            r=en.build_component_sections(self.profiles[1.5])['components']['N_compression']
            self.assertFalse(r['eligible']);self.assertIsNone(r['sigma_coefficients_c0_cx_cy'])
            self.assertIn('symmetry',r['blocking_reasons'][0]['detail'])
        for t in (1.2,1.5):
            c=self.cert[t]
            self.assertTrue(en.require_component(c,'N',-1.)['eligible'])
            self.assertTrue(en.require_component(c,'My',-1.)['eligible'])
            for sign in (-1.,1.):
                self.assertTrue(en.require_component(c,'Mx',sign)['eligible'])
            # Negative N transports to negative My when applied at gross Cg.
            self.assertLess(-1*c['components']['N_compression']['additional_My_per_N_mm'],0.)
            self.assertTrue(c['all_normal_components_eligible'])

    def test_previous_36_eligible_records_unchanged(self):
        records={str(t):{k:v for k,v in c['components'].items()
                 if not(t in (1.2,1.5) and k=='N_compression') and not(t==1.5 and k=='My_negative') and not(t==1.2 and k in ('Mx_positive','Mx_negative','My_negative'))} for t,c in self.cert.items()}
        self.assertEqual(en._canonical_sha(records),'aad2ebf87ab369041f5586cd442b3b35020495dfdfd121d6bfb500fb1df40d19')
        self.assertEqual(sum(v['eligible'] for c in self.cert.values() for v in c['components'].values()),42)
        previous_eligible={str(t):{k:v for k,v in c['components'].items()
                 if v['eligible'] and not(t in (1.2,1.5) and k=='N_compression') and not(t==1.5 and k=='My_negative') and not(t==1.2 and k in ('Mx_positive','Mx_negative','My_negative'))} for t,c in self.cert.items()}
        self.assertEqual(sum(len(v) for v in previous_eligible.values()),36)
        self.assertEqual(en._canonical_sha(previous_eligible),'aad2ebf87ab369041f5586cd442b3b35020495dfdfd121d6bfb500fb1df40d19')

    def test_certificate_hashes_and_historical_schema_no_recalculation(self):
        for schema in (en.SCHEMA,en.MY150_SCHEMA,en.AXIAL_SCHEMA,en.PREVIOUS_SCHEMA,en.LEGACY_SCHEMA):
            c=copy.deepcopy(self.cert[2.65]);c['schema']=schema;c.pop('content_sha256')
            c['content_sha256']=en._canonical_sha(c);before=copy.deepcopy(c)
            en.verify_component_sections(c);self.assertEqual(c,before)
        c=copy.deepcopy(self.cert[1.2]);before=copy.deepcopy(c)
        en.verify_component_sections(c);self.assertEqual(c,before)
        c['components']['N_compression']['effective_weighted_line_intervals'][0][3]*=.99
        with self.assertRaises(ValueError):en.verify_component_sections(c)
        for t in (1.2,1.5):
            for kw in ({'E_MPa':200000.},{'fyb_MPa':300.}):
                with self.assertRaises(ValueError):en.build_component_sections(self.profiles[t],**kw)
            p=copy.deepcopy(self.profiles[t]);p['nodes_xy_mm'][10][0]+=.01
            with self.assertRaises(ValueError):en.build_component_sections(p)

if __name__=='__main__':unittest.main()
