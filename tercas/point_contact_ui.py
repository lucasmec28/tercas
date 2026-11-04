"""Explicit contact declarations, separate from legacy/reference inputs.

Merely opening this panel never adds a choice or manufactures physical data.
All mutations precede the existing input fingerprint and export snapshots.
"""
import copy
from .point_contact import FIELD, DECLARATIONS, blank_choice, configuration, reference_basis, basis_matches

LABEL = 'Declarar contato local da carga P interna'
TITLE = 'Contato local de P — opt-in com declarações físicas'
C_LABEL = 'Comprimento real de contato c [mm]'
ORIGIN_LABEL = 'Origem: detalhe do contato de P e identificação dos dois apoios'


def render(st, data, key, disabled=False):
    """Edit only FIELD in place; preserve unavailable and invalid input verbatim."""
    with st.expander(TITLE, expanded=False):
        st.caption('Esta opção descreve um detalhe local de transmissão de P e não altera as declarações existentes sobre telha/painel. Não presume contato, ligação, distribuição de P ou travamento fornecido pela telha.')
        st.caption('Somente introdução local de P interna por compressão. Não altera ações, flexão, FLT, flechas AA/AISI, torção ou vínculos; não qualifica os apoios nem aprova o elemento.')
        st.caption('NBR 14762:2010 §9.5.1, Anexo D, Tabela D.2/Figura D.1. Limites desta rota: c ≥ 20 mm; h/t ≤ 200; c/t ≤ 210; c/h ≤ 2; ri/t ≤ 5 para Ue e ≤ 1 para U. A geometria e as distâncias são verificadas pelo cálculo, não presumidas por esta seleção.')
        st.caption('h é a altura plana da alma: H − 2(ri + t). O contato é centrado na posição x de P; a borda carregada deve ficar a mais de 1,5h de cada extremo físico declarado. Nenhuma distância até força na mesa oposta é inventada.')
        st.warning('P no apoio-limite, P paralelo não nulo e sistema 3D permanecem fora da liberação. As declarações não resolvem a introdução de força nos apoios.')
        if disabled:
            st.checkbox(LABEL, value=False, key=key+'_unavailable', disabled=True)
            st.caption('Contato local indisponível no sistema 3D. O objeto de entrada existente permanece preservado e inativo nesta rota.')
            return
        try:
            configuration(data)
        except (ValueError, TypeError, KeyError) as exc:
            st.warning('Declaração importada preservada sem edição: '+str(exc))
            return
        previous = copy.deepcopy(data.get(FIELD))
        choice = copy.deepcopy(previous) if previous is not None else blank_choice()
        selected = st.checkbox(LABEL, value=choice['enabled'], key=key+'_enabled')
        if not selected:
            if previous is not None and previous['enabled']:
                choice['enabled'] = False
                data[FIELD] = choice
            return
        choice['enabled'] = True
        choice['c_mm'] = st.number_input(C_LABEL, value=None if choice['c_mm'] is None else float(choice['c_mm']), key=key+'_c_mm', format='%.6f')
        choice['origin'] = st.text_input(ORIGIN_LABEL, value=choice['origin'], key=key+'_origin', max_chars=2000)
        st.caption('Campos vazios e caixas desmarcadas significam dados não declarados. Nenhuma dimensão de contato, apoio ou caminho de força é inferida. Marque somente condições verificadas para a peça e para o carregamento atual.')
        for name, label in DECLARATIONS.items():
            previous_declaration = choice['declarations'][name]
            choice['declarations'][name] = st.checkbox(label, value=previous_declaration, key=key+'_'+name)
            if name == 'section_geometry_and_material_verified' and not previous_declaration and choice['declarations'][name]:
                try:
                    choice['basis'] = reference_basis(data)
                except (ValueError, TypeError, KeyError) as exc:
                    st.warning('Não foi possível registrar a referência física da declaração: '+str(exc))
        data[FIELD] = choice
        if choice['declarations']['section_geometry_and_material_verified'] and not basis_matches(data, choice):
            st.warning('Geometria, material, aplicação, vão ou posição de P mudaram desde a declaração. O contato permanece pendente: confira os dados atuais, desmarque e reconfirme a declaração de geometria/material. Dados anteriores preservados.')


RESULTS_TITLE = 'Introdução local de P — resultados salvos'

def show_saved_results(st, result):
    """Display saved local evidence only; never validate or rerun a calculation."""
    if result.get('schema') not in ('NBR14762_one_span_v1', 'tercas_batch_results_v1'):
        return
    data = result.get('input_data', {})
    cfg = data.get(FIELD) if isinstance(data, dict) else None
    if not isinstance(cfg, dict) or cfg.get('enabled') is not True:
        return
    from .point_contact import saved_records
    from .presentation import display_frame
    records = saved_records(result)
    with st.expander(RESULTS_TITLE, expanded=False):
        st.caption('Somente o critério de introdução local de P registrado no cálculo salvo. Não aprova ligações, apoios ou o elemento completo. Consultar este bloco não recalcula nem requalifica o histórico.')
        st.caption('P no apoio-limite e P paralelo não nulo permanecem pendentes. Um registro histórico sem vínculo com as declarações salvas não recebe resistência ou índice novo.')
        if not records:
            st.caption('Não há caso ELU com força P real nos registros disponíveis para este bloco.')
            return
        statuses = {'computed': 'Calculado — critério local', 'not_evaluated': 'Pendente',
                    'pending': 'Pendente', 'not_applicable': 'Não aplicável'}
        view = [{'Combinação': row.get('combination_id'),
                 'P normal [N]': row.get('P_normal_N'),
                 'P paralelo [N]': row.get('P_parallel_N'),
                 'c [mm]': row.get('c_mm'),
                 'FRd [N]': row.get('FRd_N'),
                 'Índice': row.get('index'),
                 'Situação local': statuses.get(row.get('status'), row.get('status')),
                 'Motivo / alcance': row.get('reason')} for row in records]
        st.dataframe(display_frame(view), hide_index=True, width='stretch')
