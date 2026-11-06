"""Optional EN6.27 component for selected girders, no structural model changes."""
import copy
import math
from . import en_simplified_interaction as core
from .torsion_vlasov.intervals import Interval as I

SCHEMA='three_girt_EN_6_27_component_v1'
COLLECTION_SCHEMA='three_girt_EN_6_27_collection_v1'


def prepare(demand,en_source,*,profile=None):
    if profile is None:
        from .three_girt_en_normal.application import _profile_and_section
        profile,_=_profile_and_section(demand)
    return core.capacities(profile,en_source['component_sections'])


def calculate_row(demand,case,beam,en_row,capacity,web_capacity):
    from .three_girt_assessment.application import _zero_torsional_shear
    raw=beam['normal_action_polynomials'];normal=en_row['normal_action_reference']
    if normal.get('available') is not True:raise ValueError('Transporte do centroide EN indisponível.')
    fields=copy.deepcopy(normal['corrected_polynomials_R01']);length=beam['length_mm']
    for axis in ('Mx','My'):fields[axis+'_original']=copy.deepcopy(normal['original_polynomials_R01'][axis])
    m=raw['My_strong_Nmm'];fields['Vstrong']=[-(j+1)*m[j+1]/length for j in range(len(m)-1)] or [0.]
    mw=raw['Mz_weak_Nmm'];fields['Vweak']=[(j+1)*mw[j+1]/length for j in range(len(mw)-1)] or [0.]
    weak=all(v==0. for v in raw['Mz_weak_Nmm'][1:]);torsion=_zero_torsional_shear(beam,case['model'])
    result=core.polynomial_bound(fields,capacity,web_capacity,weak_zero=weak,torsion_zero=torsion)
    out=dict(schema=SCHEMA,algorithm_schema=core.SCHEMA,source=core.SOURCE,scope=core.SCOPE,
        source_beam_sha256=core._sha(beam),combination_id=case['combination']['id'],
        girt=beam['girt'],segment_id=beam['id'],capacity_reference=copy.deepcopy(capacity),
        normal_action_reference=copy.deepcopy(normal),source_polynomials=fields,
        web_capacity_lower_N=web_capacity,result=result,**{k:False for k in core.FLAGS})
    out['content_sha256']=core._sha(out)
    return out


def validate_internal(out):
    from .en_interaction_capacity_reference import REFERENCES
    cap=out['capacity_reference'];ref=REFERENCES[cap['thickness_mm']]
    if (out.get('schema')!=SCHEMA or out.get('algorithm_schema')!=core.SCHEMA or out.get('source')!=core.SOURCE or out.get('scope')!=core.SCOPE
        or core._sha(cap)!=core._sha(ref) or out.get('content_sha256')!=core._sha({k:v for k,v in out.items() if k!='content_sha256'})
        or any(out.get(k) is not False for k in core.FLAGS)):
        raise ValueError('Snapshot de interação EN da travessa incompatível.')
    r=out['result']
    if type(r.get('weak_shear_identically_zero')) is not bool or type(r.get('torsional_shear_identically_zero')) is not bool:
        raise ValueError('Prova de domínio de cortante EN inválida.')
    core.validate_polynomial_bound(r,ref,out['web_capacity_lower_N'],
        weak_zero=r['weak_shear_identically_zero'],torsion_zero=r['torsional_shear_identically_zero'])
    # Replay only the small saved polynomial-to-control identities.
    fields=out['source_polynomials']
    for key in core.ACTIONS:
        values=fields[key]
        if (not isinstance(values,list) or not 1<=len(values)<=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in values)):raise ValueError('Polinômio salvo M–V inválido.')
        a=[I(v) for v in values]+[I(0.)]*(3-len(values))
        expected=(a[0],a[0]+a[1]/2.,a[0]+a[1]+a[2])
        for ctrl,interval in zip(r['controls'],expected):
            lo,hi=ctrl['intervals'][key]
            # Bernstein conversion has additional outward padding; containment
            # verifies the stored source coefficients, not a new demand solve.
            if lo>float(interval.lo) or hi<float(interval.hi):raise ValueError('Controle M–V não cobre o polinômio salvo.')


