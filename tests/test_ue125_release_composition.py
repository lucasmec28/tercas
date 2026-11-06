"""Synthetic release composition only; no user project data or load history."""
import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from docx import Document
from tercas import deflection_scope, roof_top_nbr as nbr
from tercas import ue_catalog_nbr_bending as qualification
from tercas.application import calculate
from tercas.study_completion import complete_result
from tercas.torsion_applicability import saved_notice
from test_roof_catalog_nbr import inputs


def declared_inputs(parallel=.03):
    data=inputs(parallel=parallel,span=5000.)
    # Match the existing UI preset to the declared synthetic fy/fu, rather than
    # retaining the default A36 label with manually replaced fy=300.
    data['steel_name']='USI-CIVIL 300'
    data['member_application']='purlin'
    data['inclination']=dict(value=0.,unit='degrees',spacing_basis='roof',
        permanent_basis='roof',live_basis='horizontal',wind_basis='roof')
    data['segments']=[dict(start_mm=0.,end_mm=5000.,Ly_top_effective_mm=5000.,
        Ly_bottom_effective_mm=5000.,Lz_effective_mm=5000.,Cb_mode='one',
        restraint_provenance='Synthetic full span; no intermediate restraint')]
    if parallel==0.:
        data['P_parallel_uls']=0.; data['P_parallel_sls']=0.
    data[deflection_scope.FIELD]=deflection_scope.MODE
    return data


def assert_strong_complete_biaxial_pending(result):
    row=nbr.preserved(result)['records'][0]
    assert row['FLT']['MRd_flt_Nmm']>0
    parts=[row['MRd_section_effective_Nmm'],row['FLT']['MRd_flt_Nmm'],row['MRd_distortional_Nmm']]
    assert row['MRd_bending_component_Nmm']==min(parts)
    assert row['bending_component_index']==row['Msd_max_abs_Nmm']/min(parts) and 'biaxial' not in row
    assert row['bending_component_status']=='computed_strong_pure_bending'
    assert result[qualification.FIELD]['strong']['local']['MRd_Nmm']==pytest.approx(5154709.919603469)
    assert result[qualification.FIELD]['strong']['distortional']['Mdist_Nmm']==pytest.approx(13999871.753852382)
    assert result[qualification.FIELD]['strong_bending_complete'] is True
    assert result[qualification.FIELD]['biaxial_qualified'] is False
    assert result['whole_member_approved'] is False
    assert result['combined_ELS_approved'] is False
    global_ev=result['global_verification']
    assert global_ev['whole_member_approved'] is False
    assert global_ev['approved_within_declared_checklist'] is False
    assert global_ev['status']=='inconclusivo'
    assert any('torsion_warping'==c['id'] and c['status']=='pending' for c in global_ev['checks'])
    assert any('distor' in c['id'].lower() and c['status']=='meets' for c in global_ev['checks'])
    notice=saved_notice(result)
    assert notice is not None and 'não é limite normativo' in ' '.join(notice['lines'])
    return row


@pytest.mark.parametrize('parallel',[0.,.03])
def test_same_profile_keeps_local_ELS_and_torsion_scope_separate(parallel):
    data=declared_inputs(parallel);before=copy.deepcopy(data)
    result=complete_result(calculate(data)); assert_strong_complete_biaxial_pending(result)
    assert data==before and result['input_data']==before
    assert_strong_complete_biaxial_pending(json.loads(json.dumps(result,allow_nan=False)))


def test_real_UI_qualifies_only_available_Ue125_components_and_exports(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    data=declared_inputs();payload=json.dumps(data).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    downloads={};original=st.download_button
    def capture(label,value,*a,**k):
        if label in ('Baixar estudo e resultados (JSON)','Baixar memória parcial (Word)'):
            downloads[label]=value
        return original(label,value,*a,**k)
    monkeypatch.setattr(st,'download_button',capture)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
    button=lambda label:next(x for x in app.button if x.label==label)
    button('Aplicar entradas do arquivo').click().run(timeout=30)
    editor_input=copy.deepcopy(app.session_state.last_input)
    # The editor populates documented provenance/empty weak-axis fields.
    # Numeric inputs and the explicit coherent-contour adoption must not change.
    for key in ('properties','ue_catalog_reference','L_mm','segments','inclination',
                'q_uls','q_sls','P_uls','P_sls','x_uls','x_sls',
                'q_parallel_uls','q_parallel_sls','P_parallel_uls','P_parallel_sls'):
        assert editor_input[key]==data[key]
    button('Calcular verificações disponíveis').click().run(timeout=60)
    assert not app.exception
    assert not any('Não foi possível calcular' in item.value for item in app.error)
    assert app.session_state.last_input['properties']['fy_MPa']==300.
    result=copy.deepcopy(app.session_state.result);assert_strong_complete_biaxial_pending(result)
    assert result['input_data']==editor_input
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==result
    document=Document(io.BytesIO(downloads['Baixar memória parcial (Word)']))
    text='\n'.join(p.text for p in document.paragraphs)
    assert 'Distorção forte por aproximação elástica qualificada, sem dispensa.' in text
    assert 'interação §9.9 pendente, sem índice biaxial' in text
    assert 'não é limite normativo' in text
    assert 'não previsão do giro físico' in text
    def forbidden(*a,**k):raise AssertionError('Rerender reopened source or ran solver')
    monkeypatch.setattr('tercas.roof_top_load.refined',forbidden)
    monkeypatch.setattr('tercas.ue_catalog_nbr_bending.qualify',forbidden)
    monkeypatch.setattr('tercas.direct_torsion.solve_member',forbidden)
    app.run(timeout=60)
    assert not app.exception and app.session_state.result==result
    assert app.session_state.last_input==editor_input
