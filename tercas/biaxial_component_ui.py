"""Read-only presentation of a saved, explicitly selected flexural component."""
from .biaxial_component import FIELD,ROW,TEXT,SOURCE,preserved_snapshot,claims_result,GIRT_SCHEMA
from .presentation import fmt


def _read(result):
    try:return preserved_snapshot(result),None
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
        return None,'Registro da componente biaxial inválido: '+str(exc)+' Recalcule explicitamente. Não houve cálculo nem requalificação ao abrir este resultado.'


def description(record):
    axis='horizontal normal ao fechamento' if record['schema']==GIRT_SCHEMA else 'normal'
    if record['total_cases']==0:
        return 'Nenhum estado ELS selecionado para a componente flexional biaxial. Sem conclusão ELS completo ou aprovação global.'
    return (f"Componente flexional biaxial: seção integral demonstrada em {record['qualified_cases']} "
        f"de {record['total_cases']} estados ELS registrados. Somente a flecha {axis} recebe "
        'comparação com o limite informado; ELS físico completo e aprovação global permanecem pendentes.')


def show(st,result):
    if not claims_result(result):return
    record,error=_read(result)
    if error:st.error(error);return
    st.info(description(record))
    with st.expander('Escopo da componente flexional biaxial',expanded=False):
        st.caption(record['scope'])
        st.caption('Modelo de linha R01 com dA=t ds; dobras retidas e tensões exteriores. '
            'A comparação uniforme das mesas é uma condição suficiente de engenharia, '
            'não uma fórmula geral da NBR para mesas com qualquer gradiente. '
            'N=B=0 define somente a componente matemática; não declara essas ações físicas nulas.')
        st.caption('Os dois deslocamentos são calculados simultaneamente no backend. '
            'Não se soma o máximo de cada eixo, não se acrescenta linha de flecha paralela '
            'e não se aplica à resultante o limite da componente normal.')
        st.caption(f"Referência: {record['reference_id']}. Identidade da evidência salva: {record['snapshot_sha256']}.")
        pending=[cid for cid,r in record['records'].items() if not r['qualified_gross_flexural_component']]
        if pending:st.warning('Crivo inconclusivo/fora do domínio numérico: '+', '.join(pending)+'. Não é reprovação. Nenhum índice escalar foi recuperado.')


def report(doc,result):
    if not claims_result(result):return
    record,error=_read(result)
    doc.add_heading('Componente horizontal da flexão biaxial — travessa isolada' if record and record['schema']==GIRT_SCHEMA else 'Componente normal da flexão biaxial — seção integral',1)
    if error:doc.add_paragraph(error);return
    doc.add_paragraph(description(record));doc.add_paragraph(record['scope'])
    doc.add_paragraph(SOURCE+'. Comparação uniforme da mesa como condição suficiente de engenharia; '
        'não é uma expressão normativa geral de seção reduzida sob gradiente biaxial. '
        'Alma, duas mesas e dois lábios são verificados conjuntamente; dobras permanecem no modelo MLE. '
        'N=B=0 nesta prova é exclusão matemática da componente, não medida da demanda física.')
    doc.add_paragraph('Tensor da mesma seção R01 (linha dA=t ds): K=E [[Ix,−Ixy],[−Ixy,Iy]]. '
        'Vetores locais [normal, paralelo] simultâneos; sem segunda rotação ou duplicação do PP. '
        'Resposta Euler–Bernoulli prismática biapoiada, procura contínua dos extremos por trechos. '
        'A resultante e a outra componente não recebem o limite normal. Torção/empenamento não incluídos.')
    for cid,r in record['records'].items():
        if not r['qualified_gross_flexural_component']:
            doc.add_paragraph(cid+': '+r['reason'])
    doc.add_paragraph('P junto ao apoio representa a→0+ no interior: sua parcela de flexão tende a zero, '
        'mas a força original, a reação e a camada de cortante antes de P permanecem. '
        'A posição finita de P não é convertida em limite de apoio. Introdução local e ligação não aprovadas.')
    doc.add_paragraph('Fonte própria: '+record['reference_id']+'; SHA-256 do contorno: '+record['geometry_source_sha256']+'.')
    doc.add_paragraph('Integridade da emissão salva: '+record['snapshot_sha256']+'. A leitura deste registro '
        'confere consistência, sem consultar fontes vivas nem reexecutar o crivo ou a resposta. '
        'O cálculo escalar anterior foi preservado somente como diagnóstico, sem fornecer este índice.')
