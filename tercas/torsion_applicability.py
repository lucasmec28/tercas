"""Read-only warnings from saved linear demands, never a design criterion.

No solve, new rotation threshold, historical migration or status change occurs
here. The existing numeric warning is a modelling screen, not a code limit.
"""
import math

from .report_audit import technical_number as number


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _rotation(phi, warning, numerics):
    if not isinstance(numerics, dict):
        raise ValueError('Dados numéricos da triagem de giro malformados.')
    limit = numerics.get('rotation_warning_rad')
    if (not _finite(phi) or not _finite(limit) or limit <= 0
            or numerics.get('rotation_warning_is_normative_limit') is not False
            or type(warning) is not bool or warning != (abs(phi) > limit)):
        raise ValueError('Giro, aviso ou limiar de triagem salvo inconsistente.')
    return abs(phi), warning, limit


def aisi_lines(evidence):
    """Called only after the existing AISI snapshot reader validates its hashes."""
    computed = [r for r in evidence['records'] if r.get('G81') is not None]
    if not computed:
        return []
    ratios = []
    warnings = 0
    for r in computed:
        g = r['G81']
        if not _finite(g.get('ratio')) or g['ratio'] < 0:
            raise ValueError('Índice G8.1 salvo inválido.')
        ratios.append(g['ratio'])
        a = r.get('AISI_analysis')
        if a is not None:
            if not isinstance(a, dict):
                raise ValueError('Análise AISI salva malformada.')
            _, warning, _ = _rotation(a.get('max_abs_phi_rad'),
                r.get('first_order_small_rotation_warning'), a.get('numerics', {}))
            warnings += warning
    exceeded = sum(v > 1 for v in ratios)
    lines = [f'G8.1 AISI: {exceeded} de {len(ratios)} casos ELU com |B|/Ba > 1; '
        'máximo salvo = '+number(max(ratios), 1.)+'. '+
        'É uma comparação condicional da demanda linear com a resistência AISI ao bimomento, '
        'não comprovação de ruptura física nem reprovação global NBR. '
        'O diagnóstico acima de 1 permanece visível mesmo com a aplicabilidade da análise pendente.']
    if warnings:
        lines.append(f'{warnings} casos AISI também têm aviso de giro na sua própria análise. '
            'A interpretação física de G8.1/H4 permanece indisponível nesta primeira ordem. '
            'H4 ≤ 1, quando calculado, é apenas condição algébrica sob as hipóteses declaradas; '
            'H4 > 1 com denominadores de piso não demonstra atendimento e não prova ruptura.')
    return lines


def _saved_lines(result):
    evidence = result.get('torsion_evidence')
    if evidence is None:
        return None
    if not isinstance(evidence, dict) or not isinstance(evidence.get('records'), list):
        raise ValueError('Registro de torção salvo malformado.')
    if not evidence['records']:
        if evidence.get('computed_cases', 0) != 0:
            raise ValueError('Demandas calculadas sem os registros correspondentes.')
        return None
    from .application import fingerprint
    if (fingerprint(result['input_data']) != result.get('input_fingerprint')
            or evidence.get('source_input_fingerprint') != result.get('input_fingerprint')
            or evidence.get('schema') not in ('purlin_torsion_batch_summary_v1',
                                             'purlin_torsion_batch_evidence_v1')):
        raise ValueError('Demanda de torção não corresponde às entradas salvas.')
    rows = []
    identities = set()
    for r in evidence['records']:
        key = (r['combination_id'], r['limit_state'])
        if (key in identities or key[1] not in ('ELU', 'ELS')
                or r.get('source_input_fingerprint') != result['input_fingerprint']):
            raise ValueError('Identidade/vínculo de combinação torsional inválido.')
        identities.add(key)
        a = r.get('analysis')
        if a is None:
            continue
        domain = a['analysis_domain']
        if (a.get('schema') not in ('single_vlasov_member_summary_v1', 'single_vlasov_member_demand_v1')
                or (a.get('combination_id'), a.get('limit_state')) != key
                or domain.get('order') != 1 or domain.get('small_rotation_kinematics') is not True):
            raise ValueError('Domínio/identidade da análise torsional salvo inconsistente.')
        phi, warning, limit = _rotation(a['max_abs_phi']['phi_rad'],
            a.get('small_rotation_warning'), a.get('numerics', {}))
        rows.append((phi, warning, limit, a))
    if type(evidence.get('computed_cases')) is not int or evidence['computed_cases'] != len(rows):
        raise ValueError('Contagem de demandas torsionais salvas inconsistente.')
    if not rows:
        return None
    # Existing AISI snapshots bind the exact saved torsion object. A mismatch
    # must not leave an apparently valid, quantitative applicability banner.
    aisi = result.get('aisi_torsion_component')
    if aisi is not None:
        from .aisi_torsion_component import preserved
        aisi = preserved(result)
    maximum = max(r[0] for r in rows)
    warnings = sum(r[1] for r in rows)
    limits = sorted({r[2] for r in rows})
    lines = ['Aplicabilidade da análise de primeira ordem não estabelecida. '+
        (f'{warnings} de {len(rows)} combinações têm aviso de pequeno giro. '
         if warnings else 'Nenhum aviso de giro nas combinações salvas; isso não valida a primeira ordem. ')+
        'Máximo |φ linear| = '+number(maximum)+' rad ('+number(math.degrees(maximum))+'°). '+
        'Esse valor é resultado da linearização, não previsão do giro físico. '+
        ('Com o aviso ativo, a interpretação física da resposta linear fica indisponível. ' if warnings else '')+
        'Triagem salva: '+', '.join(number(v) for v in limits)+' rad; não é limite normativo nem critério de ruptura.']
    if all(r[3]['analysis_domain'].get('intermediate_braces') is False for r in rows):
        lengths = sorted({r[3]['length_mm'] for r in rows})
        if not all(_finite(v) and v > 0 for v in lengths):
            raise ValueError('Vão da análise torsional salvo inválido.')
        lines.append('Vlasov usa o vão salvo de '+', '.join(number(v) for v in lengths)+
            ' mm, sem apoio intermediário. Comprimentos efetivos informados para verificações '
            'de estabilidade não criam vínculos nem encurtam este modelo de torção.')
    if aisi is not None:
        lines.extend(aisi_lines(aisi))
    return dict(warning=bool(warnings), lines=lines)


def saved_notice(result):
    """Fail closed on inconsistent saved data; never repair or hide that fact."""
    try:
        return _saved_lines(result)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        return dict(warning=True, lines=['Aplicabilidade torsional indisponível: registro salvo '
            'inconsistente ('+str(exc)+'). Nenhum resumo quantitativo de giro/G8.1 deste aviso '
            'foi emitido. Confira o arquivo original ou recalcule explicitamente.'])


def show(st, result):
    notice = saved_notice(result)
    if notice is not None:
        (st.error if notice['warning'] else st.warning)(notice['lines'][0])
        for line in notice['lines'][1:]:
            st.warning(line)


def report(doc, result):
    notice = saved_notice(result)
    if notice is not None:
        for line in notice['lines']:
            doc.add_paragraph(line)
