"""EN recovery fixtures with the original isolated-Ue inputs and UI seed.

The old QA files that hosted these helpers were not recovered. Keep their
original data contract here rather than coupling EN tests to another suite's
new defaults. Importing this module does not calculate a case or open an app.
"""
from tercas import ue_catalog_reference as own, roof_top_load as roof
from tercas import direct_self_weight as pp
from tercas.application import defaults,calculate
from tercas.batch import calculate_batch
from tercas.study_completion import complete_result


def inputs(index=0,angle=0.,line='web_midplane',mode='direct',L=4000.):
    d=pp.activate(defaults(index));d.update(member_application='purlin',load_mode=mode,L_mm=L,
        q_uls=.03,q_sls=.02,P_uls=0.,P_sls=0.,x_uls=L/2,x_sls=L/2,
        roof_top_load=roof.choice(line),inclination=dict(value=angle,unit='degrees'))
    d['segments']=[dict(start_mm=0.,end_mm=L,Ly_effective_mm=L,Lz_effective_mm=L,
        Cb_mode='one',restraint_provenance='Synthetic declared full-span lengths')]
    return own.activate(d)


def run(d):
    return complete_result(calculate_batch(d) if d['load_mode']=='area' else calculate(d))


def seed():
    d=pp.activate(defaults(0));d.update(roof_top_load=roof.choice(),q_uls=.03,q_sls=.02,
        member_application='purlin')
    return d


def load_app(monkeypatch):
    import json
    from pathlib import Path
    from types import SimpleNamespace
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    d=seed();payload=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
    next(x for x in app.button if x.label=='Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception
    return app,d
