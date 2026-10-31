import copy
import csv
import importlib.util
import math
from pathlib import Path
import random
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("load_combinations",ROOT/"tercas/load_combinations.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

BASE=dict(spacing_m=1.5,permanent_kgf_m2=10.,live_kgf_m2=25.,
          wind_up_kgf_m2=80.,wind_down_kgf_m2=50.,mass_kg_m=3.04)

class TestLoads(unittest.TestCase):
    def test_table_counts(self):
        self.assertEqual(len(m.fixed_combinations()),48)
        for typ,n in zip(m.COMBINATION_TYPES,[32,8,6,2]):
            self.assertEqual(len(m.fixed_combinations([typ])),n)

    def test_tsv_exact(self):
        source=ROOT/"tests/fixtures/robot_combinacoes.tsv"
        cases={'1':'PP','2':'CP','3':'SC','4':'V_Cima','5':'V_Baixo'}
        expected=[]
        for r in csv.reader(source.read_text(encoding='utf-8-sig').splitlines(),delimiter='\t'):
            coeff={cases[r[i]]:float(r[i+1].replace(',','.')) for i in range(2,len(r),2) if r[i]}
            expected.append((r[0],r[1],coeff))
        self.assertEqual([(r['id'],r['limit_state'],r['coefficients']) for r in m.fixed_combinations()],expected)

    def test_wind_exclusion(self):
        for c in m.fixed_combinations():
            self.assertFalse({'V_Cima','V_Baixo'}<=set(c['coefficients']))

    def test_conversion(self):
        r=m.characteristic_area_cases(**BASE)
        self.assertAlmostEqual(r['PP'],3.04*9.80665/1000)
        self.assertAlmostEqual(r['CP'],.14709975)
        self.assertAlmostEqual(r['SC'],.367749375)
        self.assertAlmostEqual(r['V_Cima'],-1.176798)
        self.assertAlmostEqual(r['V_Baixo'],.73549875)

    def test_pp_not_scaled_by_spacing(self):
        a=m.characteristic_area_cases(**BASE)
        b=m.characteristic_area_cases(**dict(BASE,spacing_m=3.))
        self.assertEqual(a['PP'],b['PP'])
        self.assertAlmostEqual(a['CP']*2,b['CP'])

    def test_zero_wind_keeps_source_identity(self):
        r=m.combine_area_actions(L_mm=3000,**dict(BASE,wind_up_kgf_m2=0,wind_down_kgf_m2=0))
        self.assertEqual(len(r['combinations']),48)
        self.assertEqual(r['case_q_N_mm']['V_Cima'],0)

    def test_signed_superposition(self):
        r=m.combine_area_actions(L_mm=3000,**BASE)
        c=next(c for c in r['combinations'] if c['id']=='ELUN_00019')
        q=(3.04+10*1.5-1.4*80*1.5)*9.80665/1000
        self.assertLess(q,0)
        self.assertAlmostEqual(c['q_N_mm'],q)
        self.assertAlmostEqual(c['effects_at_midspan']['midspan_moment_Nmm'],q*3000**2/8)
        self.assertEqual(c['sign'],'ascendente')

    def test_no_selection(self):
        self.assertEqual(m.fixed_combinations([]),[])
        self.assertEqual(m.combine_area_actions(L_mm=3000,selected_types=[],**BASE)['combinations'],[])

    def test_selection_no_fake_other_family(self):
        r=m.combine_area_actions(L_mm=3000,selected_types=['ELS frequente'],**BASE)
        self.assertEqual(len(r['combinations']),6)
        self.assertTrue(all(c['limit_state']=='ELS' for c in r['combinations']))

    def test_unselected_families_not_reintroduced(self):
        ids={c['id'] for c in m.fixed_combinations(['ELU normal','ELS rara'])}
        self.assertEqual(len(ids),40)
        self.assertFalse(any(i.startswith(('ELSF','ELSQP')) for i in ids))

    def test_bad_types(self):
        for value in ['ELU normal',['unknown'],[True],['ELS rara','ELS rara']]:
            with self.assertRaises(ValueError):m.fixed_combinations(value)

    def test_invalid_inputs(self):
        for field in BASE:
            for bad in [None,True,float('nan'),float('inf'),-1]:
                with self.subTest(field=field,bad=bad):
                    with self.assertRaises(ValueError):m.characteristic_area_cases(**dict(BASE,**{field:bad}))
        for field in ('mass_kg_m','spacing_m'):
            with self.assertRaises(ValueError):m.characteristic_area_cases(**dict(BASE,**{field:0}))

    def test_no_input_mutation(self):
        b=copy.deepcopy(BASE)
        a=m.fixed_combinations();a[0]['coefficients']['PP']=99
        self.assertEqual(m.fixed_combinations()[0]['coefficients']['PP'],1.25)
        m.combine_area_actions(L_mm=3000,**b)
        self.assertEqual(b,BASE)

    def test_no_automatic_concentrated_action(self):
        r=m.combine_area_actions(L_mm=3000,**BASE)
        self.assertTrue(all(c['P_N']==0 for c in r['combinations']))

    def test_pure_permanent_combo(self):
        r=m.combine_area_actions(L_mm=3000,**BASE)
        c=next(c for c in r['combinations'] if c['id']=='ELUN_00032')
        self.assertAlmostEqual(c['q_N_mm'],(3.04+15)*9.80665/1000)

    def test_random_equilibrium_and_signed_moments(self):
        rng=random.Random(15)
        for _ in range(50):
            L=rng.uniform(100,10000)
            inp=dict(spacing_m=rng.uniform(.1,5),mass_kg_m=rng.uniform(.1,50),
                     **{k:rng.uniform(0,500) for k in BASE if k not in ('spacing_m','mass_kg_m')})
            result=m.combine_area_actions(L_mm=L,**inp)
            for c in result['combinations']:
                e=c['effects_at_midspan'];q=c['q_N_mm']
                self.assertAlmostEqual(e['left_reaction_N']+e['right_reaction_N'],q*L,places=7)
                self.assertAlmostEqual(e['midspan_moment_Nmm'],q*L**2/8,delta=1e-5)
                self.assertAlmostEqual(e['V_N'],0,places=7)

    def test_effect_at_coordinate(self):
        e=m.uniform_effects(.2,3000,750)
        self.assertEqual(e['V_N'],150)
        self.assertEqual(e['M_Nmm'],168750)
        for x in (-1,3001,None):
            if x is None:continue
            with self.assertRaises(ValueError):m.uniform_effects(.2,3000,x)

if __name__=='__main__':unittest.main(verbosity=2)
