"""Exercise production direct/area Word dispatch, not the isolated UI helper.

Unrelated early emitters/readers are stubbed. After the actual family renderer
runs, stop at the next component and serialize the real docx it received.
"""
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile
import pytest


@pytest.mark.parametrize('entrypoint', ['word', 'batch_word'])
def test_real_word_dispatch_includes_family_before_global_early_return(monkeypatch, entrypoint):
    from tercas import report, study_completion, nbr_ue_family_ui as family
    from tercas import roof_top_nbr_ui, ue_catalog_ui, torsion_applicability
    for name in ('domain_report', 'homogeneous_reference_report', 'ue_reference_report',
                 'ue_family_reference_report', 'deflection_scope_report',
                 'gross_component_report', 'aa_component_report'):
        monkeypatch.setattr(report, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(report, 'component_record_is_readable', lambda result: False)
    monkeypatch.setattr(report, 'is_girt', lambda data: False)
    monkeypatch.setattr(ue_catalog_ui, 'report', lambda *args: None)
    monkeypatch.setattr(roof_top_nbr_ui, '_word_presenters', lambda result: SimpleNamespace())
    evidence = dict(records=[dict(combination_id='SYNTHETIC_ELU', components=[dict(
        route='published_nominal_reference', method='local',
        demand=dict(axis='normal', sign=None, Msd_Nmm=2.), capacity_Nmm=4.,
        index=.5, reference_comparison='within_reference', status='component_index',
        reason='Synthetic reference, not whole-member approval')])], pending_reason=None)
    reads = []
    def preserved(result):
        reads.append(result)
        return evidence
    monkeypatch.setattr(family, 'preserved', preserved)
    captured = []
    class StopAfterFamily(Exception):
        pass
    def next_component(doc, result):
        captured.append(doc)
        raise StopAfterFamily
    monkeypatch.setattr(torsion_applicability, 'report', next_component)
    # No global snapshot: family reporting must precede that early return.
    result = dict(input_data={}, synthetic=True)
    with pytest.raises(StopAfterFamily):
        getattr(report, entrypoint)(result)
    assert reads == [result]
    assert len(captured) == 1
    doc = captured[0]
    assert sum(p.text == family.TITLE for p in doc.paragraphs) == 1
    assert len(doc.tables) == 1 and len(doc.tables[0].rows) == 2
    output = BytesIO()
    doc.save(output)
    with ZipFile(output) as archive:
        xml = archive.read('word/document.xml').decode()
    assert 'SYNTHETIC_ELU' in xml and family.TITLE in xml
