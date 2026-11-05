"""Pure My− t1.50: independent physical integration and closed-domain guards."""
import copy
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from tercas.three_girt_en_normal import en1993_normal_components as en


class My150CertificateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles={p['thickness_mm']:p for p in (
            json.loads(p.read_text()) for p in
            (Path(__file__).resolve().parents[1]/'tercas/data/torsion_profiles').glob('ue*.json'))}
        cls.cert={t:en.build_component_sections(p) for t,p in cls.profiles.items()}

    def test_other_38_unchanged_records_identical_to_frozen_v3(self):
        records={str(t):{k:v for k,v in c['components'].items()
                        if not(t==1.5 and k=='My_negative') and not(t==1.2 and k in ('Mx_positive','Mx_negative','My_negative'))} for t,c in self.cert.items()}
        self.assertEqual(sum(map(len,records.values())),38)
        self.assertEqual(en._canonical_sha(records),
                         'ce227621016bbb33fcf93506d9ee63b0ccfdb880cc980e9a0d830b6684267779')
        self.assertEqual(sum(v['eligible'] for c in self.cert.values() for v in c['components'].values()),42)

    def test_independent_quadrature_and_face_bounds(self):
        c=self.cert[1.5];r=c['components']['My_negative'];n=np.array(self.profiles[1.5]['nodes_xy_mm'])
        rho=r['local_panels'][2]['rho'];cg=np.array(c['gross_properties']['centroid_xy_mm'])
        # Independent clipping against two web bands, not returned intervals.
        y0,y1=min(n[60:149,1]),max(n[60:149,1]);width=y1-y0
        cuts_y=(y0+rho*width/2,y1-rho*width/2)
        J=np.zeros((3,3));result=np.zeros(3);points=[]
        coeff=np.array(r['sigma_coefficients_c0_cx_cy']);effort=r['ULS_pure_effort_signed']
        z,w=np.polynomial.legendre.leggauss(4)
        for i,(a,b) in enumerate(zip(n[:-1],n[1:])):
            d=b-a;cuts={0.,1.}
            if 60<=i<148 and d[1]!=0:
                cuts.update(float((y-a[1])/d[1]) for y in cuts_y if 0<(y-a[1])/d[1]<1)
            ordered=sorted(cuts)
            for lo,hi in zip(ordered,ordered[1:]):
                midpoint=a+(lo+hi)/2*d
                if 60<=i<148 and cuts_y[0]<midpoint[1]<cuts_y[1]:continue
                normal=np.array([-d[1],d[0]])/np.linalg.norm(d)
                for u in (lo,hi):
                    points.extend(a+u*d+side*.75*normal for side in (-1,0,1))
                for u,weight in zip((lo+hi)/2+(hi-lo)*z/2,w*(hi-lo)/2):
                    pt=a+u*d;da=weight*np.linalg.norm(d)*1.5
                    J+=da*np.outer(np.r_[1.,pt],np.r_[1.,pt])
                    stress=coeff[0]+coeff[1:]@(pt-cg)
                    result+=da*stress*np.array([1.,pt[1]-cg[1],-(pt[0]-cg[0])])
        np.testing.assert_allclose(result,[0.,0.,1.],rtol=0,atol=2e-12)
        center=J[0,1:]/J[0,0];tensor=J[1:,1:]-np.outer(J[0,1:],J[0,1:])/J[0,0]
        self.assertAlmostEqual(J[0,0],309.8485018099485,places=10)
        np.testing.assert_allclose(center,r['effective_properties']['centroid_xy_mm'],atol=1e-11)
        self.assertAlmostEqual(tensor[0,0],115047.13112236939,places=7)
        points=np.array(points);stress=effort*(coeff[0]+(points-cg)@coeff[1:])
        self.assertAlmostEqual(max(abs(stress)),250.,places=11)
        np.testing.assert_allclose(coeff,[1.2646250463225738e-5,-8.692089843912355e-6,0.],rtol=1e-12)
        self.assertFalse(r['moment_transport_required'])
        self.assertEqual(r['stiffeners'],[])
        for bound,ids in zip(r['outstand_flange_bounds'],(range(20,60),range(148,188))):
            self.assertEqual(bound['bound_stress_ends_MPa'],[149.,0.])
            self.assertEqual(bound['rho'],1.)
            self.assertFalse(bound['Eq5_17_used'])
            self.assertLessEqual(bound['maximum_actual_minus_bound_MPa'],-.614)
            self.assertLess(bound['lip_max_compression_MPa'],0.)
            xmin=min(n[min(ids):max(ids)+2,0]);b=max(n[min(ids):max(ids)+2,0])-xmin
            for i in ids:
                d=n[i+1]-n[i];normal=np.array([-d[1],d[0]])/np.linalg.norm(d)
                for u in (0.,1.):
                    for side in (-1,0,1):
                        p=n[i]+u*d+side*.75*normal
                        compression=-effort*(coeff[0]+coeff[1:]@(p-cg))
                        self.assertLessEqual(compression,149*(1-(p[0]-xmin)/b))
        audit=r['fixed_point_iteration_audit']
        self.assertTrue(audit['final_recheck'])
        self.assertLess(abs(audit['residual']),1e-13)
        self.assertAlmostEqual(rho,.8192481544433549,places=12)

    def test_four_starts_and_no_convergence_or_domain_fallback(self):
        nodes,t,gross,groups,_=en._geometry(self.profiles[1.5])
        r=self.cert[t]['components']['My_negative']
        for start in (1.,.4,.7,.95):
            rr=en._negative_my_web_reduced(copy.deepcopy(r),nodes,t,gross,groups,initial_rho=start)
            self.assertAlmostEqual(rr['local_panels'][2]['rho'],r['local_panels'][2]['rho'],places=12)
        with self.assertRaises(ValueError):
            en._negative_my_web_reduced(copy.deepcopy(r),nodes,t,gross,groups,max_iterations=1)
        for start in (0.,-1.,float('nan')):
            with self.assertRaises(ValueError):
                en._negative_my_web_reduced(copy.deepcopy(r),nodes,t,gross,groups,initial_rho=start)
        nodes,t,gross,groups,_=en._geometry(self.profiles[2.])
        with self.assertRaises(ValueError):
            en._negative_my_web_reduced(copy.deepcopy(r),nodes,t,gross,groups)
        self.assertTrue(self.cert[1.2]['components']['My_negative']['eligible'])
        with patch.object(en,'_negative_my_web_reduced',side_effect=ValueError('guard')):
            failed=en.build_component_sections(self.profiles[1.5])['components']['My_negative']
        self.assertFalse(failed['eligible'])
        self.assertIsNone(failed['effective_properties'])
        self.assertIsNone(failed['sigma_coefficients_c0_cx_cy'])

    def test_flange_reduction_and_asymmetry_fail_closed(self):
        original=en._critical
        def insufficient_flange(k,t,b):
            return original(k,t,b)*(.5 if k==1.70 and t==1.5 else 1.)
        with patch.object(en,'_critical',side_effect=insufficient_flange):
            r=en.build_component_sections(self.profiles[1.5])['components']['My_negative']
        self.assertFalse(r['eligible'])
        self.assertIsNone(r['sigma_coefficients_c0_cx_cy'])
        self.assertIn('flange',r['blocking_reasons'][0]['detail'])
        original_refs=en._my_refs_for
        def asymmetric(*args):
            refs=original_refs(*args);refs[0]=(refs[0][0],.1,1.)
            return refs
        with patch.object(en,'_my_refs_for',side_effect=asymmetric):
            r=en.build_component_sections(self.profiles[1.5])['components']['My_negative']
        self.assertFalse(r['eligible'])
        self.assertIsNone(r['effective_properties'])
        self.assertIn('symmetry',r['blocking_reasons'][0]['detail'])

    def test_history_and_material_are_not_reinterpreted(self):
        for schema in (en.LEGACY_SCHEMA,en.PREVIOUS_SCHEMA,en.AXIAL_SCHEMA,en.MY150_SCHEMA):
            c=copy.deepcopy(self.cert[1.5]);c['schema']=schema;c.pop('content_sha256')
            c['content_sha256']=en._canonical_sha(c);old=copy.deepcopy(c)
            with patch.object(en,'build_component_sections',side_effect=AssertionError('no recalculation')):
                en.verify_component_sections(c)
            self.assertEqual(c,old)
        for kwargs in ({'fyb_MPa':300.},{'gamma_M0':1.1},{'E_MPa':200000.}):
            with self.assertRaises(ValueError):en.build_component_sections(self.profiles[1.5],**kwargs)

if __name__=='__main__':unittest.main()
