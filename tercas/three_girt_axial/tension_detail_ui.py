"""Simple, optional common connection-detail controls and saved trace."""
from .tension_detail import blank_detail,WELD_U_MODE

OPTIONS={'Manual: An0, An e Ct auditados':None,
         'Solda da mesa inferior no topo da viga':'lower_flange_weld',
         'Duas soldas longitudinais na mesa: Ct de U para Ue (hipótese)':WELD_U_MODE,
         'Parafusos na alma, uma fileira vertical':'web_bolt_single_transverse_row'}
WELDS={'A definir':'undefined','Somente transversais':'transverse_only',
       'Longitudinais':'longitudinal','Longitudinais e transversais':'mixed'}


def controls(st,config,prefix):
    selected=st.selectbox('Forma de informar a ligação para tração',list(OPTIONS),key=prefix+'_nbr_detail_mode')
    mode=OPTIONS[selected]
    previous_key=prefix+'_nbr_detail_previous_mode'
    previous=st.session_state.get(previous_key)
    if mode!=previous and WELD_U_MODE in (mode,previous):
        # Session persistence can retain hidden widgets. A new visit to this
        # extrapolated branch must not inherit former dimensions or acceptance.
        branch_prefix=prefix+'_nbr_detail_'+WELD_U_MODE
        for key in list(st.session_state):
            if str(key).startswith(branch_prefix):del st.session_state[key]
    st.session_state[previous_key]=mode
    if mode is None:return False
    detail=blank_detail(mode);config['tension_connection']=detail;t=config['tension']
    k=prefix+'_nbr_detail_'+mode
    st.caption('Um detalhe comum para a referência de tração, sem inventário de ligações. Esta escolha não altera vínculos mecânicos, esforços ou o dimensionamento de soldas/parafusos.')
    outside=st.selectbox('Seção fora das ligações', ['An0 auditado','Sem furos ou recortes, confirmar'],key=k+'_outside')
    if outside=='An0 auditado':
        t['An0_mm2']=st.number_input('An0 fora da ligação [mm²]',min_value=.001,value=None,key=k+'_an0')
    else:
        detail['outside_mode']='confirmed_unperforated'
        detail['outside_unperforated_confirmed']=st.checkbox('Confirmo ausência de furos e recortes fora das ligações',value=False,key=k+'_outside_confirm')
        st.caption('An0=A somente após esta confirmação e a indicação da origem. Isso não é inferido pela escolha do vínculo.')
    t['outside_area_origin']=st.text_input('Origem de An0 e caminhos fora da ligação',value='',key=k+'_outside_origin')
    g=detail['geometry']
    if mode=='web_bolt_single_transverse_row':
        g['count']=st.number_input('Parafusos na vertical',min_value=1,max_value=20,value=2,step=1,key=k+'_count')
        ds={'Selecione o diâmetro':None,'Ø1/2″ (12,7 mm)':12.7,'Ø5/8″ (15,875 mm)':15.875}
        g['diameter_mm']=ds[st.selectbox('Diâmetro nominal do parafuso',list(ds),key=k+'_diameter')]
        if g['count']>1:g['pitch_mm']=st.number_input('Passo vertical regular entre centros [mm]',min_value=.001,value=None,key=k+'_pitch')
        st.caption('Folga diametral adotada: 2 mm. Furo de 14,7 mm para 1/2″ e 17,875 mm para 5/8″. É furo circular alargado: a Tabela 15 dá d+1,5 mm para furo-padrão nesses diâmetros. Ramo automático limitado a t≤4,75 mm, conforme o domínio suficiente de §10.3.1. A conformidade completa do detalhe não é verificada aqui.')
        g['single_row_in_flat_web_confirmed']=st.checkbox('Confirmo uma única fileira vertical, na mesma seção transversal, inteiramente na alma plana',value=False,key=k+'_row_confirm')
        g['no_other_losses_confirmed']=st.checkbox('Confirmo que esta seção não possui outros furos ou recortes',value=False,key=k+'_loss_confirm')
        st.caption('An=0,9[A−n(d+2)t]. Ct usa a chapa equivalente desdobrada, incluindo mesas, curvas e lábios: g=max[p,A/t−(n−1)p]. Para um só parafuso, g=A/t. Dois parafusos verticais não são dois parafusos na direção da força.')
        st.warning('O desconto dos furos é aplicado somente à tração axial. Não atualiza flexão, torção ou o modelo de seção intacta EN; esses resultados não verificam a região perfurada.')
    elif mode==WELD_U_MODE:
        st.warning('Hipótese extrapolada: expressão de Ct do U com soldas longitudinais aplicada ao Ue ligado apenas pela mesa. Não é uma regra normativa explicitamente demonstrada para este detalhe de Ue.')
        st.caption('Ct=min(1−0,36x/L; 0,9). Resultado calculado inferior a 0,5 torna o detalhe inadmissível nesta hipótese; o app não o eleva a 0,5. An=A somente para seção sem perdas.')
        g['length_mm']=st.number_input('L: comprimento longitudinal de cada cordão [mm]',min_value=.001,value=None,key=k+'_length')
        g['eccentricity_mm']=st.number_input('x: distância perpendicular do centróide do Ue ao plano da ligação [mm]',min_value=0.,value=None,key=k+'_eccentricity')
        st.caption('Use o centróide da seção Ue completa, incluindo lábios e dobras, e o plano real de conexão da mesa. Não reutilize x de ligação pela alma. L é o comprimento de cada cordão, não a soma dos dois.')
        g['two_equal_continuous_longitudinal_welds_confirmed']=st.checkbox('Confirmo dois cordões longitudinais contínuos de igual comprimento na mesma mesa, sem transversais',value=False,key=k+'_two_welds')
        g['no_holes_or_losses_confirmed']=st.checkbox('Confirmo seção da ligação sem furos, recortes ou outras perdas',value=False,key=k+'_no_losses')
        g['extrapolation_accepted']=st.checkbox('Adoto a hipótese extrapolada de Ct de U para Ue ligado pela mesa',value=False,key=k+'_hypothesis')
    else:
        g['arrangement']=WELDS[st.selectbox('Orientação dos cordões da mesa inferior',list(WELDS),key=k+'_arrangement')]
        if g['arrangement']=='transverse_only':
            g['An_mm2']=st.number_input('Área bruta somente das partes efetivamente conectadas [mm²]',min_value=.001,value=None,key=k+'_transverse_area')
            st.caption('Somente cordões transversais: Ct=1 pelo §9.6.2. An é somente a área das partes conectadas, não a área total do Ue. Identifique essa parte na origem do detalhe.')
        elif g['arrangement'] in ('longitudinal','mixed'):
            bk=k+'_'+g['arrangement']
            g['An_mm2']=st.number_input('An auditado para a solda da mesa inferior [mm²]',min_value=.001,value=None,key=bk+'_an')
            g['Ct']=st.number_input('Ct auditado para a solda da mesa inferior',min_value=.001,max_value=1.,value=None,key=bk+'_ct')
            g['length_mm']=st.number_input('Comprimento longitudinal efetivo da ligação [mm]',min_value=.001,value=None,key=bk+'_length')
            g['eccentricity_mm']=st.number_input('Excentricidade entre centróide e plano da ligação [mm]',min_value=0.,value=None,key=bk+'_eccentricity')
            g['ct_origin']=st.text_input('Método e justificativa do Ct da mesa inferior',value='',key=bk+'_ct_origin')
            st.caption('Esta rota conserva An e Ct auditados. Para adotar a expressão de U como hipótese extrapolada para Ue, selecione a opção separada de duas soldas longitudinais na mesa.')
        else:st.info('Defina a orientação dos cordões. A escolha soldada, sozinha, não define An nem Ct.')
    detail['origin']=st.text_input('Origem e descrição do detalhe para tração',value='',key=k+'_origin')
    detail['reference_scope_confirmed']=st.checkbox('Confirmo que os dados informados representam a referência comum de tração das três travessas',value=False,key=k+'_scope_confirm')
    return True


