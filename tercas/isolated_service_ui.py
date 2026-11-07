"""Explicit point/direction/criterion choices and saved combined-service output."""
import copy
import math
from . import isolated_service_component as c


def controls(st,data,key):
    if data.get('member_application','purlin')!='purlin' or data.get('three_girt_model',{}).get('enabled'):return
    raw=c.configuration(data)
    with st.expander('ELS combinado: deslocamento no ponto de serviço',expanded=False):
        st.caption('Flexão biaxial e torção no mesmo campo linear, com crivo MLE suficiente das cinco paredes. Seleção opcional explícita; não altera a flecha uniaxial já escolhida.')
        enabled=st.checkbox('Calcular deslocamento combinado no ponto declarado',value=bool(raw and raw['enabled']),key=key+'_enabled')
        if raw is None and not enabled:return
        out=copy.deepcopy(raw) if raw else c.blank_choice()
        if raw is None:
            # Reuse the already selected nominal model, visibly and editably.
            from .torsion_study import section_for
            try:
                section_for(data);out['nominal_intact_section_declared']=True
            except (ValueError,TypeError,KeyError,OSError):pass
        out['enabled']=enabled;data[c.CHOICE]=out
        if not enabled:return
        st.caption('Requer contorno próprio Ue e demanda Vlasov do mesmo vão. O índice exibido é condicional ao campo linear; não é aprovação física de grande giro.')
        point=st.selectbox('Ponto do deslocamento', ['Não selecionado','CG','Ponto da linha de carga no topo','Coordenadas explícitas a partir do CG'],
            index=({'CG':1,'Ponto da linha de carga no topo':2}.get(out['point_label'],3 if out['point_label'] else 0)),key=key+'_point')
        if point=='CG':out['point_xy_from_CG_mm']=[0.,0.];out['point_label']=point
        elif point=='Ponto da linha de carga no topo':
            try:
                from .roof_top_load import geometry
                g=geometry(data)
                if not g['coherent_torsion_section']:raise ValueError('Contorno próprio necessário.')
                out['point_xy_from_CG_mm']=[g['x_from_CG_mm'],g['y_from_CG_mm']];out['point_label']=point
            except (ValueError,TypeError,KeyError) as exc:
                out['point_xy_from_CG_mm']=[None,None];out['point_label']=point;st.caption(str(exc))
        elif point=='Coordenadas explícitas a partir do CG':
            out['point_label']=st.text_input('Identificação do ponto de serviço',value=out['point_label'] if out['point_label'] not in ('CG','Ponto da linha de carga no topo') else '',key=key+'_point_label')
            for i,axis in enumerate(('x para abertura','y para cima')):
                out['point_xy_from_CG_mm'][i]=st.number_input('Ponto: '+axis+' a partir do CG [mm]',value=out['point_xy_from_CG_mm'][i],format='%.6f',key=key+'_point_'+str(i))
        else:out['point_label']='';out['point_xy_from_CG_mm']=[None,None]
        labels=['Não selecionada','Vertical global','Normal local à cobertura','Vetor explícito nos eixos locais']
        current=labels.index(out['direction_label']) if out['direction_label'] in labels else 0
        direction=st.selectbox('Direção a comparar',labels,index=current,key=key+'_direction')
        out['direction_label']='' if direction==labels[0] else direction
        if direction=='Normal local à cobertura':out['projection_xy']=[0.,-1.]
        elif direction=='Vertical global':
            from .inclination_adapter import configuration
            _,ang=configuration(data);theta=ang['radians']
            out['projection_xy']=[math.sin(theta),-math.cos(theta)]
        elif direction=='Vetor explícito nos eixos locais':
            for i,axis in enumerate(('x','y')):
                out['projection_xy'][i]=st.number_input('Direção unitária: '+axis,value=out['projection_xy'][i],format='%.9f',key=key+'_direction_'+str(i))
        else:out['projection_xy']=[None,None]
        out['reference_declared']=st.checkbox('Comparar relativamente à corda dos extremos físicos do mesmo ponto',value=out['reference_declared'],key=key+'_chord')
        choices=[None,'nbr_A1_pair','declared_limit']
        names={None:'Selecione o critério','nbr_A1_pair':'NBR Tabela A.1: rara de mesmo sentido L/180 e sucção característica isolada L/120',
               'declared_limit':'Limite declarado para as combinações ELS já selecionadas'}
        out['criterion']=st.selectbox('Critério de deslocamento',choices,index=choices.index(out['criterion']),format_func=lambda v:names[v],key=key+'_criterion')
        if out['criterion']=='nbr_A1_pair':
            st.caption('Notas e/f: o caso de sucção é calculado separadamente, sem PP/CP e sem alterar a matriz fornecida. Defina a parcela de deslocamento e confira as combinações raras selecionadas. Empoçamento permanece avaliação própria da cobertura.')
        if out['criterion']=='declared_limit':out['limit_mm']=st.number_input('Limite declarado [mm]',value=out['limit_mm'],min_value=0.,format='%.6f',key=key+'_limit')
        out['criterion_origin']=st.text_input('Parcela do deslocamento, aplicação e origem do critério',value=out['criterion_origin'],key=key+'_criterion_origin')
        out['nominal_intact_section_declared']=st.checkbox('Adotar a seção nominal íntegra, sem furos ou recortes, neste modelo de serviço',value=out['nominal_intact_section_declared'],key=key+'_intact')
        out['model_origin']=st.text_input('Origem e identificação do modelo de serviço',value=out['model_origin'],key=key+'_origin')
        missing=c.missing_configuration(out)
        if missing:st.caption('Ainda necessário: '+'; '.join(missing))


