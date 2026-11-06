"""Read-only NBR load-height component presentation, never a solver boundary."""
import copy
from .roof_top_nbr import FIELD,COMPUTED,SCOPE,SOURCE,preserved
from .presentation import display_frame,fmt
from .report_audit import technical_number

TITLE='FLT — resistência NBR com carga no topo'
ROW='FLT — carga no topo (vão inteiro)'
NOTE=('O índice refere-se somente à componente FLT do modelo declarado. '
      'O mínimo local–FLT–D exige todas as capacidades ou dispensa qualificada; não verifica B/T. '
      'M–V mantém o denominador de seção efetiva e a rota AISI não é alterada.')


def _status(r):
    if r.get('status')!=COMPUTED:return 'Pendente'
    if r.get('resistance_is_lower_envelope'):
        return 'Envoltória inconclusiva — não é reprovação' if r['index']>1 else 'Atende à envoltória da componente FLT'
    return 'Não atende à componente FLT' if r['index']>1 else 'Atende à componente FLT'


def summary_rows(evidence):
    out=[]
    for r in evidence['records']:
        ok=r['status']==COMPUTED
        out.append({'Combinação':r['combination_id'],'Situação':_status(r),
            'Msd [kN·m]':r['Msd_max_abs_Nmm']/1e6 if ok else None,
            'Me com altura [kN·m]':r['Me_Nmm']/1e6 if ok else None,
            'MRd,FLT [kN·m]':r['FLT']['MRd_flt_Nmm']/1e6 if ok else None,
            'Índice':r.get('index'),'Pendência / escopo':r['reason'] if not ok or r.get('resistance_is_lower_envelope') or r.get('bending_component_status')=='pending_distortional' else NOTE})
    return out


def show(st,result):
    try:ev=preserved(result)
    except (ValueError,TypeError,KeyError) as exc:
        st.warning('Resistência NBR no topo não exibida: '+str(exc));return
    if ev is None:return
    st.subheader(TITLE);st.caption(SOURCE);st.warning(SCOPE)
    st.caption(f"{ev['computed_cases']} combinações ELU com componente calculada; {ev['pending_cases']} pendentes. "+NOTE)
    if ev.get('inconclusive_envelope_cases'):st.info(str(ev['inconclusive_envelope_cases'])+' resultado(s) direto(s) com piso insuficiente: decisão inconclusiva, não reprovação.')
    if ev.get('reason'):st.info(ev['reason'])
    rows=summary_rows(ev)
    if rows:st.dataframe(display_frame(rows),hide_index=True,width='stretch')
    biaxial=[r for r in ev['records'] if 'biaxial' in r]
    if biaxial:
        from .roof_biaxial import SCOPE as BIAXIAL_SCOPE
        st.caption(BIAXIAL_SCOPE)
        st.dataframe(display_frame([biaxial_row(r) for r in biaxial]),hide_index=True,width='stretch')
    with st.expander('Memória NBR do topo: curva, fontes e componentes salvas',expanded=False):
        st.json({k:ev[k] for k in ('domain','source_section','source_roof_snapshot_sha256')})
        labels=[r['combination_id'] for r in ev['records']]
        if labels:
            selected=st.selectbox('Combinação da componente NBR no topo',labels,index=None,
                placeholder='Selecione para abrir o cálculo salvo',key='roof_nbr_record_'+ev['snapshot_sha256'])
            if selected is not None:st.json(next(r for r in ev['records'] if r['combination_id']==selected))


