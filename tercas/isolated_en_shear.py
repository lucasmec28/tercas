"""Optional web-only EN snapshot on the already validated isolated demand.

Vy=dMx/ds is the strong/web shear in this solver; Vx is the weak shear.
The existing §6.1.5 geometric capacity floor is independent of the §6.1.6
stress component and never supplies a general N-M-V interaction denominator.
"""
import copy
import math
import numpy as np

from .three_girt_shear import en_web_lower_capacity, SOURCE_EN
from .torsion_vlasov.intervals import Interval as I, stack
from .torsion_vlasov.yield_envelope import _member_polynomials

SCHEMA = 'isolated_EN_web_shear_sufficient_v1'
SCOPE = ('Componente da alma: Vy=dMx/ds, hw=H−t e área hw·t; Vx fraco e Tsv/Tw não '
         'são convertidos em Vy. Teto ≤1 é suficiente somente para a componente Vy transversal '
         'de §6.1.5; acima é inconclusivo. '
         'Teto ≤0,5 é o limiar da componente transversal; dispensa §6.1.10(1) somente no '
         'domínio declarado sem flexão/cortante fracos, B, Tsv e Tw. Com outros esforços, '
         'a dispensa permanece pendente. Não conclui interação geral, estabilidade, forças locais, ligações ou ELS.')
FLAGS = ('whole_member_approved', 'complete_EN_design_qualified', 'global_stability_qualified',
         'general_N_M_V_interaction_qualified', 'weak_shear_resistance_qualified',
         'torsional_shear_buckling_qualified', 'NBR_capacities_used', 'AISI_capacities_used')
NUMERICAL_SCOPE = 'Outward-rounded recovered affine demand; geometric capacity floor evaluated in binary64; not an FE-error certificate'
AXES = dict(web_shear='Vy_N', strong_moment='Mx_physical_Nmm',
            derivative='Vy=dMx/ds', excluded_weak_shear='Vx_N')


def _criteria(upper, restricted_domain):
    return (dict(index_upper=upper, status='meets' if upper <= 1. else 'inconclusive',
                 component_scope='transverse_Vy_only', observed_failure=False),
            dict(ratio_upper=upper, threshold=.5,
                 transverse_component_threshold_met=upper <= .5,
                 status='meets' if upper <= .5 and restricted_domain else 'pending',
                 shear_reduction_waiver_qualified=upper <= .5 and restricted_domain,
                 general_interaction_qualified=False))


def _weak_zero(demand):
    return (demand['support_reactions']['left_force_xy_N'][0] == 0.
        and all(a['q_xy_N_mm' if a['kind']=='uniform' else 'force_xy_N'][0] == 0.
                for a in demand['loads'])
        and all(s['Vx_N'] == 0. for s in demand.get('support_limit_states', [])))


def _waiver_domain(demand):
    """Exact zero proofs, no tolerances or discarded B/T/weak actions.

    Saved summaries already contain complete individual-field extrema. Reading
    them checks the proof's saved scalars; it does not rebuild any field.
    """
    fields=('B_Nmm2','Tsv_Nmm','Tw_Nmm')
    if demand['schema']=='single_vlasov_member_demand_v1':
        zero={key:all(v==0. for e in demand['elements'] for v in e['coefficients'][key])
            and all(s[key]==0. for s in demand.get('support_limit_states',[])) for key in fields}
    else:
        zero={key:demand['field_envelopes'][key]['maximum_absolute']['value']==0.
            and all(s[key]==0. for s in demand.get('support_limit_states',[])) for key in fields}
    weak_zero=_weak_zero(demand)
    return dict(weak_bending_and_shear_identically_zero=weak_zero,
        bimoment_identically_zero=zero['B_Nmm2'],
        torsional_shear_identically_zero=zero['Tsv_Nmm'] and zero['Tw_Nmm'])


