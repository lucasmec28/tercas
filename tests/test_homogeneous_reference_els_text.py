"""Exact allowlist: qualified ELS status prose only, never results or ELU."""
import copy
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from docx import Document
from tercas.application import calculate
from tercas.batch import calculate_batch
from tercas.homogeneous_reference import (load_reference, calculate_reference,
    LEGACY_ELS_STATUS, REFERENCE_ELS_STATUS, REPORTING_VERSION)

# Independently state the expected values, so changing both implementation
# constants does not silently relax the contract of this revision.
OLD = 'Pendente: propriedades/críticos e resistências do eixo fraco por sentido não fornecidos; sem aprovação biaxial.'
NEW = ('Propriedades e críticos próprios por sentido fornecidos. Flecha forte: componente com Ief uniaxial. '
       'Rigidez efetiva sob flexão biaxial/Ief combinado e flecha fraca não qualificadas; '
       'sem conclusão de ELS completo nem aprovação global.')


def differences(actual, expected, path=()):
    if isinstance(actual,dict) and isinstance(expected,dict):
        if actual.keys()!=expected.keys():return [(path,'keys',sorted(actual),sorted(expected))]
        return [change for k in actual for change in differences(actual[k],expected[k],path+(k,))]
    if isinstance(actual,list) and isinstance(expected,list):
        if len(actual)!=len(expected):return [(path,'length',len(actual),len(expected))]
        return [change for i,(a,b) in enumerate(zip(actual,expected)) for change in differences(a,b,path+(i,))]
    return [] if actual==expected else [(path,expected,actual)]


@pytest.mark.parametrize('angle',(0,5,-5))
@pytest.mark.parametrize('mode',('direct','area'))
def test_only_concrete_els_text_paths_change_every_other_value_is_exact(mode,angle):
    assert LEGACY_ELS_STATUS==OLD and REFERENCE_ELS_STATUS==NEW
    data=load_reference('U125',angle)
    if mode=='direct':
        data.update(load_mode='direct',q_uls=.4,q_sls=.2,q_parallel_uls=angle*.02,
                    q_parallel_sls=angle*.01,P_uls=100.,P_sls=40.,x_uls=1200.,x_sls=1100.)
    before=copy.deepcopy(data)
    base=calculate_batch(data) if mode=='area' else calculate(data)
    actual=calculate_reference(data)
    assert data==before
    record=actual.pop('homogeneous_reference_evidence')
    assert record['reporting_version']==REPORTING_VERSION
    expected=copy.deepcopy(base)
    allowed=[]
    if mode=='area':
        for i,case in enumerate(base['cases']):
            if case['combination']['limit_state']=='ELS' and case['evidence']['inclination']['resistance_status']==OLD:
                path=('cases',i,'evidence','inclination','resistance_status')
                allowed.append((path,OLD,NEW))
                expected['cases'][i]['evidence']['inclination']['resistance_status']=NEW
    elif base['inclination_evidence']['ELS']['resistance_status']==OLD:
        allowed.append((('inclination_evidence','ELS','resistance_status'),OLD,NEW))
        expected['inclination_evidence']['ELS']['resistance_status']=NEW
    assert differences(actual,base)==allowed
    assert actual==expected  # Entire tree, including ELU, all quantities and flags.
    assert len(allowed)==(0 if angle==0 else 18 if mode=='area' else 1)
    actual['homogeneous_reference_evidence']=record
    if angle==5:
        from tercas.report import word,batch_word
        report=(batch_word if mode=='area' else word)(actual)
        paragraphs='\n'.join(p.text for p in Document(BytesIO(report)).paragraphs)
        assert NEW in paragraphs and OLD not in paragraphs


def test_pre_correction_reference_cache_is_not_reused(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    data=load_reference('U125',5);data.update(load_mode='direct',q_sls=.2,q_parallel_sls=.05)
    payload=json.dumps(data).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
    next(b for b in app.button if b.label=='Aplicar entradas do arquivo').click().run(timeout=30)
    old=calculate_reference(data)
    old['homogeneous_reference_evidence'].pop('reporting_version')
    old['inclination_evidence']['ELS']['resistance_status']=OLD
    app.session_state['result']=old
    app.run(timeout=30)
    assert not app.exception and 'result' not in app.session_state
    assert app.session_state.last_input==data
