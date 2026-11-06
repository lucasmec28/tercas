"""Fail closed for inherited strong-axis tabulated criticals after elastic edits.

Rev07 records E=200 GPa for Pierin; source G and Poisson ratio are unknown.
The app's original G=77000 MPa is only an operational change detector, never a
claim about the table's elastic model. No scale factor or Poisson ratio is inferred.
"""
import math
from .catalogs import critical_defaults
from .core.selecao import select
from .core.local_table12 import local_critical, SOURCE as TABLE12_SOURCE

SOURCE_E_MPA = 200000.
APP_ORIGINAL_G_MPA = 77000.


def _same(a, b):
    return (isinstance(a, (int, float)) and not isinstance(a, bool)
            and math.isfinite(a) and isinstance(b, (int, float))
            and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-8))


def qualify_legacy_strong_criticals(data):
    """Return effective criticals plus an audit trail, without mutating inputs.

    Legacy imports have no structured origin flag. Equal catalogue values or an
    unchanged catalogue source therefore remain inherited, even if free text was
    edited. Independently supplied values with independent provenance retain the
    existing manual-input route; this guard does not certify that analysis.
    """
    original = critical_defaults(data['catalog_index'])
    props = data['properties']
    origin = data.get('critical_origin', '')
    automatic_catalogue_origin = ('planilha V03, 03_Perfis, linha ' in origin
                                  and '; valores tabulados, não validação independente' in origin)
    source_mismatch = automatic_catalogue_origin and original['critical_origin'] not in origin
    changed = []
    if not _same(props.get('E_MPa'), SOURCE_E_MPA):
        changed.append('E difere de 200000 MPa declarado para a fonte')
    if not _same(props.get('G_MPa'), APP_ORIGINAL_G_MPA):
        changed.append('G difere da configuração original do app; G e ν da fonte não foram explicitados')
    effective = {}
    evidence = {
        'source_E_MPa': SOURCE_E_MPA,
        'source_G_MPa': None,
        'source_nu': None,
        'app_original_G_MPa': APP_ORIGINAL_G_MPA,
        'source_note': 'Rev07: Pierin declara E=200 GPa; ν não explicitado. '
                       'G=77000 MPa é configuração original do app, não dado atribuído à tabela.',
        'fields': {},
        'warnings': [],
    }
    for key, label in [('Ml_Nmm', 'Ml'), ('Mdist_Nmm', 'Mdist')]:
        value = data.get(key)
        tabulated = original[key]
        inherited = (value is not None and
                     (source_mismatch or (tabulated is not None and
                      (_same(value, tabulated) or original['critical_origin'] in origin))))
        effective[label] = {'value': value, 'origin': origin}
        status = 'tabulated_original_configuration' if inherited else 'supplied_or_absent'
        info = {'status': status, 'inherited_tabulated': inherited, 'input_value_Nmm': value}
        reasons = list(changed)
        if source_mismatch:
            reasons.append('origem automática do catálogo não corresponde à seção/linha selecionada')
        if inherited and reasons:
            reason = (label + ' tabulado do eixo forte não avaliado: ' + '; '.join(reasons)
                      + '. Exige análise elástica compatível e rastreada; sem escala automática '
                        'e sem atribuir ν à fonte. Valor original preservado somente para auditoria.')
            effective[label] = {'value': None, 'origin': origin, 'reason': reason}
            info.update(status=('not_evaluated_incompatible_catalogue_source' if source_mismatch
                                else 'not_evaluated_incompatible_elastic_inputs'), reason=reason)
            evidence['warnings'].append(reason)
        evidence['fields'][label] = info
    # The legacy direct route also inherited a Table 12 result computed at E=200 GPa.
    # Keep its original input for audit, but do not silently use it after editing E.
    if not source_mismatch and original['Ml_Nmm'] is None and data.get('Ml_Nmm') is not None:
        section = select(data['catalog_index'])
        nominal = {key: item['value'] for key, item in section['fields'].items()}
        def formula(properties, E):
            return local_critical(section['family'], properties['h'], properties['bf'],
                                  properties['t'], properties['Wx_cm3']*1000, E,
                                  nu=.3, D_mm=properties['lip'])['Ml_Nmm']
        try:
            legacy_value = formula(nominal, SOURCE_E_MPA)
        except (TypeError, ValueError):
            legacy_value = None
        origin_is_automatic = (TABLE12_SOURCE in origin and
                              ('; Ml calculado: ' in origin or '; derivação com E do aço selecionado: ' in origin))
        inherited = _same(data['Ml_Nmm'], legacy_value) or origin_is_automatic
        if inherited:
            info = evidence['fields']['Ml']
            info.update(inherited_automatic_table12=True,
                        formula_nu=.3,
                        formula_nu_origin='Parâmetro já adotado na fórmula do app; não é ν atribuído a Pierin',
                        status='automatic_table12_original_configuration')
            # inputs_for_section already computes this explicit route with current E.
            # Verify the numeric result against exactly that existing formula; never
            # scale a table or silently recompute the legacy direct input here.
            try:
                current_value = formula(props, props.get('E_MPa'))
            except (TypeError, ValueError):
                current_value = None
            fresh_scan = (origin.startswith(original['critical_origin'])
                          and origin.endswith('; derivação com E do aço selecionado: ' + TABLE12_SOURCE)
                          and _same(data['Ml_Nmm'], current_value))
            if fresh_scan:
                info.update(status='automatic_table12_recomputed_for_current_E',
                            formula_E_MPa=props.get('E_MPa'),
                            formula_parameters={key:props[key] for key in ('h','bf','t','lip','Wx_cm3')})
            elif (_same(props.get('E_MPa'), SOURCE_E_MPA)
                  and _same(data['Ml_Nmm'], legacy_value)
                  and _same(data['Ml_Nmm'], current_value)):
                info.update(formula_E_MPa=SOURCE_E_MPA,
                            formula_parameters={key:props[key] for key in ('h','bf','t','lip','Wx_cm3')})
            else:
                reason = ('Ml automático da Tabela 12 não avaliado: E ou parâmetros atuais não qualificam '
                          'o valor automático herdado. Requer recálculo rastreado dos parâmetros da fórmula; '
                          'não houve escala ou recálculo silencioso. ν=0,3 é parâmetro existente do app, '
                          'não ν atribuído a Pierin. Valor original preservado somente para auditoria.')
                effective['Ml'] = {'value':None, 'origin':origin, 'reason':reason}
                info.update(status='not_evaluated_stale_automatic_table12',reason=reason)
                evidence['warnings'].append(reason)
    return effective, evidence


