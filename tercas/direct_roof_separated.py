"""Known profile self-weight at CG, entered direct external actions at roof top."""
import copy
from .direct_self_weight import evidence, calculation_inputs, TEXT
from .ltb_load_height import finite
SCHEMA = 'roof_top_load_evidence_v3'
BASIS = 'direct_external_top_profile_PP_CG'


def combinations(data):
    ev = evidence(data)
    if ev is None: raise ValueError('Convenção explícita sem PP necessária para separação.')
    effective = calculation_inputs(data)
    out = []
    for state, suffix in (('ELU','uls'), ('ELS','sls')):
        trace = ev['states'][suffix]
        p = finite(data['P_'+suffix], 'P '+state)
        pp = finite(data.get('P_parallel_'+suffix,0.), 'P paralelo '+state)
        out.append(dict(id='DIRECT_'+state, limit_state=state,
            type=state+' direto — ações externas + PP automático',
            q_N_mm=effective['q_'+suffix], P_N=p,
            x_mm=finite(data['x_'+suffix], 'posição P '+state),
            q_vector=copy.deepcopy(trace['total_q_N_mm']), P_vector=dict(normal=p,parallel=pp),
            external_q_vector=copy.deepcopy(trace['external_q_N_mm']),
            profile_PP_q_vector=copy.deepcopy(trace['profile_PP_q_N_mm']),
            profile_PP_factor=trace['factor'], load_basis=BASIS, source=TEXT))
    return out


def actions(combo, geo, *, include_parallel=False):
    acts=[]; parallel=[]
    for name, vector, is_pp in [('EXTERNAL', combo['external_q_vector'], False),
                                 ('PP', combo['profile_PP_q_vector'], True)]:
        if vector['parallel'] != 0: parallel.append(name)
        if vector['normal'] == 0 and vector['parallel'] == 0: continue
        ex=None
        if geo['coherent_torsion_section']:
            ex=geo['CG_xy_mm'][0]-geo['SC_xy_mm'][0] if is_pp else geo['x_from_SC_mm']
        acts.append(dict(name=name, kind='uniform', q_down_N_mm=vector['normal'],q_parallel_N_mm=vector['parallel'],
            height_above_SC_mm=0. if is_pp else geo['height_above_SC_mm'], x_from_SC_mm=ex,
            load_line_source='PP no CG, calculado uma única vez pela massa do perfil' if is_pp else geo['source']))
    pv=combo['P_vector']
    if pv['parallel'] != 0: parallel.append('P')
    if pv['normal'] != 0 or pv['parallel'] != 0:
        acts.append(dict(name='P',kind='point',P_down_N=pv['normal'],P_parallel_N=pv['parallel'],s_mm=combo['x_mm'],
            height_above_SC_mm=geo['height_above_SC_mm'],x_from_SC_mm=geo['x_from_SC_mm'],
            load_line_source=geo['source'],position='fixed'))
    if not include_parallel:
        for a in acts:
            a.pop('q_parallel_N_mm',None);a.pop('P_parallel_N',None)
    return acts,parallel
