"""Independent, saved completion inventory for the isolated purlin.

This is a scope/data inventory, not another resistant equation or approval gate.
Explicit records are expected regardless of which numeric outputs happen to exist.
Rendering validates saved records and never constructs a new historical snapshot.
"""
import copy
import hashlib
import json

from .serviceability_plan import prepare, SOURCE_SHA256

FIELD = 'completion_requirements'
SCHEMA = 'isolated_purlin_completion_requirements_v1'
SCOPED_SCHEMA = 'isolated_purlin_completion_requirements_v2_support_scope'
# IDs are fixed independently of observed numerical checks. None means there is
# no consolidated producer for that requirement, not normative inapplicability.
DEFINITIONS = (
 ('actions', 'Ações e combinações', 'NBR14762 §§6.7 e Anexo A', None,
  'Separar permanentes, variáveis, posições e famílias ELU/ELS; completar o caso específico da nota f sem alterar a matriz fornecida.'),
 ('section_material', 'Seção, material e origem', 'NBR14762 §§4,8.3,9.2', None,
  'Geometria, espessura, raios, fy e origem coerentes; fu quando pertinente. Dados publicados Pierin e contorno próprio são referências diferentes; fy nominal não comprova produto.'),
 ('analysis_applicability', 'Aplicabilidade da análise', 'NBR14762 §8.1', None,
  'Modelo representativo e efeitos relevantes. Giro linear grande não é giro físico qualificado; equilíbrio numérico não basta. A norma não exige GMNIA ou ensaio em todo caso.'),
 ('local', 'Flambagem local na flexão', 'NBR14762 §9.8.2.1', 'local',
  'Consumir a fonte, eixo e campo de tensão do ramo calculado. Um ramo puro não conclui automaticamente o campo combinado com bimomento.'),
 ('distortional', 'Flambagem distorcional', 'NBR14762 §9.8.2.3', 'distortional',
  'Verificação ou dispensa demonstrada para a seção/sinal aplicáveis. Falta de método para outro ramo não é proibição normativa da família.'),
 ('stability', 'Estabilidade lateral com torção', 'NBR14762 §§8.2,9.8.2.2', 'FLT_coverage',
  'Comprimentos resistentes, diagrama e alturas das parcelas compatíveis. Leff não cria apoio nem encurta o vão físico de esforços/flechas.'),
 ('shear', 'Cortantes e seus domínios', 'NBR14762 §9.8.3; componentes EN separadas', 'shear',
  'Cobrir componentes não nulas e instabilidade ao cortante; tensão elástica de cisalhamento não substitui sozinha a verificação resistente.'),
 ('bending_shear', 'Flexão com cortante', 'NBR14762 §9.8.4; EN §6.1.10 em fonte separada', 'MV',
  'Solicitações concomitantes e denominadores compatíveis, sem somar máximos independentes ou misturar resistências entre normas.'),
 ('biaxial', 'Flexão biaxial', 'NBR14762 §9.9, rota N=0', 'biaxial',
  'Dispensa da parcela fraca exige ambas as ações paralelas explicitamente nulas. Não dispensa torção ou serviço combinado.'),
 ('torsion', 'Torção e empenamento', 'NBR14762 §8.1; componente complementar EN §6.1.6', 'torsion_warping',
  'Tsv, Tw e B do mesmo modelo e combinação; condições seccionais EN ficam separadas da estabilidade e da conclusão integral NBR.'),
 ('axial_scope', 'Domínio axial', 'NBR14762 §9.9', 'axial_scope',
  'N=0 é a hipótese explícita do vão isolado; não se exige resistência axial fictícia. Uma rede com N necessita de outra análise.'),
 ('point_introduction', 'Introdução localizada de P', 'NBR14762 §9.5.1 e Anexo D, quando aplicável', 'point_introduction_scope',
  'P real exige caminho da força e detalhe. P no limite matemático de apoio não descreve contato finito nem apaga reações.'),
 ('support_web', 'Alma nas reações de apoio', 'NBR14762 §9.5.1 e Anexo D.1', None,
  'Em cada apoio: alma ligada a viga/pilar e origem, ou contato pela mesa com c, distância ao extremo físico, mesa conectada, força oposta/distância e sinal compressivo. A rota local já existe em painel separado.'),
 ('support_model', 'Compatibilidade dos vínculos', 'NBR14762 §8.1', None,
  'Declarar translações, giro torsional e empenamento nos extremos. Garfo ideal é hipótese de análise, não detalhe de parafuso/solda nem exigência de inspeção.'),
 ('service_stiffness', 'Rigidez de serviço', 'NBR14762 §9.8.5(a)/(b)', 'deflection',
  'MLE sob tensões de serviço ou MSE no seu domínio. Ief uniaxial não qualifica automaticamente rigidez de flexão biaxial com B; crivo suficiente inconclusivo não é falha.'),
 ('service_displacement', 'Deslocamentos relevantes combinados', 'NBR14762 §8.1 e Anexo A', 'combined_ELS_scope',
  'Definir ponto e direção; compor flexão e rotação no mesmo campo e posição, com referência/corda compatível. Não somar flecha reduzida escalar e phi bruto de modelos diferentes.'),
 ('service_criteria', 'Limites e parcelas de serviço', 'NBR14762 Anexo A, Tabela A.1 notas a,e,f', None,
  'L/180: combinação rara, variáveis no mesmo sentido da permanente. L/120: somente variáveis opostas com valor característico. Selecionar parcelas e sequência construtiva conforme A.2.4/A.3.3; limites mais rigorosos podem aplicar-se.'),
 ('ponding', 'Empoçamento da cobertura', 'NBR14762 Anexo A, Tabela A.1 nota g', None,
  'Avaliar drenagem, declividade e deformada relevante. A nota requer evitar empoçamento, mas não fornece aqui um limiar angular universal.'),
 ('connections', 'Ligações e ancoragens', 'NBR14762 Seção 10, conforme detalhe', None,
  'Dimensionamento da ligação completa é separado do perfil e não implementado neste painel. Necessita arranjo, elementos, materiais, fixadores/soldas, distâncias e ações de transferência; não se presume detalhe físico.'),
)
REQUIRED_IDS = tuple(r[0] for r in DEFINITIONS)
_FALSE_FLAGS = ('whole_member_approved','combined_ELS_approved','normative_design_complete')

