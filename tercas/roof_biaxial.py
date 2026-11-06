"""NBR 9.9 separate-axis capacities, not a coupled buckling eigenvalue.

NBR 14762:2010 9.9 uses the two resistances of 9.8.2. The latter permits
SC-load expressions for a stabilizing application point. With the application's
physical force [parallel, -normal], the parallel-load contribution to twice the
rotational potential is +F_parallel*(x_load-x_SC)*phi**2. Every parallel action
must be non-destabilizing before this limited route uses the Annex E resistance.
Normal-load height remains in the existing strong-axis operator. Neither this
classification nor the NBR interaction assesses primary torsion/warping.
"""
import copy
from .ltb_load_height import finite

SCHEMA = 'NBR_9_9_separate_axis_roof_scope_v1'
SOURCE = 'NBR14762:2010 §§9.8.2.2 (p48), 9.9 (p53), Anexo E (p82).'
SCOPE = ('Interação flexional NBR §9.9, N=0, com resistências por eixo: forte com '
         'altura e fraco pelo Anexo E/Cm=1, sem aproveitar a posição estabilizante '
         'das ações paralelas. Momentos concomitantes na mesma seção. Não é '
         'autovalor biaxial, interação com torção/bimomento ou aprovação global.')


def classify(actions, geometry):
    rows=[]; reasons=[]
    for a in actions:
        key='q_parallel_N_mm' if a['kind']=='uniform' else 'P_parallel_N'
        value=finite(a.get(key), 'componente paralela individual')
        if value==0:continue
        x=a.get('x_from_SC_mm')
        x=None if x is None else finite(x,'posição paralela relativa ao CT')
        term=None if x is None else value*x
        if not geometry.get('coherent_torsion_section') or term is None:
            state='unknown'; reasons.append(a['name']+': posição relativa ao CT não qualificada')
        elif term<0:
            state='destabilizing'; reasons.append(a['name']+': posição desestabilizante no eixo fraco')
        else:state='neutral_parallel_height' if term==0 else 'stabilizing'
        rows.append(dict(name=a['name'],kind=a['kind'],parallel_force=value,
            x_from_SC_mm=x,rotational_stiffness_term=term,position_classification=state))
    return dict(schema=SCHEMA,source=SOURCE,scope=SCOPE,actions=rows,
        applicable=bool(rows) and not reasons,reason='; '.join(reasons),
        strong_axis_projection_only=True,weak_favorable_height_used=False,
        combined_buckling_eigenvalue=False,primary_torsion_assessed=False,
        Me_eigenoperator_uses_normal_projection_only=True,
        whole_member_approved=False)


def classify_for_roof(actions, geometry):
    """The numerical reader contract is qualified for seven exact contours only."""
    out=classify(actions,geometry)
    if geometry.get('coherent_torsion_section'):
        from .roof_biaxial_geometry import supported_geometry
        if not supported_geometry(geometry):
            out.update(applicable=False,reason='Consumo por eixo ainda não integrado para este contorno; '
                'rota atual restrita às sete referências próprias Ue100. Não é proibição normativa da seção.')
    return out


def torque_records(actions, include_parallel):
    out=[]
    for a in actions:
        uniform=a['kind']=='uniform'
        normal=a['q_down_N_mm'] if uniform else a['P_down_N']
        parallel=a['q_parallel_N_mm'] if uniform else a['P_parallel_N']
        value=-a['x_from_SC_mm']*normal
        if include_parallel:value-=a['height_above_SC_mm']*parallel
        out.append(dict(name=a['name'],kind=a['kind'],value=value,units='N' if uniform else 'Nmm'))
    return out


def annotate_projection(calculation, actions):
    """Keep the scalar eigenoperator unchanged and report the actual load torque."""
    out=copy.deepcopy(calculation)
    out['normal_projection_primary_torque_by_action']=copy.deepcopy(out['primary_torque_by_action'])
    out['primary_torque_by_action']=torque_records(actions,True)
    out['primary_torque_report_includes_parallel_actions']=True
    return out


