"""Own-reference load lines and separate torsion diagnosis, with no default arm."""
import copy
import html
import math
from .torsion_study import FIELD, SCHEMA, LABELS, ROLES, SCOPE, configuration, blank_choice, section_for
from .presentation import fmt, display_frame


def active_roles(data):
    from .batch import area_bundle
    from .torsion_vlasov.adapter import active_action_roles
    return [r for r in active_action_roles({'load_bundle':area_bundle(data)}) if r in ROLES]


def diagram(section, records):
    """Exact point geometry with separate labels, including coincident lines."""
    import textwrap
    cg=section['properties']['centroid_xy_mm'];sc=section['properties']['shear_center_xy_mm']
    points=[(x-cg[0],y-cg[1]) for x,y in section['nodes_xy_mm']]
    tags=[('CG',0.,0.,'#111827'),('CC',sc[0]-cg[0],sc[1]-cg[1],'#b45309')]
    for role,rec in records.items():
        xy=rec['xy_from_CG_mm']
        if rec['declared'] and rec['origin'].strip() and all(v is not None for v in xy):
            tags.append((role,xy[0],xy[1],'#2563eb'))
    groups={}
    for label,x,y,color in tags:
        if (x,y) not in groups:groups[(x,y)]={'labels':[],'color':color}
        groups[(x,y)]['labels'].append(label)
    coords=points+list(groups)
    xmin=min(x for x,y in coords)-15;xmax=max(x for x,y in coords)+15
    ymin=min(y for x,y in coords)-15;ymax=max(y for x,y in coords)+15
    scale=min(260/(xmax-xmin),240/(ymax-ymin))
    def xy(x,y):return 20+(x-xmin)*scale,50+(ymax-y)*scale
    path=' '.join(('M' if i==0 else 'L')+f'{xy(x,y)[0]:.5f},{xy(x,y)[1]:.5f}' for i,(x,y) in enumerate(points))
    out=['<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Seção Ue, CG, centro de cisalhamento e linhas declaradas" viewBox="0 0 580 350" style="width:100%;max-width:680px;background:#f8fafc;font-family:Arial,sans-serif">',
         '<text x="16" y="20" font-size="12">Seção local: x → abertura, y ↑; coordenadas a partir do CG [mm]</text>',
         f'<path d="{path}" fill="none" stroke="#475569" stroke-width="4"/>']
    label_y=65
    for (x,y),group in groups.items():
        u,v=xy(x,y);color=group['color']
        out.append(f'<path d="M{u:.5f},{v:.5f} L302,{label_y-3} H313" fill="none" stroke="{color}" stroke-width="0.8"/>')
        out.append(f'<circle cx="{u:.5f}" cy="{v:.5f}" r="4" fill="{color}"/>')
        lines=textwrap.wrap(' / '.join(group['labels']),width=33,break_long_words=False)
        for line in lines:
            out.append(f'<text x="318" y="{label_y}" font-size="11" fill="{color}">{html.escape(line)}</text>')
            label_y+=13
        if len(group['labels'])>1:
            out.append(f'<text x="318" y="{label_y}" font-size="10" fill="#475569">Pontos coincidentes declarados</text>');label_y+=13
        label_y+=14
    out.append('<text x="16" y="330" font-size="11">CC = centro de cisalhamento. PP no CG; linhas ausentes não são inferidas.</text></svg>')
    return ''.join(out)


