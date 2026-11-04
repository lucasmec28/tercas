"""Read-only rendering of saved AA ceilings, with explicit independent choices."""
from .aa_component import (FIELD,MODE,LOCAL_MODE,MODES,LABEL,METHOD_LABELS,selected,
    scope_text,SCHEMA,GIRT_SCHEMA,SOURCE,AXIS,preserved_snapshot,claims_result)


SAVED_GLOBAL_NOTICE='O resumo global reproduz o estado originalmente salvo. Suas contagens não foram recompostas após a recusa deste registro AA e não incorporam essa recusa. A leitura não recalcula nem requalifica o histórico.'

def _read(result):
    try:return preserved_snapshot(result),None
    except (ValueError,TypeError,KeyError,ArithmeticError,IndexError) as exc:
        return None,'Registro do teto AA inválido: '+str(exc)+' Recalcule explicitamente. A leitura não executou novo cálculo nem requalificou histórico.'


def description(record):
    axis='horizontal normal ao fechamento' if record['schema']==GIRT_SCHEMA else 'normal à cobertura'
    return (f"Teto AA da componente {axis}: {record['bounded_cases']} de {record['total_cases']} estados ELS têm teto utilizável; "
        f"{record['sufficient_cases']} atendem ao limite por condição suficiente. Teto não é flecha exata. "
        'Os demais estados continuam pendentes; ELS físico completo e aprovação global não são concluídos.')


def show(st,result):
    if not claims_result(result):return
    record,error=_read(result)
    if error:
        st.error(error)
        if isinstance(result.get('global_verification'),dict):st.caption(SAVED_GLOBAL_NOTICE)
        return
    st.info(description(record))
    with st.expander('Escopo do teto flexional biaxial AA',expanded=False):
        st.caption(record['scope']);st.caption('Método escolhido: '+METHOD_LABELS[record['choice']]+'. Não houve seleção, fusão ou transferência automática entre métodos.')
        st.caption(AXIS)
        st.caption('O índice, quando presente, é a razão conservadora teto/limite e só indica suficiência da componente. Teto acima do limite fica inconclusivo, nunca reprovado por essa desigualdade.')
        st.caption('Suportes seccionais com 70 dígitos e margem numérica, não aritmética intervalar formal. Green racional condicionado a esses suportes. Não há prova de unicidade ou estabilidade física.')
        if record['choice']==LOCAL_MODE:st.caption('Partição local: orçamento de 64 avaliações, sem encurtar o vão ou criar apoios. Só a cobertura completa entrega teto utilizável.')
        st.caption(f"Fonte: {record['reference_id']}. Identidade salva: {record['snapshot_sha256']}.")


def report(doc,result):
    if not claims_result(result):return
    record,error=_read(result)
    doc.add_heading('Teto de componente flexional biaxial — somente alma AA reduzível',1)
    if error:
        doc.add_paragraph(error)
        if isinstance(result.get('global_verification'),dict):doc.add_paragraph(SAVED_GLOBAL_NOTICE)
        return
    doc.add_paragraph(description(record));doc.add_paragraph(record['scope'])
    doc.add_paragraph(SOURCE+'. A lei AA da alma provém da norma; a prova de teto por equilíbrio conjunto, PSD e Green é uma derivação mecânica suficiente, não um algoritmo textual prescrito pela NBR.')
    doc.add_paragraph('Método explicitamente escolhido: '+METHOD_LABELS[record['choice']]+'. Métodos independentes; nenhuma fusão ou escolha automática. '+AXIS)
    doc.add_paragraph('A componente normal é confrontada somente com seu limite declarado. A outra componente é preservada no registro, sem linha nova de flecha paralela/vertical e sem aplicar-lhe o limite normal. Não são somados máximos de eixos distintos.')
    doc.add_paragraph('O valor mostrado é um teto do máximo absoluto, não a flecha calculada exata ou uma estimativa. A razão teto/limite só produz atendimento suficiente quando ≤ 1. Acima de 1 o critério permanece inconclusivo, sem índice de reprovação. A flecha escalar anterior permanece apenas em diagnóstico separado.')
    doc.add_paragraph('P deve estar estritamente no interior. O limite a→0+ não é convertido em P=0 nem em posição finita. Esse estado permanece pendente na rota AA, preservadas as ações e reações anteriores.')
    doc.add_paragraph('Contorno R01, dA=t ds; dobras retidas, centroide móvel e Ixy preservados. Não-alma integral e material elástico são guardas obrigatórias. N=B=0 define a componente matemática, não a demanda física. Suportes com 70 dígitos e padding não são aritmética intervalar formal; Green racional condicionado aos suportes. Não há prova de unicidade, seleção contínua ou estabilidade.')
    doc.add_paragraph('Bundle SHA-256: '+record['bundle_manifest_sha256']+'. Emissão salva: '+record['snapshot_sha256']+'. A leitura confere vínculos salvos sem fontes vivas nem novo solver. Hash de integridade não é assinatura ou certificação do modelo físico.')
    for cid,r in record['records'].items():
        if not r['qualified_bound_component']:doc.add_paragraph(cid+': '+r['reason'])


def render_choice(st,data,key):
    active=st.checkbox(LABEL,value=selected(data),key=key)
    if active:
        current=data.get('deflection_model') if selected(data) else MODE
        choice=st.selectbox('Método para o teto AA',MODES,index=MODES.index(current),
            format_func=lambda m:METHOD_LABELS[m],key=key+'_method')
        data['deflection_model']=choice
        st.caption(scope_text(data))
        st.caption('Métodos separados. P junto ao apoio, mesa/lábio reduzidos e conjunto 3D não são admitidos. Teto acima do limite permanece inconclusivo.')
    elif selected(data):data.pop('deflection_model',None)
    return active