SCOPE = 'Inventário de fechamento da terça isolada. Registra requisitos e limites de implementação, sem converter componentes em aprovação normativa.'
EXCLUSIONS = ('Telha não contribui com rigidez nem travamento.',
              'Ensaios, GMNIA e limite angular arbitrário não são impostos universalmente.',
              'Leff é resistente; o vão físico integral permanece na análise.',
              'Ligações completas permanecem fora do dimensionamento do perfil neste app.')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
        separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _eligible(result):
    return (result.get('schema') in ('NBR14762_one_span_v1','tercas_batch_results_v1')
        and result.get('input_data',{}).get('member_application','purlin') == 'purlin')


def _source(result):
    out={k:result.get(k) for k in ('schema','input_data','input_fingerprint',
            'load_bundle','global_verification','model_domain_evidence')}
    from .support_scope import EVIDENCE
    if EVIDENCE in result:out[EVIDENCE]=result[EVIDENCE]
    return out


def _records(result):
    checks=result.get('global_verification',{}).get('checks',[])
    from .support_scope import saved as saved_support_scope, STATE, TEXT
    support_scope=saved_support_scope(result)
    records=[]
    for key,label,source,suffix,note in DEFINITIONS:
        if key=='support_web' and support_scope is not None:
            records.append(dict(id=key,label='Apoios locais — fora do escopo por decisão do usuário',
                source=support_scope['source'],condition_and_minimum_data=TEXT,
                evidence_ids=[],listed_component_counts={s:0 for s in ('meets','fails','pending','not_applicable')},
                evidence_state=STATE,requirement_state=STATE,
                not_consolidated_is_not_normative_inapplicability=True,
                blocks_listed_scope_completion=False,index=None,
                support_approved=False,normative_exemption=False))
            continue
        selected=[r for r in checks if suffix and
                  (r.get('id')==suffix or r.get('id','').endswith(':'+suffix))]
        local_objective = (key=='service_displacement' and bool(selected)
            and all(r.get('status')=='not_applicable' and r.get('trace',{}).get('criterion_scope')
                    =='outside_requested_local_deflection_objective' for r in selected))
        if local_objective:
            label='ELS combinado adicional — fora do objetivo solicitado'
            source='Escopo declarado: local_uniaxial_component_v1'
            note=('O critério escolhido verifica somente a vertical local da terça, normal à cobertura. '
                  'Não requer escolher ponto torsional ou calcular resultante/vertical global. '
                  'ELS combinado permanece análise adicional opcional; não há aprovação integral do membro.')
        counts={s:sum(r.get('status')==s for r in selected)
                for s in ('meets','fails','pending','not_applicable')}
        records.append(dict(id=key,label=label,source=source,condition_and_minimum_data=note,
            evidence_ids=[r['id'] for r in selected],listed_component_counts=counts,
            evidence_state='listed_components' if selected else 'not_consolidated',
            requirement_state=('outside_requested_local_deflection_objective' if local_objective else
                'outside_member_design_scope' if key=='connections' else
                'declared_N_zero_scope' if key=='axial_scope' and selected and
                    counts['not_applicable']==len(selected) else 'closure_not_qualified'),
            not_consolidated_is_not_normative_inapplicability=True))
    return records


