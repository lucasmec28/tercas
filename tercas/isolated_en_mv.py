"""Optional saved EN6.27 component on the same isolated polynomial demand."""
import copy
import math
import numpy as np
from . import en_simplified_interaction as core
from .torsion_vlasov.intervals import Interval as I, stack, power_to_bernstein
from .torsion_vlasov.yield_envelope import _member_polynomials

SCHEMA='isolated_EN_6_27_component_v1'


def calculate(demand,profile,certificate,web):
    from .isolated_en_shear import _weak_zero,_waiver_domain
    cap=core.capacities(profile,certificate);pol,ids=_member_polynomials(demand)
    weak=_weak_zero(demand);torsion=_waiver_domain(demand)['torsional_shear_identically_zero']
    pieces=[]
    for j,source in enumerate(ids):
        fields=dict(N=[0.],Mx=pol['Mx'][j,:3],My=pol['My'][j,:3],Vstrong=pol['Vy'][j],Vweak=pol['Vx'][j],
            Mx_original=pol['Mx'][j,:3],My_original=pol['My'][j,:3])
        pieces.append(dict(source_piece=copy.deepcopy(web['pieces'][j]['source_piece']),
            **core.polynomial_bound(fields,cap,web['capacity']['Vw_Rd_lower_N'],weak_zero=weak,torsion_zero=torsion)))
    maximum=max(p['index_upper'] for p in pieces);shear=max(p['shear_ratio_upper'] for p in pieces)
    out=dict(schema=SCHEMA,algorithm_schema=core.SCHEMA,source=core.SOURCE,scope=core.SCOPE,
        source_demand_sha256=core._sha(demand),source_geometry_sha256=certificate['nodes_sha256'],
        combination_id=demand['combination_id'],member_id=demand['member_id'],
        capacity_reference=cap,web_capacity_lower_N=web['capacity']['Vw_Rd_lower_N'],
        pieces=pieces,full_member_field_covered=True,index_upper=maximum,shear_ratio_upper=shear,
        method='Concurrent degree-two Bernstein controls; signed-capacity minima; Mf/Mpl=0',
        normal_actions='N=0; physical Mx/My retained without total-stress cancellation; B checked separately by EN6.1.6',
        **core.verdict(maximum,shear,weak_zero=weak,torsion_zero=torsion),
        **{key:False for key in core.FLAGS})
    out['content_sha256']=core._sha(out)
    return out



def _saved_source_controls(summary, source):
    """Replay equilibrium identities from saved loads/reactions, never an FE solve.

    This binds EVERY element, not only the few compact extreme witnesses.
    No profile, material model, resistance builder or stress envelope is called.
    """
    def vector(values):
        return isinstance(values,list) and len(values)==2 and all(type(v) in (int,float) and math.isfinite(v) for v in values)
    if not vector(summary['support_reactions']['left_force_xy_N']):raise ValueError('Reação fonte M–V inválida.')
    for load in summary['loads']:
        key='q_xy_N_mm' if load['kind']=='uniform' else 'force_xy_N'
        if load['kind'] not in ('uniform','point') or not vector(load.get(key)):
            raise ValueError('Carga fonte M–V inválida.')
        if load['kind']=='point' and (type(load.get('s_mm')) not in (int,float) or not math.isfinite(load['s_mm'])):
            raise ValueError('Posição fonte M–V inválida.')
    if source['kind']=='support_limit':
        state=next(s for s in summary['support_limit_states'] if s['element_id']==source['element_id'])
        fields={a:[I(state[k])] for a,k in (('Mx','Mx_physical_Nmm'),('My','My_physical_Nmm'),
            ('Vstrong','Vy_N'),('Vweak','Vx_N'))}
    else:
        if any(load['kind']=='point' and source['a_mm']<load['s_mm']<source['b_mm'] for load in summary['loads']):
            raise ValueError('Trecho M–V cruza salto de carga pontual sem preservar ambos os lados.')
        q=[I(0.),I(0.)]
        for action in summary['loads']:
            if action['kind']=='uniform':q=[q[j]+action['q_xy_N_mm'][j] for j in (0,1)]
        ra=[I(x) for x in summary['support_reactions']['left_force_xy_N']]
        a=I(source['a_mm']);ell=I(source['b_mm'])-a
        v=[-ra[j]-q[j]*a for j in (0,1)]
        mx=-ra[1]*a-q[1]*a*a/2.;my=ra[0]*a+q[0]*a*a/2.
        for point in summary['loads']:
            if point['kind']=='point' and point['s_mm']<=source['a_mm']:
                v=[v[j]-point['force_xy_N'][j] for j in (0,1)]
                distance=a-point['s_mm']
                mx=mx-point['force_xy_N'][1]*distance;my=my+point['force_xy_N'][0]*distance
        fields=dict(Mx=[mx,v[1]*ell,-q[1]*ell*ell/2.],My=[my,-v[0]*ell,q[0]*ell*ell/2.],
            Vstrong=[v[1],-q[1]*ell],Vweak=[v[0],-q[0]*ell])
    fields['N']=[I(0.)]
    fields['Mx_original']=fields['Mx'];fields['My_original']=fields['My']
    result={}
    for key,values in fields.items():
        padded=stack(values+[I(0.)]*(3-len(values)))
        result[key]=power_to_bernstein(padded[:,None])[:,0]
    return result


