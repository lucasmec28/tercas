"""Versioned complementary completion sidecar; the source result stays immutable.

Unlike legacy v1 display, this new contract replays only scalar source/formula
checks. No member solver, history upgrade or normative global approval occurs.
"""
import copy
import hashlib
from pathlib import Path
from io import BytesIO
from . import application as a, mechanics, sources
from .. import completion_requirements as requirements

SCHEMA = 'support_web_completion_v1'
SCOPE = ('Evidência consolidada somente para o critério local da alma nas reações. '
         'Não dimensiona ligação completa, ancoragem ou apoio completo e não aprova o membro.')
PERSISTENCE = ('Conserve também o JSON original do estudo: este arquivo complementar não contém o resultado-base e não substitui um arquivo de entrada.')
HISTORICAL_READ = ('Fechamento histórico salvo, sem recalcular ou requalificar a resistência local. '
                   'Vínculo com a fonte, integridade e coerência dos dados salvos foram conferidos.')
FALSE_FLAGS = ('whole_member_approved', 'normative_design_complete', 'connection_design_checked')
# Pinned technical implementation, not a signature of a user's physical detail.
_AUTHORITY = {'support_web/mechanics.py': 'e8b5182651709388cbcb943f0c2843fd425bd88990cf83f7d73b4000cfa0910c', 'core/anexo_d.py': '6d8c3f272659b13028f1d775c83a6322edd70f7fcbf7f240fcda51f61810446e'}


def _authority():
    root = Path(__file__).resolve().parents[1]
    actual = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
              for name in _AUTHORITY}
    if not actual or actual != _AUTHORITY:
        raise ValueError('Autoridade escalar da versão de fechamento alterada; não requalificar histórico.')
    return actual


def _reconcile_source(result, assessment):
    a.saved_assessment(result, assessment)
    source = sources.extract(result)  # Saved-demand authentication, no member solve.
    expected_metadata = dict(
        source_schema=result.get('schema'),
        source_input_fingerprint=result.get('input_fingerprint'),
        source_scope=source.get('scope'),
        legacy_detail_evidence=source.get('legacy_details', {}),
        source_metadata={k:v for k,v in source.items()
                         if k not in ('supports','legacy_details','section')},
        limits=list(a.LIMITS))
    if any(assessment.get(k) != v for k,v in expected_metadata.items()):
        raise ValueError('Metadados, limites ou proveniência local divergem da fonte autenticada.')
    records = source['supports']
    keys = [(r['support_id'], r['combination_id']) for r in records]
    if not keys or len(keys) != len(set(keys)):
        raise ValueError('Inventário de reações vazio ou duplicado.')
    if assessment['section'] != source['section']:
        raise ValueError('Seção/material local divergente da fonte.')
    if [r['source_record'] for r in assessment['rows']] != records:
        raise ValueError('Forças, posições ou inventário local divergentes da fonte salva.')
    a._configuration(result, assessment['configuration'], source)
    return source


def _reconcile(result, assessment):
    source = _reconcile_source(result, assessment)
    for row in assessment['rows']:
        expected = mechanics.evaluate_reaction(source['section'], row['source_record'], row['detail'])
        if row['local'] != expected:
            raise ValueError('Resistência, detalhe ou decisão local divergente da fórmula desta versão.')
    return source


def _projection(result, assessment):
    base = requirements.saved(result)
    if base is None:
        raise ValueError('Inventário original de fechamento ausente; calcule o estudo antes de consolidar apoios.')
    records = copy.deepcopy(base['records'])
    support = next(r for r in records if r['id'] == 'support_web')
    counts = assessment['summary']
    evidence = []
    for row in assessment['rows']:
        src, local = row['source_record'], row['local']
        evidence.append(dict(support_id=src['support_id'], combination_id=src['combination_id'],
            source_record_sha256=a.fingerprint(src), detail_sha256=a.fingerprint(row['detail']),
            status=local['status'], criterion_status=local.get('criterion_status'),
            index=local.get('index'), scope=mechanics.SCOPE))
    support.update(evidence_state='authenticated_local_support_components',
        requirement_state='local_support_component_recorded_not_full_support_design',
        local_evidence=evidence, local_summary=copy.deepcopy(counts),
        complete_load_introduction_qualified=False, connection_design_checked=False)
    return dict(required_ids=list(requirements.REQUIRED_IDS), records=records,
                source_completion_sha256=base['snapshot_sha256'],
                **{k: False for k in FALSE_FLAGS})


def build(result, assessment):
    from ..support_scope import saved as saved_scope
    if saved_scope(result) is not None:
        raise ValueError('Apoios locais fora do escopo por decisão do usuário; sem consolidação resistente.')
    authority = _authority()
    _reconcile(result, assessment)
    out = dict(schema=SCHEMA, source_fingerprint=a.source_fingerprint(result),
        authority=authority, assessment=copy.deepcopy(assessment),
        completion=_projection(result, assessment), scope=SCOPE,
        **{k: False for k in FALSE_FLAGS})
    out['snapshot_sha256'] = a.fingerprint(out)
    return out


def _read_envelope(result, envelope, *, replay):
    if (not isinstance(envelope, dict) or envelope.get('schema') != SCHEMA
        or envelope.get('source_fingerprint') != a.source_fingerprint(result)
        or envelope.get('authority') != _authority() or envelope.get('scope') != SCOPE
        or any(envelope.get(k) is not False for k in FALSE_FLAGS)
        or envelope.get('snapshot_sha256') != a.fingerprint(
            {k:v for k,v in envelope.items() if k != 'snapshot_sha256'})):
        raise ValueError('Fechamento complementar alterado ou de outra fonte.')
    if replay:_reconcile(result, envelope['assessment'])
    else:_reconcile_source(result, envelope['assessment'])
    if envelope.get('completion') != _projection(result, envelope['assessment']):
        raise ValueError('Inventário complementar divergente da evidência local autenticada.')
    return copy.deepcopy(envelope)


def saved(result, envelope):
    """Legacy replay validator, including the pinned scalar formula."""
    return _read_envelope(result, envelope, replay=True)


def read_saved(result, envelope):
    """Read historical evidence without invoking any resistance calculation.

    Source, metadata, hashes, saved arithmetic and inventory remain checked.
    The stored capacity is not requalified by this presentation-only reader.
    """
    return _read_envelope(result, envelope, replay=False)


def _word(result, envelope, *, historical):
    from docx import Document
    from .report import append
    current = read_saved(result, envelope) if historical else saved(result, envelope)
    doc = Document()
    doc.add_heading('Fechamento complementar: alma nos apoios', 0)
    doc.add_paragraph(SCOPE)
    doc.add_paragraph(PERSISTENCE)
    doc.add_paragraph('Resultado-base imutável: '+current['source_fingerprint'])
    doc.add_paragraph(HISTORICAL_READ if historical else 'Reações, posições, inventário, seção e resistência local reconciliados por verificação escalar, sem resolver novamente o membro. Dados físicos continuam declarados.')
    append(doc, result, current['assessment'])
    doc.add_heading('Inventário de fechamento preservado', 1)
    for row in current['completion']['records']:
        doc.add_paragraph(row['label']+': '+row['evidence_state']+'. '+row['condition_and_minimum_data'])
    stream = BytesIO(); doc.save(stream); return stream.getvalue()


def word(result, envelope):
    """Legacy replay export; not called by the current app UI."""
    return _word(result, envelope, historical=False)


def word_saved(result, envelope):
    """Export the stored historical completion without a formula replay."""
    return _word(result, envelope, historical=True)