def rows(record):
    out=[]
    labels={'within_declared_linear_model':'Atende no campo linear declarado',
            'above_declared_linear_model':'Excede no campo linear declarado',
            'numerical_boundary_inconclusive':'Pendente na fronteira numérica',
            'gross_MLE_sufficient_condition_inconclusive':'Crivo suficiente MLE inconclusivo'}
    for r in record['records']:
        check=r['comparison'];row={'Caso':r['id'],'Situação':r['reason'] or r['status']}
        if check:
            row.update({'Situação':labels[check['criterion_status']],
                'Deslocamento: limite superior [mm]':check['envelope']['abs_displacement_upper_mm'],
                'Limite [mm]':check['limit_mm'],'Índice superior no campo linear':check['index_upper'],
                'Índice inferior no campo linear':check['index_lower'],
                'x testemunha [mm]':check['envelope']['witness']['station_mm']})
        out.append(row)
    return out


def show(st,result):
    try:record=c.saved(result)
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:st.warning('Serviço combinado não exibido: '+str(exc));return
    if record is None:return
    st.subheader('ELS combinado no ponto declarado')
    st.caption(record['scope'])
    if record['missing']:st.warning('; '.join(record['missing']))
    st.caption('Ponto: '+record['configuration']['point_label']+'. Direção: '+record['configuration']['direction_label']+'. Corda dos extremos físicos do mesmo ponto.')
    if record['records']:st.dataframe(rows(record),hide_index=True)
    st.caption('Limite superior ≤1 é suficiente no campo linear; limite inferior >1 demonstra excesso nesse campo. Crivo MLE inconclusivo deixa índice ausente, sem concluir falha física. Nenhum limite angular normativo foi criado.')


def report(doc,result):
    try:record=c.saved(result)
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:doc.add_paragraph('Serviço combinado não exibido: '+str(exc));return
    if record is None:return
    doc.add_heading('ELS combinado no ponto declarado',1);doc.add_paragraph(record['scope'])
    cfg=record['configuration']
    doc.add_paragraph('Ponto: '+cfg['point_label']+'; direção: '+cfg['direction_label']+'; referência: corda dos extremos físicos do mesmo ponto. '+cfg['criterion_origin'])
    for reason in record['missing']:doc.add_paragraph(reason)
    for row in rows(record):doc.add_paragraph(' | '.join(str(k)+': '+str(v) for k,v in row.items()))
    doc.add_paragraph('Índices condicionais ao campo linear e ao crivo MLE. Não aprovam estabilidade, empoçamento nem a interpretação física de grande giro.')