def qualify_strong_criticals(data):
    from .ue_catalog_reference import claims_reference
    if claims_reference(data):
        reason='Contorno próprio Ue: críticos de outro modelo não são herdados; capacidades próprias ainda pendentes.'
        effective={k:dict(value=None,origin=data.get('critical_origin',''),reason=reason) for k in ('Ml','Mdist')}
        evidence=dict(source='ue_catalog_own_contour',pierin_U_reference=dict(status='outside_U_scope',reason=reason,axial_calculation_implemented=False),fields={k:dict(status='not_evaluated_own_contour',input_value_Nmm=data.get(k+'_Nmm'),reason=reason) for k in ('Ml','Mdist')},warnings=[reason])
        from .ue_catalog_nbr_bending import qualify, FIELD
        certificate = qualify(data)
        if certificate is not None:
            local = certificate['strong']['local']
            dist = certificate['strong']['distortional']
            effective['Ml'] = dict(value=local['Ml_Nmm'], origin=local['origin'])
            effective['Mdist']['reason'] = dist['reason']
            evidence[FIELD] = certificate
            evidence['fields']['Ml'] = dict(status='computed_own_contour_Table12b',
                input_value_Nmm=data.get('Ml_Nmm'), computed_value_Nmm=local['Ml_Nmm'],
                inherited_tabulated=False, reference_id=certificate['reference_id'],
                formula_nu=local['formula_nu'], source_binding=certificate['source_binding'])
            evidence['fields']['Mdist']['reason'] = dist['reason']
            evidence['warnings'] = [dist['reason']]
        return effective,evidence
    effective, evidence = qualify_legacy_strong_criticals(data)
    # New U table overlay is distinct from legacy workbook/Table12 provenance.
    # Qualify after the legacy path so imported old projects retain their route.
    from .strong_pierin import qualify
    override, reference = qualify(data, legacy=(effective, evidence))
    evidence['pierin_U_reference'] = reference
    if override is not None:
        effective['Ml'] = override
        evidence['fields']['Ml'] = {
            'status':reference['use_status'], 'inherited_tabulated':True,
            'input_value_Nmm':data.get('Ml_Nmm'), 'reference_id':reference.get('id'),
            'source':'Pierin2013 Table1 U Mlx',
        }
        if override.get('reason'):
            evidence['fields']['Ml']['reason'] = override['reason']
            evidence['warnings'].append(override['reason'])
    return effective, evidence
