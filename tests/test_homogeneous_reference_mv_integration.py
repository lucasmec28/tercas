"""Integrate the exact published M–V trace without importing its old caveat."""
import ast
import copy
import hashlib
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from docx import Document
from tercas.homogeneous_reference import (load_reference,calculate_reference,evidence,
    REPORTING_VERSION,TRACE_NOTE,FIELD)

ROOT=Path(__file__).resolve().parents[1]
R2_VERSION='homogeneous_reference_els_status_20261103_r2'
R2_TRACE=('Ressalva de rastreabilidade: em alguns casos P no limite do apoio, o subcampo '
          'NBR_branches.MV.result descreve o subproblema interior. A linha exibida de interação '
          'e prescribed_point.MV_limit_states contêm o envelope governante. Esses registros '
          'não devem ser confundidos; o subcampo legado isolado não representa o envelope.')
HISTORICAL_PATCH_DOCUMENTS={
 'docs/SUPPORT_LIMIT_MV_TRACE_20261103.txt':'0e02a902e7c247c5d4437c74a631ff979b13b88586fe2fc623ec7f7d986d4948',
 'tests/test_support_limit_mv_trace.py':'bacd41569abec3527125a7b22841777b72d314c0e059f8af463d32a6c80ae64c',
}


# Extracted from the independently frozen published batch.py, whole-file SHA
# effbae50eb35d4762f271fbf22a8b886f4bebc3bee15c7dd107f75e8dfecf7b4.
# The Ue dispatch and the strong-only T14 status label are outside this M–V
# contract. Freeze the actual trace and numerical row routines, not unrelated
# future code in the module. Existing numeric regressions below remain intact.
PUBLISHED_MV_CORE = {
    'support_limit_mv_trace': {
        'bytes': '33e3715e4358164daa3e35783578e1d4ab134f446012a856ec46c3527ff89e50',
        'ast': 'e0b6575e0c38409a17e39e6b2d604415350f490f147e71a66dba74f2ed1040ff'},
    'mobile_rows': {
        'bytes': '56e8880ed20534952fab04c903ee039e93a1e0c90b577aad01c3b1da930abe46',
        'ast': 'b336ebad11e67cd20af75f06dcde9a3b29816219e47a837449dabc1f0f319392'},
}


def _mv_core_fingerprints(source, name):
    nodes = [n for n in ast.parse(source).body
             if isinstance(n, ast.FunctionDef) and n.name == name]
    assert len(nodes) == 1, 'Missing or duplicate published M–V routine: ' + name
    node = nodes[0]
    raw = ''.join(source.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    return {'bytes': hashlib.sha256(raw.encode()).hexdigest(),
            'ast': hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()}


def _assert_published_mv_core(source):
    for name, expected in PUBLISHED_MV_CORE.items():
        assert _mv_core_fingerprints(source, name) == expected, name


def test_published_mv_documents_and_trace_core_remain_exact():
    for name,want in HISTORICAL_PATCH_DOCUMENTS.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==want
    _assert_published_mv_core((ROOT/'tercas/batch.py').read_bytes().decode('utf-8'))


@pytest.mark.parametrize('before,after', [
    ("row['Índice']=max(row['Índice'],(v/vr)**2)",
     "row['Índice']=min(row['Índice'],(v/vr)**2)"),
    ("governing=max(states,key=lambda key:states[key]['index_squared'])",
     "governing=min(states,key=lambda key:states[key]['index_squared'])"),
    ("'V_N':q*L/2+combo['P_N']", "'V_N':q*L/2-combo['P_N']"),
])
def test_published_mv_core_guard_detects_formula_and_trace_mutations(before, after):
    source=(ROOT/'tercas/batch.py').read_bytes().decode('utf-8')
    assert source.count(before)==1
    with pytest.raises(AssertionError):
        _assert_published_mv_core(source.replace(before,after,1))


def test_published_mv_core_guard_is_local_but_rejects_duplicate_definition():
    source=(ROOT/'tercas/batch.py').read_bytes().decode('utf-8')
    _assert_published_mv_core(source+'\n# Unrelated module inventory note.\n')
    with pytest.raises(AssertionError,match='duplicate'):
        _assert_published_mv_core(source+'\ndef mobile_rows(rs,result,combo):\n return {}\n')


@pytest.mark.parametrize('angle',(0,5,-5))
def test_reference_support_trace_is_governing_and_preserves_raw_interior(angle):
    data=load_reference('U150',angle);before=copy.deepcopy(data)
    result=calculate_reference(data)
    assert data==before and result['input_data']==before
    record=result['homogeneous_reference_evidence']
    assert record['reporting_version']==REPORTING_VERSION
    assert record['support_limit_mv_trace']==TRACE_NOTE and 'trace_limitation' not in record
    support=[]
    for case in result['cases']:
        c=case['combination']
        if c['limit_state']!='ELU' or c.get('point_position')!='support_limit':continue
        mv=case['evidence']['NBR_branches']['MV']
        row=next(r for r in case['rows'] if r['Verificação']=='Flexão e cortante concomitantes')
        idx=case['evidence']['prescribed_point']['MV_limit_states']['governing_index_squared']
        assert mv['result']['index_squared']==row['Índice']==idx
        assert mv['result']==mv['limit_states'][mv['governing_state']]
        assert set(mv['limit_states'])=={'interior_q_only','support_layer'}
        assert mv['result']['a_mm'] is None and mv['result']['a_limit']=='a→0+'
        assert mv['interior_q_only_result']['a_mm']==data['L_mm']/2
        assert mv['limit_states']['support_layer']['V_N']==c['q_N_mm']*data['L_mm']/2+c['P_N']
        support.append(c['id'])
    assert len(result['cases'])==58 and len(support)==4
    assert result['whole_member_approved'] is False
    from tercas.report import batch_word
    text='\n'.join(p.text for p in Document(BytesIO(batch_word(result))).paragraphs)
    assert TRACE_NOTE in text and R2_TRACE not in text


@pytest.mark.parametrize('historical', (False,True))
def test_word_serializes_recorded_trace_and_accepts_legitimate_r2_key(historical):
    data=load_reference('U125');data.update(load_mode='direct',q_uls=.4,q_sls=.2,q_parallel_sls=.05)
    result=calculate_reference(data)
    record=result['homogeneous_reference_evidence']
    expected=TRACE_NOTE
    if historical:
        record.pop('support_limit_mv_trace')
        record.update(reporting_version=R2_VERSION,trace_limitation=R2_TRACE)
        expected=R2_TRACE
    before=copy.deepcopy(result)
    from tercas.report import word
    text='\n'.join(p.text for p in Document(BytesIO(word(result))).paragraphs)
    assert expected in text
    if historical:assert TRACE_NOTE not in text
    else:assert R2_TRACE not in text
    assert result==before


def test_same_input_r2_cache_is_removed_without_changing_physical_marker(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    data=load_reference('U125',5);data['load_mode']='direct'
    marker=copy.deepcopy(data[FIELD]);payload=json.dumps(data).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    app=AppTest.from_file(str(ROOT/'app.py')).run(timeout=30)
    next(b for b in app.button if b.label=='Aplicar entradas do arquivo').click().run(timeout=30)
    old=calculate_reference(data)
    record=old['homogeneous_reference_evidence'];record.pop('support_limit_mv_trace')
    record.update(reporting_version=R2_VERSION,trace_limitation=R2_TRACE)
    app.session_state['result']=old
    app.run(timeout=30)
    assert not app.exception and 'result' not in app.session_state
    assert app.session_state.last_input==data and app.session_state.last_input[FIELD]==marker