def render_choice(st,data,key):
    c=configuration(data)
    from .roof_top_load import enabled as roof_top_enabled
    if data.get('member_application','purlin')=='purlin' and roof_top_enabled(data):
        st.caption('Declarações manuais anteriores preservadas e inativas neste esquema de cobertura.')
        from .direct_torsion import active as direct_active
        is_direct = direct_active(data)
        if data.get('load_mode')!='area' and not is_direct:
            st.warning('A envoltória conservadora de Me está disponível no esquema de topo, sob suas hipóteses uniaxiais. '
                       'Torção, torque, bimomento e H4 permanecem pendentes no modo direto: ações já combinadas '
                       'não separam PP e cobertura; a força substituta no topo não representa o torque real.')
            return
        st.caption('Linhas de carga definidas automaticamente pelo esquema de cobertura; PP no CG.')
        try:
            from .torsion_study import automatic_roof_choice
            automatic=automatic_roof_choice(data)
            if automatic is None:
                st.caption('Torção pendente: não há contorno torsional próprio coerente para qualificar as linhas horizontais. Excentricidade desconhecida não é torque nulo.')
                return
            if is_direct:
                records = {'EXTERNAL': automatic['load_lines']['CP'], 'P': automatic['load_lines']['P']}
                st.caption('Modo direto separado: PP no CG com 1,25 ELU/1,0 ELS; q e P externos no topo. '
                           'Vlasov preserva todas as componentes; H4 exige o domínio forte uniaxial e fontes AISI disponíveis.')
            else:
                roles=active_roles(data)
                records={r:v for r,v in automatic['load_lines'].items() if r in roles}
            st.markdown(diagram(section_for(data),records),unsafe_allow_html=True)
            st.caption('Geometria e linhas do mesmo contorno próprio; diagnóstico elástico separado, sem capacidade à torção ou aprovação global.')
        except (ValueError,TypeError,KeyError,OSError,ArithmeticError) as exc:
            st.warning('Linhas automáticas de torção pendentes: '+str(exc))
        return
    if data.get('member_application','purlin')=='wall_girt':
        st.caption('Torção da terça inativa na travessa isolada. Declarações armazenadas preservadas; não significam torção nula nem vínculo comprovado.')
        if c is not None:
            with st.expander('Declarações torsionais armazenadas, inativas',expanded=False):st.json(c)
        return
    with st.expander('Torção da terça — linhas de carga e método',expanded=False):
        st.caption(SCOPE)
        enabled=st.checkbox('Analisar torção Vlasov (diagnóstico elástico)',value=bool(c and c['enabled']),key=key+'_enabled')
        if c is None and not enabled:return
        c=copy.deepcopy(c) if c is not None else blank_choice();c['enabled']=enabled
        data[FIELD]=c
        if not enabled:
            st.caption('Modelo desativado; declarações armazenadas preservadas. Não significa torção nula.')
            return
        if data.get('load_mode')!='area':
            st.warning('Diagnóstico de torção pendente no modo direto. O adaptador exige ações por área separadas; não inventa linhas para ações já combinadas.')
            return
        try:roles=active_roles(data)
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
            st.warning('Linhas ativas dependem das ações válidas: '+str(exc));return
        st.caption('PP do perfil: CG, incluído uma única vez. Informe só ações não nulas nas combinações selecionadas. '+
            'x positivo aponta da alma para a abertura; y positivo aponta para cima na seção local. '+
            'A inclinação gira as forças, não essas coordenadas. Campos vazios permanecem não informados.')
        for role in roles:
            old=c['load_lines'].get(role,dict(declared=False,xy_from_CG_mm=[None,None],origin=''))
            declared=st.checkbox('Informar linha — '+LABELS[role],value=old['declared'],key=key+'_'+role+'_declared')
            # Do not append a record merely because its inactive control was drawn.
            if not declared and role not in c['load_lines']:continue
            record=copy.deepcopy(old);record['declared']=declared
            if declared:
                cols=st.columns(2)
                for i,axis in enumerate(('x','y')):
                    value=record['xy_from_CG_mm'][i]
                    with cols[i]:record['xy_from_CG_mm'][i]=st.number_input(
                        role+': '+axis+' a partir do CG [mm]',value=None if value is None else float(value),
                        format='%.6f',key=key+'_'+role+'_'+axis)
                record['origin']=st.text_input('Origem/idealização da linha — '+role,value=record['origin'],key=key+'_'+role+'_origin')
            c['load_lines'][role]=record
        incomplete=[role for role in roles if not (c['load_lines'].get(role,{}).get('declared')
            and c['load_lines'][role]['origin'].strip()
            and all(v is not None for v in c['load_lines'][role]['xy_from_CG_mm']))]
        if incomplete:st.info('Não informado: '+', '.join(incomplete)+'. As combinações que usam essas ações ficam pendentes de torção; a flexão permanece calculável.')
        st.caption('Ao mudar a seção, os offsets declarados em relação ao CG são preservados. Confira a posição física na nova seção; não há ajuste para reduzir o giro.')
        try:st.markdown(diagram(section_for(data),{r:v for r,v in c['load_lines'].items() if r in roles}),unsafe_allow_html=True)
        except (ValueError,TypeError,KeyError,OSError,ArithmeticError) as exc:st.caption('Desenho da seção indisponível: '+str(exc))


