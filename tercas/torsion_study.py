"""Explicit own-reference torsion option; no modification of bending results.

The selected method is a single gross elastic Vlasov model. Its analysis is not
a resistance formula and does not qualify pure-bending capacities under B/T.
"""
import copy
import hashlib
import math
from pathlib import Path

FIELD = 'torsion_model'
SCHEMA = 'purlin_vlasov_choice_v1'
SUPPORTS = 'R01_fork_free_warping'
ROLES = ('CP', 'SC', 'V_Cima', 'V_Baixo', 'P')
LABELS = {'CP':'Permanente externo (telha/revestimento)', 'SC':'Sobrecarga',
          'V_Cima':'Vento para cima', 'V_Baixo':'Vento para baixo', 'P':'Força concentrada P'}
PINS = {
    1.20:'f74d3f941e59af0bceb3a2fdae414e8aa479b14b16cbe284c1dff3f3e816b005',
    1.50:'9a30115583275a30ab25eb8c782398a8aa5d547b8272743da9cd2f8342f880d4',
    2.00:'fde5d287a73df9adf1b9ab3e392d7207c3423acb7a8894de5553d402cc7aef90',
    2.25:'8db5d3c4a037e01e665860c1ad8878bab01330cc07fc4165f74a40c0862ec562',
    2.65:'40aada8e49914bb1384c8ac205d8035225d5c033e1e76de8fa65f022ebdd99f1',
    3.00:'e45b3298a2a95cca875b558269046090751e3bff2fa1b9dfae3cc0c1a2a97919',
    3.35:'f1e9676c843459bcb7c14341a32ab10cc90c8ab6765e056fe9bcd47e3b58dd05'}
SCOPE = ('Torção de Vlasov, GJ + ECw, conforme mecânica do Anexo A do manual CBCA: '
         'um vão prismático isolado, seção bruta própria R01, primeira ordem. '
         'Garfos ideais nas extremidades: giro de torção impedido e empenamento livre, '
         'hipótese da referência, não comprovação da ligação real. '
         'Sem contato ou travamento pela telha. Este diagnóstico calcula demanda; '
         'não acrescenta resistência com T/B nem aprova ELU ou ELS.')


def scope_for(data):
    from .ue_catalog_reference import claims_reference, SCOPE as own_scope
    return own_scope if claims_reference(data) else SCOPE


def configuration(data):
    """Absent is legacy. Missing line is permitted; malformed data are not."""
    if FIELD not in data:return None
    c = data[FIELD]
    if (not isinstance(c, dict) or set(c) != {'schema','enabled','support_hypothesis','load_lines'}
            or c.get('schema') != SCHEMA or type(c.get('enabled')) is not bool
            or c.get('support_hypothesis') != SUPPORTS):
        raise ValueError('Modelo de torção desconhecido ou incompleto; entradas não convertidas.')
    records = c['load_lines']
    if not isinstance(records, dict) or set(records)-set(ROLES):
        raise ValueError('Papéis das linhas de carga de torção inválidos.')
    for role, record in records.items():
        if (not isinstance(record, dict) or set(record) != {'declared','xy_from_CG_mm','origin'}
                or type(record.get('declared')) is not bool):
            raise ValueError('Declaração da linha '+role+' inválida.')
        xy = record['xy_from_CG_mm']
        if (not isinstance(xy, list) or len(xy) != 2 or
                any(v is not None and (isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v)) for v in xy)):
            raise ValueError('Coordenadas de '+role+' devem ser finitas ou não informadas.')
        if not isinstance(record['origin'],str):
            raise ValueError('Origem da linha '+role+' deve ser texto.')
    return copy.deepcopy(c)


def blank_choice():
    return dict(schema=SCHEMA, enabled=True, support_hypothesis=SUPPORTS, load_lines={})


def automatic_roof_choice(data):
    """Effective model choice, never a mutation of stored manual load lines."""
    from .roof_top_load import enabled as roof_enabled,geometry
    if not roof_enabled(data) or data.get('member_application','purlin')!='purlin':return None
    from .ue_family_reference import claims_reference as family_claims
    from .ue_reference import claims_reference as single_claims
    from .ue_catalog_reference import claims_reference as catalog_claims
    if not (family_claims(data) or single_claims(data) or catalog_claims(data)):return None
    g=geometry(data);c=blank_choice()
    for role in ROLES:
        c['load_lines'][role]=dict(declared=True,
            xy_from_CG_mm=[g['x_from_CG_mm'],g['y_from_CG_mm']],
            origin='Esquema de cobertura selecionado: '+g['load_line']+' na superfície superior. '+g['source'])
    return c


