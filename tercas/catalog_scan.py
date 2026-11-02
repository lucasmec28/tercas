"""Bounded catalogue comparison. No UI state, normative additions or global approval.

Every section uses the existing single-section engines. Utilization is max(index)*100,
NOT percent of checks passed. Partial/hypothetical results never become recommendations.
"""
import copy
import time
from .application import defaults, calculate, rows, fingerprint, finite
from .batch import calculate_batch
from .catalogs import catalog_labels, catalog_entry
from .weak_catalog import critical_hypothesis

_EXEMPT = {'Não aplicável', 'Dispensado pela Tabela 14', 'Não acionado pelo comprimento'}
_EXCLUDED = {'Flecha paralela à cobertura', 'Apoio esquerdo', 'Apoio direito'}


def inputs_for_section(data, index):
    """Preserve actions/restraints/material, replace all section-dependent inputs.

Manual section properties/criticals are deliberately not copied to another section.
Even the originally selected section is compared on the same catalogue basis.
"""
    fresh = defaults(index)
    out = copy.deepcopy(data)
    for key in ('catalog_index', 'properties', 'Ml_Nmm', 'Mdist_Nmm', 'critical_origin'):
        out[key] = copy.deepcopy(fresh[key])
    for key in ('E_MPa', 'G_MPa', 'fy_MPa', 'fu_MPa'):
        out['properties'][key] = data['properties'][key]
    out['property_origin'] = data.get('property_origin', '') + '; demais propriedades: catálogo da seção comparada'
    # Retain synthetic provenance of loads/restraints used by test/demo cases.
    entry = catalog_entry(index)
    from .strong_pierin import reference_for_index
    if entry['critical_values']['Ml_Nmm'] is None and reference_for_index(index)['status'] != 'tabulated_adopted_reference':
        from .core.local_table12 import local_critical
        p = out['properties']
        try:
            critical = local_critical(entry['family'], p['h'], p['bf'], p['t'],
                                      p['Wx_cm3']*1000, p['E_MPa'], D_mm=p['lip'])
            out['Ml_Nmm'] = critical['Ml_Nmm']
            out['critical_origin'] = fresh['critical_origin'] + '; derivação com E do aço selecionado: ' + critical['origin']
        except (ValueError, TypeError):
            out['Ml_Nmm'] = None
    # Lx is a restraint input; all geometric/manual critical values are section-bound.
    cfg = data.get('weak_catalog', {})
    if not isinstance(cfg, dict):
        raise ValueError('Configuração do eixo fraco deve ser um objeto.')
    out['weak_catalog'] = {'geometry_mode': 'catalog', 'Lx_mm': cfg.get('Lx_mm', data['L_mm'])}
    out['weak_axis'] = critical_hypothesis(index)
    return out


def summarize(checks, warnings=()):
    relevant = [r for r in checks if r.get('Verificação') not in _EXCLUDED]
    numeric = [r for r in relevant if finite(r.get('Índice')) and r['Índice'] >= 0]
    pending = []
    for r in relevant:
        status = str(r.get('Situação', ''))
        # A numerical candidate may still be partial or a provisional hypothesis.
        uncertain = any(t in status.lower() for t in ('parcial', 'pendente', 'hipótese', 'provisóri'))
        if uncertain or r.get('Casos pendentes', 0) or (r not in numeric and status not in _EXEMPT):
            pending.append(r.get('Verificação', 'Verificação sem identificação'))
    pending += ['Aviso: ' + str(w) for w in warnings]
    if not numeric:
        pending.append('Nenhuma verificação com índice disponível')
    worst = max(numeric, key=lambda r: r['Índice']) if numeric else None
    failed = any(r['Índice'] > 1 for r in numeric)
    status = 'Não atende aos critérios calculados' if failed else ('Parcial — não classificável como atendida' if pending else 'Atende aos critérios calculados')
    return dict(status=status, utilization_percent=100*worst['Índice'] if worst else None,
                governing_check=worst['Verificação'] if worst else None,
                governing_combination=worst.get('Combinação') if worst else None,
                evaluated_checks=len(numeric), pending_checks=len(set(pending)),
                pending=list(dict.fromkeys(pending)), criteria_satisfied=bool(numeric) and not failed and not pending,
                whole_member_approved=False)


