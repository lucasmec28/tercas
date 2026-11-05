"""New roof H4 remains conditional on screen and in saved exports."""
import copy,io,json
from pathlib import Path
from types import SimpleNamespace
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from docx import Document
from tercas import aisi_torsion_component as a,aisi_roof_height as h
from tercas.aisi_torsion_ui import report
from test_aisi_roof_height import current,data,reseal
APP=str(Path(__file__).resolve().parents[1]/'app.py')


def test_actual_app_roof_H4_and_read_only_rerender(monkeypatch):
    d=data(3.35);payload=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    downloads={};original=st.download_button
    def capture(label,data,*args,**kw):
        if label in ('Baixar estudo e resultados (JSON)','Baixar memória parcial (Word)'):downloads[label]=data
        return original(label,data,*args,**kw)
    monkeypatch.setattr(st,'download_button',capture)
    app=AppTest.from_file(APP).run(timeout=30)
    next(x for x in app.button if x.label=='Aplicar entradas do arquivo').click().run(timeout=30)
    before_labels=[w.label for w in app.number_input]
    next(x for x in app.button if x.label=='Calcular verificações disponíveis').click().run(timeout=60)
    assert not app.exception
    result=copy.deepcopy(app.session_state.result);ev=a.preserved(result)
    assert ev['H4_computed_cases']==40 and any(r['H4']['ratio']<1 for r in ev['records'])
    assert app.session_state.last_input==d and [w.label for w in app.number_input]==before_labels
    assert not result['whole_member_approved'] and 'torsion_warping' in result['global_verification']['pending_ids']
    table=next(x.value for x in app.dataframe if 'Ma,piso AISI [kN·m]' in x.value.columns)
    assert len(table)==40 and set(table['Primeira ordem física'])=={'Adequação não estabelecida'}
    assert all('algébrica' in x for x in table.loc[table['H4 Mx/Max + My/May + B/Ba']<=1,'Parcela longitudinal'])
    assert any('adequação física da primeira' in x.value for x in app.caption)
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==result
    doc=Document(io.BytesIO(downloads['Baixar memória parcial (Word)']));text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Ma,piso AISI' in text and 'inconclusivo' in text and 'adequação física da primeira' in text
    def fail(*args,**kwargs):raise AssertionError('Read-only UI must not solve')
    monkeypatch.setattr(h,'refined',fail);monkeypatch.setattr(a,'_aisi_demand',fail)
    app.run(timeout=30)
    assert not app.exception and app.session_state.result==result


SCRIPT='''
import streamlit as st
from tercas.aisi_torsion_ui import show
if 'saved' in st.session_state:show(st,st.session_state.saved)
'''


@pytest.mark.parametrize('mutation',['record','schema','ratio'])
def test_bad_saved_roof_UI_and_Word_do_not_crash_or_emit_numbers(current,mutation):
    bad=copy.deepcopy(current)
    if mutation=='record':bad[a.FIELD]['records'][0]='bad'
    elif mutation=='schema':bad[a.FIELD]['schema']=a.SCHEMA
    else:bad[a.FIELD]['records'][0]['H4']['ratio']=0.
    reseal(bad)
    app=AppTest.from_string(SCRIPT).run();app.session_state.saved=bad;app.run()
    assert not app.exception and app.error and not app.dataframe
    doc=Document();report(doc,bad);text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Nenhum índice AISI' in text and 'Ma,piso AISI' not in text