def report(doc,result):
    try:ev=preserved(result)
    except (ValueError,TypeError,KeyError) as exc:
        doc.add_paragraph('Resistência NBR no topo não exibida: '+str(exc));return
    if ev is None:return
    doc.add_heading(TITLE,1);doc.add_paragraph(SOURCE);doc.add_paragraph(SCOPE);doc.add_paragraph(NOTE)
    doc.add_paragraph(f"{ev['computed_cases']} combinações ELU calculadas; {ev['pending_cases']} pendentes. ELS não recebe estes índices de resistência.")
    if ev.get('reason'):doc.add_paragraph(ev['reason'])
    section=ev.get('source_section')
    if section:
        doc.add_paragraph('Fonte: '+section['reference_id']+'. '+section['critical_source']+' '+section['distortion_scope'])
        doc.add_paragraph('Wc='+technical_number(section['Wc_mm3'])+' mm³; Ml='+technical_number(section['Ml_Nmm'])+
            ' Nmm; fy='+technical_number(section['fy_MPa'])+' MPa. '+
            'Origem resistente SHA256: '+section['source_reference_sha256'])
    for r in ev['records']:
        p=doc.add_paragraph(r['combination_id']+' — '+_status(r)+'.');p.paragraph_format.keep_with_next=True
        if r['status']!=COMPUTED:doc.add_paragraph(r['reason']);continue
        if r.get('resistance_is_lower_envelope'):
            doc.add_paragraph('Carga direta: piso resistente do modelo escalar. Índice acima de 1 é inconclusivo; não demonstra reprovação. As transições arredondadas são tratadas pelo piso resistente, incluindo Wef limitado ao W bruto neste ramo, sem modificar a fórmula publicada.')
        f=r['FLT'];parts=[
            'Msd='+technical_number(r['Msd_max_abs_Nmm']/1e6)+' kN·m',
            'Me='+technical_number(r['Me_Nmm']/1e6)+' kN·m',
            'λ0='+technical_number(f['lambda0']),'χFLT='+technical_number(f['chi_flt']),
            'λp(χfy)='+technical_number(f['lambda_p_reduced_stress']),
            'Wc,ef='+technical_number(f['Wceff_mm3'])+' mm³',
            'MRd,FLT='+technical_number(f['MRd_flt_Nmm']/1e6)+' kN·m',
            'índice FLT='+technical_number(r['index'],limit=1.)]
        doc.add_paragraph('; '.join(parts)+'.')
        if r.get('bending_component_status')=='pending_distortional':
            doc.add_paragraph('MRd seção efetiva='+technical_number(r['MRd_section_effective_Nmm']/1e6)+
                ' kN·m. Distorção forte pendente, sem dispensa. Mínimo local–FLT–D e interação §9.9 não calculados. Sem interação com torção.')
        else:
            doc.add_paragraph('MRd seção efetiva='+technical_number(r['MRd_section_effective_Nmm']/1e6)+
                ' kN·m; MRd D='+('dispensa forte específica' if r['MRd_distortional_Nmm'] is None else
                technical_number(r['MRd_distortional_Nmm']/1e6)+' kN·m')+
                '; mínimo das componentes de flexão pura='+technical_number(r['MRd_bending_component_Nmm']/1e6)+' kN·m. Sem interação com torção.')
        if 'biaxial' in r:
            b=r['biaxial'];g=b['governing']
            doc.add_paragraph(b['scope'])
            doc.add_paragraph('Interação §9.9: x='+technical_number(g['x_mm'])+' mm; Mx='+
                technical_number(g['Mx_Nmm']/1e6)+' kN·m; My='+technical_number(g['My_Nmm']/1e6)+
                ' kN·m; MxRd='+technical_number(b['strong_capacity_Nmm']/1e6)+' kN·m; MyRd='+
                technical_number(b['weak_axis_capacities']['positive' if g['My_Nmm']>=0 else 'negative']['MRd_Nmm']/1e6)+
                ' kN·m; índice='+technical_number(g['index'],limit=1.)+'. '+biaxial_row(r)['Situação'])
    doc.add_paragraph('Rastreabilidade Me salvo SHA256: '+ev['source_roof_snapshot_sha256'])