def calculate_validated(demand, profile, model_origin, *, certificate=None):
    """Internal: caller first validates the intact pinned own-Ue ELU field."""
    from .isolated_en_stress import _sha
    dims = profile['geometry_external_mm']
    capacity = en_web_lower_capacity(h_mm=dims['h'], t_mm=dims['t'], fyb_MPa=250.)
    pol, identities = _member_polynomials(demand)
    # Affine shear has its absolute maximum at a piece endpoint. Distinct
    # elements retain both point-load sides; support-limit states are pieces.
    endpoints = stack([pol['Vy'][:, 0], pol['Vy'][:, 0] + pol['Vy'][:, 1]], axis=-1)
    pieces = []
    for k, identity in enumerate(identities):
        source = copy.deepcopy(identity)
        if source['kind'] == 'support_limit':
            state = source.pop('state')
            source.update(x_mm=state['x_mm'], position_limit=state['position_limit'])
        pieces.append(dict(source_piece=source,
            Vweb_end_intervals_N=[[float(endpoints.lo[k,j]), float(endpoints.hi[k,j])] for j in (0,1)],
            Vweb_abs_upper_N=float(np.max(endpoints[k].abs().hi))))
    upper = max(p['Vweb_abs_upper_N'] for p in pieces)
    ratio = float((I(upper) / capacity['Vw_Rd_lower_N']).hi)
    waiver_domain = _waiver_domain(demand)
    shear, reduction = _criteria(ratio, all(waiver_domain.values()))
    out = dict(schema=SCHEMA, source=SOURCE_EN, scope=SCOPE, axes=copy.deepcopy(AXES),
        combination_id=demand['combination_id'], member_id=demand['member_id'],
        source_demand_sha256=_sha(demand), source_geometry_sha256=demand['section']['nodes_sha256'],
        model_origin=model_origin, intact_section_model_declared=True,
        nominal_geometry_mm=copy.deepcopy(dims), web_area_mm2=capacity['hw_mm']*dims['t'],
        capacity=capacity, pieces=pieces, full_member_field_covered=True,
        maximum_Vweb_abs_upper_N=upper, web_shear=shear, no_web_shear_reduction=reduction,
        waiver_domain=waiver_domain,
        weak_shear_identically_zero=_weak_zero(demand),
        numerical_scope=NUMERICAL_SCOPE,
        **{key:False for key in FLAGS})
    if certificate is not None:
        try:
            from .isolated_en_mv import calculate
            out['bending_shear_component']=calculate(demand,profile,certificate,out)
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
            out['bending_shear_error']=str(exc)
    out['content_sha256'] = _sha(out)
    return out


def _finite(x, *, nonnegative=False):
    return type(x) in (int,float) and math.isfinite(x) and (not nonnegative or x >= 0.)


