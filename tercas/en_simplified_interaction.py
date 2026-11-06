"""Conservative EN13 Eq6.27 bound; never a replacement for torsional stresses.

Mf/Mpl is set to zero, increasing the shear penalty. The existing pure
EN effective sections provide a separately qualified first-yield capacity
floor. Each common Bernstein control contains concurrent N/M/V components;
a control is not a physical state and excess is only inconclusive.
"""
import copy
import math
import numpy as np
from .torsion_vlasov.intervals import Interval as I, stack, power_to_bernstein

SCHEMA='EN_6_27_sufficient_interaction_v1'
SOURCE='EN1993-1-3:2006 §§6.1.4.1,6.1.8,6.1.9,6.1.10(1), Eq6.27; Mf,Rd=0 conservative bound'
SCOPE=('Componente seccional EN N–Mx–My com os dois cortantes transversais. '
       'Transporte do centroide efetivo de N preservado sem creditar cancelamento favorável: '
       'cada momento é majorado pelos módulos original e corrigido. Para cada eixo, a parcela adicional '
       'é zero até V/Vb=0,5; acima usa (2V/Vb−1)², sem crédito de Mf/Mpl. '
       'A alma original resiste ao cortante forte; as duas mesas originais ao fraco, '
       'com capacidades EN distintas. B/Tsv/Tw permanecem na combinação de tensões '
       '§6.1.6, sem conversão artificial T→V. As verificações são complementares; '
       'esta componente não aprova a barra nem a estabilidade.')
ACTIONS=('N','Mx','My','Vstrong','Vweak','Mx_original','My_original')
FLAGS=('whole_member_approved','complete_EN_design_qualified','global_stability_qualified',
       'torsional_interaction_qualified','NBR_capacities_used','AISI_capacities_used')


def _sha(value):
    from .isolated_en_stress import _sha as digest
    return digest(value)


def capacities(profile,certificate):
    """Whole physical line/offset-face first yield, never ULS_pure_effort.

    Full physical endpoints dominate the retained effective parts. Optional
    plasticity and cold-work enhancement are not used. Source pinning rejects
    another geometry/material or changed pure-section implementation.
    """
    from .three_girt_en_normal.en1993_normal_components import verify_component_sections
    from .en_interaction_capacity_reference import qualified_reference
    verify_component_sections(certificate)
    t=profile['thickness_mm'];ref=qualified_reference(t,certificate['content_sha256'])
    if (certificate['content_sha256']!=ref['component_sections_sha256']
        or certificate['nodes_sha256']!=profile['geometry_identity']['nodes_canonical_sha256']):
        raise ValueError('Seções efetivas EN fora da referência resistente M–V qualificada.')
    nodes=I(profile['nodes_xy_mm']);cg=I(certificate['gross_properties']['centroid_xy_mm'])
    delta=nodes[1:]-nodes[:-1];length=(delta[:,0].square()+delta[:,1].square()).sqrt()
    normal=stack([-delta[:,1]/length,delta[:,0]/length],axis=-1)
    points=stack([nodes[:-1]-cg,nodes[1:]-cg],axis=1)
    result={}
    for key,component in certificate['components'].items():
        if component['eligible'] is not True:raise ValueError('Ramo efetivo ausente: '+key)
        coeff=I(component['sigma_coefficients_c0_cx_cy']);maximum=0.
        for face in (-1,0,1):
            xy=points+normal[:,None,:]*(face*t/2)
            values=coeff[0]+xy[:,:,0]*coeff[1]+xy[:,:,1]*coeff[2]
            maximum=max(maximum,float(np.max(values.abs().hi)))
        lower=float((I(250.)/I(maximum)).lo)
        floor=math.floor(lower)
        if floor<=0 or floor!=ref['signed_capacity_floor'][key]:
            raise ValueError('Piso resistente EN diverge da referência conferida: '+key)
        result[key]=floor
    return copy.deepcopy(ref)


def _normal_limits(cap):
    c=cap['signed_capacity_floor']
    return dict(N=min(c['N_tension'],c['N_compression']),
        Mx=min(c['Mx_positive'],c['Mx_negative']),My=min(c['My_positive'],c['My_negative']))


def objective(intervals,cap,web_capacity):
    limits=_normal_limits(cap)
    if web_capacity!=cap['shear_capacity_lower_N']['strong']:
        raise ValueError('Capacidade forte EN não corresponde à referência.')
    normal=I(0.)
    for key in ('N','Mx','My'):
        value=I(*intervals[key]).abs()
        if key!='N':
            original=I(*intervals[key+'_original']).abs()
            value=I(np.maximum(value.lo,original.lo),np.maximum(value.hi,original.hi))
        normal=normal+value/limits[key]
    ratios={};penalties={}
    for action,axis in (('Vstrong','strong'),('Vweak','weak')):
        shear=I(*intervals[action]).abs()/cap['shear_capacity_lower_N'][axis]
        hinge=2*shear-I(1.)
        penalty=I(np.maximum(0.,hinge.lo),np.maximum(0.,hinge.hi)).square()
        if float(shear.hi)<=.5:penalty=I(0.)
        ratios[axis]=float(shear.hi);penalties[axis]=float(penalty.hi)
    penalty=max(penalties.values())
    return dict(normal_ratio_upper=float(normal.hi),shear_ratio_upper=max(ratios.values()),
        strong_shear_ratio_upper=ratios['strong'],weak_shear_ratio_upper=ratios['weak'],
        shear_penalty_upper=penalty,index_upper=float((normal+I(penalty)).hi))


