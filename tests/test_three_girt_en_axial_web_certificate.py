"""Independent retained-strip geometry and explicit axial transport contract."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

import numpy as np
from tercas.three_girt_en_normal import en1993_normal_components as en


class AxialWebCertificateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths=(Path(__file__).resolve().parents[1]/'tercas/data/torsion_profiles').glob('ue*.json')
        cls.profiles={p['thickness_mm']:p for p in map(lambda p:json.loads(p.read_text()),paths)}
        cls.cert={t:en.build_component_sections(p) for t,p in cls.profiles.items()}

    def test_independent_removed_rectangle_and_retained_gauss(self):
        for t in (2.,2.25):
            c=self.cert[t]; r=c['components']['N_compression']; g=c['gross_properties']
            n=np.array(self.profiles[t]['nodes_xy_mm']); cg=np.array(g['centroid_xy_mm'])
            web=r['local_panels'][2]; L=(1-web['rho'])*web['b_mm']; removed=t*L
            # Central web is straight at x=0; corner material stays retained.
            xweb=float(n[100,0]); mid=(n[60,1]+n[148,1])/2
            A=g['A_mm2']-removed
            center=(g['A_mm2']*cg-removed*np.array([xweb,mid]))/A
            ix=g['Ix_strong_mm4']+g['A_mm2']*cg[1]**2-t*L**3/12-removed*mid**2-A*center[1]**2
            iy=g['Iy_weak_mm4']+g['A_mm2']*cg[0]**2-removed*xweb**2-A*center[0]**2
            eff=r['effective_properties']
            np.testing.assert_allclose([eff['A_mm2'],eff['Ix_strong_mm4'],eff['Iy_weak_mm4']],[A,ix,iy],rtol=2e-13)
            np.testing.assert_allclose(eff['centroid_xy_mm'],center,atol=1e-12,rtol=0.)
            z,w=np.polynomial.legendre.leggauss(4); J=np.zeros((3,3)); result=np.zeros(3)
            for i,lo,hi in r['effective_line_intervals']:
                self.assertTrue(0<=lo<hi<=1)
                d=n[i+1]-n[i]
                for u,weight in zip((lo+hi)/2+(hi-lo)*z/2,w*(hi-lo)/2):
                    p=n[i]+u*d;da=t*np.linalg.norm(d)*weight; v=np.r_[1,p]
                    J+=da*np.outer(v,v)
                    result+=da*(-1/A)*np.array([1,p[1]-cg[1],-(p[0]-cg[0])])
            np.testing.assert_allclose(J[0,0],A,rtol=2e-14)
            np.testing.assert_allclose(J[0,1:]/A,center,atol=2e-12,rtol=0.)
            ex,ey=r['centroid_shift_from_gross_mm']
            np.testing.assert_allclose(result,[-1.,0.,ex],atol=2e-13,rtol=0.)
            self.assertEqual(ey,0.);self.assertGreater(ex,0.)
            self.assertEqual(eff['Ixy_mm4'],0.)
            self.assertLess(abs(r['symmetry_audit']['raw_ey_mm']),1e-12)
            bands=r['retained_bands'][2]['retained_fraction_bands']
            np.testing.assert_allclose(bands,[[0,web['rho']/2],[1-web['rho']/2,1]],atol=0,rtol=0)
            for band in r['retained_bands']:
                if band['panel']!='web':self.assertEqual(band['retained_fraction_bands'],[[0.,1.]])
            self.assertLess(web['rho'],1.)
            self.assertTrue(all(st['chi_d']==1. for st in r['stiffeners']))

    def test_uniform_operator_excludes_eccentricity_and_requires_transport(self):
        for t in (2.,2.25):
            r=self.cert[t]['components']['N_compression']; A=r['effective_properties']['A_mm2']
            self.assertEqual(r['sigma_coefficients_c0_cx_cy'],[1/A,0.,0.])
            self.assertAlmostEqual(r['ULS_pure_effort_signed'],-250*A,places=9)
            self.assertTrue(r['moment_transport_required'])
            self.assertEqual(r['additional_My_per_N_mm'],r['centroid_shift_from_gross_mm'][0])
            self.assertEqual(r['additional_Mx_per_N_mm'],0.)
            self.assertNotEqual(r['section_status'],'integral_demonstrated_at_ULS')
        r=self.cert[2.25]['components']['N_compression']
        self.assertAlmostEqual(r['effective_properties']['A_mm2'],477.225593556,places=8)
        self.assertAlmostEqual(r['centroid_shift_from_gross_mm'][0],.558330161,places=8)
        self.assertAlmostEqual(self.cert[2.]['components']['N_compression']['stiffeners'][0]['lambda_d'],.631180296,places=8)

    def test_reduction_never_promoted_and_as_guard_fails_closed(self):
        # Exercise the final restricted geometry guard independently of entry
        # construction: no rho or chi infinitesimally below 1 may be waived.
        nodes,t,gross,groups,_=en._geometry(self.profiles[2.])
        original=self.cert[2.]['components']['N_compression']
        for field in ('flange','chi'):
            r=copy.deepcopy(original)
            if field=='flange':r['local_panels'][1]['rho']=np.nextafter(1.,0.)
            else:r['stiffeners'][0]['chi_d']=np.nextafter(1.,0.)
            with self.assertRaises(ValueError):en._uniform_web_reduced(r,nodes,t,gross,groups)
        r=copy.deepcopy(original); shifted=nodes.copy();shifted[100,1]+=.01
        with self.assertRaises(ValueError):en._uniform_web_reduced(r,shifted,t,gross,groups)

    def test_retained_strips_do_not_overlap_or_change_physical_As(self):
        for t in (2.,2.25):
            r=self.cert[t]['components']['N_compression']; by_segment={}
            for i,lo,hi in r['effective_line_intervals']:
                by_segment.setdefault(i,[]).append((lo,hi))
            for intervals in by_segment.values():
                ordered=sorted(intervals)
                self.assertTrue(all(a[1]<=b[0] for a,b in zip(ordered,ordered[1:])))
            for st in r['stiffeners']:
                for i,lo,hi in st['line_intervals']:
                    self.assertIn((0.,1.),by_segment[i])
                    self.assertTrue(0.<=lo<hi<=1.)
                self.assertEqual(st['stress_domain_audit']['min_line_compression_MPa'],250.)
                self.assertEqual(st['stress_domain_audit']['max_offset_face_compression_MPa'],250.)

    def test_legacy_hash_validation_without_recalculation(self):
        c=copy.deepcopy(self.cert[2.65]);c['schema']=en.LEGACY_SCHEMA
        c.pop('content_sha256');c['content_sha256']=en._canonical_sha(c)
        before=copy.deepcopy(c);en.verify_component_sections(c);self.assertEqual(c,before)
        c['components']['N_tension']['sigma_coefficients_c0_cx_cy'][0]*=2
        with self.assertRaises(ValueError):en.verify_component_sections(c)

    def test_other_34_unchanged_component_records_match_frozen_source(self):
        records={str(t):{k:v for k,v in c['components'].items()
                 if not (t in (1.2,1.5,2.,2.25) and k=='N_compression') and not(t==1.5 and k=='My_negative') and not(t==1.2 and k in ('Mx_positive','Mx_negative','My_negative'))} for t,c in self.cert.items()}
        self.assertEqual(en._canonical_sha(records),'a31148aa3503929d7e626f15ced28f465f66d06e9ec262ac918105193de9d5ec')


if __name__=='__main__':unittest.main()
