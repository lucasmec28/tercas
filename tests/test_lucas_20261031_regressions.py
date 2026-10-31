import copy,json,math,unittest,warnings
from scipy.integrate import IntegrationWarning
from tercas.core.protocolo_ief import model,peak,deflection,integration_points
from tercas.drawing_cases import drawing_cases
from tercas.application import example

class IntegrationBreakpoints(unittest.TestCase):
    def test_symmetric_near_duplicate(self):
        args=model(3000,200000,606600,25110000,q=1.7297323091652603)
        with warnings.catch_warnings(record=True) as ws:
            warnings.simplefilter('always',IntegrationWarning)
            x,d=peak(args)
        self.assertFalse([w for w in ws if issubclass(w.category,IntegrationWarning)])
        self.assertAlmostEqual(d,5*args[4]*3000**4/(384*200000*606600),places=10)
        self.assertAlmostEqual(x,1500,places=8)
    def test_points_coalesce_only_roundoff(self):
        self.assertEqual(len(integration_points(3000,1500,math.nextafter(1500,0))),3)
        self.assertEqual(len(integration_points(3000,1500,1500.000001)),4)
    def test_asymmetric_point_formula(self):
        L=3000;E=200000;I=606600;P=1000;a=970
        args=model(L,E,I,1e15,P=P,a=a)
        for z in [a,math.nextafter(a,0),math.nextafter(a,math.inf),1500]:
            with warnings.catch_warnings(record=True) as ws:
                warnings.simplefilter('always',IntegrationWarning);d=deflection(args,z)
            self.assertFalse([w for w in ws if issubclass(w.category,IntegrationWarning)])
            b=L-a
            expected=P*b*z*(L*L-b*b-z*z)/(6*L*E*I) if z<=a else P*a*(L-z)*(L*L-a*a-(L-z)**2)/(6*L*E*I)
            self.assertAlmostEqual(d,expected,places=10)

class DrawingCases(unittest.TestCase):
    def test_area_preview_exposes_point_without_summing_maxima(self):
        d=example();d['load_mode']='area';d['area_inputs']['wind_down_kgf_m2']=50
        original=copy.deepcopy(d);previews=drawing_cases(d)
        self.assertGreater(previews[0][1]['P_uls'],0)
        self.assertTrue(any(c['P_uls']==0 for _,c in previews))
        self.assertEqual(d,original)
        from tercas.batch import area_bundle
        actual={(c['q_N_mm'],c.get('P_N',0)) for c in area_bundle(d)['combinations']}
        self.assertTrue(all((c['q_uls'],c['P_uls']) in actual for _,c in previews))
    def test_no_point_preview_for_els_frequent_only(self):
        d=example();d.update(load_mode='area',selected_types=['ELS frequente'])
        self.assertTrue(all(c['P_uls']==0 for _,c in drawing_cases(d)))
    def test_direct_unchanged(self):
        d=example();self.assertEqual(drawing_cases(d),[('Entradas diretas ELU',d)])
