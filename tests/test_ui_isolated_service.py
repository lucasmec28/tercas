"""Actual direct workflow and saved conditional displacement table."""
import copy,io,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from docx import Document
from test_direct_torsion import inputs
from test_isolated_service_component import choice
from tercas import isolated_service_component as c
APP=str(Path(__file__).resolve().parents[1]/'app.py')


@pytest.mark.parametrize('reference',['legacy_own','catalog_19'])
def test_direct_combined_service_screen_exports_and_readonly_rerender(monkeypatch,reference):
    d=inputs(t=3.35,q=.01);d[c.CHOICE]=choice('declared_limit')
    if reference=='catalog_19':
        from tercas.ue_catalog_reference import activate
        d['catalog_index']=19;d['steel_name']='Personalizado';d=activate(d)
    payload=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    downloads={};original=st.download_button
    def capture(label,data,*args,**kwargs):
        if label in ('Baixar estudo e resultados (JSON)','Baixar memória parcial (Word)'):downloads[label]=data
        return original(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',capture)
    app=AppTest.from_file(APP).run(timeout=45)
    next(x for x in app.button if x.label=='Aplicar entradas do arquivo').click().run(timeout=45)
    assert not app.exception
    assert next(x for x in app.checkbox if x.label=='Calcular deslocamento combinado no ponto declarado').value
    next(x for x in app.button if x.label=='Calcular verificações disponíveis').click().run(timeout=90)
    assert not app.exception
    assert not any('Não foi possível calcular' in e.value for e in app.error),[e.value for e in app.error]
    result=copy.deepcopy(app.session_state.result);ev=c.saved(result)
    from tercas.isolated_service_panorama import validate_saved, BINDING
    assert BINDING in result['global_verification'];validate_saved(result)
    linear=next(r for r in result['global_verification']['checks'] if r['id']=='ELS:DIRECT_ELS:combined_point_linear')
    assert linear['status']=='meets' and linear['index'] is not None
    assert ev['computed_cases']==1 and ev['records'][0]['comparison']['index_upper'] is not None
    if reference=='legacy_own':assert app.session_state.last_input==d
    else:
        actual=app.session_state.last_input
        assert actual[c.CHOICE]==d[c.CHOICE]
        for key in ('E_MPa','G_MPa','fy_MPa','fu_MPa','h','bf','lip','t','ri_mm'):
            assert actual['properties'][key]==d['properties'][key]
        for key in ('L_mm','q_uls','q_sls','P_uls','P_sls','x_uls','x_sls'):
            assert actual[key]==d[key]
        assert result['input_data']==actual
    table=next(x.value for x in app.dataframe if 'Índice superior no campo linear' in x.value.columns)
    assert len(table)==1 and table.iloc[0]['Caso']=='DIRECT_ELS'
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==result
    doc=Document(io.BytesIO(downloads['Baixar memória parcial (Word)']))
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'ELS combinado no ponto declarado' in text and 'DIRECT_ELS' in text
    assert 'nenhum novo deslocamento foi calculado' not in text
    with patch('tercas.torsion_vlasov.vlasov.solve_member',side_effect=AssertionError('no solver')), \
         patch('tercas.direct_torsion.solve_member',side_effect=AssertionError('no direct solver')), \
         patch('tercas.isolated_service_mechanics.calculate',side_effect=AssertionError('no mechanics cache miss')):
        app.run(timeout=45)
    assert not app.exception and app.session_state.result==result
    assert not result['whole_member_approved']
    next(x for x in app.number_input if x.label=='Limite declarado [mm]').set_value(21.).run(timeout=45)
    assert not app.exception and 'result' not in app.session_state
    assert app.session_state.last_input[c.CHOICE]['limit_mm']==21.
