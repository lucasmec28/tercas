"""Explicit section model choice and snapshot-only EN display/Word."""
import copy
from . import isolated_en_application as a
from .presentation import display_frame,fmt

LABEL='Verificar tensões combinadas e cisalhamento torsional (EN)'
DECLARATION='Adotar seção nominal intacta, sem furos ou recortes, neste complemento EN'
ORIGIN='Origem/hipótese do modelo de seção intacta EN'
TITLE='Tensões combinadas e cisalhamento torsional — complemento EN'


def render_choice(st,data,key):
    own=isinstance(data.get('ue_family_reference'),dict) or isinstance(data.get('ue_reference'),dict)
    if not own and a.CHOICE not in data:return
    if data.get('member_application','purlin')!='purlin':
        if a.CHOICE in data:st.caption('Complemento EN isolado inativo nesta aplicação; a rede tem sua verificação própria.')
        return
    try:
        changed=a.reset_changed_declaration(data);c=a.configuration(data)
    except ValueError as exc:
        st.warning(str(exc));return
    with st.expander('Complemento EN — torção e interação de tensões',expanded=False):
        st.caption(a.SCOPE)
        if changed:st.info('Seção/material mudou: opção preservada, declaração e origem retiradas. Declare novamente para a seção atual.')
        # Identity belongs to widget keys too, so a previous checkbox cannot re-adopt another profile.
        key+='_'+a.identity(data)[:16]
        enabled=st.checkbox(LABEL,value=bool(c and c['enabled']),key=key+'_enabled')
        if c is None and not enabled:return
        c=copy.deepcopy(c) if c is not None else a.choice(data)
        c['enabled']=enabled;data[a.CHOICE]=c
        if not enabled:
            st.caption('Opção desativada; declaração salva preservada. Históricos não são recalculados.')
            return
        c['intact_section_model_declared']=st.checkbox(DECLARATION,
            value=c['intact_section_model_declared'],key=key+'_intact')
        c['model_origin']=st.text_input(ORIGIN,value=c['model_origin'],key=key+'_origin')
        reason=a._domain_reason(data,c)
        if reason:st.warning('Complemento EN pendente: '+reason)
        st.caption('Somente Ue100 próprio, N=0, fyb=fya=250 MPa e ELU. Seções efetivas EN; '
            'E=210000 MPa e γM0=1 no critério, sem alterar E/G das ações calculadas. '
            'O modelo Vlasov e suas linhas de carga precisam estar disponíveis. '
            'Cortantes transversais EN6.1.5 e interação EN6.1.10 nos dois eixos complementam 6.1.6; '
            'estabilidade e ELS permanecem separados.')


def rows(ev):
    out=[]
    for row in ev['records']:
        check=row['check'];criteria=check['criteria'] if check else {}
        web=row.get('web_shear_component')
        mv=web.get('bending_shear_component') if web else None
        mv_error=web.get('bending_shear_error') if web else None
        out.append({'Combinação':row['combination_id'],
            'Teto normal EN':criteria.get('normal',{}).get('index_upper_bound'),
            'Teto cisalhamento EN':criteria.get('shear',{}).get('index_upper_bound'),
            'Teto interação σ–τ EN':criteria.get('interaction',{}).get('index_upper_bound'),
            'Componente de tensões':('Suficiente no campo declarado' if check['section_stress_criteria_sufficiently_satisfied']
                else 'Inconclusivo pelo teto; não é reprovação') if check else 'Pendente',
            'Teto cortante transversal da alma EN':web['web_shear']['index_upper'] if web else None,
            'Componente da alma':('Suficiente para Vy transversal pelo piso de Vw,Rd' if web['web_shear']['status']=='meets'
                else 'Inconclusivo pelo piso; não é reprovação') if web else 'Sem cálculo salvo',
            'Redução adicional por V EN':('Dispensada nos dois eixos' if mv['shear_reduction_waived']
                else 'Incluída na equação 6.27') if mv else 'Pendente: cálculo EN6.27 indisponível' if mv_error else ('Dispensada no domínio sem B/torção/flexão fraca'
                if web['no_web_shear_reduction']['status']=='meets' else 'Registro histórico restrito; sem requalificação') if web else 'Pendente',
            'Teto dos dois cortantes EN':mv['shear_ratio_upper'] if mv else None,
            'Teto M–V adicional EN6.27':mv['index_upper'] if mv else None,
            'M–V adicional EN6.27':('Suficiente no domínio salvo' if mv['component_qualified'] else 'Inconclusivo pelo teto') if mv else 'Pendente no cálculo salvo' if mv_error else 'Sem registro adicional',
            'Motivo':row.get('reason') or row.get('web_shear_error') or (mv['reason'] if mv else web.get('bending_shear_error','') if web else '')})
    return out