def show_result(st,result):
    evidence=result.get('torsion_evidence')
    if not isinstance(evidence,dict):return
    st.subheader('Torção de Vlasov — diagnóstico separado')
    st.warning(SCOPE)
    if evidence.get('reason'):st.warning(evidence['reason'])
    st.caption(str(evidence.get('computed_cases',0))+' combinações calculadas; '+str(evidence.get('pending_model_cases',0))+' pendentes de dados. '+
        'Tsv, Tw e B não alteram as resistências de flexão pura existentes. O complemento longitudinal AISI, quando calculado, aparece separadamente.')
    if evidence.get('pending_numerical_cases'):
        st.error(str(evidence['pending_numerical_cases'])+' combinações não passaram na qualificação numérica. Não foram omitidas nem liberadas como demanda válida.')
    records=evidence.get('records',[])
    if records:
        st.dataframe(display_frame(summary_rows(evidence)),hide_index=True,width='stretch')
        warnings=sum(bool(r.get('analysis',{}).get('small_rotation_warning')) for r in records if isinstance(r.get('analysis'),dict))
        if warnings:st.error(f'{warnings} combinações excedem o aviso de pequeno giro do estudo. A solução linear não é validação física para giros elevados. 0,05 rad é triagem numérica, não limite normativo.')
    with st.expander('Premissas, reações e estados de torção preservados',expanded=False):
        if result.get('schema')=='tercas_three_girt_results_v1' or result.get('input_data',{}).get('member_application','purlin')!='purlin':st.json(evidence)
        elif result.get('schema')=='NBR14762_one_span_v1':st.caption('Consulte os dados salvos em “Exibir memória numérica salva do caso direto” ou no arquivo JSON, sem novo cálculo.')
        else:st.caption('A memória completa está preservada no arquivo JSON. Em “Memória numérica e rastreabilidade”, selecione explicitamente uma combinação para consultar seus dados salvos de torção, sem novo cálculo.')


def summary_rows(evidence):
    rows=[]
    for r in evidence.get('records',[]):
        a=r.get('analysis');row={'Caso':r['combination_id'],'Estado':r['limit_state'],
            'Diagnóstico':'Calculado elástico' if isinstance(a,dict) else 'Qualificação numérica pendente' if r.get('status')=='pending_numerical_qualification' else 'Dados pendentes'}
        if isinstance(a,dict):
            maximum=a['max_abs_phi']
            row.update({'|giro| [rad]':abs(maximum['phi_rad']),'x do giro [mm]':maximum['x_mm'],
                        'Giro elevado (triagem)':a['small_rotation_warning']})
            envelopes=a.get('field_envelopes',{})
            for field,label,scale in [('Tsv_Nmm','|Tsv| [kN·m]',1e6),('Tw_Nmm','|Tw| [kN·m]',1e6),('B_Nmm2','|B| [kN·m²]',1e9)]:
                if envelopes.get(field):row[label]=abs(envelopes[field]['maximum_absolute']['value'])/scale
        else:row['Faltas']='; '.join(r.get('missing',[])).replace('Missing application line/origin for ','Linha/origem não informada: ')
        rows.append(row)
    return rows


def report(doc,result):
    evidence=result.get('torsion_evidence')
    if not isinstance(evidence,dict):return
    doc.add_heading('Torção de Vlasov — demanda elástica separada',1)
    doc.add_paragraph(evidence.get('scope_pt',SCOPE))
    if evidence.get('reason'):doc.add_paragraph(evidence['reason'])
    doc.add_paragraph('Combinações calculadas: '+str(evidence.get('computed_cases',0))+'. Pendentes de dados: '+str(evidence.get('pending_model_cases',0))+'. '+
        'A demanda NBR permanece separada. O complemento longitudinal AISI, quando calculado, tem memória própria e não requalifica os critérios NBR de flexão pura.')
    if evidence.get('pending_numerical_cases'):
        doc.add_paragraph('Qualificação numérica pendente em '+str(evidence['pending_numerical_cases'])+' combinações. Nenhuma resposta inválida foi promovida a demanda qualificada.')
    choice=evidence.get('choice_snapshot',{}).get('load_lines',{})
    if evidence.get('direct_load_basis'):
        doc.add_paragraph(evidence['direct_self_weight']['scope'])
        choice={'EXTERNAL':choice['CP'],'P':choice['P']}
    for role,record in choice.items():
        doc.add_paragraph(role+': '+('linha declarada' if record['declared'] else 'não informada')+
            '; [x,y] a partir do CG [mm]=['+', '.join('não informado' if v is None else fmt(v) for v in record['xy_from_CG_mm'])+']; origem: '+record['origin'])
    for row in summary_rows(evidence):
        doc.add_paragraph(' | '.join(k+': '+(fmt(v) if isinstance(v,(int,float)) and not isinstance(v,bool) else str(v)) for k,v in row.items()))
    doc.add_paragraph('Os extremos listados pertencem a componentes diferentes; não são somados nem constituem uma interação resistente. '+
        'Giros elevados limitam a interpretação da primeira ordem. O aviso 0,05 rad não é limite normativo. '+
        'O JSON registra reações, equilíbrio, hipóteses e estados concomitantes do diagnóstico.')
    from .torsion_material_ui import report as material_report
    material_report(doc,result)
