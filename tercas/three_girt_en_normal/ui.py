"""Explicit opt-in and read-only saved normal-component display."""
from ..three_girt_scope import view, central, NOTICE
from .application import reference_configuration,saved_component
LABEL='Incluir tensões normais e cisalhamento pela EN'
MODEL_LABEL='Declarar modelo de seção nominal intacta, sem furos ou recortes'
LEVELS={'upper':'Superior','middle':'Central','lower':'Inferior'}


def controls(st,data,demand_fingerprint,prefix):
    if not st.checkbox(LABEL,value=False,key=prefix+'_en_normal_enabled'):return None
    config=reference_configuration(dict(input_fingerprint=demand_fingerprint))
    st.caption('Complemento seccional EN1993-1-3:2006, separado da NBR. Soma N, duas flexões e B na mesma fibra e posição. Apenas componentes com seção efetiva demonstrada no ELU; trechos fora do domínio ficam pendentes. Inclui cisalhamento e interação sigma–tau nos ramos elegíveis; não verifica estabilidade ou ELS.')
    with st.expander('Domínio do complemento normal EN'):
        st.caption('Seção própria Ue100×50×17, ri=t; fyb=fya=250 MPa, E de resistência=210000 MPa, nu=0,3 e gammaM0=1,00. Mantém E e combinações da demanda atual; não representa projeto integral EN. Espessura de cálculo/material reais precisam corresponder ao modelo declarado.')
        config['intact_section_model_declared']=st.checkbox(MODEL_LABEL,value=False,key=prefix+'_en_normal_intact')
        config['section_model_origin']=st.text_input('Origem ou hipótese da seção nominal EN',value='',key=prefix+'_en_normal_origin')
        st.caption('Declaração do modelo da barra, sem inventário nem dimensionamento de ligações. Não substitui ruptura líquida. Ramo com alma comprimida: 2,00/2,25/2,65/3,00/3,35 mm usam prova conservadora de mesa em balanço, sem crédito à rigidez do lábio. Mantém apoio translacional na junção; modos acoplados com translação das junções não estão cobertos. Em 2,00/2,25 mm a alma integral usa Eq.4.4 no estado puro ELU, não tensão de serviço. Em 1,20/1,50 mm usa a alma reduzida descrita abaixo; o sentido real do momento sempre seleciona seu próprio operador.')
        st.caption('N comprimido em 2,00/2,25 mm usa seção efetiva com a faixa central da alma removida, mantendo mesas/lábios integrais. sigmaN=N/Aeff,N; o deslocamento do centroide gera Mx,corr=Mx−Ney e My,corr=My+Nex antes de escolher os ramos de flexão. A rede original e suas reações/rigidezes não são recalculadas.')
        st.caption('N comprimido em 1,20/1,50 mm usa larguras locais e redução distorcional dos dois enrijecedores físicos pelo procedimento EN passos 1–2. A espessura efetiva reduz somente os As retidos, nunca a alma inteira. O transporte N·e continua obrigatório e ocorre uma única vez; os momentos corrigidos escolhem seus próprios ramos efetivos.')
        st.caption('My negativo em 1,50 mm usa alma efetiva reduzida por ponto fixo no ELU e mesas integrais com majorante triangular 149→0 MPa. Em 1,20 mm usa majorante misto 172→−43 MPa da própria mesa, sem crédito ao lábio. Mx± em 1,20 mm usa mesa comprimida localmente reduzida, Ixy e operador afim completos; o As físico permanece integral pela Eq5.17 no ELU normalizado nas faces. Os 42 ramos puros dos sete perfis estão disponíveis neste domínio, sem aprovação global.')
        st.caption('Nas trocas de sinal, coeficientes distintos são cobertos pela união de limites superiores; a testemunha física não é o máximo exato. Limite superior acima de 1 sem testemunha de excesso permanece inconclusivo.')
    return config


def rows(component):
    records=[]
    labels={'within_1_by_full_interval_upper_bound':'Dentro do limite pelo limite superior',
        'above_1_at_concomitant_state':'Excesso normal em estado concomitante',
        'above_1_at_checked_state_full_envelope_incomplete':'Excesso normal em estado verificado; envelope parcial',
        'incomplete_section_branch_coverage':'Parcial: falta ramo de seção efetiva',
        'unresolved_numerical_bound':'Limite numérico não decidiu',
        'within_1_in_declared_section_model':'Dentro do limite normal no modelo',
        'above_1_in_declared_section_model':'Acima do limite normal no modelo'}
    for level,item in component['per_member'].items():
        normal=item.get('normal')
        witness=(normal.get('witness') if normal else item['complete_envelope'] or item['partial_maximum'])
        record=dict(Travessa=LEVELS[level],Cobertura=f"{item['complete_segments']}/{item['ELU_segments']} trechos ELU",
            Envelope='Completo no recorte' if item['complete'] else 'PARCIAL, não é envelope completo',
            Combinação=None if witness is None else witness['combination_id'],
            Resultado=labels.get(item['normal_criterion'],'Não concluído'),
            Ramos_pendentes=', '.join(item['blocking_components']) or 'Nenhum ramo seccional faltante')
        if normal:
            record['Índice_testemunha']=normal['index_lower_witness']
            record['Limite_superior']=normal['index_upper_bound'] if item['complete'] else normal['partial_index_upper_bound']
        else:record['Índice_normal']=None if witness is None else witness['normal_index']
        records.append(record)
    return records