def verdict(maximum,shear,*,weak_zero,torsion_zero):
    if type(weak_zero) is not bool or type(torsion_zero) is not bool:raise ValueError('Metadados de domínio devem ser booleanos.')
    sufficient=maximum<=1. and shear<=1.
    return dict(status='sufficient' if sufficient else 'inconclusive_upper_bound',
        component_qualified=sufficient,transverse_subproblem_sufficient=sufficient,
        shear_reduction_waived=shear<=.5,observed_failure=False,
        reason='Torção e empenamento são mantidos na verificação complementar EN6.1.6, não convertidos em cortante transversal.',
        weak_shear_identically_zero=weak_zero,torsional_shear_identically_zero=torsion_zero,
        weak_transverse_shear_included=True,torsion_zero_required=False,
        separate_EN_6_1_6_required=True)


def polynomial_bound(fields,capacity,web_capacity,*,weak_zero,torsion_zero):
    """Common degree-2 controls; coefficients may be already enclosed intervals."""
    if set(fields)!=set(ACTIONS):raise ValueError('Seven explicit concurrent action fields required')
    controls={}
    for key in ACTIONS:
        raw=fields[key]
        if not isinstance(raw,I):
            arr=np.asarray(raw)
            if arr.ndim!=1 or arr.dtype.kind not in 'fi' or not np.all(np.isfinite(arr)) or any(isinstance(v,(bool,np.bool_)) for v in raw):
                raise ValueError('Finite real action coefficients required')
        values=raw if isinstance(raw,I) else I(raw)
        if values.lo.ndim!=1 or not 1<=len(values.lo)<=3:raise ValueError('Polynomial degree at most two required')
        padded=stack([values[k] if k<len(values.lo) else I(0.) for k in range(3)])
        controls[key]=power_to_bernstein(padded[:,None])[:,0]
    rows=[]
    for j in range(3):
        intervals={k:[float(v.lo[j]),float(v.hi[j])] for k,v in controls.items()}
        rows.append(dict(control=j,intervals=intervals,is_physical_state=False,
            **objective(intervals,capacity,web_capacity)))
    maximum=max(r['index_upper'] for r in rows);shear=max(r['shear_ratio_upper'] for r in rows)
    return dict(controls=rows,index_upper=maximum,shear_ratio_upper=shear,
        **verdict(maximum,shear,weak_zero=weak_zero,torsion_zero=torsion_zero))


def validate_polynomial_bound(out,capacity,web_capacity,*,weak_zero,torsion_zero):
    rows=out['controls']
    if not isinstance(rows,list) or len(rows)!=3:raise ValueError('Controles M–V incompletos.')
    for j,row in enumerate(rows):
        if type(row.get('control')) is not int or row.get('control')!=j or row.get('is_physical_state') is not False:
            raise ValueError('Controle M–V não é testemunha física.')
        intervals=row['intervals']
        if set(intervals)!=set(ACTIONS):raise ValueError('Ações M–V incompletas.')
        for pair in intervals.values():
            if (not isinstance(pair,list) or len(pair)!=2 or any(type(v) not in (int,float)
                or not math.isfinite(v) for v in pair) or pair[0]>pair[1]):raise ValueError('Intervalo M–V inválido.')
        if any(type(row.get(k)) not in (int,float) or not math.isfinite(row[k]) or row[k]!=v
               for k,v in objective(intervals,capacity,web_capacity).items()):
            raise ValueError('Aritmética M–V salva divergente.')
    maximum=max(r['index_upper'] for r in rows);shear=max(r['shear_ratio_upper'] for r in rows)
    expected=dict(index_upper=maximum,shear_ratio_upper=shear,
        **verdict(maximum,shear,weak_zero=weak_zero,torsion_zero=torsion_zero))
    if any((out.get(k) is not v) if type(v) is bool else out.get(k)!=v for k,v in expected.items()):raise ValueError('Estado M–V salvo divergente.')


def capacity_text(cap,*,include_axial=True):
    """Format the saved denominators only; no resistance recalculation."""
    limits=_normal_limits(cap);v=cap['shear_capacity_lower_N']
    axial=f"Nmin={limits['N']} N; " if include_axial else ''
    return (f"Pisos de resistência EN usados, t={cap['thickness_mm']:.2f} mm: "+axial+
        f"Mx,min={limits['Mx']} Nmm; My,min={limits['My']} Nmm; "
        f"Vforte,min={v['strong']:.6f} N; Vfraco,min={v['weak']:.6f} N. "
        "Os denominadores e seus hashes completos ficam no JSON.")
