"""Explicit local bearing subset; never changes loads, restraints or bending.

Optional absent/disabled input leaves the legacy branch unchanged. A positive
answer here concerns only local introduction by the recorded contact. It is not
connection design, physical verification, or complete member approval.
"""
import copy
import math
import hashlib
import json

FIELD = 'point_contact'
SCHEMA = 'point_contact_internal_compression_v1'
SOURCE = 'ABNT NBR 14762:2010 §9.5.1; Anexo D, Tabela D.2 e Figura D.1'
DECLARATIONS = {
    'section_geometry_and_material_verified': 'Declaro que a altura externa H, a espessura t, o raio interno ri e o material informados correspondem ao caso, com dois cantos de 90° na alma.',
    'compression_at_90_degrees': 'Declaro P compressiva introduzida por contato em uma mesa, no eixo forte local, com a alma a 90° da superfície de apoio/carregamento.',
    'unconnected_loaded_flange': 'Declaro a mesa sem ligação que restrinja sua rotação na região de P.',
    'no_local_stiffener': 'Declaro ausência de enrijecedor transversal na região de introdução de P.',
    'no_opposite_flange_force': 'Declaro que não existe outra força concentrada atuando na mesa oposta em todo o trecho modelado.',
    'end_reactions_through_webs': 'Declaro que ambas as reações de extremidade são transmitidas exclusivamente pelas almas ligadas a outra viga ou pilar, conforme §9.5.1.',
    'no_end_flange_contact': 'Declaro ausência de assento ou contato pelas mesas nas extremidades.',
    'physical_ends_match_span': 'Declaro que os extremos físicos da peça coincidem com 0 e L, sem balanços nem continuidade além deles.',
}
SCOPE = ('Somente introdução local interna de P compressiva em uma mesa não conectada, '
         'sem outra força concentrada na mesa oposta, sem enrijecedor local e com reações pelas almas. '
         'Não altera P, sua posição, vínculos, flexão, FLT, torção, AA/AISI ou o modelo 3D. '
         'P no limite junto ao apoio e componente paralela não nula permanecem pendentes. '
         'Esta opção descreve um detalhe local de transmissão de P e não altera as declarações existentes sobre telha/painel. '
         'Não presume contato, ligação, distribuição de P ou travamento fornecido pela telha. '
         'Declarações não comprovam condições físicas nem dimensionam ligações.')


def blank_choice():
    return dict(schema=SCHEMA, enabled=False, c_mm=None, origin='', basis=None,
                declarations={key: False for key in DECLARATIONS})


def configuration(data):
    """Validate structure only; absent physical values remain explicit pending."""
    if FIELD not in data:
        return None
    raw = data[FIELD]
    if (not isinstance(raw, dict) or set(raw) != {'schema', 'enabled', 'c_mm', 'origin', 'declarations', 'basis'}
            or raw.get('schema') != SCHEMA or type(raw.get('enabled')) is not bool):
        raise ValueError('Declaração de contato local desconhecida ou incompleta; entradas não convertidas.')
    c = raw['c_mm']
    if c is not None and not _finite(c):
        raise ValueError('Comprimento de contato deve ser número finito ou não informado; booleano não é comprimento.')
    if not isinstance(raw['origin'], str) or len(raw['origin']) > 2000:
        raise ValueError('Origem do contato local deve ser texto com até 2000 caracteres.')
    declared = raw['declarations']
    if (not isinstance(declared, dict) or set(declared) != set(DECLARATIONS)
            or any(type(v) is not bool for v in declared.values())):
        raise ValueError('Declarações do contato local ausentes ou inválidas; cada condição exige booleano explícito.')
    basis = raw['basis']
    if basis is not None:
        if (not isinstance(basis, dict) or set(basis) != {'catalog_index', 'member_application', 'L_mm', 'x_mm', 'section_values'}
                or type(basis.get('catalog_index')) is not int
                or basis.get('member_application') not in ('purlin', 'wall_girt')
                or not isinstance(basis.get('section_values'), dict)
                or set(basis['section_values']) != {'h', 'bf', 'lip', 't', 'ri_mm', 'fy_MPa'}):
            raise ValueError('Vínculo das declarações de contato inválido; não foi reconstruído.')
        values = [basis['L_mm'], basis['x_mm'], *basis['section_values'].values()]
        if any(v is not None and not _finite(v) for v in values):
            raise ValueError('Vínculo do contato contém dimensão/material inválido.')
    return copy.deepcopy(raw)


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except (ValueError, TypeError, OverflowError):
        return False


