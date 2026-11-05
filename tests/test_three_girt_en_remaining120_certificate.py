"""Pinned t1.20: independent geometry/resultants and fail-closed branch tests."""
import copy
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
from tercas.three_girt_en_normal import en1993_normal_components as en

ROOT=Path(__file__).resolve().parents[1]
NEW=('Mx_positive','Mx_negative','My_negative')


def independent_section(nodes, group, rho, t=1.2):
    """Clip projected bands independently, then Gauss-4 integrate physical dA."""
    bounds=(0,20,60,148,188,208)
    start,end=bounds[group:group+2]
    axis=1 if group%2==0 else 0
    lower=min(nodes[start:end+1,axis]);width=np.ptp(nodes[start:end+1,axis])
    limits=(lower+rho*width/2,lower+(1-rho/2)*width)
    J=np.zeros((3,3));refs=[];vertices=[];gauss=[]
    z,w=np.polynomial.legendre.leggauss(4)
    for i,(a,b) in enumerate(zip(nodes[:-1],nodes[1:])):
        d=b-a;length=np.linalg.norm(d);cuts={0.,1.}
        if start<=i<end and d[axis]!=0:
            cuts.update(float((x-a[axis])/d[axis]) for x in limits if 0<(x-a[axis])/d[axis]<1)
        for lo,hi in zip(sorted(cuts),sorted(cuts)[1:]):
            middle=a+(lo+hi)/2*d
            if start<=i<end and limits[0]<middle[axis]<limits[1]:continue
            refs.append((i,lo,hi));normal=np.array([-d[1],d[0]])/length
            for u in (lo,hi):
                vertices.extend(a+u*d+side*t/2*normal for side in (-1,0,1))
            for u,weight in zip((lo+hi)/2+(hi-lo)*z/2,w*(hi-lo)/2):
                point=a+u*d;da=weight*length*t
                J+=da*np.outer(np.r_[1.,point],np.r_[1.,point]);gauss.append((point,da))
    return J,refs,np.array(vertices),gauss


def integrate(gauss,cg,coeff):
    result=np.zeros(3)
    for point,da in gauss:
        result+=da*(coeff[0]+coeff[1:]@(point-cg))*np.array([1.,point[1]-cg[1],-(point[0]-cg[0])])
    return result