def validate_component(source,demand):
    """Read-only: same saved EN transport, beam, topology, material and scope."""
    from .three_girt_assessment.application import _zero_torsional_shear
    for row in source['rows']:
        if 'EN_bending_shear_component' in row and 'EN_bending_shear_error' in row:
            raise ValueError('Registro EN6.27 simultaneamente calculado e pendente.')
        if 'EN_bending_shear_error' in row and (not isinstance(row['EN_bending_shear_error'],str) or not row['EN_bending_shear_error']):
            raise ValueError('Pendência EN6.27 sem motivo.')
    entries=[r for r in source['rows'] if 'EN_bending_shear_component' in r]
    marker=source.get('EN_bending_shear_schema')
    if not entries and marker is None:return
    if marker!=COLLECTION_SCHEMA:raise ValueError('Inventário EN6.27 sem versão reconhecida.')
    props=demand['input_data']['properties'];t=source['component_sections']['thickness_mm']
    expected_props=dict(h=100.,bf=50.,lip=17.,t=t,ri_mm=t,fy_MPa=250.)
    if any(type(props.get(k)) not in (int,float) or not math.isfinite(props[k]) or props[k]!=v for k,v in expected_props.items()):
        raise ValueError('Geometria/material declarado fora do domínio EN6.27 salvo.')
    enrows={(r['combination_id'],r['girt'],r['segment_id']):r for r in source['rows']}
    models={(c['combination']['id'],b['girt'],b['id']):(c,b) for c in demand['cases']
        if c['combination']['limit_state']=='ELU' for b in c['model']['beams']}
    required=set(enrows)
    actual={(r['combination_id'],r['girt'],r['segment_id']) for r in source['rows']
        if 'EN_bending_shear_component' in r or 'EN_bending_shear_error' in r}
    if actual!=required:raise ValueError('Inventário da interação EN incompleto ou fora do escopo central.')
    for row in entries:
        out=row['EN_bending_shear_component'];validate_internal(out)
        key=(row['combination_id'],row['girt'],row['segment_id']);case,beam=models[key];en=enrows[key]
        if (out['source_beam_sha256']!=core._sha(beam)
            or core._sha(out['normal_action_reference'])!=core._sha(en['normal_action_reference'])
            or out['capacity_reference']['component_sections_sha256']!=source['component_sections']['content_sha256']
            or out['web_capacity_lower_N']!=out['capacity_reference']['shear_capacity_lower_N']['strong']
            or any(out[k]!=row[k] for k in ('combination_id','girt','segment_id'))):
            raise ValueError('Interação EN não corresponde à mesma barra/seção/caso.')
        raw=beam['normal_action_polynomials'];length=beam['length_mm'];m=raw['My_strong_Nmm']
        fields=copy.deepcopy(en['normal_action_reference']['corrected_polynomials_R01'])
        for axis in ('Mx','My'):fields[axis+'_original']=copy.deepcopy(en['normal_action_reference']['original_polynomials_R01'][axis])
        fields['Vstrong']=[-(j+1)*m[j+1]/length for j in range(len(m)-1)] or [0.]
        mw=raw['Mz_weak_Nmm'];fields['Vweak']=[(j+1)*mw[j+1]/length for j in range(len(mw)-1)] or [0.]
        weak=all(v==0. for v in raw['Mz_weak_Nmm'][1:]);torsion=_zero_torsional_shear(beam,case['model'])
        if (core._sha(out['source_polynomials'])!=core._sha(fields) or out['result']['weak_shear_identically_zero'] is not weak
            or out['result']['torsional_shear_identically_zero'] is not torsion):
            raise ValueError('Ações ou domínio da interação EN foram trocados.')


def populate(demand,component,*,profile):
    """Fresh-calculation hook: EN source owns its independent optional 6.27 rows."""
    models={(c['combination']['id'],b['girt'],b['id']):(c,b) for c in demand['cases']
        if c['combination']['limit_state']=='ELU' for b in c['model']['beams']}
    component['EN_bending_shear_schema']=COLLECTION_SCHEMA
    try:capacity=prepare(demand,component,profile=profile);error=None
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:capacity=None;error=str(exc)
    for row in component['rows']:
        try:
            if capacity is None:raise ValueError(error or 'Pisos EN6.27 indisponíveis.')
            case,beam=models[(row['combination_id'],row['girt'],row['segment_id'])]
            row['EN_bending_shear_component']=calculate_row(demand,case,beam,row,capacity,capacity['shear_capacity_lower_N']['strong'])
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:row['EN_bending_shear_error']=str(exc)


