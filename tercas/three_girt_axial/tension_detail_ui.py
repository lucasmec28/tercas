"""Simple, optional common connection-detail controls and saved trace."""
from .tension_detail import blank_detail

OPTIONS={'Manual: An0, An e Ct auditados':None,
         'Solda da mesa inferior no topo da viga':'lower_flange_weld',
         'Parafusos na alma, uma fileira vertical':'web_bolt_single_transverse_row'}
WELDS={'A definir':'undefined','Somente transversais':'transverse_only',
       'Longitudinais':'longitudinal','Longitudinais e transversais':'mixed'}


def controls(st,config,prefix):
    selected=st.selectbox('Forma de informar a ligação para tração',list(OPTIONS),key=prefix+'_nbr_detail_mode')
    mode=OPTIONS[selected]
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
            st.caption('A Fig.4d representa U ligado pela alma. A fórmula de U com soldas longitudinais não é estendida automaticamente à mesa inferior do Ue. Comprimento e excentricidade são registrados, sem fabricar Ct.')
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
        st.caption(f"An calculado/declarado = {d['An_mm2']:.4f} mm²; Ct = {d['Ct']:.6f}. "+('Dados confirmados para a referência.' if not r['missing'] else 'Prévia: há declarações/dados pendentes; Nt,Rd não foi liberado.'))
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
        doc.add_paragraph(f"An = {d['An_mm2']:.6f} mm²; Ct = {d['Ct']:.8f}. "+('Dados confirmados para a referência.' if not r['missing'] else 'Prévia incompleta; não libera Nt,Rd.'))
        if 'g_effective_mm' in d:
            pitch='não se aplica' if d['vertical_pitch_mm'] is None else f"{d['vertical_pitch_mm']:.6f} mm"
            doc.add_paragraph(f"Uma seção transversal: n = {d['bolt_count']}; d = {d['bolt_diameter_mm']:.6f} mm; df = d+2 = {d['hole_diameter_mm']:.6f} mm; t = {d['t_mm']:.6f} mm; passo vertical = {pitch}. An = 0,9[A - n df t].")
            doc.add_paragraph(f"Chapa equivalente da Fig.4b: B = A/t = {d['developed_width_mm']:.6f} mm, incluindo mesas, curvas e lábios; e1+e2 = {d['developed_edge_sum_mm']:.6f} mm; g = {d['g_effective_mm']:.6f} mm. Ct = min(2,5d/g; 1). Não é a regra de duas posições longitudinais de parafusos.")
            doc.add_paragraph('Furo circular alargado real adotado: folga 2 mm. Para estes diâmetros, a Tabela 15 especifica d+1,5 mm como furo-padrão. O ramo automático é limitado a t do perfil <= 4,75 mm, condição suficiente do domínio de §10.3.1. As checagens geométricas locais são necessárias, mas não verificam todas as distâncias, o furo executado ou a ligação.')
        else:
            doc.add_paragraph('Arranjo de solda: '+d['weld_arrangement']+'. '+d['clause']+'.')
            if d['weld_arrangement']!='transverse_only':doc.add_paragraph(f"Comprimento longitudinal = {d['length_mm']} mm; excentricidade = {d['eccentricity_mm']} mm. Origem do Ct: {d['ct_origin']}.")
    if r['missing']:doc.add_paragraph('Pendências: '+'; '.join(r['missing']))
    doc.add_paragraph('Nt,Rd = min[A fy/1,10; An0 fu/1,35; Ct An fu/1,65]. Esta entrada verifica somente resistência axial da seção; não dimensiona parafusos, soldas, esmagamento, rasgamento, bloco de cisalhamento, peça de apoio ou transferência de forças. Ct não elimina excentricidade física. Furos não atualizam as capacidades de flexão/torção nem o modelo intacto EN. A região perfurada permanece fora desses resultados. Nenhuma aprovação global é emitida.')