def reference_basis(data):
    """Pure binding to the current local case; not a physical attestation."""
    props = data.get('properties', {})
    L = data.get('L_mm')
    x = L / 2 if data.get('load_mode') == 'area' and _finite(L) else data.get('x_uls')
    return dict(catalog_index=data.get('catalog_index'),
                member_application=data.get('member_application', 'purlin'),
                L_mm=L, x_mm=x,
                section_values={k: copy.deepcopy(props.get(k)) for k in ('h','bf','lip','t','ri_mm','fy_MPa')})


def basis_matches(data, cfg=None):
    """Compare declared configuration without refreshing its historical binding."""
    if cfg is None:
        cfg = data.get(FIELD)
    return isinstance(cfg, dict) and cfg.get('basis') is not None and cfg['basis'] == reference_basis(data)


def evaluate(data, spec):
    """Return None when inactive, otherwise only the local point branch."""
    cfg = configuration(data)
    if cfg is None or not cfg['enabled']:
        return None
    common = dict(source=SOURCE, contact_contract=cfg, scope=SCOPE,
                  physical_conditions_verified=False, connection_design_checked=False)
    def pending(reason, **extra):
        return dict(common, status='not_evaluated', reason=reason, **extra)
    from .three_girt_application import enabled as three_girt_enabled
    if three_girt_enabled(data):
        return pending('Contato local opcional restrito ao vão isolado; não qualifica o sistema 3D.')
    p = data.get('P_uls')
    parallel = data.get('P_parallel_uls', 0.)
    if not _finite(p) or not _finite(parallel):
        return pending('Componentes locais da força P ausentes ou inválidas.')
    if parallel != 0:
        return pending('P possui componente paralela local não nula; a introdução combinada não está qualificada neste subconjunto.',
                       force_N=p, parallel_force_N=parallel)
    if p == 0:
        return dict(common, status='not_applicable', reason='Nenhuma força concentrada P nas duas componentes locais deste caso.')
    if p < 0:
        return pending('P não é compressiva no sentido local declarado; este subconjunto não verifica tração ou contato na mesa oposta.', force_N=p)
    missing = [key for key, value in cfg['declarations'].items() if value is not True]
    if missing:
        return pending('Condições físicas não declaradas para a introdução local: ' +
                       '; '.join(DECLARATIONS[key].removeprefix('Declaro ') for key in missing),
                       missing_declarations=missing, force_N=p)
    if not basis_matches(data, cfg):
        return pending('Declarações de contato não vinculadas à seção, material, aplicação, vão e posição atuais. Reconfirme a declaração de geometria/material; nenhum vínculo foi atualizado automaticamente.', force_N=p)
    if not cfg['origin'].strip():
        return pending('Falta a origem do comprimento de contato e das declarações locais; nenhum detalhe foi presumido.', force_N=p)
    c = cfg['c_mm']
    if not _finite(c) or c <= 0:
        return pending('Comprimento de contato da carga concentrada ausente ou inválido (é necessário um valor finito e positivo). Introdução local permanece pendente; nenhum comprimento foi presumido.', force_N=p)
    section = spec['selected_section']
    family = section.get('family')
    if family not in ('U', 'Ue'):
        return pending('Família fora do subconjunto de seções U/Ue implementado.', force_N=p)
    fields = section['fields']
    values = {key: fields.get(key, {}).get('value') for key in ('h', 't', 'ri_mm', 'fy_MPa')}
    H, t, ri, fy = (values[key] for key in ('h', 't', 'ri_mm', 'fy_MPa'))
    if (any(not _finite(v) for v in values.values()) or min(H, t, fy) <= 0 or ri < 0):
        return pending('Altura externa, espessura, raio interno ou fy ausentes/inválidos; não são inferidos do contato.', force_N=p)
    h = H - 2 * (ri + t)
    L, x = data.get('L_mm'), data.get('x_uls')
    if (not _finite(L) or not _finite(x) or L <= 0 or not 0 < x < L or h <= 0):
        return pending('Geometria da alma plana ou posição interna de P inválida para o subconjunto.', force_N=p)
    # The real physical endpoints were explicitly declared at 0/L. This distance
    # is NOT reused as a fictitious distance to a load on the opposite flange.
    end_distance = min(x - c / 2, L - x - c / 2)
    trace = dict(family=family, h_flat_mm=h, H_external_mm=H, t_mm=t, ri_mm=ri,
                 fy_MPa=fy, c_mm=c, theta_degrees=90, x_mm=x,
                 contact_edges_mm=[x-c/2, x+c/2], physical_endpoints_mm=[0., L],
                 end_distance_mm=end_distance,
                 classification_basis='no_opposite_concentrated_force_declared',
                 opposite_clear_distance_mm=None, loaded_flange_count=1,
                 flange_connection='unconnected', gamma=1.35)
    if end_distance <= 1.5 * h:
        return pending('Contato fora do subconjunto interno: a distância livre da borda carregada ao extremo físico da peça deve superar 1,5h. O caso próximo ao apoio permanece pendente.', force_N=p, domain=trace)
    if c < 20:
        return pending('Contato c inferior a 20 mm, fora do domínio implementado da Tabela D.2; c não foi aumentado automaticamente.', force_N=p, domain=trace)
    if h/t > 200 or c/t > 210 or c/h > 2:
        return pending('Geometria fora dos limites implementados da Tabela D.2: h/t ≤ 200, c/t ≤ 210 e c/h ≤ 2.', force_N=p, domain=trace)
    radius_limit = 5 if family == 'Ue' else 1
    if ri/t > radius_limit:
        return pending(f'Raio fora da linha interna de uma mesa não conectada: ri/t ≤ {radius_limit} para {family}.', force_N=p, domain=trace)
    from .core.anexo_d import frd
    try:
        capacity = frd(h=h, t=t, ri=ri, c=c, fy=fy,
                       end_distance=end_distance, opposite_clear_distance=None,
                       no_opposite_force=True, connected=False, lip=family=='Ue', theta=90)
    except (ValueError, TypeError, ArithmeticError) as exc:
        return pending('Introdução local fora do domínio implementado: '+str(exc), force_N=p, domain=trace)
    if not _finite(capacity) or capacity <= 0:
        return pending('Resistência local não finita ou não positiva; sem índice de aceitação.', force_N=p, domain=trace)
    index = p / capacity
    if not _finite(index) or index <= 0:
        return pending('Índice local não representável como número finito e positivo; sem aceitação.', force_N=p, domain=trace)
    result = dict(common, status='computed', FRd_N=capacity, force_N=p,
                  index=index, patch_mm=[x-c/2, x+c/2], origin=cfg['origin'],
                  domain=trace, criterion_status='meets' if p <= capacity else 'fails')
    result['evidence_sha256'] = _saved_digest(result)
    return result


