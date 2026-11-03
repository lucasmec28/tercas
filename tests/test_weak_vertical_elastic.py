import math
import unittest
from tercas.weak_vertical_elastic import study_weak_vertical, _green, _solve

class BeamTests(unittest.TestCase):
    L=4000.; E=200000.; I=101200.
    def run_case(self, **kw):
        return study_weak_vertical(L=self.L,E=self.E,Iy=self.I,**kw)
    def close(self,a,b,rel=1e-9):
        self.assertLessEqual(abs(a-b),rel*max(1.,abs(b)))
    def test_no_spring_uniform(self):
        q=.1; L=self.L; EI=self.E*self.I
        r=self.run_case(q=q)
        self.close(r['deflection_max_down']['value_mm'],5*q*L**4/(384*EI))
        self.close(r['deflection_max_down']['x_mm'],L/2)
        self.close(r['My_max']['value_Nmm'],q*L**2/8)
    def test_no_spring_mid_point(self):
        P=100.; L=self.L; EI=self.E*self.I
        r=self.run_case(P=P,a=L/2)
        self.close(r['deflection_max_down']['value_mm'],P*L**3/(48*EI))
        self.close(r['My_max']['value_Nmm'],P*L/4)
    def test_one_finite_spring(self):
        q=.1; P=50.; L=self.L; EI=self.E*self.I; k=17.
        r=self.run_case(q=q,P=P,a=L/2,springs=[dict(x=L/2,k=k,origin='test assumption')])
        f=L**3/(48*EI)
        d=5*q*L**4/(384*EI)+P*f
        R=d/(f+1/k)
        self.close(r['springs'][0]['reaction_up_N'],R)
        self.close(r['springs'][0]['displacement_down_mm'],R/k)
        for v in r['residuals'].values(): self.assertLess(abs(v),1e-7)
    def test_rigid_limit_only_comparator(self):
        q=.1; L=self.L
        r=self.run_case(q=q,springs=[dict(x=L/2,k=1e12,origin='test only finite asymptote')])
        self.close(r['springs'][0]['reaction_up_N'],5*q*L/8)
        self.close(r['My_min']['value_Nmm'],-q*L**2/32)
        self.close(r['My_max']['value_Nmm'],9*q*L**2/512)
        self.assertTrue(any('Negative My' in s for s in r['warnings']))
        # Independent rigid-center piecewise quartic: left root t=(1+sqrt(33))/32.
        t=(1+math.sqrt(33))/32
        self.close(r['deflection_max_down']['value_mm'],q*L**4/(self.E*self.I)*(t/384-t**3/32+t**4/24))
    def test_zero_and_duplicate_springs(self):
        r=self.run_case(springs=[dict(x=1000,k=4,origin='test')]*2)
        self.assertEqual(r['deflection_max_abs']['value_mm'],0.)
        self.assertEqual(sum(s['reaction_up_N'] for s in r['springs']),0.)
        a=self.run_case(q=.1,springs=[dict(x=1000,k=8,origin='test')])
        b=self.run_case(q=.1,springs=[dict(x=1000,k=4,origin='test')]*2)
        self.close(a['deflection_max_down']['value_mm'],b['deflection_max_down']['value_mm'])
    def test_green_reciprocal(self):
        self.close(_green(700,2600,self.L,self.E*self.I),_green(2600,700,self.L,self.E*self.I))
    def test_independent_beam_element_assembly(self):
        # Independent Hermite beam FE stiffness + consistent UDL. It is exact
        # at nodes for this piecewise constant EI/UDL, with point/spring nodes.
        xs=[0.,900.,1700.,2800.,self.L]; n=2*len(xs); EI=self.E*self.I
        K=[[0.]*n for _ in range(n)]; f=[0.]*n; q=.1; P=70.
        for e,(xl,xr) in enumerate(zip(xs,xs[1:])):
            h=xr-xl
            ke=[[12,6*h,-12,6*h],[6*h,4*h*h,-6*h,2*h*h],
                [-12,-6*h,12,-6*h],[6*h,2*h*h,-6*h,4*h*h]]
            fe=[q*h/2,q*h*h/12,q*h/2,-q*h*h/12]
            for i in range(4):
                f[2*e+i]+=fe[i]
                for j in range(4): K[2*e+i][2*e+j]+=EI/h**3*ke[i][j]
        f[4]+=P
        for j,k in [(1,11.),(3,23.)]: K[2*j][2*j]+=k
        ids=[i for i in range(n) if i not in (0,n-2)]
        u=[0.]*n
        for i,v in zip(ids,_solve([[K[i][j] for j in ids] for i in ids],[f[i] for i in ids])): u[i]=v
        r=self.run_case(q=q,P=P,a=1700,springs=[dict(x=900,k=11,origin='test'),dict(x=2800,k=23,origin='test')])
        for s,j in zip(r['springs'],[1,3]):
            self.assertGreater(u[2*j],0)
            self.close(s['displacement_down_mm'],u[2*j])
            self.close(s['reaction_up_N'],s['k']*u[2*j])
        for v in r['residuals'].values(): self.assertLess(abs(v),1e-7)

    def test_invalid(self):
        for kw in [dict(q=-1),dict(P=1),dict(springs=[dict(x=2000,k=float('inf'),origin='test')]),dict(springs=[dict(x=2000,k=1,origin='')])]:
            with self.assertRaises(ValueError): self.run_case(**kw)
    def test_tension_only_slack_and_equilibrium(self):
        r=self.run_case(P=100,a=100,springs=[dict(x=400,k=1e6,origin='test'),dict(x=3000,k=100,origin='test')])
        self.assertFalse(r['springs'][1]['active'])
        self.assertLess(r['springs'][1]['displacement_down_mm'],0)
        self.assertEqual(r['springs'][1]['reaction_up_N'],0)
        for v in r['residuals'].values(): self.assertLess(abs(v),1e-7)

if __name__=='__main__': unittest.main()
