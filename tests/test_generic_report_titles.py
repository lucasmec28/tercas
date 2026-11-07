"""Neutral report headings must not modify retained engineering results."""
import copy
import hashlib
import json
from io import BytesIO

import pytest
from docx import Document

from tercas import application, batch, report


def result_digest(result):
    return hashlib.sha256(json.dumps(
        result, sort_keys=True, ensure_ascii=False, allow_nan=False,
    ).encode()).hexdigest()


@pytest.mark.parametrize('kind,direct_title,batch_title', [
    ('purlin', 'Estudo de terça', 'Terças por combinações'),
    ('wall_girt', 'Estudo de travessa lateral', 'Travessas laterais por combinações'),
])
@pytest.mark.parametrize('mode', ['direct', 'area'])
def test_word_titles_are_generic_and_results_remain_unchanged(
    kind, direct_title, batch_title, mode, monkeypatch,
):
    data = application.example()
    data.update(member_application=kind, load_mode=mode,
                selected_types=['ELS quase permanente'])
    result = (application.calculate(data) if mode == 'direct'
              else batch.calculate_batch(data))
    before = copy.deepcopy(result)
    digest = result_digest(result)
    fingerprint = result['input_fingerprint']

    def no_recalculation(*args, **kwargs):
        pytest.fail('Word export must read the saved result without recalculation')

    monkeypatch.setattr(application, 'calculate', no_recalculation)
    monkeypatch.setattr(batch, 'calculate', no_recalculation)
    monkeypatch.setattr(batch, 'calculate_batch', no_recalculation)
    exporter = report.word if mode == 'direct' else report.batch_word
    doc = Document(BytesIO(exporter(result)))
    titles = [p.text for p in doc.paragraphs if p.style.name == 'Title']
    assert titles == [direct_title if mode == 'direct' else batch_title]
    assert result == before
    assert result['input_fingerprint'] == fingerprint
    assert result_digest(result) == digest


def test_app_page_and_visible_title_are_generic():
    import ast
    from pathlib import Path
    from streamlit.testing.v1 import AppTest

    app_path = Path(__file__).resolve().parents[1] / 'app.py'
    tree = ast.parse(app_path.read_text())
    configs = [node for node in ast.walk(tree)
               if isinstance(node, ast.Call)
               and isinstance(node.func, ast.Attribute)
               and isinstance(node.func.value, ast.Name)
               and node.func.value.id == 'st'
               and node.func.attr == 'set_page_config']
    assert len(configs) == 1
    page_title = next(keyword.value for keyword in configs[0].keywords
                      if keyword.arg == 'page_title')
    assert ast.literal_eval(page_title) == 'Terças e travessas laterais'
    app = AppTest.from_file(str(app_path)).run(timeout=30)
    assert not app.exception
    assert [title.value for title in app.title] == ['Terças e travessas laterais']