def report(doc, result):
    """Read saved input/declarations only; no solver, validator or new verdict."""
    data = result.get('input_data', {})
    cfg = data.get(FIELD) if isinstance(data, dict) else None
    if not isinstance(cfg, dict):
        return
    doc.add_heading('Introdução local de P — declarações salvas', 1)
    doc.add_paragraph(SOURCE+'. '+SCOPE)
    doc.add_paragraph('Opção registrada: '+('ativa' if cfg.get('enabled') is True else 'inativa')+
                      '; schema: '+str(cfg.get('schema', 'não registrado'))+'.')
    contact_text = str(cfg['c_mm'])+' mm' if _finite(cfg.get('c_mm')) else 'não informado'
    doc.add_paragraph('Comprimento longitudinal de contato c salvo: '+contact_text+
                      '. Origem declarada (P e ambos os apoios): '+str(cfg.get('origin', 'não registrada'))+'.')
    doc.add_paragraph('Vínculo de configuração salvo: '+str(cfg.get('basis') or 'não informado')+'.')
    declared = cfg.get('declarations')
    if isinstance(declared, dict):
        for key, label in DECLARATIONS.items():
            value = declared.get(key)
            status = 'Declarado' if value is True else ('Não declarado' if value is False else 'Não registrado')
            doc.add_paragraph(status+': '+label.removeprefix('Declaro '))
    doc.add_paragraph('Domínio desta opção: c ≥ 20 mm; h/t ≤ 200; c/t ≤ 210; c/h ≤ 2; '
                      'ri/t ≤ 5 para Ue ou ≤ 1 para U. h é a parte plana da alma, '
                      'H−2(ri+t), e a borda de contato deve estar a mais de 1,5h do extremo físico. '
                      'Ausência de força na mesa oposta é declaração de configuração, não distância inventada. '
                      'P no limite junto ao apoio continua fora do subconjunto. '
                      'Este bloco transcreve entradas salvas, sem resolver ou requalificar o histórico.')
    for item in saved_records(result):
        label = 'Calculado — somente critério local' if item['status'] == 'computed' else 'Pendente no registro'
        values = '; '.join(name+'='+str(item[key])+unit for key,name,unit in [('P_normal_N','P normal',' N'),('P_parallel_N','P paralelo',' N'),('c_mm','c',' mm'),('FRd_N','FRd local',' N'),('index','índice local','')] if item[key] is not None)
        doc.add_paragraph(item['combination_id']+' — '+label+'. '+values+'. '+item['reason'])



