from pathlib import Path
from io import BytesIO
from streamlit.testing.v1 import AppTest
from docx import Document
from tercas.application import defaults,calculate,rows
from tercas.drawing import svg
from tercas.report import word
APP=str(Path(__file__).resolve().parents[1]/'app.py')
def test_profile_change_preserves_project_inputs_and_lengths():
 a=AppTest.from_file(APP).run(timeout=30)
 values={'L_0':4200.,'upper_0':2100.,'lower_0':1800.,'torsion_0':4000.,'weak_lx_0':3900.,'q_uls_0':.876,'q_sls_0':.543,'inclination_value_0':12.5}
 for key,v in values.items():
  next(w for w in a.number_input if w.key==key).set_value(v).run(timeout=30)
 assert not a.exception
 before=a.session_state.last_input
 a.selectbox[0].set_value(8).run(timeout=30)
 assert not a.exception
 after=a.session_state.last_input
 for key in ['L_mm','q_uls','q_sls','segments','steel_name','inclination','area_inputs','selected_types']:
  assert after[key]==before[key],key
 assert after['weak_catalog']['Lx_mm']==3900.
 assert after['catalog_index']==8
 assert after['properties']['h']!=before['properties']['h'] or after['properties']['t']!=before['properties']['t'] or after['properties']['bf']!=before['properties']['bf']

def test_lengths_before_property_and_load_inputs():
 a=AppTest.from_file(APP).run(timeout=30)
 labels=[n.label for n in a.number_input]
 ix=labels.index('Área [cm²]')
 for label in ['Ly — mesa superior (menor inércia) [mm]','Ly — mesa inferior (menor inércia) [mm]','Comprimento efetivo torsional Lz [mm]','Lx efetivo — instabilidade da flexão fraca [mm]']:
  assert labels.index(label)<ix

def test_axes_and_els_omission_with_explicit_mc_scope():
 d=defaults();d['q_parallel_sls']=.12
 result=calculate(d)
 assert not any(row['Verificação']=='Flecha paralela à cobertura' for row in rows(result))
 text='\n'.join(p.text for p in Document(BytesIO(word(result))).paragraphs)
 assert 'Flecha paralela à cobertura fora do escopo' in text
 drawing=svg(d)
 assert 'section-local-axes' in drawing and '>X</text>' in drawing and '>Y</text>' in drawing
