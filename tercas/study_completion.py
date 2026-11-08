"""Add new, explicit assessment snapshots at the UI calculation boundary.

Legacy mechanics remain available unchanged. This function must not be used
to requalify a historical report merely because it is opened or downloaded.
"""
import copy
from .application import fingerprint
from .global_verification import build_global_verification

VERSION = 'study_completion_v1_20261103'


def complete_result(result):
    if fingerprint(result['input_data']) != result.get('input_fingerprint'):
        raise ValueError('Resultado/entradas divergentes; calcule novamente.')
    from .torsion_study import attach
    from .ue_catalog_reference import attach_source
    out = attach(attach_source(result))
    from .aisi_torsion_component import finalize
    out = finalize(out)
    from .isolated_en_application import finalize as finalize_EN
    out = finalize_EN(out)
    from .isolated_service_component import finalize as finalize_service
    out = finalize_service(out)
    from .roof_top_load import attach as attach_roof_top_load
    out = attach_roof_top_load(out)
    from .roof_top_nbr import attach as attach_roof_nbr
    out = attach_roof_nbr(out)
    from .nbr_ue_family_application import attach as attach_nbr_family
    out = attach_nbr_family(out)
    out['global_verification'] = build_global_verification(out)
    out['whole_member_approved'] = False
    out['completion_snapshot'] = dict(schema=VERSION,
        source_input_fingerprint=result['input_fingerprint'],
        original_mechanics_changed=False, historical_results_requalified=False)
    from .completion_requirements import attach as attach_requirements
    return attach_requirements(out)


def show_global(st, result):
    from .nbr_ue_family_ui import show as show_nbr_family
    show_nbr_family(st, result)
    from .torsion_applicability import show as show_applicability
    show_applicability(st, result)
    record = result.get('global_verification')
    if not isinstance(record,dict):return
    from .roof_top_nbr import validate_saved_global
    try:
        validate_saved_global(result)
        from .isolated_en_application import validate_saved_global as validate_EN_global
        validate_EN_global(result)
        from .nbr_family_panorama import validate_saved as validate_NBR_family_global
        validate_NBR_family_global(result)
        from .isolated_service_panorama import validate_saved as validate_service_global
        validate_service_global(result)
        from .support_scope import validate_saved_inventory
        validate_saved_inventory(result,record)
    except (ValueError,TypeError,KeyError) as exc:
        st.warning('Panorama não exibido: '+str(exc));return
    message = record['display_summary']
    if record['status'] == 'reprovado':st.error(message)
    else:st.warning(message)
    st.caption('Panorama dos critérios listados no modelo declarado. Índices de verificações diferentes '
               'não são somados nem representam uma utilização global. '
               'Tirantes, cantoneiras, ligações e ancoragens não são dimensionados.')
    if record.get('point_limit_scope_note'):st.caption(record['point_limit_scope_note'])
    from .completion_requirements import show as show_requirements
    show_requirements(st,result)
    from .isolated_service_ui import show as show_service
    show_service(st,result)
    from .report_audit import show_saved_issues
    show_saved_issues(st,result)


def report_global(doc, result):
    return _report_global(doc,result)


def _report_global(doc,result,roof_nbr_presentation=None):
    from .nbr_ue_family_ui import report as report_nbr_family
    report_nbr_family(doc, result)
    from .torsion_applicability import report as report_applicability
    report_applicability(doc, result)
    record = result.get('global_verification')
    if not isinstance(record,dict):return
    from .roof_top_nbr import validate_saved_global
    try:
        if roof_nbr_presentation is None:validate_saved_global(result)
        else:roof_nbr_presentation.validate_global(result)
        from .isolated_en_application import validate_saved_global as validate_EN_global
        validate_EN_global(result)
        from .nbr_family_panorama import validate_saved as validate_NBR_family_global
        validate_NBR_family_global(result)
        from .isolated_service_panorama import validate_saved as validate_service_global
        validate_service_global(result)
        from .support_scope import validate_saved_inventory
        validate_saved_inventory(result,record)
    except (ValueError,TypeError,KeyError) as exc:
        doc.add_paragraph('Panorama não exibido: '+str(exc));return
    doc.add_heading('Estado conjunto das verificações',1)
    doc.add_paragraph(record['display_summary'])
    doc.add_paragraph('O resumo mantém faltas e não atendimentos de cada combinação. '
        'Não soma índices nem transforma o maior índice disponível em utilização global. '
        'O modelo declarado não certifica condições de campo; tirantes, cantoneiras, '
        'ligações e ancoragens permanecem fora do dimensionamento.')
    for state in ('ELU','ELS'):
        r=record.get('by_limit_state',{}).get(state)
        if r:
            status=r['status']
            if record.get('sectional_conditions_policy'):
                status={'aprovado':'critérios listados atendidos', 'reprovado':'não atendimento em critérios listados',
                        'inconclusivo':'critérios listados inconclusivos'}.get(status,status)
            doc.add_paragraph(state+': '+status+'. Inclui os critérios comuns listados do modelo; não conclui o estado limite completo.'
                if record.get('sectional_conditions_policy') else state+': '+status+'. Inclui as pendências comuns do modelo.')
    if record.get('point_limit_scope_note'):doc.add_paragraph(record['point_limit_scope_note'])
    from .completion_requirements import report as report_requirements
    report_requirements(doc,result)
    from .isolated_service_ui import report as report_service
    report_service(doc,result)
    from .report_audit import report_saved_issues
    report_saved_issues(doc,result)
    from .roof_top_load_ui import report as report_roof_top_load
    if roof_nbr_presentation is None:report_roof_top_load(doc,result)
    else:
        from .roof_top_load_ui import _report
        _report(doc,result,nbr_report=roof_nbr_presentation.report)