def _saved_digest(record):
    payload = {k: v for k, v in record.items() if k != 'evidence_sha256'}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def _saved_numeric_coherent(raw, cfg, data, combination, normal, parallel, family):
    """Validate links among saved scalars only; never call a resistance formula."""
    try:
        if (raw.get('status') != 'computed' or raw.get('source') != SOURCE
                or raw.get('contact_contract') != cfg or cfg.get('schema') != SCHEMA
                or not basis_matches(data, cfg)
                or raw.get('evidence_sha256') != _saved_digest(raw)
                or not _finite(normal) or normal <= 0 or not _finite(parallel) or parallel != 0
                or raw.get('force_N') != normal
                or combination.get('point_position') == 'support_limit'
                or not _finite(raw.get('FRd_N')) or raw['FRd_N'] <= 0
                or not _finite(raw.get('index')) or raw['index'] <= 0
                or raw['index'] != normal/raw['FRd_N']
                or raw.get('criterion_status') != ('meets' if raw['index'] <= 1 else 'fails')):
            return False
        declared = cfg.get('declarations')
        if (not isinstance(declared, dict) or set(declared) != set(DECLARATIONS)
                or any(v is not True for v in declared.values())):
            return False
        trace = raw.get('domain', {})
        x = combination.get('x_mm', data.get('x_uls'))
        c, L = cfg.get('c_mm'), data.get('L_mm')
        if not all(_finite(v) for v in (x,c,L)):
            return False
        props = data.get('properties', {})
        H,t,ri,fy = (props.get(k) for k in ('h','t','ri_mm','fy_MPa'))
        if not all(_finite(v) for v in (H,t,ri,fy)) or family not in ('U','Ue'):
            return False
        edges = [x-c/2, x+c/2]
        return (trace.get('family') == family
                and trace.get('H_external_mm') == H and trace.get('t_mm') == t
                and trace.get('ri_mm') == ri and trace.get('fy_MPa') == fy
                and trace.get('h_flat_mm') == H-2*(ri+t)
                and trace.get('classification_basis') == 'no_opposite_concentrated_force_declared'
                and trace.get('opposite_clear_distance_mm') is None
                and trace.get('loaded_flange_count') == 1
                and trace.get('flange_connection') == 'unconnected'
                and trace.get('theta_degrees') == 90 and trace.get('gamma') == 1.35
                and trace.get('c_mm') == c and trace.get('x_mm') == x
                and trace.get('physical_endpoints_mm') == [0.,L]
                and trace.get('contact_edges_mm') == edges and raw.get('patch_mm') == edges
                and trace.get('end_distance_mm') == min(edges[0],L-edges[1]))
    except (TypeError, ValueError, ArithmeticError, KeyError, OverflowError):
        return False

