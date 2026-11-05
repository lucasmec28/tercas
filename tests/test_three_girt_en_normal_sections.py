"""Focused regression and independent numerical checks for the restricted API."""
import copy
import hashlib
import json
import math
from pathlib import Path
import unittest

import numpy as np

from tercas.three_girt_en_normal.en1993_normal_components import (MATERIAL, PURE_ACTIONS, build_component_sections,
                                      require_component, verify_component_sections,
                                      _distortional_area_witness)
HERE = Path(__file__).resolve().parent
PROFILES = HERE.parent/"tercas/data/torsion_profiles"


def family():
    return {float(json.loads(p.read_text())["thickness_mm"]):json.loads(p.read_text())
            for p in sorted(PROFILES.glob("ue*.json"))}


def quadrature(nodes,t,stress,center):
    """Independent Gauss integration of [N,Mx,My], no production matrix use."""
    z,w = np.polynomial.legendre.leggauss(5)
    out = np.zeros(3)
    for a,b in zip(nodes[:-1],nodes[1:]):
        length = np.linalg.norm(b-a)
        for u,weight in zip((z+1)/2,w/2):
            point=a+u*(b-a); x,y=point-center
            sigma=stress(point)
            out += weight*length*t*sigma*np.array([1,y,-x])
    return out


class ENComponentsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles=family()
        assert len(cls.profiles)==7
        cls.cert={t:build_component_sections(p) for t,p in cls.profiles.items()}

    def test_declared_coverage_for_all_42_component_cases(self):
        for t,c in self.cert.items():
            expected={"N_tension":True,"N_compression":True,"Mx_positive":True,
                      "Mx_negative":True,"My_positive":True,"My_negative":True}
            self.assertEqual({k:v["eligible"] for k,v in c["components"].items()},expected)
            self.assertTrue(c["all_normal_components_eligible"])

    def test_no_gross_fallback_or_effective_centroid_when_blocked(self):
        for c in self.cert.values():
            for v in c["components"].values():
                if v["eligible"]: continue
                self.assertIsNone(v["sigma_coefficients_c0_cx_cy"])
                self.assertIsNone(v["effective_properties"])
                self.assertNotIn("centroid_shift_from_gross_mm",v)
                self.assertGreater(len(v["blocking_reasons"]),0)

    def test_signed_unit_resultants_by_independent_gauss_integration(self):
        max_error=0.
        for t,c in self.cert.items():
            p=self.profiles[t]; nodes=np.array(p["nodes_xy_mm"]); center=np.array(c["gross_properties"]["centroid_xy_mm"])
            for name,v in c["components"].items():
                if not v["eligible"]: continue
                if v.get("moment_transport_required") or v.get("effective_line_intervals"): continue  # Tested on retained strips separately.
                coeff=np.array(v["sigma_coefficients_c0_cx_cy"])
                axis,sign=PURE_ACTIONS[name]
                actual=quadrature(nodes,t,lambda pt: sign*(coeff[0]+coeff[1:]@(pt-center)),center)
                expected=np.zeros(3); expected[axis]=sign
                error=float(max(abs(actual-expected)));max_error=max(max_error,error)
                np.testing.assert_allclose(actual,expected,rtol=0,atol=2e-12)
                self.assertEqual(v["centroid_shift_from_gross_mm"],[0.,0.])
                self.assertEqual(v["additional_Mx_per_N_mm"],0.)
                self.assertEqual(v["additional_My_per_N_mm"],0.)
        self.assertLess(max_error,2e-12)

    def test_ULS_pure_state_is_fyb_with_explicit_Eq4_4_integral_web_trial(self):
        for c in self.cert.values():
            for v in c["components"].values():
                if v.get("section_status") in ("effective_web_reduced_negative_My_ULS", "effective_local_flange_reduced_pure_Mx_ULS"):
                    self.assertAlmostEqual(v["ULS_max_abs_line_or_face_stress_MPa"],250.)
                    self.assertLess(v["ULS_max_abs_line_stress_MPa"],250.)
                    continue  # Independent dedicated fixed-point/face certificate tests.
                self.assertAlmostEqual(v["ULS_max_abs_line_stress_MPa"],250.)
                for panel in v["local_panels"]:
                    if panel["branch"] == "tension":continue
                    ref=panel["slenderness_reference_stress_MPa"]
                    if ref!=250.:
                        self.assertEqual(v['action'],'My_negative')
                        self.assertEqual(panel['panel'],'web')
                        trial=panel['Eq4_4_ULS_integral_trial']
                        self.assertTrue(trial['integral_trial'])
                        self.assertEqual(ref,trial['sigma_com_Ed_MPa'])
                        self.assertGreater(trial['lambda_p_at_fyb'],panel['lambda_p_integral_limit'])
                    self.assertAlmostEqual(panel["lambda_p"],math.sqrt(ref/panel["sigma_cr_MPa"]),places=14)
                for st in v["stiffeners"]:
                    self.assertAlmostEqual(st["lambda_d"],math.sqrt(250./st["sigma_cr_MPa"]),places=14)
                    if v["eligible"] and v.get("section_status") == "effective_local_distortional_reduced_uniform_compression_ULS":
                        self.assertAlmostEqual(st["Eq5_17_As_red_over_As_at_ULS"],st["chi_d"],places=15)
                        self.assertLess(st["chi_d"],1.)
                        self.assertFalse(st["integral_fixed_point"])
                    elif v["eligible"]:
                        self.assertGreater(st["chi_d"],0.)
                        self.assertLessEqual(st["chi_d"],1.)
                        self.assertEqual(st["Eq5_17_As_red_over_As_at_ULS"],1.)
                        self.assertGreaterEqual(st["Eq5_17_unclamped_As_ratio_at_ULS"],1.)
                        self.assertGreaterEqual(st["Eq5_17_reduced_strength_minus_stress_MPa"],0.)
                        self.assertTrue(st["integral_fixed_point"])

    def test_uniform_compression_hand_formula_web_and_flange(self):
        for t,c in self.cert.items():
            panels={p["panel"]:p for p in c["components"]["N_compression"]["local_panels"]}
            rm=1.5*t; corner=rm*(1-1/math.sqrt(2))
            for key,b in (("web",100-t-2*corner),("lower_flange",50-t-2*corner)):
                p=panels[key]
                self.assertAlmostEqual(p["b_mm"],b,places=12)
                scr=4*math.pi**2*210000/(12*(1-.3**2))*(t/b)**2
                self.assertAlmostEqual(p["sigma_cr_MPa"],scr,places=9)
                lam=math.sqrt(250/scr)
                rho=1. if lam<=.5+math.sqrt(.03) else min(1.,(lam-.22)/lam**2)
                self.assertAlmostEqual(p["rho"],rho,places=14)

    def test_compressed_assemblies_by_independent_gauss_integrals(self):
        for t,c in self.cert.items():
            nodes=np.array(self.profiles[t]["nodes_xy_mm"])
            for v in c["components"].values():
                for st in v["stiffeners"]:
                    z,w=np.polynomial.legendre.leggauss(5); A=0.;mx=0.;my=0.;yy=0.
                    for i,lo,hi in st["line_intervals"]:
                        a,b=nodes[i:i+2];length=np.linalg.norm(b-a)
                        for u,wt in zip((lo+hi)/2+(hi-lo)*z/2,w*(hi-lo)/2):
                            pt=a+u*(b-a);da=wt*length*t
                            A+=da;mx+=da*pt[0];my+=da*pt[1];yy+=da*pt[1]**2
                    self.assertAlmostEqual(A/st["As_mm2"],1.,places=13)
                    np.testing.assert_allclose([mx/A,my/A],st["centroid_xy_mm"],rtol=0,atol=1e-11)
                    self.assertAlmostEqual((yy-my*my/A)/st["Is_mm4"],1.,places=10)
                    self.assertGreaterEqual(st["stress_domain_audit"]["min_line_compression_MPa"],-1e-9)
                    self.assertGreaterEqual(st["stress_domain_audit"]["min_offset_face_compression_MPa"],-1e-9)

    def test_top_bottom_reflection(self):
        for c in self.cert.values():
            a,b=[c["components"][x] for x in ("Mx_positive","Mx_negative")]
            self.assertEqual(a["eligible"],b["eligible"])
            self.assertEqual(len(a["stiffeners"]),len(b["stiffeners"]))
            wa=next(p for p in a["local_panels"] if p["panel"] == "web")
            wb=next(p for p in b["local_panels"] if p["panel"] == "web")
            self.assertEqual(wa["k_sigma"],23.9)
            self.assertEqual(wb["k_sigma"],23.9)
            for sa,sb in zip(a["stiffeners"],b["stiffeners"]):
                for key in ("As_mm2","Is_mm4","b1_mm","sigma_cr_MPa","lambda_d","chi_d"):
                    self.assertAlmostEqual(sa[key]/sb[key],1.,places=10)

    def test_My_inverse_tension_lip_does_not_waive_mixed_flange(self):
        for c in self.cert.values():
            v=c["components"]["My_negative"]
            self.assertTrue(v["eligible"])
            self.assertEqual(len(v["outstand_flange_bounds"]),2)
            for bound in v["outstand_flange_bounds"]:
                self.assertFalse(bound["physical_As_assumed_wholly_tensile"])
                self.assertFalse(bound["Eq5_17_used"])
                self.assertTrue(bound["lip_is_noncompressive"])
                self.assertTrue(bound["pointwise_dominance_demonstrated"])
            if not v["eligible"]:
                self.assertIn("ULS_LOCAL_REDUCTION_NOT_IMPLEMENTED",{b["code"] for b in v["blocking_reasons"]})
            for audit in v["tension_assemblies"]:
                self.assertGreater(audit["max_line_compression_MPa"],0.)
                self.assertLess(audit["min_line_compression_MPa"],0.)

    def test_chi_below_one_integral_ULS_fixed_point_not_service(self):
        cases=[(1.2,"My_positive"),(1.5,"Mx_positive"),(1.5,"Mx_negative"),(1.5,"My_positive")]
        for t,key in cases:
            v=self.cert[t]["components"][key]
            self.assertTrue(v["eligible"])
            self.assertTrue(all(p["rho"] == 1. for p in v["local_panels"]))
            p=self.profiles[t];nodes=np.array(p["nodes_xy_mm"])
            center=np.array(self.cert[t]["gross_properties"]["centroid_xy_mm"])
            coeff=np.array(v["sigma_coefficients_c0_cx_cy"])
            effort=v["ULS_pure_effort_signed"]
            line=effort*(coeff[0]+(nodes-center)@coeff[1:])
            self.assertAlmostEqual(max(abs(line)),250.,places=12)
            for st in v["stiffeners"]:
                self.assertLess(st["chi_d"],1.)
                comp=-effort*(coeff[0]+(np.array(st["centroid_xy_mm"])-center)@coeff[1:])
                self.assertAlmostEqual(comp,st["sigma_com_Ed_MPa"],places=11)
                self.assertLess(comp,st["chi_d"]*250.)
                self.assertEqual(st["Eq5_17_As_red_over_As_at_ULS"],1.)
                self.assertGreater(st["Eq5_17_unclamped_As_ratio_at_ULS"],1.)
                self.assertTrue(st["integral_fixed_point"])
                # Unchanged As and local widths leave the entire section and
                # centroid unchanged. Unit efforts are rebalanced separately.
                self.assertEqual(v["effective_properties"],self.cert[t]["gross_properties"])

    def test_Eq5_17_exact_cap_does_not_promote_just_below_one(self):
        raw,cap,margin=_distortional_area_witness(.9,225.)
        self.assertEqual((raw,cap,margin),(1.,1.,0.))
        raw,cap,margin=_distortional_area_witness(.9,math.nextafter(225.,math.inf))
        self.assertLess(raw,1.);self.assertLess(cap,1.);self.assertLess(margin,0.)
        raw,cap,margin=_distortional_area_witness(.9,math.nextafter(225.,-math.inf))
        self.assertGreater(raw,1.);self.assertEqual(cap,1.);self.assertGreater(margin,0.)
        for chi,stress in ((.9,0.),(.9,-1.),(0.,225.),(1.01,225.)):
            with self.assertRaises(ValueError):_distortional_area_witness(chi,stress)

    def test_revision_changes_only_four_prior_and_five_outstand_components(self):
        # Portable historical expectation, not a path to the research tree.
        prior={(t,key) for t in self.cert for key in PURE_ACTIONS
               if key=="N_tension" or (key=="N_compression" and t>=2.65)
               or (key in ("Mx_positive","Mx_negative","My_positive") and t>=2.)}
        current={(t,key) for t,c in self.cert.items() for key,v in c["components"].items() if v["eligible"]}
        self.assertEqual(len(prior),25)
        self.assertFalse(prior-current)
        self.assertEqual(current-prior,{(1.2,"Mx_positive"),(1.2,"Mx_negative"),(1.2,"My_negative"),(1.5,"My_negative"),(1.2,"My_positive"),(1.5,"Mx_positive"),(1.5,"Mx_negative"),(1.5,"My_positive"),(2.,"My_negative"),(2.25,"My_negative"),(2.65,"My_negative"),(3.,"My_negative"),(3.35,"My_negative"),(2.,"N_compression"),(2.25,"N_compression"),(1.2,"N_compression"),(1.5,"N_compression")})
        self.assertEqual(len(current),42)
        # Previously admitted branches still have the same pure gross stress
        # coefficients, checked against the independent frozen source values.
        for t,key in prior:
            p=self.profiles[t]["own_properties"]
            expected=([1/p["A_mm2"],0.,0.] if key.startswith("N_") else
                      [0.,0.,1/p["Ix_strong_mm4"]] if key.startswith("Mx_") else
                      [0.,-1/p["Iy_weak_mm4"],0.])
            np.testing.assert_allclose(self.cert[t]["components"][key]["sigma_coefficients_c0_cx_cy"],expected,rtol=2e-12,atol=0.)

    def test_branch_helper_and_physical_frame_mapping(self):
        c=self.cert[2.65]
        self.assertEqual(require_component(c,"N",1.)["action"],"N_tension")
        self.assertEqual(require_component(c,"N",-1.)["action"],"N_compression")
        self.assertEqual(require_component(c,"Mx",-1.)["action"],"Mx_negative")
        self.assertEqual(require_component(c,"My",1.)["action"],"My_positive")
        self.assertEqual(require_component(c,"My",-1.)["action"],"My_negative")
        self.assertEqual(require_component(self.cert[1.2],"My",-1.)["action"],"My_negative")
        self.assertIsNone(require_component(c,"My",0.))
        with self.assertRaises(ValueError):require_component(c,"Mz",1.)
        with self.assertRaises(ValueError):require_component(c,"N",float("nan"))
        with self.assertRaises(ValueError):require_component(c,"N",True)
        self.assertEqual(c["frame_mapping"],"Mx_R01=-My_frame; My_R01=-Mz_frame")

    def test_material_and_geometry_are_fail_closed(self):
        p=self.profiles[2.65]
        for kwargs in ({"E_MPa":200000.},{"gamma_M0":1.1},{"fya_MPa":300.},{"fyb_MPa":350.},{"nu":float('nan')},{"fyb_MPa":True}):
            with self.assertRaises(ValueError): build_component_sections(p,**kwargs)
        for mutate in (lambda x:x["nodes_xy_mm"][0].__setitem__(0,999.),
                       lambda x:x["geometry_external_mm"].__setitem__("ri",3.),
                       lambda x:x["own_properties"].__setitem__("A_mm2",1.),
                       lambda x:x.__setitem__("thickness_mm",2.3)):
            q=copy.deepcopy(p);mutate(q)
            with self.assertRaises(ValueError):build_component_sections(q)
        q=copy.deepcopy(p);q["nodes_xy_mm"][0][0]+=1.
        q["geometry_identity"]["nodes_canonical_sha256"]=hashlib.sha256(json.dumps(q["nodes_xy_mm"],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        with self.assertRaises(ValueError):build_component_sections(q)

    def test_mutation_and_no_input_mutation(self):
        p=copy.deepcopy(self.profiles[2.65]);before=copy.deepcopy(p)
        c=build_component_sections(p);self.assertEqual(p,before);verify_component_sections(c)
        c["components"]["My_negative"]["eligible"]=False
        with self.assertRaises(ValueError):verify_component_sections(c)
        with self.assertRaises(ValueError):require_component(c,"N",1.)


if __name__ == "__main__":
    unittest.main(verbosity=2)
