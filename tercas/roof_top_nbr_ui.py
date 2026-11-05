"""Read-only NBR load-height component presentation, never a solver boundary."""
import copy
from .roof_top_nbr import FIELD,COMPUTED,SCOPE,SOURCE,preserved
from .presentation import display_frame,fmt
from .report_audit import technical_number

TITLE='FLT — resistência NBR com carga no topo'
ROW='FLT — carga no topo (vão inteiro)'
NOTE=('O índice refere-se somente à componente FLT do modelo declarado. '
      'O mínimo local–FLT–D é uma componente de flexão pura; não verifica B/T. '
      'M–V mantém o denominador de seção efetiva e a rota AISI não é alterada.')


def _status(r):
    if r.get('status')!=COMPUTED:return 'Pendente'
    return 'Não atende à componente FLT' if r['index']>1 else 'Atende à componente FLT'


def summary_rows(evidence):
    out=[]
    for r in evidence['records']:
        ok=r['status']==COMPUTED
        out.append({'Combinação':r['combination_id'],'Situação':_status(r),
            'Msd [kN·m]':r['Msd_max_abs_Nmm']/1e6 if ok else None,
            'Me com altura [kN·m]':r['Me_Nmm']/1e6 if ok else None,
            'MRd,FLT [kN·m]':r['FLT']['MRd_flt_Nmm']/1e6 if ok else None,
            'Índice':r.get('index'),'Pendência / escopo':NOTE if ok else r['reason']})
    return out


def show(st,result):
    try:ev=preserved(result)
    except (ValueError,TypeError,KeyError) as exc:
        st.warning('Resistência NBR no topo não exibida: '+str(exc));return
    if ev is None:return
    st.subheader(TITLE);st.caption(SOURCE);st.warning(SCOPE)
    st.caption(f"{ev['computed_cases']} combinações ELU com componente calculada; {ev['pending_cases']} pendentes. "+NOTE)
    if ev.get('reason'):st.info(ev['reason'])
    rows=summary_rows(ev)
    if rows:st.dataframe(display_frame(rows),hide_index=True,width='stretch')
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
        f=r['FLT'];parts=[
            'Msd='+technical_number(r['Msd_max_abs_Nmm']/1e6)+' kN·m',
            'Me='+technical_number(r['Me_Nmm']/1e6)+' kN·m',
            'λ0='+technical_number(f['lambda0']),'χFLT='+technical_number(f['chi_flt']),
            'λp(χfy)='+technical_number(f['lambda_p_reduced_stress']),
            'Wc,ef='+technical_number(f['Wceff_mm3'])+' mm³',
            'MRd,FLT='+technical_number(f['MRd_flt_Nmm']/1e6)+' kN·m',
            'índice FLT='+technical_number(r['index'],limit=1.)]
        doc.add_paragraph('; '.join(parts)+'.')
        doc.add_paragraph('MRd seção efetiva='+technical_number(r['MRd_section_effective_Nmm']/1e6)+
            ' kN·m; MRd D='+('dispensa forte específica' if r['MRd_distortional_Nmm'] is None else
            technical_number(r['MRd_distortional_Nmm']/1e6)+' kN·m')+
            '; mínimo das componentes de flexão pura='+technical_number(r['MRd_bending_component_Nmm']/1e6)+' kN·m. Sem interação com torção.')
    doc.add_paragraph('Rastreabilidade Me salvo SHA256: '+ev['source_roof_snapshot_sha256'])


def presentation_rows(result,rows,combination_id=None):
    """Replace only legacy FLT presentation, never change the underlying rows."""
    if FIELD not in result or not any(str(r.get('Verificação','')).startswith('FLT — trecho ') for r in rows):return rows
    try:ev=preserved(result)
    except (ValueError,TypeError,KeyError) as exc:ev=None;error='Componente NBR no topo inválida: '+str(exc)
    else:error=None
    records=[] if ev is None else [r for r in ev['records'] if combination_id is None or r['combination_id']==combination_id]
    computed=[r for r in records if r['status']==COMPUTED];pending=[r for r in records if r['status']!=COMPUTED]
    chosen=max(computed,key=lambda r:r['index']) if computed else None
    note=NOTE
    if pending:note+=f' Há {len(pending)} combinação(ões) pendente(s); consulte a componente NBR no topo.'
    if error:note=error
    if not chosen and records:note=records[0]['reason']
    new={'Verificação':ROW,'Situação':(('Parcial — ' if pending else '')+_status(chosen)) if chosen else 'Não avaliado',
        'Índice':chosen['index'] if chosen else None,
        'Demanda / valor':str(chosen['Msd_max_abs_Nmm']/1e6)+' kN·m' if chosen else '—',
        'Resistência / limite':str(chosen['FLT']['MRd_flt_Nmm']/1e6)+' kN·m' if chosen else '—',
        'Referência':'NBR14762 §9.8.2.2; Me com altura por combinação','Observação':note}
    if combination_id is None:
        combos={c['id']:c for c in result.get('load_bundle',{}).get('combinations',[])}
        cid=chosen['combination_id'] if chosen else records[0]['combination_id'] if records else None
        new['Combinação']=(cid+' — '+combos[cid]['type']) if cid in combos else 'Não disponível'
    out=[];inserted=False
    for row in rows:
        if str(row.get('Verificação','')).startswith('FLT — trecho '):
            if not inserted:out.append(new);inserted=True
        else:out.append(copy.deepcopy(row))
    return out
