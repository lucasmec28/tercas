import unittest,random,math,copy
from tercas.weak_axis import interaction_envelope,capacities,validate
from tercas.application import example,calculate,rows
from tercas.batch import calculate_batch
from tercas.core.travamentos_nbr import moment

def props():
 return dict(W_mm3=10000.,Wc_mm3=20000.,Ml_Nmm=4e6,Mdist_Nmm=5e6,Nex_N=1e6,Nez_N=1e6,r0_mm=20.,j_mm=-10.,Cm=1.,Cs=1,provenance='SYNTHETIC same axis/section sign; regression only')
def configured():
 d=example();d['q_parallel_uls']=.1;d['weak_axis']={s:props() for s in ('positive','negative')};return d

class WeakTests(unittest.TestCase):
 def test_word_provenance(self):
  from tercas.report import word
  from docx import Document
  from io import BytesIO
  doc=Document(BytesIO(word(calculate(configured()))));text=' '.join(p.text for p in doc.paragraphs)
  self.assertIn('Nex_N',text);self.assertIn('SYNTHETIC same axis/section sign',text);self.assertIn('Interação concomitante',text);self.assertIn('rota restrita de flexão fraca/Anexo E',text);self.assertNotIn('Sem dimensionamento de torção primária, flexão biaxial',text)
 def test_batch_word_scope(self):
  from tercas.report import batch_word
  from docx import Document
  from io import BytesIO
  d=configured();d['load_mode']='area';d['selected_types']=['ELU normal'];d['inclination']={'value':10,'unit':'degrees'}
  text=' '.join(p.text for p in Document(BytesIO(batch_word(calculate_batch(d)))).paragraphs)
  self.assertIn('os resultados cobrem as duas posições prescritas',text);self.assertNotIn('Sem dimensionamento de torção primária, flexão biaxial',text)
 def test_cm_reduction_rejected_direct(self):
  d=configured();d['weak_axis']['positive']['Cm']=.5
  with self.assertRaisesRegex(ValueError,'Cm = 1'):calculate(d)
 def test_cm_reduction_rejected_batch(self):
  d=configured();d['load_mode']='area';d['selected_types']=['ELU normal'];d['inclination']={'value':10,'unit':'degrees'};d['weak_axis']['positive']['Cm']=.5
  with self.assertRaisesRegex(ValueError,'Cm = 1'):calculate_batch(d)
 def test_cm_one_all_combinations(self):
  d=configured();d['load_mode']='area';d['selected_types']=['ELU normal'];d['inclination']={'value':10,'unit':'degrees'}
  for case in calculate_batch(d)['cases']:
   ev=case['evidence']['inclination']
   if ev['parallel_demand']:
    self.assertTrue(ev.get('weak_axis_capacities'))
    for cap in ev['weak_axis_capacities'].values():self.assertEqual(cap['annex_e']['Cm_adopted'],1)
 def test_provisional_label_even_when_index_passes(self):
  d=configured();d.update(q_uls=.01,P_uls=0,q_parallel_uls=.01);d['weak_axis']['positive']['provisional_hypothesis']=True
  row=next(x for x in rows(calculate(d)) if x['Verificação']=='Flexão biaxial');self.assertLess(row['Índice'],1);self.assertIn('hipótese provisória',row['Situação'])
 def test_provisional_label_mobile_and_summary(self):
  d=configured();d['weak_axis']['positive']['provisional_hypothesis']=True;d['load_mode']='area';d['selected_types']=['ELU normal'];d['inclination']={'value':10,'unit':'degrees'}
  z=calculate_batch(d)
  for c in z['cases']:
   for row in c['rows']:
    if row['Verificação']=='Flexão biaxial':self.assertIn('hipótese provisória',row['Situação'])
  row=next(x for x in z['summary'] if x['Verificação']=='Flexão biaxial');self.assertIn('hipótese provisória',row['Situação'])
 def test_provisional_label_word_table(self):
  from tercas.report import word,batch_word
  from docx import Document
  from io import BytesIO
  d=configured();d['weak_axis']['positive']['provisional_hypothesis']=True
  for blob in [word(calculate(d))]:
   doc=Document(BytesIO(blob));rows_text=[' '.join(c.text for c in row.cells) for table in doc.tables for row in table.rows];self.assertTrue(any('Flexão biaxial' in t and 'hipótese provisória' in t for t in rows_text))
  d['load_mode']='area';d['selected_types']=['ELU normal'];d['inclination']={'value':10,'unit':'degrees'}
  doc=Document(BytesIO(batch_word(calculate_batch(d))));rows_text=[' '.join(c.text for c in row.cells) for table in doc.tables for row in table.rows];self.assertTrue(any('Flexão biaxial' in t and 'hipótese provisória' in t for t in rows_text))
 def test_two_sides_separate(self):
  d=configured();d['weak_axis']['negative']['Cs']=-1
  c=capacities(d,'U');self.assertNotEqual(c['positive']['annex_e']['Me_Nmm'],c['negative']['annex_e']['Me_Nmm'])
 def test_no_origin(self):
  d=configured();d['weak_axis']['positive']['provenance']='';self.assertEqual(capacities(d,'U')['positive']['status'],'not_evaluated')
 def test_no_bilateral_copy(self):
  d=configured();del d['weak_axis']['negative'];d['q_parallel_uls']=-.1
  z=calculate(d)['inclination_evidence']['ELU']['biaxial'];self.assertIn('negative',z['missing'])
 def test_complete_fixed(self):
  d=configured();r=calculate(d);z=r['inclination_evidence']['ELU']['biaxial'];self.assertEqual(z['status'],'computed_fixed_position');self.assertFalse(r['whole_member_approved']);self.assertTrue(any(x['Verificação']=='Flexão biaxial' and x['Índice'] is not None for x in rows(r)))
 def test_invalid_cs(self):
  d=configured();d['weak_axis']['positive']['Cs']=True
  with self.assertRaises(ValueError):validate(d)
 def test_ui_empty_valid(self):
  d=configured();d['weak_axis']={'positive':dict(Cs=None,Cm=None,provenance='')};validate(d)
 def test_bad_unknown(self):
  d=configured();d['weak_axis']['positive']['fake']=1
  with self.assertRaises(ValueError):validate(d)
 def test_signed_critical(self):
  d=configured();d['weak_axis']['positive']['Mdist_Nmm']=-1
  with self.assertRaises(ValueError):validate(d)
 def test_no_weff_swap(self):
  d=configured();d['weak_axis']['positive']['W_mm3']=30000
  with self.assertRaises(ValueError):capacities(d,'U')
 def test_no_u_exemption_for_ue(self):
  d=configured();d['weak_axis']['positive']['plain_u_no_distortion']=True
  with self.assertRaises(ValueError):capacities(d,'Ue')
 def test_no_strong_data(self):
  d=configured();d['route_domain']=False
  z=calculate(d)['inclination_evidence']['ELU']['biaxial'];self.assertIn('strong',z['missing'])
 def test_mobile_stays_partial(self):
  d=configured();d['load_mode']='area';d['selected_types']=['ELU normal'];d['inclination']={'value':10,'unit':'degrees'}
  r=calculate_batch(d)
  for c in r['cases']:
   if c['combination'].get('P_N'):
    row=next(x for x in c['rows'] if x['Verificação']=='Flexão biaxial');self.assertIn(c['combination']['point_position'],('center','support_limit'));self.assertIn('não certificam',c['scope_notes'][0]);self.assertFalse(r['whole_member_approved'])
 def test_zero_axis_missing_capacity_no_block(self):
  z=interaction_envelope(3000,0,0,.1,0,1500,None,{'positive':{'MRd_Nmm':1e6}})
  self.assertEqual(z['status'],'computed_fixed_position')
 def test_mixed_sign_interior_dense_reference(self):
  rng=random.Random(817)
  for i in range(100):
   L=3000;a=rng.uniform(50,2950);qx,qy=[rng.uniform(-2,2) for _ in range(2)];px,py=[rng.uniform(-5000,5000) for _ in range(2)];rx=3e6;rp=1.2e6;rn=.7e6
   z=interaction_envelope(L,qx,px,qy,py,a,rx,{'positive':{'MRd_Nmm':rp},'negative':{'MRd_Nmm':rn}})
   def idx(x):
    mx=moment(x,L,qx,px,a);my=moment(x,L,qy,py,a);return abs(mx)/rx+abs(my)/(rp if my>=0 else rn)
   grid=max(idx(L*j/10000) for j in range(10001));exact=z['governing']['index']
   with self.subTest(i=i):self.assertGreaterEqual(exact+1e-10,grid);self.assertLessEqual(exact-grid,1e-3)
if __name__=='__main__':unittest.main()
