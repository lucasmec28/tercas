import copy
import json
from pathlib import Path
from types import SimpleNamespace
import streamlit as st
from streamlit.testing.v1 import AppTest
from tercas import torsion_material_ui as ui
from tercas.torsion_material import FIELD
from test_torsion_nominal_integration import inputs

APP=str(Path(__file__).resolve().parents[1]/'app.py')
def button(a,label):return next(x for x in a.button if x.label==label)


def prepared(monkeypatch):
    d=inputs();payload=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    a=AppTest.from_file(APP).run(timeout=30)
    button(a,'Aplicar entradas do arquivo').click().run(timeout=30)
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    assert not a.exception
    return a


def test_explicit_detail_no_rerun_solve_and_input_invalidation(monkeypatch):
    a=prepared(monkeypatch);base=copy.deepcopy(a.session_state.result);calls=[];old=ui.deepen
    def spy(*args,**kw):calls.append(args[1]);return old(*args,**kw)
    monkeypatch.setattr(ui,'deepen',spy)
    a.run(timeout=30);assert calls==[] and a.session_state.result==base
    button(a,'Detalhar tensões desta combinação').click().run(timeout=60)
    assert not a.exception and len(calls)==1
    saved=copy.deepcopy(a.session_state.result)
    assert len(saved[FIELD]['records'])==1
    assert {k:v for k,v in saved.items() if k!=FIELD}==base
    a.run(timeout=30);assert len(calls)==1 and a.session_state.result==saved
    next(x for x in a.number_input if x.label=='CP: x a partir do CG [mm]').set_value(11.).run(timeout=30)
    assert not a.exception and 'result' not in a.session_state
    assert not any(x.label=='Detalhar tensões desta combinação' for x in a.button)


def test_failed_detail_keeps_base_and_recovery_is_atomic(monkeypatch):
    a=prepared(monkeypatch);base=copy.deepcopy(a.session_state.result);old=ui.deepen
    def fail(*a,**kw):raise ValueError('Injected numerical failure for atomicity QA')
    monkeypatch.setattr(ui,'deepen',fail)
    button(a,'Detalhar tensões desta combinação').click().run(timeout=60)
    assert not a.exception and a.session_state.result==base
    assert any('resultado base foi preservado' in x.value for x in a.error)
    monkeypatch.setattr(ui,'deepen',old)
    button(a,'Detalhar tensões desta combinação').click().run(timeout=60)
    assert not a.exception and FIELD in a.session_state.result
    assert {k:v for k,v in a.session_state.result.items() if k!=FIELD}==base
