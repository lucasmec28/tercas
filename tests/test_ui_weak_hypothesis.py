from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_provisional_label_visible_in_results():
 a=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
 next(x for x in a.number_input if x.label=='q paralelo ELU [kN/m]').set_value(.1)
 a.button[1].click().run(timeout=30)
 assert not a.exception
 assert not a.error
 seen=False
 for table in a.dataframe:
  df=table.value
  if 'Verificação' in df.columns:
   selected=df[df['Verificação']=='Flexão biaxial']
   if len(selected):
    assert 'hipótese provisória' in selected.iloc[0]['Situação'];seen=True
 assert seen