def render_saved(st,tension):
    r=tension.get('connection_detail')
    if r is None:return
    st.caption('Detalhe de tração: '+('fileira vertical de parafusos na alma' if r['input']['mode']=='web_bolt_single_transverse_row' else 'solda apenas na mesa inferior')+'. Resistência da ligação não verificada.')
    d=r['derived']
    if d:
        ct='inadmissível' if d['Ct'] is None else f"{d['Ct']:.6f}"
        st.caption(f"An calculado/declarado = {d['An_mm2']:.4f} mm²; Ct = {ct}. "+('Dados confirmados para a referência.' if not r['missing'] else 'Prévia: há declarações/dados pendentes; Nt,Rd não foi liberado.'))
        if d.get('extrapolated_hypothesis'):
            st.warning(f"Hipótese extrapolada U → Ue pela mesa: Ct bruto = {d['raw_Ct']:.8f}; teto 0,9. L por cordão = {d['length_mm']:.4f} mm; x do centróide completo ao plano = {d['eccentricity_mm']:.4f} mm. An=A, sem fator 0,9 na área.")
            if not d['Ct_admissible']:st.error('Ct calculado < 0,5: detalhe inadmissível nesta hipótese. Nt,Rd não liberado; nenhum piso artificial foi aplicado.')
        if 'g_effective_mm' in d:st.caption(f"Largura desenvolvida A/t = {d['developed_width_mm']:.4f} mm; e1+e2 = {d['developed_edge_sum_mm']:.4f} mm; g efetivo = {d['g_effective_mm']:.4f} mm; furo real adotado = {d['hole_diameter_mm']:.4f} mm.")
    if r['missing']:st.info('Pendências do detalhe de tração: '+'; '.join(r['missing']))


