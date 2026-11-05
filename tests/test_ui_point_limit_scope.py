"""The exclusion is visible even with finite-contact opt-in absent."""
import copy
from streamlit.testing.v1 import AppTest
from tercas.global_verification import attach_global_verification
from test_point_limit_scope import batches


def saved_global_panel(result):
    import streamlit as st
    from tercas.study_completion import show_global
    show_global(st,result)


def test_global_note_visible_without_physical_optin(batches,monkeypatch):
    import tercas.global_verification as global_module
    import tercas.point_contact as contact
    r=attach_global_verification(batches[0]);before=copy.deepcopy(r)
    assert 'point_contact' not in r['input_data']
    def forbidden(*a,**k):raise AssertionError('No reanalysis in saved UI')
    monkeypatch.setattr(global_module,'build_global_verification',forbidden)
    monkeypatch.setattr(contact,'evaluate',forbidden)
    app=AppTest.from_function(saved_global_panel,args=(r,)).run(timeout=30)
    assert not app.exception
    notes=[v.value for v in app.caption]
    assert any('não dispensa normativa' in v and 'cobre somente o contato central' in v for v in notes)
    assert r==before


def test_old_global_snapshot_not_given_new_exclusion_note(batches):
    r=attach_global_verification(batches[0])
    r['global_verification'].pop('point_limit_scope_note')
    r['global_verification'].pop('point_limit_exclusion_ids')
    before=copy.deepcopy(r)
    app=AppTest.from_function(saved_global_panel,args=(r,)).run(timeout=30)
    assert not app.exception
    assert not any('não dispensa normativa' in v.value for v in app.caption)
    assert r==before
