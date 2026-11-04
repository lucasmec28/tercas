"""Input guard only: no new local-introduction mechanics or assumed contact."""
import pytest
from tercas.application import build_spec, calculate, example, translate
from tercas.core import ramos_genericos

MISSING = object()
REASON = 'Comprimento de contato da carga concentrada ausente ou inválido (é necessário um valor finito e positivo). Introdução local permanece pendente; nenhum comprimento foi presumido.'


def fixture():
    result = calculate(example())
    return result['input_snapshot'], {'section_checks': result['section_checks']}


@pytest.mark.parametrize('value', [MISSING, None, 0, -1, True, False, float('nan'), float('inf'), -float('inf'), '40'])
def test_core_rejects_missing_invalid_contact_before_arithmetic(value, monkeypatch):
    spec, base = fixture()
    if value is MISSING:
        spec['introduction']['point'].pop('c_mm')
    else:
        spec['introduction']['point']['c_mm'] = value
    def forbidden(**kwargs):
        raise AssertionError('No capacity formula may run for invalid contact.')
    monkeypatch.setattr(ramos_genericos, 'frd', forbidden)
    result = ramos_genericos.calculate(spec, base)
    assert result['point'] == {'status': 'not_evaluated', 'reason': REASON}
    assert 'pendente' in translate(result['point']['reason'])
    assert 'ausente ou inválido' in translate(result['point']['reason'])


@pytest.mark.parametrize('value', [None, 0, -1])
def test_public_optional_contact_retains_pending(value):
    data = example()
    data['patch_mm'] = value
    result = calculate(data)
    assert result['NBR_branches']['point'] == {'status': 'not_evaluated', 'reason': REASON}
    assert result['whole_member_approved'] is False


@pytest.mark.parametrize('value', [MISSING, True, False, float('nan'), float('inf'), -float('inf'), '40'])
def test_public_invalid_schema_contract_is_unchanged(value):
    data = example()
    if value is MISSING:
        data.pop('patch_mm')
    else:
        data['patch_mm'] = value
    with pytest.raises(ValueError):
        build_spec(data)


def test_positive_contact_and_existing_capacity_are_exactly_unchanged():
    spec, base = fixture()
    current = ramos_genericos.calculate(spec, base)
    # Frozen numerical regression from the pre-guard didactic example, not a
    # statement that its contact describes a real project.
    assert current['point'] == {
        'status': 'computed', 'FRd_N': 10124.936073865776,
        'force_N': 1500.0, 'index': 0.14814908351587142,
        'patch_mm': [1480.0, 1520.0], 'origin': 'Contato central sintético'}


def test_subminimum_positive_contact_is_not_automatically_increased():
    spec, base = fixture()
    spec['introduction']['point']['c_mm'] = 10.0
    assert ramos_genericos.calculate(spec, base)['point'] == {
        'status': 'not_evaluated',
        'reason': 'contato fora do dominio: nao elevar c automaticamente'}


def test_absent_origin_preserves_existing_reason():
    spec, base = fixture()
    spec['introduction']['point']['origin'] = ''
    assert ramos_genericos.calculate(spec, base)['point'] == {
        'status': 'not_evaluated', 'reason': 'point patch geometry and origin missing'}


def test_contact_alone_does_not_assume_end_web_connections():
    spec, base = fixture()
    for name in ('left', 'right'):
        spec['introduction'][name]['route'] = None
    new = ramos_genericos.calculate(spec, base)
    assert new['point']['status'] == 'not_evaluated'
    assert 'end-web connections' in new['point']['reason']


def test_zero_point_load_does_not_require_fictitious_contact():
    data = example()
    data.update(P_uls=0.0, patch_mm=None)
    result = calculate(data)
    assert result['NBR_branches']['point']['status'] == 'not_applicable'
    assert 'index' not in result['NBR_branches']['point']


def test_word_renders_new_portuguese_reason_and_preserves_old_saved_reason():
    import copy
    from io import BytesIO
    from docx import Document
    from tercas.global_verification import attach_global_verification
    from tercas.report import word
    data = example()
    data['patch_mm'] = None
    current = attach_global_verification(calculate(data))
    before = copy.deepcopy(current)
    text = '\n'.join(p.text for p in Document(BytesIO(word(current))).paragraphs)
    assert REASON in text
    assert 'NoneType' not in text
    assert current == before
    historical = copy.deepcopy(current)
    old_reason = "unsupported operand type(s) for /: 'NoneType' and 'int'"
    historical['NBR_branches']['point']['reason'] = old_reason
    for check in historical['global_verification']['checks']:
        if check['id'] == 'ELU:DIRECT_ELU:point_introduction_scope':
            check['reason'] = old_reason
    before = copy.deepcopy(historical)
    text = '\n'.join(p.text for p in Document(BytesIO(word(historical))).paragraphs)
    assert old_reason in text
    assert REASON not in text
    assert historical == before


def test_saved_issues_ui_renders_new_portuguese_reason():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string("""
import streamlit as st
from tercas.application import example, calculate
from tercas.global_verification import attach_global_verification
from tercas.report_audit import show_saved_issues
data = example()
data['patch_mm'] = None
result = attach_global_verification(calculate(data))
show_saved_issues(st, result)
""").run(timeout=30)
    assert not app.exception
    text = '\n'.join(item.value for item in app.caption)
    assert REASON in text
    assert 'NoneType' not in text