def scan_catalog(data, indices=None, *, max_seconds=None, progress=None, cancelled=None):
    """Sequential bounded comparison; results remain partial after timeout/cancellation.

max_seconds is a soft between-section bound: a running calculation is not killed.
progress(completed,total,row) receives a copy. No cross-request mutable cache/state.
All 209 entries are selected by default; no hidden cut-off or load/combination changes.
"""
    labels = catalog_labels()
    indices = list(range(len(labels))) if indices is None else list(indices)
    if any(not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(labels) for i in indices):
        raise ValueError('Índice de perfil inválido.')
    if len(indices) > len(labels) or len(set(indices)) != len(indices):
        raise ValueError('Lista de perfis repetida ou maior que o catálogo.')
    if max_seconds is not None and (not finite(max_seconds) or max_seconds <= 0):
        raise ValueError('Limite operacional deve ser positivo e finito.')
    start = time.monotonic()
    output = []
    stop_reason = None
    original_fingerprint = fingerprint(data)
    for index in indices:
        if cancelled is not None and cancelled():
            stop_reason = 'cancelled'; break
        if max_seconds is not None and time.monotonic() - start >= max_seconds:
            stop_reason = 'time_limit'; break
        row = dict(catalog_index=index, profile=labels[index], mass_kg_m=None)
        try:
            item = inputs_for_section(data, index)
            row['mass_kg_m'] = item['properties']['mass_kg_m']
            if not finite(row['mass_kg_m']) or row['mass_kg_m'] <= 0:
                raise ValueError('Massa linear não disponível/positiva no catálogo.')
            if item.get('load_mode') == 'area':
                result = calculate_batch(item)
                checks = result['summary']
                warnings = [w for c in result['cases'] for w in c['warnings']]
            else:
                result = calculate(item)
                checks = rows(result)
                warnings = result['coverage_warnings'] + result.get('critical_warnings', []) + result['numerical_warnings']
            row.update(summarize(checks, warnings))
            row['checks'] = checks
            row['weak_critical_reference'] = copy.deepcopy(result.get('weak_critical_reference'))
            row['strong_critical_reference'] = copy.deepcopy(result.get('strong_critical_reference'))
        except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
            row.update(status='Não calculado — dados insuficientes ou incompatíveis',
                       utilization_percent=None, governing_check=None, governing_combination=None,
                       evaluated_checks=0, pending_checks=1, pending=[str(exc)],
                       criteria_satisfied=False, whole_member_approved=False, checks=[])
        output.append(row)
        if progress is not None:
            progress(len(output), len(indices), copy.deepcopy(row))
    output.sort(key=lambda r: (r['mass_kg_m'] if finite(r['mass_kg_m']) else float('inf'), r['profile'], r['catalog_index']))
    return dict(schema='tercas_catalog_scan_v1', input_fingerprint=original_fingerprint,
                rows=output, requested_count=len(indices), completed_count=len(output),
                complete=len(output) == len(indices), stop_reason=stop_reason,
                unprocessed_indices=[i for i in indices if i not in {r['catalog_index'] for r in output}],
                elapsed_seconds=time.monotonic()-start, whole_member_approved=False,
                notes=['Utilização (%) = 100 × maior índice dos critérios calculados; não é porcentagem de aprovação.',
                       'Índices de interação quadrática permanecem na métrica original do critério.',
                       'Pendências, hipóteses e avisos impedem classificação como atendimento completo dos critérios.',
                       'Propriedades/críticos manuais da seção anterior não são transferidos; catálogo e hipóteses rastreadas de cada seção são usados.',
                       'Nas 124 linhas U exatas, nova seleção/comparação usa Mlx Pierin no lugar da Tabela 12. Importação direta de projeto legado mantém sua fonte; não há escala ou fallback silencioso para E/G alterados.',
                       'Peso próprio varia por seção no modo área. Ações diretas permanecem exatamente as informadas, inclusive eventual peso próprio nelas embutido.',
                       'Comparação restrita às verificações implementadas; não constitui aprovação global de projeto.'])