def text_lines(ev):
    c=ev['configuration']
    lines=[a.SCOPE,'Modelo de seção nominal intacta: '+c['model_origin'],
        'Três limites independentes: |σ| ≤ 250 MPa; |τ| ≤ 144,337567 MPa; sqrt(σ²+3τ²) ≤ 275 MPa. '
        'A folga 1,1 da interação não relaxa os outros dois limites.',
        'As duas faces e todo o campo longitudinal são cobertos. O controle de Bernstein é um limite numérico, '
        'não um estado físico de tensões. Nenhum teto acima de 1 é rotulado como falha.',
        'Nesta rota isolada N=0. As tensões normais de flexão usam seções efetivas EN; B/V/Tsv/Tw usam a seção bruta coerente. Material EN fixo: '
        'fyb=fya=250 MPa, E=210000 MPa, ν=0,3, γM0=1. E/G da análise e combinações originais são preservados.',
        'A componente de tensões não conclui por si só flambagem por cisalhamento EN6.1.5, redução N–M–V EN6.1.10, '
        'estabilidade, adequação da primeira ordem, forças locais, ligações ou ELS.',
        f"{ev['computed_cases']} casos ELU calculados; {ev['pending_cases']} pendentes; {ev['ELS_cases_excluded']} casos ELS fora deste critério."]
    webs=[r['web_shear_component'] for r in ev['records'] if 'web_shear_component' in r]
    if webs:
        mvs=[w['bending_shear_component'] for w in webs if 'bending_shear_component' in w]
        errors=[w['bending_shear_error'] for w in webs if 'bending_shear_error' in w]
        historical=sum('bending_shear_component' not in w and 'bending_shear_error' not in w for w in webs)
        lines += ['EN6.1.5: sw≤hw=H−t produz piso conservador da alma forte. '
            'Sem crédito de enrijecedores. '
            'Cada trecho e ambos os lados de P, inclusive before-P quando declarado, são preservados.']
        if mvs:
            from .en_simplified_interaction import SCOPE as MV_SCOPE, capacity_text
            lines += ['Na componente EN6.27 calculada, as duas mesas originais fornecem duas almas com hw=b−t '
                'para o cortante fraco; não se reutiliza a capacidade forte.',
                MV_SCOPE,capacity_text(mvs[0]['capacity_reference'],include_axial=False),
                'Componente adicional EN6.27: soma dos módulos N/NRd, Mx/MxRd e My/MyRd, mais a maior penalidade '
                'max(0,2|V|/VbRd−1)² dos dois eixos, junto de |V|≤VbRd em ambos. '
                'Mf=0 não usa reserva de mesas/plasticidade. Os pisos de flexão vêm dos operadores puros efetivos EN '
                'e do primeiro escoamento nas faces físicas; não usam ULS_pure_effort nem MRd NBR.',
                f'{len(mvs)} casos com 6.27 calculado; {sum(m["component_qualified"] for m in mvs)} suficientes no domínio salvo. '
                'Torção não precisa ser nula: B/Tsv/Tw continuam nas três desigualdades 6.1.6. '
                'Ambas as componentes precisam atender; nenhuma delas prova estabilidade ou aprovação global.',
                'A aplicação de 6.1.10 por dois cortantes transversais e 6.1.6 para torção segue a interpretação documentada '
                'no manual oficial SCIA Engineer 17.0, pp. 80–86. O registro antigo de limiar da alma é preservado, não reclassificado.',
                'Fonte de implementação: https://help.scia.net/download/17.0/en/SteelCodeCheck_Theory_enu.pdf']
        if errors:
            cases='caso' if len(errors)==1 else 'casos'
            lines += [f'EN6.27 pendente em {len(errors)} {cases} do cálculo salvo: '+ '; '.join(sorted(set(errors))) + '.',
                'A componente adicional não foi concluída neste cálculo salvo. '
                'O resultado da alma forte permanece separado e não demonstra dispensa da interação nos dois eixos. '
                'Nenhuma aprovação global é emitida; a visualização preserva os resultados sem recalcular.']
        if historical:
            from .isolated_en_shear import SCOPE
            lines += [SCOPE, 'Registro histórico restrito à alma. VEd inclui cortante de torque na definição de EN1993-1-5 §1.4; '
                'esta implementação antiga não demonstra dispensa para a seção. Não se recalcula nem reclassifica o histórico.']
    else:
        lines.append('Sem componente salva de cortante da alma EN6.1.5/6.1.10. Histórico não recalculado.')
    if ev.get('reason'):lines.append(ev['reason'])
    return lines


def show(st,result):
    try:ev=a.preserved(result)
    except (ValueError,TypeError,KeyError) as exc:
        st.error('Registro EN isolado inválido: '+str(exc));return
    if ev is None:return
    st.subheader(TITLE)
    for line in text_lines(ev):st.caption(line)
    if ev['records']:st.dataframe(display_frame(rows(ev)),hide_index=True,width='stretch')
    st.caption('Memória e fontes preservadas no JSON. Visualizar ou exportar não executa novo cálculo.')


def report(doc,result):
    try:ev=a.preserved(result)
    except (ValueError,TypeError,KeyError) as exc:
        doc.add_heading('Complemento EN isolado — registro inválido',1)
        doc.add_paragraph(str(exc)+' Nenhum índice EN desse registro foi emitido.');return
    if ev is None:return
    doc.add_heading(TITLE,1)
    for line in text_lines(ev):doc.add_paragraph(line)
    for row in rows(ev):
        doc.add_paragraph(' | '.join(k+': '+(fmt(v) if type(v) in (int,float) else str(v))
            for k,v in row.items() if v is not None))
    doc.add_paragraph('Fonte das tensões: EN1993-1-3:2006 §6.1.6(3)–(5), pp.46–47; '
        'componente de alma, quando salva: §§6.1.5 e 6.1.10(1), pp.45–46 e 55. '
        'Fonte geométrica própria: '+str(ev.get('source_profile',{}).get('profile_id','pendente'))+'. '
        'Hash do snapshot torsional: '+ev['source_torsion_snapshot_sha256']+'.')
