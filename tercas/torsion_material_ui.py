"""Selected material diagnostic UI and report: no automatic extra solve."""
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING, localcontext
import math
from .presentation import fmt, measurement_text
from .torsion_material import SCOPE, available_cases, preserved_details, deepen

LABELS = {'von_mises': 'Equivalente nominal de von Mises',
          'normal_tension': 'Tração longitudinal na linha média',
          'normal_compression': 'Compressão longitudinal na linha média',
          'shear_absolute': 'Cisalhamento longitudinal-contorno, |τ|'}


def bound(value, upper=False):
    if value is None:return 'não determinado'
    if isinstance(value, bool) or not math.isfinite(value):
        raise ValueError('Limite nominal não finito ou não numérico.')
    decimal = Decimal.from_float(float(value))
    with localcontext() as context:
        context.prec = max(28, len(decimal.as_tuple().digits)+4, decimal.adjusted()+4)
        q = decimal.quantize(Decimal('0.01'),
            rounding=ROUND_CEILING if upper else ROUND_FLOOR)
    return format(q, '.2f').replace('.', ',')


def interval(record, lower='lower_MPa', upper='upper_MPa'):
    return '['+bound(record[lower])+ '; '+bound(record[upper], True)+']'


def text_lines(packet):
    """Human-readable fields of the stored record; never recompute maxima."""
    combo = packet['source_combination']
    lines = [packet['combination_id']+' | '+combo['limit_state']+' | '+measurement_text(combo['expression'])]
    env = packet.get('material_envelope')
    if not isinstance(env, dict):
        return lines+['Detalhe pendente: '+'; '.join(packet.get('missing', []))]
    lines.append('fy nominal do material salvo: '+fmt(env['fy_MPa'])+' MPa; sem coeficiente de resistência.')
    lines.append('Intervalos numéricos exibidos com duas casas e arredondamento externo. O JSON preserva a precisão completa.')
    for field, label in LABELS.items():
        r = env['stress_envelopes'][field];w = r['witness'];s = w['longitudinal_state']
        lines.append(label+': '+interval(r)+' MPa. '+
            ('Intervalo fechado à tolerância numérica.' if r['converged'] else 'Refinamento numérico não fechado.'))
        position = s.get('position_limit')
        if position and 'before P' in position:
            position = 'limite a→0+, antes de P; camada analítica, não elemento de comprimento finito'
        elif not position:
            position = 'seção do modelo'
            if s.get('side') in ('left','right'):
                position += '; lado '+{'left':'esquerdo','right':'direito'}[s['side']]
        lines.append('Testemunha concomitante: x='+fmt(s['x_mm'])+' mm; '+str(position)+
            '; segmento do contorno '+str(w['section_segment_index'])+
            '; face Saint-Venant '+str(w['saint_venant_face_sign'])+'.')
    f = env['proportional_load_to_nominal_material_yield']
    if f['kind'] == 'exact_zero_field':
        lines.append('Campo de ações nulo: nenhum fator finito de início de escoamento nominal foi definido.')
    else:
        lines.append('Fator proporcional até escoamento nominal: '+interval(f, 'lower', 'upper')+'.')
        if f['upper'] is None:
            lines.append('O teto do fator não foi determinado pelos limites numéricos; isso não demonstra capacidade ilimitada.')
    lines.append('O fator escala todas as ações desta combinação, inclusive PP; não aumenta somente vento ou sobrecarga.')
    lines.append('Giro máximo do campo fonte: '+fmt(env['source_max_abs_phi_rad'])+' rad. '+
                 'O fator de escoamento não valida a primeira ordem nem garante que o material seja o primeiro mecanismo de falha.')
    if env['source_small_rotation_warning']:
        lines.append('Giro elevado no campo fonte: interpretação física da primeira ordem limitada. 0,05 rad é triagem numérica, não limite normativo.')
    if not env['all_requested_field_bounds_converged']:
        lines.append('O orçamento numérico não fechou todos os intervalos à tolerância. Limites preservados, sem aprovação.')
    return lines


def render(st, result):
    """Return the same object unless a successful explicit request adds a detail."""
    ids = available_cases(result)
    if not ids and 'torsion_nominal_material_details' not in result:return result
    with st.expander('Tensões concomitantes — diagnóstico nominal', expanded=False):
        st.warning(SCOPE)
        st.caption('A demanda automática acima permanece inalterada. Aprofunde uma combinação por vez; nenhum cálculo adicional ocorre ao consultar ou baixar resultados.')
        if ids:
            fp = result['input_fingerprint']
            cases = {c['combination']['id']: c['combination'] for c in result['cases']}
            selected = st.selectbox('Combinação para detalhar tensões', ids,
                format_func=lambda i: i+' — '+cases[i]['limit_state'], key='nominal_case_'+fp)
            if st.button('Detalhar tensões desta combinação', key='nominal_run_'+fp):
                try:
                    with st.spinner('Calculando somente a combinação selecionada...'):
                        updated = deepen(result, selected)
                except (ValueError, TypeError, KeyError, OSError, ArithmeticError) as exc:
                    st.error('Não foi possível aprofundar este caso. O resultado base foi preservado. '+str(exc))
                else:
                    result = updated
                    st.session_state.result = updated
        try:
            records = preserved_details(result)
            prepared = [(packet, text_lines(packet)) for packet in records.values()]
        except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
            st.error('O anexo nominal salvo é inválido e não foi reproduzido. O resultado base foi preservado; nenhum cálculo foi refeito. '+str(exc));return result
        for packet, lines in prepared:
            st.markdown('**'+packet['combination_id']+' — detalhe solicitado**')
            for line in lines:st.caption(line)
    return result


def report(doc, result):
    try:
        records = preserved_details(result)
        prepared = [(packet, text_lines(packet)) for packet in records.values()]
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        doc.add_heading('Tensões concomitantes — registro nominal inválido', 1)
        doc.add_paragraph('O anexo nominal salvo não foi reproduzido por inconsistência. Os demais dados foram preservados; nenhum cálculo foi refeito e nenhuma qualificação foi acrescentada. '+str(exc))
        return
    if not records:return
    doc.add_heading('Tensões concomitantes — referência nominal de material', 1)
    doc.add_paragraph(SCOPE)
    doc.add_paragraph('Somente as combinações aprofundadas por comando explícito aparecem neste anexo. Ele não altera a demanda automática, as resistências ou o estado global. Os máximos de componentes diferentes têm testemunhas próprias e não são somados.')
    for packet, lines in prepared:
        doc.add_heading(packet['combination_id']+' — detalhe solicitado', 2)
        for line in lines:
            paragraph=doc.add_paragraph(line)
            if (any(line.startswith(label+':') for label in LABELS.values()) or
                    line.startswith(('Fator proporcional até escoamento nominal:',
                        'O teto do fator não foi determinado',
                        'O fator escala todas as ações', 'Giro máximo do campo fonte:'))):
                paragraph.paragraph_format.keep_with_next=True
