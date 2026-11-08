"""Read saved isolated ELU P inventory; retain support reactions separately."""
import copy
import math
from ..support_web import sources as supports


def extract(result):
    if result.get('schema') not in ('NBR14762_one_span_v1','tercas_batch_results_v1'):
        raise ValueError('Introdução de P restrita ao vão isolado salvo.')
    if result.get('input_data',{}).get('member_application','purlin')!='purlin':
        raise ValueError('Componente restrita à terça isolada; travessa não convertida.')
    src=supports.extract(result)
    if src['section']['family']!='Ue':
        raise ValueError('Ampliação restrita a Ue; a rota legada U permanece inalterada.')
    points=[]
    for record in src['supports']:
        if record['support_id']!='left':continue
        trace=record['trace'];c=trace['combination'];cid=c['id'];x=c['x_mm']
        if result['schema']=='NBR14762_one_span_v1':
            ev=result['inclination_evidence']['ELU']
        else:
            ev=next(case['evidence']['inclination'] for case in result['cases'] if case['combination']['id']==cid)
        states=copy.deepcopy([s for s in ev.get('states',[]) if s.get('x_mm')==x])
        # Moment is the signed section moment concomitant with P, not a force
        # applied at the contact and not an envelope over a finite patch.
        moments=[s.get('normal',{}).get('M_Nmm') for s in states]
        if not moments or any(type(m) not in (int,float) or not math.isfinite(m) for m in moments):
            raise ValueError('Momento concomitante salvo na posição P ausente/inválido: '+cid)
        if any(not math.isclose(m,moments[0],rel_tol=2e-10,abs_tol=1e-7) for m in moments):
            raise ValueError('Momento descontínuo/incoerente na posição P: '+cid)
        points.append(dict(point_id=cid,combination_id=cid,limit_state='ELU',x_mm=x,
            L_mm=trace['L_mm'],mathematical_point_limit=trace['mathematical_point_limit'],
            normal_N=c['P_vector']['normal'],parallel_N=c['P_vector']['parallel'],
            moment_strong_Nmm=moments[0],concomitant_states=states,
            source_axis_convention=('Força aplicada P sobre a barra, conforme P_vector; sinais não invertidos. '+ev.get('convention','')),
            combination=copy.deepcopy(c)))
    if len({p['point_id'] for p in points})!=len(points) or not points:
        raise ValueError('Inventário ELU de P ausente/duplicado.')
    return dict(section=copy.deepcopy(src['section']),points=points,
                support_reactions=copy.deepcopy(src['supports']),
                ELS_combinations_excluded=src['ELS_combinations_excluded'])