def floor_can_govern(weak, governing):
    my=governing.get('My_Nmm',0.)
    if not my:return False
    c=weak['positive' if my>0 else 'negative']
    return (c.get('Mdist_lower_bound_Nmm') is not None
        and c['MRd_dist_Nmm']<min(c['MRd_local_Nmm'],c['MRd_FLT_Nmm']))


def _moment_coefficients(q,p,L,a,after):
    return (-q/2, q*L/2+p*(L-a)/L-(p if after else 0.),p*a if after else 0.)


def _candidate_state(x,combo,L,rx,weak):
    from .core.travamentos_nbr import moment
    q,p=combo['q_vector'],combo['P_vector'];a=combo['x_mm']
    mx=moment(x,L,q['normal'],p['normal'],a)
    my=moment(x,L,q['parallel'],p['parallel'],a)
    ry=weak['positive' if my>=0 else 'negative']['MRd_Nmm']
    return dict(x_mm=x,Mx_Nmm=mx,My_Nmm=my,index=abs(mx)/rx+abs(my)/ry)


def _pieces(combo,L):
    a=combo['x_mm']
    return [(lo,hi,after) for lo,hi,after in ((0.,a,False),(a,L,True)) if lo<hi]


def _polynomial(combo,L,rx,weak,lo,hi,after,sx,sy):
    q,p=combo['q_vector'],combo['P_vector'];a=combo['x_mm']
    mx=_moment_coefficients(q['normal'],p['normal'],L,a,after)
    my=_moment_coefficients(q['parallel'],p['parallel'],L,a,after)
    ry=weak['positive' if sy==1 else 'negative']['MRd_Nmm']
    co=[sx*x/rx+sy*y/ry for x,y in zip(mx,my)]
    xs=[lo,hi]
    if co[0]:
        vertex=-co[1]/(2*co[0])
        if lo<vertex<hi:xs.append(vertex)
    return dict(start_mm=lo,end_mm=hi,after_P=after,strong_sign=sx,weak_sign=sy,
        coefficients=co,candidate_x_mm=xs)


def interaction(combo, L, strong_capacity, own):
    """Fresh exact polynomial envelope, with an independently checkable trace.

    |Mx|/Rx+|My|/Ry(sign My) is the maximum of the four signed linear
    combinations. Each is quadratic on either side of P. Endpoints and an
    interior vertex therefore contain every possible maximum, including mixed
    signs/reversal. No independent maxima of Mx and My are added.
    """
    strong_capacity=finite(strong_capacity,'resistência forte',True)
    caps=own['signed_scalar_capacities']
    weak={sign:copy.deepcopy(caps[key]) for sign,key in
          (('positive','weak_web_compressed'),('negative','weak_lips_compressed'))}
    for c in weak.values():finite(c.get('MRd_Nmm'),'resistência fraca',True)
    certificate=[_polynomial(combo,L,strong_capacity,weak,lo,hi,after,sx,sy)
        for lo,hi,after in _pieces(combo,L) for sx in (-1,1) for sy in (-1,1)]
    xs=sorted({x for c in certificate for x in c['candidate_x_mm']})
    states=[_candidate_state(x,combo,L,strong_capacity,weak) for x in xs]
    g=max(states,key=lambda state:state['index']);idx=g['index']
    floor_used=floor_can_govern(weak,g)
    verdict='meets' if idx<=1 else 'inconclusive' if floor_used else 'fails'
    return dict(schema=SCHEMA,source=SOURCE,scope=SCOPE,status='computed_fixed_position',missing=[],
        governing=g,candidate_count=len(xs),envelope_certificate=certificate,
        weak_axis_capacities=weak,strong_capacity_Nmm=strong_capacity,
        criterion_status=verdict,weak_distortional_floor_can_govern=floor_used,
        combined_buckling_eigenvalue=False,primary_torsion_assessed=False,whole_member_approved=False)