def presentation_rows(result,rows,combination_id=None):
    """Replace resolved FLT/biaxial presentation, never mutate the legacy rows."""
    if FIELD not in result or not any(str(r.get('Verificação','')).startswith('FLT — trecho ') for r in rows):return rows
    try:ev=preserved(result)
    except (ValueError,TypeError,KeyError) as exc:ev=None;error='Componente NBR no topo inválida: '+str(exc)
    else:error=None
    records=[] if ev is None else [r for r in ev['records'] if combination_id is None or r['combination_id']==combination_id]
    computed=[r for r in records if r['status']==COMPUTED];pending=[r for r in records if r['status']!=COMPUTED]
    chosen=max(computed,key=lambda r:r['index']) if computed else None
    note=chosen['reason'] if chosen and (chosen.get('resistance_is_lower_envelope') or chosen.get('bending_component_status')=='pending_distortional') else NOTE
    if pending:note+=f' Há {len(pending)} combinação(ões) pendente(s); consulte a componente NBR no topo.'
    if error:note=error
    if not chosen and records:note=records[0]['reason']
    new={'Verificação':ROW,'Situação':(('Parcial — ' if pending else '')+_status(chosen)) if chosen else 'Não avaliado',
        'Índice':chosen['index'] if chosen else None,
        'Demanda / valor':str(chosen['Msd_max_abs_Nmm']/1e6)+' kN·m' if chosen else '—',
        'Resistência / limite':str(chosen['FLT']['MRd_flt_Nmm']/1e6)+' kN·m' if chosen else '—',
        'Referência':'NBR14762 §9.8.2.2; Me com altura por combinação','Observação':note}
    if combination_id is None:
        from .roof_top_load import combination_inventory
        combos={c['id']:c for c in combination_inventory(result)}
        cid=chosen['combination_id'] if chosen else records[0]['combination_id'] if records else None
        new['Combinação']=(cid+' — '+combos[cid]['type']) if cid in combos else 'Não disponível'
    out=[];inserted=False
    for row in rows:
        if str(row.get('Verificação','')).startswith('FLT — trecho '):
            if not inserted:out.append(new);inserted=True
        else:out.append(copy.deepcopy(row))
    return replace_biaxial_rows(out,records,combination_id)


def biaxial_row(record):
    b=record['biaxial'];g=b['governing'];status=b['criterion_status']
    return {'Verificação':'Flexão biaxial','Situação':
        {'meets':'Atende ao critério calculado','fails':'Não atende ao critério calculado',
         'inconclusive':'Pendente — piso resistente insuficiente'}[status],
        'Índice':g['index'],'Demanda / valor':f"x={g['x_mm']} mm; Mx={g['Mx_Nmm']} Nmm; My={g['My_Nmm']} Nmm",
        'Resistência / limite':'|Mx|/MxRd + |My|/MyRd ≤ 1; N=0',
        'Referência':b['source'],'Observação':b['scope'], 'Combinação':record['combination_id']}


def replace_biaxial_rows(rows,records,combination_id):
    computed=[r for r in records if 'biaxial' in r]
    if not computed:return rows
    chosen=max(computed,key=lambda r:r['biaxial']['governing']['index'])
    new=biaxial_row(chosen)
    if combination_id is not None:new.pop('Combinação')
    # Uniaxial records need no weak interaction. Pending strong-axis cases remain
    # explicitly uncovered, rather than being hidden by another case's index.
    if any(r['status']!=COMPUTED for r in records):
        new['Situação']='Parcial — '+new['Situação']
        new['Observação']+=' Há combinações pendentes; o índice não cobre essas combinações.'
    if not any(r.get('Verificação')=='Flexão biaxial' for r in rows):return rows+[new]
    return [copy.deepcopy(new) if r.get('Verificação')=='Flexão biaxial' else r for r in rows]


def presentation_inclination(result,evidence,combination_id=None):
    """A displayed legacy pending label must not contradict its saved successor."""
    if FIELD not in result:return evidence
    try:saved=preserved(result)
    except (ValueError,TypeError,KeyError):return evidence
    cid='DIRECT_ELU' if combination_id is None else combination_id
    row=next((r for r in saved['records'] if r['combination_id']==cid and 'biaxial' in r),None)
    if row is None:return evidence
    out=copy.deepcopy(evidence)
    target=out.get('ELU') if combination_id is None else out
    if not isinstance(target,dict) or 'states' not in target:return evidence
    b=row['biaxial'];target['resistance_status']=biaxial_row(row)['Situação']+'. '+b['scope']
    target['biaxial']={k:copy.deepcopy(b[k]) for k in ('status','governing','missing','candidate_count')}
    target['strong_capacity_Nmm']=b['strong_capacity_Nmm']
    target['weak_axis_capacities']={sign:dict(copy.deepcopy(c),
        annex_e=dict(Me_Nmm=c['Me_Nmm']),
        provenance='Fonte própria salva '+saved['source_section']['reference_id']+'; '+b['scope'])
        for sign,c in b['weak_axis_capacities'].items()}
    return out