def render_saved(st,demand):
    if demand.get('EN_normal_N_M_B_error'):st.warning('Componente normal EN não calculada: '+demand['EN_normal_N_M_B_error'])
    c=view(saved_component(demand),demand)
    if c is None:return
    st.subheader('Componente normal N+M+B pelo critério EN')
    has_shear=any('shear_interaction' in row for row in c['per_member'].values())
    st.warning('Resultado condicionado ao modelo de seção declarado. Cobertura incompleta de seção efetiva impede conclusão integral; estabilidade da barra e aplicabilidade da primeira ordem permanecem separadas.' if has_shear else 'Resultado histórico somente normal. Cisalhamento e interação sigma–tau não foram calculados neste snapshot.')
    st.dataframe(rows(c),hide_index=True)
    axial=c['component_sections']['components']['N_compression']
    if axial.get('moment_transport_required'):
        st.caption(f"Compressão uniforme com seção efetiva reduzida: Aeff,N={axial['effective_properties']['A_mm2']:.6f} mm²; ex={axial['centroid_shift_from_gross_mm'][0]:.6f} mm. Momentos adicionais por N·e incluídos uma única vez nos momentos corrigidos; sinais e testemunhas usam esses valores.")
    if any('normal' in row for row in c['per_member'].values()):
        st.caption('Normal: testemunha física |sigmaN + sigmaMx + sigmaMy + sigmaB| /250 e limite superior são separados. Só cobertura completa com limite superior ≤1 demonstra atendimento. Limite inferior da testemunha >1 comprova excesso; os demais casos permanecem inconclusivos. Os limites são numéricos em binary64, não certificados formais intervalares.')
    else:
        st.caption('Índice = maior |sigmaN + sigmaMx + sigmaMy + sigmaB| / 250 MPa, nas duas faces de cada segmento facetado. Campos concomitantes e extremos analíticos no vão. Empenamento constante através da espessura: não é solução de sólido curvo exato.')
    st.caption('Pendência de ramo não significa reprovação. Um máximo parcial não é envelope completo. NBR e AISI permanecem separadas; seus denominadores não entram neste índice. O critério de tensões não substitui flambagem por cisalhamento EN §6.1.5 nem interação N–M–V §6.1.10.')
    if has_shear:
        st.subheader('Cisalhamento e interação normal–cisalhamento EN')
        st.dataframe(shear_rows(c),hide_index=True)
        st.caption('Limites: |tau| ≤ 250/√3 MPa e √(sigma² + 3tau²) ≤ 275 MPa. A testemunha usa a mesma estação e fibra; o limite superior cobre continuamente todo o intervalo e a parede, mas não é uma combinação física de máximos. Se a cobertura é parcial, os números abrangem apenas os ramos calculados.')
    with st.expander('Prova seccional e memória normal EN'):
        if has_shear:st.caption('Limites superiores numéricos em binary64, com margem de arredondamento proporcional às magnitudes. Não são certificados formais de aritmética intervalar.')
        st.json(dict(configuration=c['configuration'],material=c['component_sections']['material'],
            component_sections=c['component_sections']['components'],per_member=c['per_member']))


def shear_rows(component):
    labels={'within_1_by_full_interval_upper_bound':'Dentro do limite pelo limite superior',
        'above_1_at_concomitant_state':'Excesso em estado concomitante',
        'above_1_at_checked_state_full_envelope_incomplete':'Excesso verificado; cobertura parcial',
        'incomplete_section_branch_coverage':'Parcial: falta ramo de seção efetiva',
        'unresolved_numerical_bound':'Limite numérico não decidiu'}
    records=[]
    for level,item in component['per_member'].items():
        values=item.get('shear_interaction')
        if values is None:continue
        for key,name in (('shear','Cisalhamento'),('interaction','Interação sigma–tau')):
            row=values[key]
            records.append(dict(Travessa=LEVELS[level],Critério=name,
                Índice_testemunha=None if row is None else row['index_lower_witness'],
                Limite_superior=None if row is None else row['index_upper_bound'] if values['complete'] else row['partial_index_upper_bound'],
                Cobertura='Completa no recorte' if values['complete'] else 'PARCIAL',
                Resultado='Sem ramo elegível' if row is None else labels[row['criterion']]))
    return records