def validate_saved(out,web,row,summary,ev):
    from .en_interaction_capacity_reference import qualified_reference
    from .isolated_en_shear import _weak_zero,_waiver_domain
    ref=qualified_reference(ev['source_profile']['thickness_mm'],row['check']['component_sections_sha256'])
    if (not isinstance(out,dict) or out.get('schema')!=SCHEMA or out.get('algorithm_schema')!=core.SCHEMA or out.get('source')!=core.SOURCE
        or out.get('scope')!=core.SCOPE or core._sha(out.get('capacity_reference'))!=core._sha(ref)
        or out.get('content_sha256')!=core._sha({k:v for k,v in out.items() if k!='content_sha256'})
        or out.get('source_demand_sha256')!=row['source_analysis_sha256']
        or out.get('source_geometry_sha256')!=summary['section']['nodes_sha256']
        or out.get('combination_id')!=row['combination_id'] or out.get('member_id')!=summary['member_id']
        or row['check']['component_sections_sha256']!=ref['component_sections_sha256']
        or out.get('web_capacity_lower_N')!=web['capacity']['Vw_Rd_lower_N']
        or out.get('full_member_field_covered') is not True
        or any(out.get(k) is not False for k in core.FLAGS)
        or out.get('method')!='Concurrent degree-two Bernstein controls; signed-capacity minima; Mf/Mpl=0'
        or out.get('normal_actions')!='N=0; physical Mx/My retained without total-stress cancellation; B checked separately by EN6.1.6'):
        raise ValueError('Snapshot M–V EN incompatível ou escopo ampliado.')
    pieces=out['pieces'];weak=_weak_zero(summary);torsion=_waiver_domain(summary)['torsional_shear_identically_zero']
    if not isinstance(pieces,list) or len(pieces)!=len(web['pieces']):raise ValueError('Cobertura M–V incompleta.')
    for piece,w in zip(pieces,web['pieces']):
        if piece['source_piece']!=w['source_piece']:raise ValueError('Identidade de trecho M–V alterada.')
        core.validate_polynomial_bound(piece,ref,out['web_capacity_lower_N'],weak_zero=weak,torsion_zero=torsion)
        for action,expected in _saved_source_controls(summary,piece['source_piece']).items():
            for j,control in enumerate(piece['controls']):
                lo,hi=control['intervals'][action]
                if lo>float(expected.lo[j]) or hi<float(expected.hi[j]):
                    raise ValueError('Controle M–V não cobre ações/cortantes concomitantes da fonte salva.')
        if any(c['intervals'][a]!=c['intervals'][a+'_original'] for c in piece['controls'] for a in ('Mx','My')):
            raise ValueError('Fonte isolada sem transporte não pode alterar momentos originais.')
        if any(c['intervals']['N']!=[0.,0.] and not (c['intervals']['N'][0]<=0.<=c['intervals']['N'][1]
            and max(abs(v) for v in c['intervals']['N'])<1e-300) for c in piece['controls']):
            raise ValueError('Fonte isolada N=0 alterada.')
        # The same recovered affine shear is checked against the independently
        # stored web endpoints; neither piece may silently omit before-P.
        for j,k in ((0,0),(2,1)):
            lo,hi=piece['controls'][j]['intervals']['Vstrong']
            wlo,whi=w['Vweb_end_intervals_N'][k]
            if lo>wlo or hi<whi:raise ValueError('Controle M–V não cobre o cortante da alma salvo.')
    by_piece={(p['source_piece']['kind'],p['source_piece']['element_id']):p for p in pieces}
    for state in summary['witnesses']+summary.get('support_limit_states',[]):
        kind='support_limit' if state.get('element_index') is None else 'element'
        piece=by_piece[(kind,state['element_id'])];u=I(state['u'])
        weights=[(I(1.)-u).square(),2*u*(I(1.)-u),u.square()]
        for action,key in (('Mx','Mx_physical_Nmm'),('My','My_physical_Nmm'),('Vstrong','Vy_N'),('Vweak','Vx_N')):
            value=I(0.)
            for control,weight in zip(piece['controls'],weights):value=value+I(*control['intervals'][action])*weight
            if not float(value.lo)<=state[key]<=float(value.hi):raise ValueError('Controle M–V não cobre a testemunha da mesma seção.')
    for action,key in (('Mx','Mx_physical_Nmm'),('My','My_physical_Nmm'),('Vstrong','Vy_N'),('Vweak','Vx_N')):
        maximum=max(abs(v) for p in pieces for c in p['controls'] for v in c['intervals'][action])
        source=summary['field_envelopes'][key]
        if any(abs(source[k]['value'])>maximum for k in ('minimum','maximum','maximum_absolute')):
            raise ValueError('Envelope M–V menor que o campo fonte salvo.')
    maximum=max(p['index_upper'] for p in pieces);shear=max(p['shear_ratio_upper'] for p in pieces)
    expected=dict(index_upper=maximum,shear_ratio_upper=shear,
        **core.verdict(maximum,shear,weak_zero=weak,torsion_zero=torsion))
    if any((out.get(k) is not v) if type(v) is bool else out.get(k)!=v for k,v in expected.items()):raise ValueError('Estado global da componente M–V divergente.')