def build(result):
    if not _eligible(result):return None
    from .support_scope import saved as saved_support_scope
    scoped=saved_support_scope(result) is not None
    return dict(schema=SCOPED_SCHEMA if scoped else SCHEMA,source_sha256=digest(_source(result)),normative_source_sha256=SOURCE_SHA256,
        required_ids=[k for k in REQUIRED_IDS if not (scoped and k=='support_web')],records=_records(result),service_preparation=prepare(result),
        **{k:False for k in _FALSE_FLAGS},
        scope=SCOPE, exclusions=list(EXCLUSIONS))


def attach(result):
    out=copy.deepcopy(result);record=build(result)
    if record is not None:
        record['snapshot_sha256']=digest(record);out[FIELD]=record
    return out


def saved(result):
    """Validate source inventory and limit arithmetic only; no history upgrade or solve."""
    record=result.get(FIELD)
    if record is None:return None
    from .support_scope import saved as saved_support_scope
    scoped=saved_support_scope(result) is not None
    if (not isinstance(record,dict) or record.get('schema')!=(SCOPED_SCHEMA if scoped else SCHEMA) or not _eligible(result)
            or record.get('source_sha256')!=digest(_source(result))
            or record.get('normative_source_sha256')!=SOURCE_SHA256
            or record.get('scope')!=SCOPE or record.get('exclusions')!=list(EXCLUSIONS)
            or record.get('snapshot_sha256')!=digest({k:v for k,v in record.items() if k!='snapshot_sha256'})
            or any(record.get(k) is not False for k in _FALSE_FLAGS)
            or record.get('required_ids')!=[k for k in REQUIRED_IDS if not (scoped and k=='support_web')]
            or [r.get('id') for r in record.get('records',[])]!=list(REQUIRED_IDS)
            or record.get('records')!=_records(result)):
        raise ValueError('Inventário salvo incompleto, alterado ou de outra fonte; nenhum histórico requalificado.')
    plan=record.get('service_preparation')
    if (not isinstance(plan,dict) or plan.get('combined_ELS_approved') is not False
            or plan.get('source_matrix_changed') is not False
            or any(r.get('status')!='prepared_not_calculated' or r.get('index') is not None
                   or r.get('displacement_mm') is not None for r in plan.get('prepared_cases',[]))):
        raise ValueError('Preparação de serviço não pode conter aprovação ou resultado calculado.')
    if plan != prepare(result):
        raise ValueError('Inventário ou aritmética de preparação de serviço divergente da fonte salva.')
    return copy.deepcopy(record)


def show(st,result):
    try:r=saved(result)
    except (ValueError,TypeError,KeyError) as exc:st.warning(str(exc));return
    if r is None:return
    from .completion_service_evidence import presentation
    evidence,error=presentation(result)
    with st.expander('Requisitos para concluir a terça isolada',expanded=False):
        st.caption(r['scope'])
        for row in r['records']:
            st.markdown('**'+row['label']+'**: '+row['condition_and_minimum_data'])
            for message in evidence.get(row['id'],[]):st.caption('Evidência calculada/salva: '+message)
        if error:st.warning(error)
        if not evidence:
            for message in _preparation_messages(r):st.caption(message)
        else:st.caption('Preparação normativa preservada. Respostas efetivamente calculadas e pendências específicas constam do componente ELS combinado abaixo.')


def report(doc,result):
    try:r=saved(result)
    except (ValueError,TypeError,KeyError) as exc:doc.add_paragraph(str(exc));return
    if r is None:return
    from .completion_service_evidence import presentation
    evidence,error=presentation(result)
    doc.add_heading('Requisitos para concluir a terça isolada',1)
    doc.add_paragraph(r['scope'])
    for row in r['records']:
        doc.add_paragraph(row['label']+' ('+row['source']+'): '+row['condition_and_minimum_data']+
            (' Evidência ELS autenticada detalhada a seguir.' if row['id'] in evidence else
             ' Evidência no inventário salvo: '+row['evidence_state']+'.'))
        for message in evidence.get(row['id'],[]):doc.add_paragraph(message)
    if error:doc.add_paragraph(error)
    if not evidence:
        doc.add_paragraph('Preparação de serviço salva: não altera combinações fornecidas e não contém deslocamentos calculados.')
        for message in _preparation_messages(r):doc.add_paragraph(message)
    else:
        doc.add_paragraph('Preparação normativa preservada; respostas e pendências efetivamente calculadas estão no componente ELS combinado, sem alterar a matriz fornecida.')


def _preparation_messages(record):
    """Presentation only: preserve the saved plan and historical wording."""
    local = any(r.get('requirement_state')=='outside_requested_local_deflection_objective'
                for r in record['records'])
    for message in record['service_preparation']['missing']:
        combined = message in (
            'Ponto, direção e referência/corda dos deslocamentos relevantes.',
            'Rigidez de serviço compatível com o campo combinado conforme §9.8.5.')
        yield ('Somente se for solicitada a análise combinada adicional: '+message
               if local and combined else message)