def saved_records(result):
    """Typed saved values for the complement only. Never rebuild a missing check."""
    data = result.get('input_data', {})
    cfg = data.get(FIELD) if isinstance(data, dict) else None
    if not isinstance(cfg, dict) or cfg.get('enabled') is not True:
        return []
    if result.get('schema') == 'tercas_batch_results_v1':
        cases = [(item.get('combination', {}), item.get('evidence', {})) for item in result.get('cases', [])]
    elif result.get('schema') == 'NBR14762_one_span_v1':
        cases = [(dict(id='DIRECT_ELU', limit_state='ELU',
                       P_vector=dict(normal=data.get('P_uls'), parallel=data.get('P_parallel_uls', 0.))), result)]
    else:
        return []
    snapshot = result.get('common_input_snapshot', result.get('input_snapshot', {}))
    family = snapshot.get('selected_section', {}).get('family') if isinstance(snapshot,dict) else None
    output = []
    for combination, evidence in cases:
        if combination.get('limit_state') != 'ELU':
            continue
        vector = combination.get('P_vector', {})
        normal, parallel = vector.get('normal'), vector.get('parallel')
        if not any(_finite(p) and p != 0 for p in (normal, parallel)):
            continue
        raw = evidence.get('NBR_branches', {}).get('point', {})
        raw = raw if isinstance(raw, dict) else {}
        numeric = _saved_numeric_coherent(raw,cfg,data,combination,normal,parallel,family)
        reason = raw.get('reason', '')
        if not raw:
            reason = 'Sem registro local salvo; a declaração isolada não constitui cálculo.'
        elif raw.get('status') == 'computed' and not numeric:
            reason = 'Registro local não vinculado a estas declarações ou incompleto; histórico não requalificado. O resumo global é o originalmente salvo; suas contagens não foram recompostas após a recusa deste complemento.'
        elif not reason and not numeric:
            reason = 'Introdução local pendente no registro salvo.'
        if numeric:
            reason = {'meets': 'Atende ao critério local no registro salvo.', 'fails': 'Não atende ao critério local no registro salvo.'}.get(raw.get('criterion_status'), 'Critério local calculado no registro salvo.')
            reason += ' Não aprova ligação, apoios ou elemento completo.'
        output.append(dict(combination_id=str(combination.get('id', 'não registrado')),
                           P_normal_N=normal if _finite(normal) else None,
                           P_parallel_N=parallel if _finite(parallel) else None,
                           c_mm=cfg.get('c_mm') if _finite(cfg.get('c_mm')) else None,
                           FRd_N=raw['FRd_N'] if numeric else None,
                           index=raw['index'] if numeric else None,
                           status='computed' if numeric else 'pending', reason=str(reason)))
    return output