class Remaining120CertificateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles={p['thickness_mm']:p for p in
            (json.loads(f.read_text()) for f in (ROOT/'tercas/data/torsion_profiles').glob('ue*.json'))}
        cls.certs={t:en.build_component_sections(p) for t,p in cls.profiles.items()}
        cls.cert=cls.certs[1.2];cls.nodes=np.array(cls.profiles[1.2]['nodes_xy_mm'])

    def test_only_three_records_change_and_global_scope_stays_false(self):
        records={str(t):{k:v for k,v in c['components'].items() if not(t==1.2 and k in NEW)}
                 for t,c in self.certs.items()}
        self.assertEqual(sum(map(len,records.values())),39)
        self.assertEqual(en._canonical_sha(records),'32f6a817f880e882cbb0f1956f198a1be938b438adc656ba495ec2355729a3e1')
        for c in self.certs.values():
            self.assertEqual(c['schema'],en.SCHEMA)
            self.assertTrue(c['schema'].endswith('_v5'))
            self.assertTrue(c['all_normal_components_eligible'])
            self.assertFalse(c['physical_geometry_verified']);self.assertFalse(c['whole_member_approved'])
            self.assertEqual(sum(v['eligible'] for v in c['components'].values()),6)

    def test_independent_mx_clipping_full_tensor_uls_and_as(self):
        n=self.nodes;cg=np.array(self.cert['gross_properties']['centroid_xy_mm'])
        for action,sign,group in [('Mx_positive',1,1),('Mx_negative',-1,3)]:
            r=self.cert['components'][action];start,end=(20,60) if sign==1 else (148,188)
            width=np.ptp(n[start:end+1,0]);critical=4*math.pi**2*210000/(12*(1-.3**2))*(1.2/width)**2
            lam=math.sqrt(250/critical);rho=(lam-.22)/lam**2
            self.assertAlmostEqual(rho,.9629985360850789,places=14)
            self.assertEqual(r['local_panels'][group]['psi'],1.)
            J,refs,vertices,gauss=independent_section(n,group,rho)
            center=J[0,1:]/J[0,0];I=J[1:,1:]-np.outer(J[0,1:],J[0,1:])/J[0,0]
            eff=r['effective_properties'];coeff=np.array(r['sigma_coefficients_c0_cx_cy'])
            np.testing.assert_allclose([J[0,0],I[1,1],I[0,0],I[0,1]],
                [eff[k] for k in ('A_mm2','Ix_strong_mm4','Iy_weak_mm4','Ixy_mm4')],rtol=2e-12,atol=1e-8)
            np.testing.assert_allclose(center,eff['centroid_xy_mm'],atol=3e-12,rtol=0)
            self.assertAlmostEqual(J[0,0],269.2062427755713,places=10)
            self.assertGreater(sign*I[0,1],751.)
            Ix,Iy,Ixy=I[1,1],I[0,0],I[0,1];ex,ey=center-cg;D=Ix*Iy-Ixy*Ixy
            np.testing.assert_allclose(coeff,[(Ixy*ex-Iy*ey)/D,-Ixy/D,Iy/D],rtol=3e-12,atol=1e-17)
            np.testing.assert_allclose(integrate(gauss,cg,coeff),[0.,1.,0.],rtol=0,atol=2e-13)
            effort=r['ULS_pure_effort_signed'];stress=effort*(coeff[0]+(vertices-cg)@coeff[1:])
            self.assertEqual(math.copysign(1,effort),sign)
            self.assertAlmostEqual(max(abs(stress)),250.,places=10)
            np.testing.assert_allclose(integrate(gauss,cg,effort*coeff),[0.,effort,0.],rtol=0,atol=2e-8)
            self.assertFalse(r['moment_transport_required'])
            self.assertEqual([r['additional_Mx_per_N_mm'],r['additional_My_per_N_mm']],[0.,0.])
            # Two independently reconstructed wrong fields fail equilibrium.
            naive=np.array([-ey/Ix,0.,1./Ix]);missing=coeff.copy();missing[0]=0.
            self.assertGreater(abs(integrate(gauss,cg,effort*naive)[2]),1000.)
            self.assertGreater(abs(integrate(gauss,cg,effort*missing)[0]),100.)
            # Rebuild physical As from the lip and the retained far-x flange band.
            lipids=range(0,20) if sign==1 else range(188,208)
            xmax=max(n[start:end+1,0]);xcut=xmax-rho*width/2
            As=0.;first=np.zeros(2);yy=0.
            z,w=np.polynomial.legendre.leggauss(4)
            for i,lo,hi in refs:
                a=n[i];d=n[i+1]-a;middle=a+(lo+hi)/2*d
                if not(i in lipids or (start<=i<end and middle[0]>=xcut)):continue
                for u,weight in zip((lo+hi)/2+(hi-lo)*z/2,w*(hi-lo)/2):
                    point=a+u*d;da=weight*np.linalg.norm(d)*1.2
                    As+=da;first+=da*point;yy+=da*point[1]**2
            center_as=first/As;Is=yy-As*center_as[1]**2;b1=center_as[0];hw=np.ptp(n[:,1])
            K=210000*1.2**3/(4*(1-.3**2))/(b1*b1*hw+b1**3)
            sigcr=2*math.sqrt(K*210000*Is)/As;ld=math.sqrt(250/sigcr);chi=1.47-.723*ld
            sigma_as=-effort*(coeff[0]+coeff[1:]@(center_as-cg));raw=chi*250/sigma_as
            st=r['stiffeners'][0]
            self.assertAlmostEqual(st['As_mm2'],As,places=11)
            self.assertAlmostEqual(st['Is_mm4'],Is,places=7)
            self.assertAlmostEqual(st['sigma_com_Ed_MPa'],sigma_as,places=10)
            self.assertAlmostEqual(st['chi_d'],chi,places=10)
            self.assertGreater(raw,1.0012);self.assertEqual(st['Eq5_17_As_red_over_As_at_ULS'],1.)
            self.assertGreater(st['Eq5_17_reduced_strength_minus_stress_MPa'],.297)
            self.assertEqual(st['t_red_mm'],1.2);self.assertEqual(st['kr_area'],0.)
            self.assertTrue(st['integral_fixed_point']);self.assertFalse(st['step3_optional_refinement_used'])
            self.assertTrue(all(v[3]==1.2 for v in r['effective_weighted_line_intervals']))
            self.assertEqual(r['final_web_certificate']['rho'],1.)
            self.assertEqual(r['final_lip_certificate']['rho'],1.)

    def test_mirrors_and_face_normalization_are_explicit(self):
        a,b=(self.cert['components'][name] for name in NEW[:2])
        np.testing.assert_allclose(np.array(a['sigma_coefficients_c0_cx_cy'])*[-1,-1,1],b['sigma_coefficients_c0_cx_cy'],atol=1e-16,rtol=0)
        aa=sorted(a['effective_line_intervals']);bb=sorted((207-i,1-hi,1-lo) for i,lo,hi in b['effective_line_intervals'])
        np.testing.assert_allclose(aa,bb,atol=1e-11,rtol=0)
        for key in NEW:
            r=self.cert['components'][key]
            self.assertIn('face',r['ULS_pure_effort_role'])
            self.assertLess(r['ULS_max_abs_line_stress_MPa'],250.)
            self.assertAlmostEqual(r['ULS_max_abs_line_or_face_stress_MPa'],250.,places=10)
        my=self.cert['components']['My_negative']
        self.assertAlmostEqual(my['local_panels'][2]['rho'],.658798214889,places=11)
        self.assertTrue(my['fixed_point_iteration_audit']['integral_flange_bounds_checked_each_iteration'])
        for b in my['outstand_flange_bounds']:
            self.assertEqual(b['bound_stress_ends_MPa'],[172.,-43.])
            self.assertEqual(b['bound_psi'],-.25);self.assertAlmostEqual(b['k_sigma'],4.01875,places=14)
            self.assertTrue(b['dominance_includes_negative_q']);self.assertLess(b['maximum_actual_minus_bound_MPa'],-.961)
            self.assertFalse(b['lip_elastic_restraint_credit']);self.assertFalse(b['Eq5_17_used'])

    def test_new_branch_failures_withhold_all_effective_coefficients(self):
        def blocked(name):
            r=en.build_component_sections(self.profiles[1.2])['components'][name]
            self.assertFalse(r['eligible']);self.assertIsNone(r['effective_properties'])
            self.assertIsNone(r['sigma_coefficients_c0_cx_cy']);self.assertTrue(r['blocking_reasons'])
            self.assertNotIn('centroid_shift_from_gross_mm',r)
        with patch.object(en,'_distortional_area_witness',return_value=(math.nextafter(1.,0.),math.nextafter(1.,0.),-1e-14)):
            for name in NEW[:2]:blocked(name)
        with patch.object(en,'_pure_resultants_quadrature',return_value=np.array([1.,1.,0.])):
            for name in NEW[:2]:blocked(name)
        solve=np.linalg.solve
        def omit_Ixy(*args):
            result=solve(*args);result[1]=0.;return result
        with patch.object(en.np.linalg,'solve',side_effect=omit_Ixy):
            for name in NEW[:2]:blocked(name)
        original=en._internal_certificate
        def reduce_final_web(g,t,stress):
            result=original(g,t,stress)
            if g['panel']=='web' and stress[0]*stress[1]<0 and abs(sum(stress))>1e-4:result['rho']=.99
            return result
        with patch.object(en,'_internal_certificate',side_effect=reduce_final_web):
            for name in NEW[:2]:blocked(name)
        with patch.object(en,'_negative_my_outstand_bounds',side_effect=ValueError('signed bound failed')):
            blocked('My_negative')

    def test_my_bound_orientation_and_domain_fail_closed(self):
        nodes,t,gross,groups,_=en._geometry(self.profiles[1.2])
        r=self.cert['components']['My_negative'];comp=np.array(r['pure_ULS_compression_coefficients_absolute'])
        for psi in (-1.01,.01,float('nan'),True):
            with self.assertRaises(ValueError):en._negative_my_outstand_bounds(nodes,t,groups,comp,psi)
        with self.assertRaises(ValueError):en._negative_my_outstand_bounds(nodes,t,groups,comp,0.)
        with self.assertRaises(ValueError):en._negative_my_outstand_bounds(nodes,t,groups,np.array([250.,0.,0.]),-.25)
        for amplitude in (170,1000):
            with patch.object(en.math,'ceil',return_value=amplitude):
                with self.assertRaises(ValueError):en._negative_my_outstand_bounds(nodes,t,groups,comp,-.25)
        for seed in (1.,.4,.7,.95):
            trial=en._negative_my_web_reduced(copy.deepcopy(r),nodes,t,gross,groups,initial_rho=seed)
            self.assertAlmostEqual(trial['local_panels'][2]['rho'],r['local_panels'][2]['rho'],places=12)
        with self.assertRaises(ValueError):en._negative_my_web_reduced(copy.deepcopy(r),nodes,t,gross,groups,max_iterations=1)
        for action in NEW[:2]:
            wrong=copy.deepcopy(self.cert['components'][action]);wrong['physical_action_sign']*=-1
            with self.assertRaises(ValueError):en._pure_mx_local_flange_reduced(wrong,nodes,t,gross,groups)
        other=en._geometry(self.profiles[1.5])
        with self.assertRaises(ValueError):en._pure_mx_local_flange_reduced(self.cert['components']['Mx_positive'],*other[:4])

    def test_frozen_v4_is_verified_not_requalified_or_recomputed(self):
        old=json.loads((ROOT/'tests/data/EN_normal_120_v4_certificate.json').read_text());before=copy.deepcopy(old)
        self.assertEqual(old['schema'],en.MY150_SCHEMA)
        with patch.object(en,'build_component_sections',side_effect=AssertionError('history must not rebuild')):
            en.verify_component_sections(old)
            for name,axis,value in [('Mx_positive','Mx',1.),('Mx_negative','Mx',-1.),('My_negative','My',-1.)]:
                self.assertFalse(old['components'][name]['eligible'])
                with self.assertRaises(ValueError):en.require_component(old,axis,value)
        self.assertEqual(old,before)
        for schema in (en.LEGACY_SCHEMA,en.PREVIOUS_SCHEMA,en.AXIAL_SCHEMA,en.MY150_SCHEMA):
            history=copy.deepcopy(old);history['schema']=schema;history.pop('content_sha256')
            history['content_sha256']=en._canonical_sha(history)
            with patch.object(en,'build_component_sections',side_effect=AssertionError('no historical rebuild')):en.verify_component_sections(history)
        for name in NEW:
            changed=copy.deepcopy(self.cert);changed['components'][name]['sigma_coefficients_c0_cx_cy'][0]+=1e-7
            with self.assertRaises(ValueError):en.verify_component_sections(changed)
        for kw in ({'fyb_MPa':300.},{'fya_MPa':300.},{'E_MPa':200000.},{'gamma_M0':1.1}):
            with self.assertRaises(ValueError):en.build_component_sections(self.profiles[1.2],**kw)


if __name__=='__main__':unittest.main()
