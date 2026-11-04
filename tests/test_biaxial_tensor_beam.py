import copy
from decimal import Decimal
from fractions import Fraction as F
import json
import math
import random
import unittest

from tercas.biaxial_gross.tensor_beam import build_beam,solve_response,evaluate,number
from tercas.biaxial_gross.bounded_polynomial import real_roots_open_unit_interval

def model(L=4000.,E=200000.):
    return dict(L_mm=L,E_MPa=E,supports='simply_supported_bending',prismatic=True,scope='gross_flexural_component_only')

def tensor(x=500000.,y=120000.,xy=0.):
    return dict(Ix_mm4=x,Iy_mm4=y,Ixy_mm4=xy)

def case(q=(.5,.04),P=(0.,0.),position=None,a=None):
    d=dict(q_N_mm=list(q),P_N=list(P),point_position=position)
    if a is not None:d['a_mm']=a
    return d

class TensorBeamTests(unittest.TestCase):
    def close(self,a,b,atol=1e-11,rtol=1e-10):
        self.assertLessEqual(abs(a-b),atol+rtol*max(abs(a),abs(b)),(a,b))

    def test_uniform_uncoupled_closed_form(self):
        m,t,c=model(),tensor(),case()
        r=solve_response(build_beam(m,t,c))
        for i,axis in enumerate(('normal','parallel')):
            expected=5*c['q_N_mm'][i]*m['L_mm']**4/(384*m['E_MPa']*t[('Ix_mm4','Iy_mm4')[i]])
            witness=r['extrema']['displacement'][axis]['maximum_absolute']
            self.close(witness['value'],expected);self.close(witness['state']['x_mm'],m['L_mm']/2)

    def test_center_point_closed_form(self):
        r=solve_response(build_beam(model(),tensor(),case((0,0),(1000,-100),'center')))
        for axis,P,I in [('normal',1000,500000),('parallel',-100,120000)]:
            self.close(r['extrema']['displacement'][axis]['maximum_absolute']['value'],P*4000**3/(48*200000*I))
        self.assertTrue(all(r['exact_checks'].values()))

    def test_offcenter_point_value_and_extremum(self):
        L,a,E,I,P=4000.,700.,200000.,500000.,1000.
        b=build_beam(model(L,E),tensor(I),case((0,0),(P,0),'finite_interior',a))
        r=solve_response(b);w=r['extrema']['displacement']['normal']['maximum_absolute']
        self.close(evaluate(b,a)['displacement_mm'][0],P*a*a*(L-a)**2/(3*E*I*L))
        self.close(w['state']['x_mm'],L-math.sqrt((L*L-a*a)/3))
        self.assertGreater(w['state']['x_mm'],a)

    def test_coupled_uniform_formula_and_stress_sign(self):
        t=tensor(xy=25000.);b=build_beam(model(),t,case())
        r=evaluate(b,2000.);Ix,Iy,Ixy=500000.,120000.,25000.;det=Ix*Iy-Ixy*Ixy
        Mx,My=r['moments_Nmm'];cx=(-My*Ix-Mx*Ixy)/det;cy=(Mx*Iy+My*Ixy)/det
        self.close(200000*r['curvatures_mm_inv'][1],cx)
        self.close(-200000*r['curvatures_mm_inv'][0],cy)
        self.assertGreater(r['displacement_mm'][0],5*.5*4000**4/(384*200000*Ix))

    def test_superposition_and_load_reversal(self):
        b1=build_beam(model(),tensor(xy=-23000),case((.5,.04),(0,0)))
        b2=build_beam(model(),tensor(xy=-23000),case((0,0),(-750,300),'finite_interior',1575))
        b3=build_beam(model(),tensor(xy=-23000),case((.5,.04),(-750,300),'finite_interior',1575))
        bn=build_beam(model(),tensor(xy=-23000),case((-.5,-.04),(750,-300),'finite_interior',1575))
        for x in [0,400,1575,2000,3210,4000]:
            states=[evaluate(b,x) for b in (b1,b2,b3,bn)]
            for key in ('displacement_mm','slopes','moments_Nmm','shears_N'):
                for i in range(2):
                    self.close(states[0][key][i]+states[1][key][i],states[2][key][i])
                    self.close(-states[2][key][i],states[3][key][i])

    def test_rotated_tensor(self):
        angle=.57;c,s=math.cos(angle),math.sin(angle);R=((c,-s),(s,c))
        def rotate(v):return [sum(R[i][j]*v[j] for j in range(2)) for i in range(2)]
        I,J=7.,3.;q,P=[2.,-1.],[-4.,3.]
        tr=tensor(c*c*I+s*s*J,s*s*I+c*c*J,-s*c*(I-J))
        base=build_beam(model(4.,210.),tensor(I,J),case(q,P,'finite_interior',.83))
        turned=build_beam(model(4.,210.),tr,case(rotate(q),rotate(P),'finite_interior',.83))
        for x in (0,.2,.83,1.25,2.,3.9,4.):
            a,b=evaluate(base,x),evaluate(turned,x)
            for key in ('displacement_mm','slopes','curvatures_mm_inv','moments_Nmm','shears_N'):
                target=rotate(a[key])
                for actual,expected in zip(b[key],target):self.close(actual,expected,atol=1e-13)

    def test_nonproportional_three_distinct_extrema(self):
        b=build_beam(model(4.,210.),tensor(7.,3.,1.1),case((2.,-1.),(-4.,3.),'finite_interior',.83))
        r=solve_response(b)['extrema']['displacement']
        n,p,z=(r[k]['maximum_absolute'] for k in ('normal','parallel','resultant_squared'))
        self.close(n['state']['x_mm'],2.157840066698477,rtol=1e-8)
        self.close(n['value'],.0023114045195964097,rtol=1e-8)
        self.close(p['state']['x_mm'],2.555646130146984,rtol=1e-8)
        self.close(p['value'],-.0008593203192972677,rtol=1e-8)
        self.close(z['state']['x_mm'],2.224039102706314,rtol=1e-8)
        self.close(math.sqrt(z['value']),.002445907102562747,rtol=1e-8)
        self.assertGreater(abs(n['state']['x_mm']-p['state']['x_mm']),.1)

    def test_support_limit_preserves_transfer_not_finite_point(self):
        q,P=(.5,.04),(1000.,-250.)
        limit=build_beam(model(),tensor(xy=25000),case(q,P,'support_limit'))
        baseline=build_beam(model(),tensor(xy=25000),case(q))
        r=solve_response(limit)
        for x in (0,10,1000,2000,3999,4000):
            self.assertEqual(evaluate(limit,x)['displacement_mm'],evaluate(baseline,x)['displacement_mm'])
        boundary=r['support_transfer_limit']
        self.assertFalse(boundary['finite_point_on_support'])
        for i in range(2):self.close(boundary['V_before_N'][i]-boundary['V_after_N'][i],P[i])
        small=build_beam(model(),tensor(xy=25000),case(q,P,'finite_interior',1e-8))
        for a,b in zip(evaluate(small,2000)['displacement_mm'],evaluate(limit,2000)['displacement_mm']):self.close(a,b,rtol=1e-9)

    def test_extremely_close_finite_point_is_not_collapsed(self):
        for a in (1e-100,math.nextafter(4000.,0.)):
            b=build_beam(model(),tensor(xy=25000),case((0,0),(1000,250),'finite_interior',a))
            r=solve_response(b)
            self.assertEqual(r['point_position'],'finite_interior');self.assertNotIn('support_transfer_limit',r)
            self.assertTrue(all(r['exact_checks'].values()))

    def test_zero_and_zero_point_location_declarations(self):
        for c in (case((0,0)),case((0,0),(0,0),'center'),case((0,0),(0,0),'finite_interior',500.)):
            r=solve_response(build_beam(model(),tensor(),c))
            self.assertEqual(r['strain_energy_Nmm'],0.)
            self.assertEqual(r['extrema']['displacement']['normal']['maximum_absolute']['value'],0.)
            self.assertFalse(r['whole_member_approved'])

    def test_fraction_and_decimal_tensor_is_not_rounded_before_algebra(self):
        t=tensor(Decimal('500000.0000000000000000001'),F(120000),Decimal('0.00000000000000000001'))
        b=build_beam(model(),t,case())
        self.assertEqual(b.Ix,F(t['Ix_mm4']));self.assertNotEqual(b.Ix,F(float(t['Ix_mm4'])))
        r=solve_response(b);self.assertTrue(all(r['exact_checks'].values()))

    def test_underflow_is_explicit_and_json_finite(self):
        b=build_beam(model(L=1.,E=1e100),tensor(1e100,1e100),case((1e-300,0)))
        r=solve_response(b)
        self.assertEqual(r['status'],'numeric_output_resolution_limited')
        self.assertTrue(r['numeric_output_resolution_limited'])
        self.assertFalse(r['gross_stiffness_applicability_established'])
        json.dumps(r,allow_nan=False)

    def test_output_overflow_refused(self):
        b=build_beam(model(L=1e200,E=1.),tensor(1.,1.),case((1.,0)))
        with self.assertRaises(ArithmeticError):solve_response(b)

    def test_input_is_not_mutated(self):
        m,t,c=model(),tensor(),case((.5,.04),(-500,100),'finite_interior',700)
        before=copy.deepcopy((m,t,c));solve_response(build_beam(m,t,c))
        self.assertEqual((m,t,c),before)

    def test_exact_sturm_preserves_seven_rational_roots_and_repetitions(self):
        from tercas.biaxial_gross.tensor_beam import multiply
        coefficients=(F(1),)
        expected=[F(1,10),F(1,4),F(1,2),F(4,5)]
        for root in [F(0),*expected,F(1,4),F(1)]:coefficients=multiply(coefficients,(-root,F(1)))
        actual=real_roots_open_unit_interval(coefficients)
        self.assertEqual(actual,[float(x) for x in expected])

    def test_clustered_degree_seven_roots_and_tiny_scale(self):
        from tercas.biaxial_gross.tensor_beam import multiply
        expected=[F(1,10),F(1,10)+F(1,10**12),F(1,4),F(1,2),F(3,4),F(9,10),F(9,10)+F(1,10**12)]
        p=(F(1,10**300),)
        for root in expected:p=multiply(p,(-root,F(1)))
        actual=real_roots_open_unit_interval(p)
        self.assertEqual(len(actual),len(expected))
        for got,want in zip(actual,expected):self.assertLessEqual(abs(got-float(want)),math.ulp(float(want)))

    def test_near_boundary_roots_and_float_indistinguishable_roots(self):
        from tercas.biaxial_gross.tensor_beam import multiply
        expected=[F(1,10**300),F(1,2),F(1)-F(1,10**16)]
        p=(F(1),)
        for root in expected:p=multiply(p,(-root,F(1)))
        actual=real_roots_open_unit_interval(p)
        self.assertEqual(len(actual),3)
        for got,want in zip(actual,expected):self.assertLessEqual(abs(got-float(want)),math.ulp(float(want)))
        p=(F(1),)
        for root in [F(1,2)-F(1,10**40),F(1,2)+F(1,10**40)]:p=multiply(p,(-root,F(1)))
        indistinguishable=real_roots_open_unit_interval(p)
        self.assertTrue(indistinguishable)
        self.assertTrue(all(abs(x-.5)<=math.ulp(.5) for x in indistinguishable))

    def test_all_extrema_cover_dense_samples(self):
        rng=random.Random(7)
        for _ in range(12):
            c=case([rng.uniform(-2,2) for _ in range(2)],[rng.uniform(-5,5) for _ in range(2)],'finite_interior',rng.uniform(.2,3.8))
            b=build_beam(model(4.,210.),tensor(7.,3.,1.1),c);r=solve_response(b)
            for k in range(51):
                state=evaluate(b,4*k/50)
                for kind,key in [('displacement','displacement_mm'),('slope','slopes')]:
                    for i,axis in enumerate(('normal','parallel')):
                        e=r['extrema'][kind][axis]
                        self.assertLessEqual(e['minimum']['value']-1e-13,state[key][i])
                        self.assertLessEqual(state[key][i],e['maximum']['value']+1e-13)
                    magnitude=sum(v*v for v in state[key])
                    self.assertLessEqual(magnitude,r['extrema'][kind]['resultant_squared']['maximum']['value']+1e-13)

    def test_invalid_inputs_fail_closed(self):
        bad=[]
        for key,value in [('L_mm',0),('L_mm',True),('L_mm','4000'),('E_MPa',float('nan')),('supports','cantilever'),('prismatic',1)]:
            m=model();m[key]=value;bad.append((m,tensor(),case()))
        for t in [tensor(0,1),tensor(1,1,1),tensor(1,1,2),tensor(float('inf'),1)]:bad.append((model(),t,case()))
        for c in [case((0,0),(1,0)),case((0,0),(1,0),'finite_interior',0),case((0,0),(1,0),'finite_interior',4000),case((0,0),(1,0),'support_limit',0),case((True,0)),case(('1',0)),case((float('nan'),0)),case((0,0),(1,0),'unknown')]:bad.append((model(),tensor(),c))
        for args in bad:
            with self.subTest(args=args),self.assertRaises(ValueError):build_beam(*args)

if __name__=='__main__':unittest.main()