def validate_saved(record, combo, strong_capacity, own):
    """Check saved polynomial proof/identities; no eigenvalue/source/resistance solve.

    A zero endpoint witness alone cannot establish the maximum. Every required
    signed polynomial, interval endpoint and interior vertex must be present;
    their concomitant indices must be <= the saved governing witness.
    No recalculated result is returned and historical records are not promoted.
    """
    if (not isinstance(record,dict) or record.get('schema')!=SCHEMA
        or record.get('source')!=SOURCE or record.get('scope')!=SCOPE):
        raise ValueError('Interação NBR no topo salva sem contrato reconhecido.')
    caps=own['signed_scalar_capacities']
    expected={sign:caps[key] for sign,key in
              (('positive','weak_web_compressed'),('negative','weak_lips_compressed'))}
    finite(strong_capacity,'resistência forte salva',True)
    for c in expected.values():finite(c.get('MRd_Nmm'),'resistência fraca salva',True)
    if (record.get('weak_axis_capacities')!=expected
        or record.get('strong_capacity_Nmm')!=strong_capacity
        or record.get('weak_distortional_floor_can_govern')!=floor_can_govern(expected,record.get('governing') or {})
        or any(record.get(k) is not False for k in
            ('combined_buckling_eigenvalue','primary_torsion_assessed','whole_member_approved'))):
        raise ValueError('Capacidades/domínio da interação NBR no topo divergentes.')
    if record.get('status')!='computed_fixed_position' or record.get('missing'):
        raise ValueError('Interação NBR no topo sem resistências completas.')
    g=record.get('governing') or {};x=finite(g.get('x_mm'),'seção concomitante')
    L=combo['span_mm'];a=combo['x_mm'];q,p=combo['q_vector'],combo['P_vector']
    if not 0<=x<=L or g!=_candidate_state(x,combo,L,strong_capacity,expected):
        raise ValueError('Aritmética concomitante NBR no topo inconsistente.')
    index=finite(g['index'],'índice concomitante salvo')
    if record.get('criterion_status')!=('meets' if index<=1 else
            'inconclusive' if record.get('weak_distortional_floor_can_govern') else 'fails'):
        raise ValueError('Conclusão da interação NBR no topo inconsistente.')
    proof=record.get('envelope_certificate');pieces=_pieces(combo,L)
    if not isinstance(proof,list) or len(proof)!=4*len(pieces):
        raise ValueError('Certificado do envelope NBR incompleto.')
    all_x=set();i=0
    for lo,hi,after in pieces:
        # Independent arithmetic checks of the supplied proof, not a fresh
        # call to the envelope producer or a source/model lookup.
        mx=(-q['normal']/2,q['normal']*L/2+p['normal']*(L-a)/L-(p['normal'] if after else 0.),p['normal']*a if after else 0.)
        my=(-q['parallel']/2,q['parallel']*L/2+p['parallel']*(L-a)/L-(p['parallel'] if after else 0.),p['parallel']*a if after else 0.)
        for sx in (-1,1):
            for sy in (-1,1):
                row=proof[i];i+=1
                if not isinstance(row,dict):raise ValueError('Parcela do certificado NBR inválida.')
                ry=expected['positive' if sy==1 else 'negative']['MRd_Nmm']
                coefficients=[sx*u/strong_capacity+sy*v/ry for u,v in zip(mx,my)]
                xs=[lo,hi]
                if coefficients[0]:
                    vertex=-coefficients[1]/(2*coefficients[0])
                    if lo<vertex<hi:xs.append(vertex)
                wanted=dict(start_mm=lo,end_mm=hi,after_P=after,strong_sign=sx,weak_sign=sy,
                    coefficients=coefficients,candidate_x_mm=xs)
                if row!=wanted:raise ValueError('Cobertura polinomial do envelope NBR divergente.')
                for station in xs:
                    all_x.add(station)
                    if _candidate_state(station,combo,L,strong_capacity,expected)['index']>index:
                        raise ValueError('Testemunha não cobre o máximo contínuo da interação NBR.')
    if x not in all_x or record.get('candidate_count')!=len(all_x):
        raise ValueError('Testemunha/inventário de candidatos NBR incoerentes.')