def append_report(doc,tension):
    r=tension.get('connection_detail')
    if r is None:return
    doc.add_heading('Detalhe simples da referência de tração',2)
    doc.add_paragraph('Origem: '+(r['input']['origin'] or 'não informada')+'. Um detalhe comum, sem inventário de ligações. A escolha não altera os vínculos mecânicos ou esforços do modelo.')
    an0=r['inputs']['An0_mm2']
    doc.add_paragraph('An0 fora das ligações = '+('pendente' if an0 is None else f'{an0:.6f} mm²')+'. Origem: '+(r['inputs']['outside_area_origin'] or 'não informada')+'.')
    d=r['derived']
    if d:
        ct='inadmissível' if d['Ct'] is None else f"{d['Ct']:.8f}"
        doc.add_paragraph(f"An = {d['An_mm2']:.6f} mm²; Ct = {ct}. "+('Dados confirmados para a referência.' if not r['missing'] else 'Prévia incompleta; não libera Nt,Rd.'))
        if 'g_effective_mm' in d:
            pitch='não se aplica' if d['vertical_pitch_mm'] is None else f"{d['vertical_pitch_mm']:.6f} mm"
            doc.add_paragraph(f"Uma seção transversal: n = {d['bolt_count']}; d = {d['bolt_diameter_mm']:.6f} mm; df = d+2 = {d['hole_diameter_mm']:.6f} mm; t = {d['t_mm']:.6f} mm; passo vertical = {pitch}. An = 0,9[A - n df t].")
            doc.add_paragraph(f"Chapa equivalente da Fig.4b: B = A/t = {d['developed_width_mm']:.6f} mm, incluindo mesas, curvas e lábios; e1+e2 = {d['developed_edge_sum_mm']:.6f} mm; g = {d['g_effective_mm']:.6f} mm. Ct = min(2,5d/g; 1). Não é a regra de duas posições longitudinais de parafusos.")
            doc.add_paragraph('Furo circular alargado real adotado: folga 2 mm. Para estes diâmetros, a Tabela 15 especifica d+1,5 mm como furo-padrão. O ramo automático é limitado a t do perfil <= 4,75 mm, condição suficiente do domínio de §10.3.1. As checagens geométricas locais são necessárias, mas não verificam todas as distâncias, o furo executado ou a ligação.')
        else:
            doc.add_paragraph('Arranjo de solda: '+d['weld_arrangement']+'. '+d['clause']+'.')
            if d['weld_arrangement']!='transverse_only':doc.add_paragraph(f"Comprimento longitudinal = {d['length_mm']} mm; excentricidade = {d['eccentricity_mm']} mm. Origem do Ct: {d['ct_origin']}.")
            if d.get('extrapolated_hypothesis'):
                doc.add_paragraph(f"Hipótese extrapolada: Ct de U com soldas longitudinais aplicado a Ue ligado pela mesa. Ct=min(1-0,36x/L; 0,9); valor bruto calculado = {d['raw_Ct']:.10f}. Ct inferior a 0,5 é inadmissível, nunca elevado a 0,5. Aplicabilidade normativa específica ao detalhe Ue não demonstrada.")
                doc.add_paragraph('Dois cordões longitudinais contínuos de igual comprimento na mesma mesa, sem transversais. L é o comprimento de cada cordão, não a soma. x é a distância perpendicular do centróide completo do Ue, incluindo lábios e dobras, ao plano real da conexão; não é a excentricidade de ligação pela alma. An=A após confirmação de seção sem furos, recortes ou perdas, sem fator 0,9 na área. An0 fora da ligação permanece separado.')
    if r['missing']:doc.add_paragraph('Pendências: '+'; '.join(r['missing']))
    doc.add_paragraph('Nt,Rd = min[A fy/1,10; An0 fu/1,35; Ct An fu/1,65]. Esta entrada verifica somente resistência axial da seção; não dimensiona parafusos, soldas, esmagamento, rasgamento, bloco de cisalhamento, peça de apoio ou transferência de forças. Ct não elimina excentricidade física. Furos não atualizam as capacidades de flexão/torção nem o modelo intacto EN. A região perfurada permanece fora desses resultados. Nenhuma aprovação global é emitida.')
