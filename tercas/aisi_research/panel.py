"""Independent research UI; only namespaced session keys are read or written."""
from . import adapter as a

PREFIX = 'tercas_aisi_research_'
RESULT = PREFIX + 'result'


def technical(value):
    return format(float(value), '.10g')


def clear_result(state):
    state.pop(RESULT, None)


def render(st):
    with st.expander('Pesquisa AISI 2024 — comparador longitudinal isolado', expanded=False):
        st.caption('Não segue seção, vão, material, cargas ou combinações do projeto atual. '
                   'As escolhas abaixo são independentes e não entram na memória Word ou nas contagens do projeto.')
        st.warning(a.WARNING)
        enabled = st.toggle('Ativar pesquisa isolada AISI 2024', key=PREFIX + 'enabled', value=False)
        if not enabled:
            clear_result(st.session_state)
            return
        try:
            a.verify_bundle()
            st.caption(a.SCOPE)
            st.caption(a.LOAD_NOTE)
            st.caption('Material AISI fixo: E=203000 MPa; G=78000 MPa; ν=0,30; Fy=250 MPa. '
                       'φb=φB=0,90; β=Cb=1. Sem benefício inelástico de Bp. '
                       'Nenhum MRd NBR ou material do projeto é reutilizado.')
            c1, c2, c3 = st.columns(3)
            with c1:
                thickness = st.selectbox('Seção própria AISI — espessura [mm]', a.THICKNESSES,
                    format_func=lambda t: f'Ue100×50×17×{t:.2f}; ri=t', key=PREFIX + 'thickness',
                    on_change=clear_result, args=(st.session_state,))
            with c2:
                length = st.selectbox('Vão próprio AISI [mm]', a.LENGTHS,
                    format_func=lambda value: f'{value / 1000:g} m', key=PREFIX + 'length',
                    on_change=clear_result, args=(st.session_state,))
            with c3:
                factor = st.selectbox('Carga congelada AISI', a.FACTORS,
                    format_func=lambda value: 'PP isolado × 1 (não combinação)' if value == 1 else 'Controle matemático: 1% do PP',
                    key=PREFIX + 'factor', on_change=clear_result, args=(st.session_state,))
            a.selection(thickness, length, factor)
            if RESULT in st.session_state:
                try:
                    a.validate_snapshot(st.session_state[RESULT], thickness, length, factor)
                except (ValueError, TypeError, KeyError, ArithmeticError):
                    clear_result(st.session_state)
                    st.warning('Resultado AISI anterior retirado por incompatibilidade. Calcule explicitamente outra vez.')
            c1, c2 = st.columns(2)
            with c1:
                clicked = st.button('Calcular índice longitudinal AISI', key=PREFIX + 'calculate')
            with c2:
                cancelled = st.button('Limpar resultado AISI', key=PREFIX + 'clear')
            if cancelled:
                clear_result(st.session_state)
            elif clicked:
                clear_result(st.session_state)
                st.session_state[RESULT] = a.evaluate(thickness, length, factor)
            if RESULT not in st.session_state:
                st.caption('Sem resultado AISI ativo. Desativar ou alterar uma escolha retira somente este resultado.')
                return
            snapshot = st.session_state[RESULT]
            # Export validates again before rendering any saved result or download.
            exported = a.export_json(snapshot, thickness, length, factor)
            record = snapshot['record']; flex = record['flexure']; terms = record['H4_terms_using_flexural_floor']
            st.subheader('Índice longitudinal condicional com piso conservador')
            st.write(f"|Mx|/Ma,piso + |B|/Ba = {terms['Mx']:.8f} + {terms['B']:.8f} = {record['H4_ratio_upper']:.8f}")
            st.caption('Referência algébrica H4: 1,00, condicionada à aplicabilidade restante. '
                       'Não é índice global de utilização nem aprovação da peça. '
                       'My transversal é zero; Mx e B são concomitantes no meio deste vão ideal.')
            st.dataframe([
                {'Grandeza': 'Mx no meio do vão [N·mm]', 'Valor': technical(record['required_midspan']['Mx_magnitude_Nmm'])},
                {'Grandeza': 'B no meio do vão [N·mm²]', 'Valor': technical(record['required_midspan']['B_Nmm2'])},
                {'Grandeza': 'Giro no meio do vão [rad]', 'Valor': technical(record['required_midspan']['phi_rad'])},
                {'Grandeza': 'Ma,piso [N·mm]', 'Valor': technical(flex['Ma_floor_Nmm'])},
                {'Grandeza': 'Ba = 0,90·By [N·mm²]', 'Valor': technical(record['bimoment']['Ba_Nmm2'])},
            ], hide_index=True, width='stretch')
            st.caption('Na derivação abaixo, M_esc = Fy·Wx é o momento de início de escoamento '
                       'na flexão forte (primeira fibra exterior), distinto do momento transversal My. '
                       'P, L e D são parcelas auxiliares do piso, não cargas ou comprimentos.')
            st.caption('Derivação: P=M_esc·(1−0,25·M_esc/Mcre) se Mcre>M_esc/2, senão P=Mcre; '
                       'L=P/(1+0,55·P/Mcrl); D=M_esc/(1+0,60·M_esc/Mcrd); '
                       'Ma,piso=0,90·min(P,L,D). Ba=0,90·Fy·Cw/max|ω|. '
                       'O piso depende dos mesmos dados elásticos elegíveis F2/F3/F4; não é fórmula literal de capacidade.')
            with st.expander('Propriedades fixas, fatores e proveniência AISI', expanded=False):
                row = snapshot['fixed_input_snapshot']; p = row['properties']
                st.caption('Geometria própria, não produto comercial certificado: ' + row['profile_id'])
                st.dataframe([{'Propriedade': label, 'Valor': technical(value)} for label, value in [
                    ('A [mm²]', p['A_mm2']), ('Ix [mm⁴]', p['Ix_strong_mm4']),
                    ('Iy [mm⁴]', p['Iy_weak_mm4']), ('J [mm⁴]', p['J_mm4']), ('Cw [mm⁶]', p['Cw_mm6']),
                    ('max|ω| [mm²]', record['bimoment']['omega_max_mm2']),
                    ('CG−SC horizontal [mm]', record['CG_minus_SC_mm'][0]),
                    ('Mcre [N·mm]', flex['Mcre_Nmm']), ('Mcrl [N·mm]', flex['Mcrl_Nmm']), ('Mcrd [N·mm]', flex['Mcrd_Nmm']),
                    ('Carga vertical [N/mm]', record['declared_uniform_force_N_mm'][1])]], hide_index=True, width='stretch')
                st.caption(snapshot['source_material_note'])
                st.caption('Fontes incorporadas e conferidas por SHA-256. Matrizes FSM originais têm pins e recibo de escala; '
                           'não são resolvidas novamente por este painel. Não há importação da pasta externa de pesquisa.')
                st.markdown('[AISI 2024 oficial: F2.2/F3.2/F4, G8.1 e H4](' + snapshot['provenance']['official_reference'] + ')')
                st.caption('C1, cisalhamento, serviço e condições reais continuam pendentes.')
                st.json(snapshot)
            st.warning(a.WARNING)
            st.download_button('Baixar somente pesquisa AISI (JSON)', exported,
                file_name='pesquisa_AISI2024_isolada.json', mime='application/json', key=PREFIX + 'download')
        except (OSError, ValueError, TypeError, KeyError, ArithmeticError, ImportError, RuntimeError) as exc:
            clear_result(st.session_state)
            st.error('Pesquisa AISI indisponível: ' + str(exc) + ' Somente o resultado AISI foi retirado.')