def presentation_rows(component):
    if component.get('EN_bending_shear_schema') is None:return []
    labels={'upper':'Superior','middle':'Central','lower':'Inferior'};out=[]
    for member in component['per_member']:
        rows=[r for r in component['rows'] if r['girt']==member]
        values=[r['EN_bending_shear_component']['result'] for r in rows if 'EN_bending_shear_component' in r]
        complete=bool(rows) and len(values)==len(rows)
        controls=[r['EN_bending_shear_component'] for r in rows if 'EN_bending_shear_component' in r]
        governing=max(controls,key=lambda r:r['result']['index_upper']) if complete else None
        out.append(dict(Travessa=labels[member],Cobertura=f'{len(values)}/{len(rows)} trechos ELU',
            Teto_cortantes_EN=max(r['shear_ratio_upper'] for r in values) if complete else None,
            Teto_interação_N_M_V_EN=max(r['index_upper'] for r in values) if complete else None,
            Combinação_teto=governing['combination_id'] if governing else None,
            Trecho_teto=governing['segment_id'] if governing else None,
            Controle_Bernstein=max(governing['result']['controls'],key=lambda c:c['index_upper'])['control'] if governing else None,
            Resultado=('Suficiente no domínio salvo' if all(r['component_qualified'] for r in values) else 'Inconclusivo pelo teto') if complete else 'Pendente',
            Redução_por_V=('Dispensada nos dois eixos' if all(r['shear_reduction_waived'] for r in values) else 'Penalidade dos dois eixos incluída') if complete else 'Pendente',
            Motivos='; '.join(sorted({r['EN_bending_shear_error'] for r in rows if 'EN_bending_shear_error' in r}))))
    return out


def text_lines():
    return [core.SCOPE,
        'EN6.27: n + mx + my + max(ρforte,ρfraca) ≤ 1, com ambos |V|/Vb,Rd ≤ 1. '
        'ρ = max(0,2|V|/Vb,Rd−1)²; Mf=0. Cada módulo de M é majorado por original e corrigido, '
        'sem creditar deslocamento favorável do centroide nem aplicar N·e duas vezes.',
        'Controles de Bernstein são limites numéricos, não estados físicos nem posições de testemunha. '
        'Pisos EN por primeiro escoamento dos operadores efetivos puros, sem reserva plástica. '
        'Alma original para o forte; duas mesas originais para o fraco. Acima do teto suficiente '
        'é inconclusivo, não falha física demonstrada. Não depende do checkbox nem de capacidades NBR.',
        'Fontes: EN1993-1-3:2006 §§6.1.3(3),6.1.5,6.1.6,6.1.10; SCIA Engineer 17.0, '
        'pp. 80, 82 e 86: https://help.scia.net/download/17.0/en/SteelCodeCheck_Theory_enu.pdf']


def render_saved(st,component):
    rows=presentation_rows(component)
    if not rows:return
    st.subheader('Interação N–M–V e cortantes pela EN')
    st.dataframe(rows,hide_index=True)
    for line in text_lines():st.caption(line)
    first=next((r['EN_bending_shear_component'] for r in component['rows'] if 'EN_bending_shear_component' in r),None)
    if first:st.caption(core.capacity_text(first['capacity_reference']))


def append_report(doc,component):
    rows=presentation_rows(component)
    if not rows:return
    doc.add_heading('Interação N–M–V e cortantes pela EN',2)
    for line in text_lines():doc.add_paragraph(line)
    first=next((r['EN_bending_shear_component'] for r in component['rows'] if 'EN_bending_shear_component' in r),None)
    if first:doc.add_paragraph(core.capacity_text(first['capacity_reference']))
    for row in rows:doc.add_paragraph('; '.join(str(k)+' = '+str(v) for k,v in row.items()))