def section_for(data):
    from .ue_catalog_reference import claims_reference, section_for as own_section
    if claims_reference(data):return own_section(data)
    """Read and validate exact source bytes on every explicit calculation."""
    from .ue_family_reference import claims_reference as family_claims, assess as family_assess
    from .ue_reference import claims_reference as single_claims, assess as single_assess
    state = family_assess(data) if family_claims(data) else single_assess(data) if single_claims(data) else None
    if not state or not state.get('calculable'):
        raise ValueError('Torção disponível somente na referência própria Ue100 íntegra e calculável.')
    t = data['properties']['t']
    if isinstance(t,bool) or t not in PINS:raise ValueError('Espessura sem contorno próprio qualificado.')
    path = Path(__file__).parent/'data'/'torsion_profiles'/f'ue100x50x17_t{t:.2f}.json'
    if hashlib.sha256(path.read_bytes()).hexdigest() != PINS[t]:
        raise ValueError('Arquivo do contorno próprio de torção alterado.')
    from .torsion_vlasov.section import load_profile
    return load_profile(path)


def pending_evidence(result, reason):
    return dict(schema='purlin_torsion_pending_v1', status='pending_model_data',
        source_input_fingerprint=result.get('input_fingerprint'), reason=reason,
        computed_cases=0, pending_model_cases=len(result.get('cases',[])),
        coverage_complete=False, resistance_qualified=False, whole_member_approved=False,
        scope=SCOPE, records=[])


def attach(result):
    """Called only after a new calculation, never while rendering old exports."""
    c = configuration(result['input_data'])
    automatic=automatic_roof_choice(result['input_data'])
    if automatic is not None:c=automatic
    if c is None or not c['enabled']:return copy.deepcopy(result)
    data = result['input_data']
    from .ue_catalog_reference import claims_reference as catalog_claims
    if catalog_claims(data) and automatic is None:
        out=copy.deepcopy(result)
        out['torsion_evidence']=pending_evidence(result,
            'Contorno próprio Ue: o adaptador de ações exige o esquema do topo ativo. Linhas manuais anteriores permanecem armazenadas, mas não substituem esse esquema.')
        out['torsion_evidence']['scope_pt']=scope_for(data)
        return out
    if data.get('member_application','purlin')=='wall_girt':
        out=copy.deepcopy(result)
        out['torsion_evidence']=pending_evidence(result,
            'Declarações de torção preservadas, mas inativas na travessa isolada: o adaptador Vlasov publicado nesta candidata é exclusivo da terça. Nenhuma linha, giro ou torção nula foi inferida para o fechamento.')
        return out
    from . import direct_torsion
    if automatic is not None and direct_torsion.active(data):
        return direct_torsion.attach(result, automatic)
    if result.get('schema') != 'tercas_batch_results_v1' or data.get('load_mode') != 'area':
        out = copy.deepcopy(result)
        out['torsion_evidence'] = pending_evidence(result,
            'O adaptador atual exige ações por área separadas e combinações preservadas. '
            'Ações diretas/3D não são decompostas ou substituídas por uma terça isolada.')
        return out
    from .ue_family_reference import claims_reference as family_claims
    from .ue_reference import claims_reference as single_claims
    from .ue_catalog_reference import claims_reference as catalog_claims
    if not (family_claims(data) or single_claims(data) or catalog_claims(data)):
        out=copy.deepcopy(result)
        out['torsion_evidence']=pending_evidence(result,
            'Declarações de linhas preservadas, mas sem aplicação à seção atual: '
            'o contorno setorial do adaptador foi qualificado apenas para as referências próprias Ue100.')
        return out
    section = section_for(data)
    from .torsion_vlasov.adapter import attach_torsion_evidence, load_lines_from_cg, summarize_torsion_evidence
    complete_lines = {k:r for k,r in c['load_lines'].items() if r['declared']
        and r['origin'].strip() and all(v is not None for v in r['xy_from_CG_mm'])}
    lines = load_lines_from_cg(section, complete_lines)
    supports = {side:dict(twist='fixed',warping='free_assumed',origin=
        'Hipótese R01 da referência própria: garfo ideal, empenamento livre; não comprova ligação real.')
        for side in ('left','right')}
    out = attach_torsion_evidence(result, section=section, load_lines=lines, supports=supports)
    from .aisi_torsion_component import attach_dense
    from .ue_catalog_reference import claims_reference as catalog_claims, attach_resistance
    out = attach_resistance(out, section) if catalog_claims(data) else attach_dense(out, section)
    from .isolated_en_application import attach_dense as attach_EN_dense
    out = attach_EN_dense(out, section)
    from .isolated_service_component import attach_dense as attach_service_dense
    out = attach_service_dense(out, section)
    out['torsion_evidence'] = summarize_torsion_evidence(out['torsion_evidence'])
    out['torsion_evidence']['choice_snapshot'] = copy.deepcopy(c)
    if automatic is not None:
        out['torsion_evidence']['load_line_choice_source']='automatic_selected_roof_scheme'
        out['torsion_evidence']['stored_manual_choice_preserved']=configuration(data)
    out['torsion_evidence']['scope_pt'] = scope_for(data)
    out['whole_member_approved'] = False
    return out
