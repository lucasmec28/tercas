"""Versioned user scope decision. No resistance, equilibrium or solver here.

Only creation/calculation paths produce this evidence. Saved readers validate
it, never migrate an earlier result or turn exclusion into normative exemption.
"""
import copy

FIELD = 'local_support_verification_scope'
MODE = 'outside_app_by_user_decision_v1'
EVIDENCE = 'local_support_scope_evidence'
STATE = 'outside_scope_by_user_decision'
TITLE = 'Verificações locais dos apoios fora do escopo'
TEXT = ('Por decisão do usuário, as verificações locais de apoio e de introdução '
        'das reações nas extremidades ficam fora do escopo deste app e serão '
        'tratadas pelo engenheiro no cálculo das ligações. Não são verificadas '
        'nem bloqueiam a conclusão dos critérios listados. Esta exclusão não '
        'significa apoio aprovado nem dispensa normativa. Reações, vínculos, '
        'esforços, deslocamentos e o modelo físico permanecem preservados. '
        'Contato local de P dentro do vão, forças interiores, cisalhamento da barra '
        'e suas interações permanecem em seus escopos próprios. O app não dimensiona ligações.')
EXCLUDED_IDS = ('support_web', 'support_force_introduction', 'NBR_branches.supports')


def enabled(data):
    if FIELD not in data:return False
    if data[FIELD] != MODE or not isinstance(data[FIELD], str):
        raise ValueError('Escopo local dos apoios desconhecido; nenhuma decisão convertida.')
    return True


def activate(data):
    enabled(data)
    out = copy.deepcopy(data)
    out[FIELD] = MODE
    return out


def adopt_for_calculation(data):
    """Current UI calculation payload, including an imported legacy study."""
    return activate(data)


def decision():
    return dict(schema=MODE, status=STATE, source='Decisão explícita do usuário sobre o escopo do app',
        reason=TEXT, excluded_check_ids=list(EXCLUDED_IDS), index=None,
        support_approved=False, normative_exemption=False, connection_design_checked=False,
        numerical_results_changed=False, whole_member_approved=False)


def _input_binding(result):
    from .application import fingerprint
    data=result['input_data']
    source=data
    if result.get('schema')=='three_girt_current_vlasov_demand_v1':
        from .three_girt_warping.application import fingerprint
        source=dict(data=data,config=result['configuration'])
    if fingerprint(source)!=result.get('input_fingerprint'):
        raise ValueError('Decisão de escopo dos apoios desvinculada das entradas salvas.')
    return result['input_fingerprint']


def annotate(result):
    """Fresh calculation only. Does not change any mechanical field."""
    if not enabled(result['input_data']):return
    result[EVIDENCE]=dict(decision(),source_input_fingerprint=_input_binding(result))


def saved(result):
    record=result.get(EVIDENCE)
    if record is None:
        if enabled(result.get('input_data',{})):
            raise ValueError('Decisão de escopo sem registro calculado; histórico não convertido.')
        return None
    if not enabled(result.get('input_data',{})) or record!=dict(decision(),source_input_fingerprint=_input_binding(result)):
        raise ValueError('Registro salvo de escopo dos apoios alterado ou incompatível.')
    return copy.deepcopy(record)


def apply_inventory(result, records):
    """Exclude only identified end-support criteria, never P/shear/model gates."""
    scope=saved(result)
    if scope is None:return records,None
    return [r for r in records if r['id'] not in EXCLUDED_IDS],scope



def validate_saved_inventory(result, summary):
    record=saved(result)
    if record is not None and (summary.get('local_support_scope_exclusion')!=record
            or any(r.get('id') in EXCLUDED_IDS for r in summary.get('checks',[]))):
        raise ValueError('Panorama salvo contradiz a decisão de escopo dos apoios locais.')
    if record is None and 'local_support_scope_exclusion' in summary:
        raise ValueError('Exclusão de apoio sem decisão salva no cálculo de origem.')
    return record

def report(doc,result):
    record=saved(result)
    if record is not None:
        doc.add_heading(TITLE,1)
        doc.add_paragraph(record['reason'])
        doc.add_paragraph('Política registrada: '+record['schema']+'. Sem índice de apoio; a exclusão não é uma verificação resistente.')