def validate_saved(out, row, summary, ev):
    """Check saved identities/arithmetic only, without sources/solver/capacity calls."""
    from .isolated_en_stress import _sha
    if (not isinstance(out,dict) or out.get('schema') != SCHEMA
        or out.get('content_sha256') != _sha({k:v for k,v in out.items() if k!='content_sha256'})
        or out.get('source') != SOURCE_EN or out.get('scope') != SCOPE or out.get('axes') != AXES
        or out.get('numerical_scope') != NUMERICAL_SCOPE
        or out.get('combination_id') != row['combination_id']
        or out.get('member_id') != summary['member_id']
        or out.get('source_demand_sha256') != row['source_analysis_sha256']
        or out.get('source_geometry_sha256') != ev['source_profile']['nodes_sha256']
        or out.get('model_origin') != ev['configuration']['model_origin']
        or out.get('intact_section_model_declared') is not True
        or out.get('full_member_field_covered') is not True
        or any(out.get(key) is not False for key in FLAGS)):
        raise ValueError('Snapshot EN de cortante da alma incompatível ou escopo ampliado.')
    t = ev['source_profile']['thickness_mm']; cap = out['capacity']; hw = 100.-t
    if (any(not _finite(cap.get(k),nonnegative=True) for k in ('hw_mm','sw_upper_mm','E_MPa',
            'fyb_MPa','gamma_M0','lambda_w_upper','fbv_lower_MPa','Vw_Rd_lower_N'))
        or out.get('nominal_geometry_mm') != dict(h=100.,b=50.,lip=17.,t=t,ri=t)
        or out.get('web_area_mm2') != hw*t
        or any(cap.get(k)!=v for k,v in dict(hw_mm=hw, sw_upper_mm=hw, E_MPa=210000.,
            fyb_MPa=250., gamma_M0=1., source=SOURCE_EN,
            capacity_kind='conservative_lower_bound').items())
        or cap.get('support_stiffener_credit') is not False
        or cap.get('longitudinal_stiffener_credit') is not False):
        raise ValueError('Geometria/material EN da alma salvos inválidos.')
    # Replay scalar arithmetic only, never open a profile or call resistance code.
    lam=.346*hw/t*math.sqrt(250./210000.)
    fbv,branch=(.58*250.,'yield') if lam<=.83 else ((.48*250./lam,'intermediate') if lam<1.4 else (.67*250./lam**2,'elastic'))
    if (cap.get('lambda_w_upper')!=lam or cap.get('fbv_lower_MPa')!=fbv
        or cap.get('branch')!=branch or cap.get('Vw_Rd_lower_N')!=hw*t*fbv):
        raise ValueError('Aritmética salva do piso EN da alma divergente.')
    pieces=out['pieces']; count=summary['element_count']; previous=0.; maximum=0.
    states=summary.get('support_limit_states',[])
    if type(count) is not int or count<=0 or not isinstance(pieces,list) or len(pieces)!=count+len(states):
        raise ValueError('Cobertura da alma incompleta, inclusive before-P.')
    for index,piece in enumerate(pieces):
        source=piece['source_piece']
        if index<count:
            if (source.get('kind')!='element' or type(source.get('element_index')) is not int
                or source['element_index']!=index or not isinstance(source.get('element_id'),str)
                or not _finite(source.get('a_mm')) or not _finite(source.get('b_mm'))
                or source['a_mm']!=previous or source['b_mm']<=previous):
                raise ValueError('Cobertura longitudinal salva da alma inválida.')
            previous=source['b_mm']
        else:
            state=states[index-count]
            if source!=dict(kind='support_limit',element_id=state['element_id'],
                            x_mm=state['x_mm'],position_limit=state['position_limit']):
                raise ValueError('Cortante before-P não corresponde ao estado salvo.')
        endpoints=piece['Vweb_end_intervals_N']
        if (not isinstance(endpoints,list) or len(endpoints)!=2
            or any(not isinstance(v,list) or len(v)!=2 or not all(_finite(x) for x in v)
                   or v[0]>v[1] for v in endpoints)):
            raise ValueError('Intervalos salvos do cortante da alma inválidos.')
        peak=max(abs(v) for pair in endpoints for v in pair)
        if not _finite(piece.get('Vweb_abs_upper_N'),nonnegative=True) or piece['Vweb_abs_upper_N']!=peak:
            raise ValueError('Máximo salvo do cortante da alma divergente.')
        maximum=max(maximum,peak)
    if previous!=summary['length_mm'] or out.get('maximum_Vweb_abs_upper_N')!=maximum:
        raise ValueError('Envelope salvo da alma incompleto/divergente.')
    # The compact source already preserves the complete individual Vy extrema.
    # A self-consistent rehash must not replace real nonzero shear by zero.
    envelope=summary['field_envelopes']['Vy_N']
    source_values=[envelope[k]['value'] for k in ('minimum','maximum','maximum_absolute')]
    if any(not _finite(v) or abs(v)>maximum for v in source_values):
        raise ValueError('Teto da alma não cobre os extremos Vy da demanda compacta.')
    by_piece={(p['source_piece']['kind'],p['source_piece']['element_id']):p for p in pieces}
    if len(by_piece)!=len(pieces):raise ValueError('Identidade de trecho de cortante duplicada.')
    for state in summary['witnesses']+states:
        kind='support_limit' if state.get('element_index') is None else 'element'
        piece=by_piece.get((kind,state['element_id']))
        if piece is None:raise ValueError('Testemunha Vy sem trecho/estado correspondente.')
        endpoints=piece['Vweb_end_intervals_N'];u=state['u'];value=state['Vy_N']
        if not _finite(u) or not 0.<=u<=1. or not _finite(value):
            raise ValueError('Testemunha compacta Vy inválida.')
        if kind=='support_limit':
            if any(not lo<=value<=hi for lo,hi in endpoints):
                raise ValueError('Intervalo before-P não contém Vy do estado compacto.')
        else:
            source=piece['source_piece']
            if state['element_index']!=source['element_index']:
                raise ValueError('Testemunha compacta Vy pertence a outro trecho.')
            at_state=I(*endpoints[0])*(I(1.)-I(u))+I(*endpoints[1])*I(u)
            if not float(at_state.lo)<=value<=float(at_state.hi):
                raise ValueError('Intervalo afim da alma não contém a testemunha compacta Vy.')
    ratio=float((I(maximum)/cap['Vw_Rd_lower_N']).hi)
    waiver_domain=_waiver_domain(summary)
    shear,reduction=_criteria(ratio,all(waiver_domain.values()))
    if (out.get('web_shear')!=shear or out.get('no_web_shear_reduction')!=reduction
        or out.get('waiver_domain')!=waiver_domain
        or any(type(v) is not bool for v in out['waiver_domain'].values())
        or type(out.get('weak_shear_identically_zero')) is not bool
        or out['weak_shear_identically_zero'] is not _weak_zero(summary)):
        raise ValueError('Critérios salvos da alma/dispensa EN divergentes.')

    if 'bending_shear_component' in out:
        from .isolated_en_mv import validate_saved as validate_mv
        validate_mv(out['bending_shear_component'],out,row,summary,ev)
    elif 'bending_shear_error' in out and (not isinstance(out['bending_shear_error'],str) or not out['bending_shear_error']):
        raise ValueError('Pendência M–V EN sem motivo.')
