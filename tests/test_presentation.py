import copy,json
from io import BytesIO
from pathlib import Path
from docx import Document
from tercas.presentation import fmt,display,display_records
from tercas.application import example,calculate
from tercas.report import word
from tercas.drawing import svg

def test_two_decimals_and_nonzero():
 assert fmt(1234.56789)=='1234,57'
 assert fmt(0)=='0,00'
 assert fmt(-0.0)=='0,00'
 assert fmt(.000001)=='<0,01'
 assert fmt(-.000001)=='−<0,01'
 assert fmt(1.00001,limit=1)=='1,00 (>1,00)'
 assert fmt(.99999,limit=1)=='1,00 (<1,00)'
 assert fmt(1.,limit=1)=='1,00'

def test_presentation_does_not_mutate_raw():
 raw=[{'Índice':1.00001,'Situação':'Não atende','Demanda / valor':'1.234567 kN·m','Referência':'§9.8.2.1','Observação':'Seção x=123.456789 mm.','ID':'ELU01'}]
 frozen=copy.deepcopy(raw);shown=display_records(raw)
 assert raw==frozen
 assert shown[0]['Índice']=='1,00 (>1,00)'
 assert shown[0]['Demanda / valor']=='1,23 kN·m'
 assert shown[0]['Observação']=='Seção x=123,46 mm.'
 assert shown[0]['Referência']=='§9.8.2.1'
 assert shown[0]['ID']=='ELU01'

def test_word_svg_and_json_precision():
 d=example();d['q_uls']=.123456789
 r=calculate(d);before=json.dumps(r,sort_keys=True)
 doc=Document(BytesIO(word(r)));text='\n'.join(p.text for p in doc.paragraphs)
 assert 'duas casas decimais' in text
 assert '0,12' in text
 assert 'q = 0,12' in svg(d)
 assert json.dumps(r,sort_keys=True)==before
 assert r['input_data']['q_uls']==.123456789

def test_number_input_keeps_full_value_after_unrelated_rerun():
 from streamlit.testing.v1 import AppTest
 a=AppTest.from_file(str(Path(__file__).parents[1]/'app.py')).run(timeout=30)
 field=next(x for x in a.number_input if x.label=='Vão entre apoios [mm]')
 field.set_value(3000.123456789).run(timeout=30)
 assert not a.exception
 assert a.session_state.last_input['L_mm']==3000.123456789
 assert next(x for x in a.number_input if x.label=='Vão entre apoios [mm]').proto.format=='%.2f'
 a.run(timeout=30)
 assert a.session_state.last_input['L_mm']==3000.123456789


def test_entry_docstring_remains_module_docstring():
 import ast
 source=(Path(__file__).parents[1]/"app.py").read_text()
 assert ast.get_docstring(ast.parse(source)).startswith("Streamlit entry point")
