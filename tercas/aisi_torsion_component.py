"""Current-input AISI G8.1 By component and N=0 H4 interaction.

This is distinct from aisi_research's 48 frozen PP controls. It consumes the
existing declared Vlasov actions, never NBR resistances. No new beam, 3D model,
Bp/Bcr requirement, or combined buckling analysis is introduced.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

from numpy.polynomial import polynomial as poly
from .torsion_vlasov.section import finite, verify_section
from .torsion_vlasov.vlasov import evaluate, solve_member, NumericalQualificationError
from .torsion_vlasov.bounded_polynomial import real_roots_open_unit_interval

E_AISI, G_AISI, STIFFNESS_FACTOR = 203000., 78000., .90
FIELD = 'aisi_torsion_component'
SCHEMA = 'aisi2024_current_input_g81_h4_v1'
REFERENCE = 'https://sdi.org/wp-content/uploads/2025/01/ANSI-SDI-AISI-S100-2024-SDI-AISI-S100-2024-C.pdf'
SCOPE = ('Complemento AISI S100-2024 G8.1: Bn=By=Fy·Cw/max|ω| e Ba=0,90·By. '
    'H4 para N=0 usa Mx, My e B da mesma combinação e seção, com capacidades AISI '
    'coerentes. A NBR 14762 permanece a referência principal; suas verificações '
    '9.8/9.9 não são substituídas. O componente não constitui aprovação global.')
LIMITS = ('Cisalhamento e suas interações são verificações separadas; G8.2 está '
    'reservado na AISI. Hipóteses de primeira ordem, produto/material, introdução '
    'local de cargas, serviço, ligações e ancoragens conservam seu próprio escopo. '
    'Tirantes do modelo 3D são bilaterais de primeira ordem, sem dimensionamento '
    'dos tirantes. N diferente de zero não é coberto por este H4 reduzido.')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
        ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def g81_capacity(section, fy_MPa):
    """Literal first-yield option on this coherent normalized section contour."""
    verify_section(section)
    fy=finite(fy_MPa,'Fy',True)
    cw=finite(section['properties']['Cw_mm6'],'Cw',True)
    omega=max(abs(finite(v,'omega')) for v in section['omega_nodes_mm2'])
    omega=finite(omega,'max|omega|',True)
    by=fy*cw/omega
    return dict(standard='AISI S100-2024',clause='G8.1-1/2, first-yield option',
        Fy_MPa=fy,Cw_mm6=cw,omega_max_mm2=omega,Bn_Nmm2=by,By_Nmm2=by,
        phi_B=.90,Ba_Nmm2=.90*by,option='Bn=By; no inelastic Bp option',
        section_content_sha256=section['content_sha256'],
        section_nodes_sha256=section['nodes_sha256'],
        sectorial_convention=section['normalization'],
        omega_extremum='Piecewise-linear sectorial coordinate; extrema at contour nodes',
        Bp_required=False,Bcr_required=False,combined_buckling_analysis_required=False,
        physical_product_verified=False)


def h4_state(state, *, Max_Nmm, May_Nmm, Ba_Nmm2):
    """Reduced H4 at ONE state. A missing capacity is allowed only at zero demand."""
    n=finite(state['N_N'],'N')
    if n != 0.:raise ValueError('N diferente de zero: H4 reduzido N=0 não aplicável.')
    terms={}
    for name,field,cap in [('Mx','Mx_physical_Nmm',Max_Nmm),
                           ('My','My_physical_Nmm',May_Nmm),('B','B_Nmm2',Ba_Nmm2)]:
        demand=finite(state[field],field)
        if demand==0.:terms[name]=0.;continue
        if name=='My' and isinstance(cap,dict):cap=cap.get('lips' if demand>0 else 'web')
        if cap is None:raise ValueError('Capacidade AISI ausente para '+name+' não nulo.')
        terms[name]=abs(demand)/finite(cap,name+' available strength',True)
    return dict(terms=terms,ratio=math.fsum(terms.values()),threshold=1.,
        concomitant=True,N_N=n)


def _bending_coefficients(analysis, element_index, field):
    # The existing transverse statics is piecewise quadratic on each element.
    values=[evaluate(analysis,element_index,u)[field] for u in (0.,.5,1.)]
    a=2.*(values[2]+values[0]-2.*values[1])
    return [values[0],values[2]-values[0]-a,a]


def h4_envelope(analysis, *, Max_Nmm, May_Nmm, Ba_Nmm2):
    """Continuous envelope of the EXISTING polynomial demand field.

Partition at each component's zeros; on each sign interval the sum of absolute
values is a polynomial. Evaluate endpoints and all derivative roots, not sums
of nonconcomitant maxima or a station-only sample. This is not an FE error bound.
"""
    if finite(analysis['analysis_domain'].get('axial_force_in_this_model_N'),'N do modelo') != 0.:
        raise ValueError('N diferente de zero ou ausente no modelo; H4 N=0 indisponível.')
    best=None;count=0
    for i,e in enumerate(analysis['elements']):
        fields=[_bending_coefficients(analysis,i,'Mx_physical_Nmm'),
                _bending_coefficients(analysis,i,'My_physical_Nmm'),e['coefficients']['B_Nmm2']]
        caps=(Max_Nmm,May_Nmm,Ba_Nmm2)
        for values,cap,name in zip(fields,caps,('Mx','My','B')):
            if any(v!=0. for v in values) and cap is None:
                raise ValueError('Capacidade AISI ausente para '+name+' não nulo.')
            if isinstance(cap,dict):
                for value in cap.values():finite(value,'capacidade '+name,True)
            elif cap is not None:finite(cap,'capacidade '+name,True)
        cuts={0.,1.}
        for values in fields:cuts.update(real_roots_open_unit_interval(values))
        cuts=sorted(cuts);locations=set(cuts)
        for a,b in zip(cuts[:-1],cuts[1:]):
            total=[0.]
            for values,cap in zip(fields,caps):
                if cap is None:continue
                sign=1. if poly.polyval((a+b)/2,values)>=0 else -1.
                if isinstance(cap,dict):cap=cap.get('lips' if sign>0 else 'web')
                if cap is None:raise ValueError('Capacidade AISI fraca ausente para o sentido solicitado.')
                total=poly.polyadd(total,[sign*v/cap for v in values])
            locations.update(r for r in real_roots_open_unit_interval(poly.polyder(total)) if a<r<b)
        for u in sorted(locations):
            s=evaluate(analysis,i,u);r=h4_state(s,Max_Nmm=Max_Nmm,May_Nmm=May_Nmm,Ba_Nmm2=Ba_Nmm2)
            count+=1
            if best is None or r['ratio']>best['ratio']:
                best=dict(r,witness={k:s[k] for k in ('combination_id','limit_state','member_id',
                    'element_id','x_mm','u','side','N_N','Mx_physical_Nmm','My_physical_Nmm','B_Nmm2')})
    if best is None:raise ValueError('Campo longitudinal vazio.')
    best.update(candidate_stations=count,method='Continuous piecewise-polynomial absolute-sum extrema',
        demand_scope='Existing qualified first-order FE field; not a discretization-error certificate',
        algebraic_sufficient_condition=best['ratio']<=1.,whole_member_approved=False)
    return best


def _strong_capacity(data, section):
    """AISI-only source resolver. Never reads MRd, NBR local criticals or row indices."""
    from .roof_top_load import enabled as roof_enabled
    if roof_enabled(data) and data.get('member_application','purlin')=='purlin':
        return None,['Carga no topo: a capacidade flexional AISI ainda não foi qualificada com o efeito de altura deste esquema. O Me elástico separado não é transplantado para H4; nenhum denominador no CT substitui a carga adotada.']
    from .aisi_research.adapter import verify_bundle, ROOT
    from .aisi_research.aisi_candidate import flexural_floor
    verify_bundle()
    rows=json.loads((ROOT/'inputs'/'elastic_inputs.json').read_text())['profiles']
    row=next((r for r in rows if r['nodes_sha256']==section['nodes_sha256']
        and r['profile_id']==section['profile_id']),None)
    if row is None:return None,['Sem críticos fortes AISI rastreados para este contorno (inclui Ue100 t=1,20).']
    p=data['properties'];L=finite(data['L_mm'],'L',True)
    if not 3000<=L<=6000:return None,['Vão fora de 3000–6000 mm do conjunto de críticos próprios.']
    # Nominal AISI stiffness in capacities; demands are independently rebuilt
    # at the declared analysis factor, never borrowed from the NBR snapshot.
    E,G=E_AISI,G_AISI
    fy=finite(p['fy_MPa'],'Fy',True)
    if fy>655:return None,['Fy fora do limite dimensional/material adotado para DSM AISI.']
    s=section['properties'];my=fy*row['exterior_moduli']['Wx_first_yield_mm3']
    mcre=math.sqrt(math.pi**2*E*s['Iy_weak_mm4']/L**2*
        (G*s['J_mm4']+math.pi**2*E*s['Cw_mm6']/L**2))
    scale=E/row['material']['E_MPa']
    try:cap=flexural_floor(my,mcre,scale*row['modal_criticals']['strong_local']['value_Nmm'],
        scale*row['modal_criticals']['strong_distortional']['value_Nmm'])
    except ValueError as exc:return None,[str(exc)]
    cap.update(standard='AISI S100-2024',axis='strong symmetric',Cb=1.,
        E_MPa=E,G_MPa=G,Fy_MPa=fy,source_material=copy.deepcopy(row['material']),
        elastic_critical_scaling=scale,source_nodes_sha256=row['nodes_sha256'],
        source_profile_id=row['profile_id'],holes_absent_assumed=True,
        scope='Conditional algebraic F2/F3/F4 floor; pure-axis capacities used by prescribed H4, not a new combined buckling solve')
    return cap,[]


def _weak_capacities(data, section):
    """Pinned pure-axis component denominators, with physical compression sides."""
    from .ue_catalog_reference import claims_reference
    if claims_reference(data):return None,['Capacidades flexionais AISI próprias ainda pendentes para este contorno Ue.']
    from .aisi_weak_sources import weak_capacity as weak
    root=Path(weak.__file__).parent
    expected='f634a4809f1fbe97a93f973f0afecfd17b59eaa040f0689bce69740e40d5f835'
    if hashlib.sha256((root/'MANIFEST.json').read_bytes()).hexdigest()!=expected:
        raise ValueError('Manifesto das capacidades fracas AISI alterado.')
    for name,sha in json.loads((root/'MANIFEST.json').read_text())['files'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:
            raise ValueError('Fonte fraca AISI alterada: '+name)
    t=section['thickness_mm'];fy=finite(data['properties']['fy_MPa'],'Fy',True)
    if t not in weak.THICKNESSES:return None,['Sem capacidades AISI fracas próprias para esta espessura.']
    if fy>655:return None,['Fy fora do domínio material DSM adotado.']
    L=finite(data['L_mm'],'L',True)
    if not 3000<=L<=6000:return None,['Vão fora de 3000–6000 mm da implementação de capacidades fracas AISI.']
    result={}
    for side in weak.SIDES:
        ref=weak.reference_capacity(t,data['L_mm'],side)
        row=weak._row(t)
        if ref['profile_id']!=section['profile_id'] or row['nodes_sha256']!=section['nodes_sha256']:
            raise ValueError('Capacidade fraca e demanda não têm o mesmo contorno.')
        my=ref['yield_and_asymmetry']['My_Nmm']*fy/weak.FY
        beta=ref['yield_and_asymmetry']['beta'];cre=ref['global_elastic']['Mcre_Nmm']
        crl=ref['Mcrl_Nmm'];crd=ref['Mcrd_identified_Nmm']
        if math.sqrt(my/crl)>5 or (crd is not None and math.sqrt(my/crd)>5):
            return None,['Esbeltez fora do domínio DSM AISI da capacidade fraca '+side+'.']
        if side=='lips':
            floor=weak.flexural_floor(my,cre,crl,crd,beta)
            ma=floor['Ma_formula_floor_Nmm']
        else:
            floor=weak.local_global_floor(my,cre,crl,beta)
            ma=floor['Ma_F2_F3_only_Nmm']
        result[side]=dict(Ma_floor_Nmm=ma,material=dict(E_MPa=E_AISI,G_MPa=G_AISI,Fy_MPa=fy),
            M_esc_Nmm=my,beta=beta,Mcre_Nmm=cre,Mcrl_Nmm=crl,Mcrd_Nmm=crd,
            floor=floor,F4_applicability=ref['F4_applicability'],
            pure_axis_denominator_only=True,mixed_field_F4_waiver=False,
            nodes_sha256=row['nodes_sha256'],source_manifest_sha256=expected,
            sign_convention='Vlasov My positive compresses lips; negative compresses web')
    return result,[]


def _aisi_demand(source):
    """Same actions/supports/mesh, separate AISI first-order stiffness only."""
    from .torsion_vlasov.adapter import support_limit_before_point
    if finite(source['analysis_domain'].get('axial_force_in_this_model_N'),'N da fonte')!=0.:
        raise ValueError('N diferente de zero na fonte; não reconstruir como membro N=0.')
    if any(finite(s.get('N_N'),'N do estado')!=0. for s in source.get('critical_states',[])):
        raise ValueError('N diferente de zero em estado da fonte; H4 reduzido indisponível.')
    result=solve_member(section=source['section'],length_mm=source['length_mm'],
        E_MPa=STIFFNESS_FACTOR*E_AISI,G_MPa=STIFFNESS_FACTOR*G_AISI,
        actions=copy.deepcopy(source['loads']),supports=copy.deepcopy(source['support_hypotheses']),
        combination_id=source['combination_id'],limit_state=source['limit_state'],
        member_id=source['member_id'],action_accounting_origin=source['action_accounting_origin'],
        elements_per_interval=32)
    if source.get('support_limit_states'):
        result['support_limit_states']=[support_limit_before_point(result)]
        result['critical_states']=result['support_limit_states']+result['critical_states']
    return result


def _base(result):
    return dict(schema=SCHEMA,source_input_fingerprint=result['input_fingerprint'],
        follows_current_inputs=True,
        load_basis='Combinações ELU atuais do projeto NBR 14762; não são automaticamente combinações LRFD AISI',
        resistance_basis='AISI S100-2024 F/G8.1/H4, phi_b=phi_B=0.90',
        implemented_domain='Contornos próprios Ue100 t1.50/2.00/2.25/2.65/3.00/3.35 e L3–6m para H4; limite de implementação, não de G8.1/H4',
        current_integration_checks_correspondence=True,
        source_actions='Current saved combinations, factors, positions and load lines',
        source_editions_mixed=False,NBR_capacities_used=False,NBR_design_check=False,
        load_eccentricity_handling='Declared action lines generate torque about SC in the initial geometry; force directions remain fixed in first-order analysis',
        flexural_capacity_model='Pure-axis Cb=1 fork/free-warping reference; Mcre is not asserted to be the critical load of the actual mixed eccentric loading',
        geometric_load_height_or_Wagner_effects_included=False,
        whole_member_approved=False,physical_design_approved=False,
        scope=SCOPE,limits=LIMITS,reference=REFERENCE,records=[])


def attach_dense(result, section):
    """Called at a NEW calculation, before the existing demand summary is made."""
    out=copy.deepcopy(result);ev=_base(result);data=result['input_data']
    from .application import fingerprint
    if fingerprint(data)!=result['input_fingerprint']:raise ValueError('Entradas/resultado desatualizados.')
    capacity=g81_capacity(section,data['properties']['fy_MPa'])
    from . import aisi_roof_height as roof_h4
    roof_context=roof_h4.prepare(result,section)
    if roof_context is None:
        strong,strong_missing=_strong_capacity(data,section)
        weak,weak_missing=_weak_capacities(data,section)
    else:
        strong=weak=None;strong_missing=weak_missing=[]
        ev.update(schema=roof_context['schema'],roof_height_source=copy.deepcopy(roof_context['source']),
            flexural_capacity_model=roof_h4.MODEL,strong_capacity_mode='per_combination_roof_height')
    ev.update(bimoment_capacity=capacity,strong_flexural_capacity=strong,
        weak_flexural_capacity=weak,material=dict(E_MPa=E_AISI,G_MPa=G_AISI,Fy_MPa=data['properties']['fy_MPa']),
        analysis_material=dict(E_MPa=STIFFNESS_FACTOR*E_AISI,G_MPa=STIFFNESS_FACTOR*G_AISI,stiffness_factor=STIFFNESS_FACTOR,
            factor_scope='Analysis stiffness only; no additional strength reduction',
            analysis='Rational elastic first-order single isolated member, N=0; not a C1.2/C1.3 structure certification'),
        original_analysis_material=dict(E_MPa=data['properties']['E_MPa'],G_MPa=data['properties']['G_MPa']),
        source_section=dict(profile_id=section['profile_id'],nodes_sha256=section['nodes_sha256'],
            content_sha256=section['content_sha256']),
        strong_capacity_missing=strong_missing)
    for record in result['torsion_evidence']['records']:
        if record['limit_state']!='ELU':continue
        r=dict(combination_id=record['combination_id'],limit_state='ELU',G81=None,H4=None,
            whole_member_approved=False,missing=[])
        a=record.get('analysis')
        if not a:
            r.update(status='pending_demand',missing=copy.deepcopy(record.get('missing',[])))
            ev['records'].append(r);continue
        if a['E_MPa']!=data['properties']['E_MPa'] or a['G_MPa']!=data['properties']['G_MPa'] or a['section']['content_sha256']!=section['content_sha256']:
            raise ValueError('Material ou seção da demanda difere das capacidades.')
        source=a
        current_strong=strong;current_weak=weak
        if roof_context is not None:
            combo=next(c for c in roof_h4.combinations(result) if c['id']==record['combination_id'])
            r['roof_height']=roof_h4.capacity_for(roof_context,combo,source)
            current_strong=r['roof_height']['strong_capacity'];current_weak=None
        try:a=_aisi_demand(source)
        except NumericalQualificationError as exc:
            r.update(status='pending_AISI_numerical_demand',missing=[str(exc)])
            ev['records'].append(r);continue
        r['AISI_analysis']=dict(E_MPa=a['E_MPa'],G_MPa=a['G_MPa'],
            actions=copy.deepcopy(a['loads']),support_hypotheses=copy.deepcopy(a['support_hypotheses']),
            source_actions_sha256=digest(source['loads']),numerics=copy.deepcopy(a['numerics']),
            source_combination=copy.deepcopy(next(c for c in roof_h4.combinations(result) if c['id']==record['combination_id'])),
            max_abs_phi_rad=abs(a['max_abs_phi']['phi_rad']),analysis_order=1,axial_force_N=0.,
            original_NBR_demand_unchanged=True)
        if roof_context is not None:
            roof_h4.check_demand(r['roof_height'],a,section)
            r['AISI_analysis']['max_abs_phi_witness']=copy.deepcopy(a['max_abs_phi'])
            r['AISI_analysis']['point_position_scope']=copy.deepcopy(source['analysis_domain'].get('point_position_scope'))
            r['AISI_analysis']['support_limit_states_preserved']=bool(a.get('support_limit_states'))
        states=a['critical_states'];state=max(states,key=lambda s:abs(s['B_Nmm2']))
        ratio=abs(state['B_Nmm2'])/capacity['Ba_Nmm2']
        r['G81']=dict(ratio=ratio,threshold=1.,component_condition=ratio<=1.,
            status='computed_conditional_component',B_Nmm2=state['B_Nmm2'],
            Ba_Nmm2=capacity['Ba_Nmm2'],x_mm=state['x_mm'],
            material_product_applicability_verified=False)
        nonzero_x=any(s['Mx_physical_Nmm']!=0. for s in states)
        nonzero_y=any(s['My_physical_Nmm']!=0. for s in states)
        missing=[]
        if roof_context is not None:
            missing.extend(r['roof_height']['missing'])
            if nonzero_y and not missing:missing.append('Flexão fraca real fora da qualificação de altura AISI; H4 pendente.')
        else:
            if nonzero_x and current_strong is None:missing.extend(strong_missing)
            if nonzero_y and current_weak is None:missing.extend(weak_missing)
        if a['analysis_domain'].get('axial_force_in_this_model_N')!=0.:
            missing.append('N não nulo ou não declarado: H4 reduzido N=0 não aplicável.')
        if missing:r.update(status='G81_computed_H4_pending',missing=missing)
        else:
            r['H4']=h4_envelope(a,Max_Nmm=current_strong['Ma_floor_Nmm'] if current_strong else None,
                May_Nmm={side:v['Ma_floor_Nmm'] for side,v in current_weak.items()} if current_weak else None,Ba_Nmm2=capacity['Ba_Nmm2'])
            if roof_context is not None:r['H4']['interpretation']=roof_h4.INTERPRETATION
            r.update(status='G81_and_H4_computed_conditional',missing=[])
        r['first_order_small_rotation_warning']=a['small_rotation_warning']
        ev['records'].append(r)
    ev.update(status='current_input_components',G81_computed_cases=sum(r['G81'] is not None for r in ev['records']),
        H4_computed_cases=sum(r['H4'] is not None for r in ev['records']),
        pending_cases=sum(r['H4'] is None for r in ev['records']))
    out[FIELD]=ev
    return out


def finalize(result):
    """Bind the new component to compact demand evidence without changing it."""
    out=copy.deepcopy(result)
    if FIELD not in out:
        ev=_base(out);torsion=out.get('torsion_evidence',{})
        reason=torsion.get('reason') or ('Demanda B e contorno setorial atuais não disponíveis: '
            'ative o modelo Vlasov elegível e declare as linhas de carga. Sem ω não se inventa By.')
        if out.get('schema')=='tercas_three_girt_results_v1' or out['input_data'].get('three_girt_model',{}).get('enabled'):
            reason='Modelo 3D bilateral de primeira ordem: não fornece o campo B requerido; N não nulo não é H4 N=0. Resistência dos tirantes não avaliada.'
        ev.update(status='pending_current_input_data',reason=reason,G81_computed_cases=0,
            H4_computed_cases=0,pending_cases=sum(c['combination']['limit_state']=='ELU' for c in out.get('cases',[])) if 'cases' in out else 1)
        # Preserve the inactive legacy girt boundary; its separate 3D route owns geometry.
        if out['input_data'].get('member_application','purlin')!='wall_girt':
            try:
                from .torsion_study import section_for
                section=section_for(out['input_data'])
                ev['bimoment_capacity']=g81_capacity(section,out['input_data']['properties']['fy_MPa'])
                ev['capacity_only']=True
            except (ValueError,KeyError,TypeError,OSError) as exc:
                ev['capacity_missing']=str(exc)
        out[FIELD]=ev
    ev=out[FIELD]
    from .ue_catalog_reference import claims_reference, source_binding
    if claims_reference(out['input_data']):
        ev['ue_catalog_source_binding']=source_binding(out['input_data'])
        ev['ue_catalog_scope']='G8.1 do mesmo contorno Ue; capacidades flexionais e H4 pendentes neste complemento.'
        ev['implemented_domain']=ev['ue_catalog_scope']
    ev['source_torsion_snapshot_sha256']=digest(out.get('torsion_evidence'))
    ev['snapshot_sha256']=digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    return out


def preserved(result):
    """Render/export only saved numbers. Never reopen or recalculate old results."""
    ev=result.get(FIELD)
    if ev is None:return None
    if not isinstance(ev,dict) or not isinstance(ev.get('records'),list) or any(not isinstance(r,dict) for r in ev['records']):
        raise ValueError('Registro AISI malformado.')
    if any(ev.get(k) is not None and not isinstance(ev[k],dict) for k in ('material','analysis_material','bimoment_capacity','strong_flexural_capacity')) or any(r.get(k) is not None and not isinstance(r[k],dict) for r in ev['records'] for k in ('G81','H4')):
        raise ValueError('Capacidade/estado AISI malformado.')
    if ev.get('schema')==SCHEMA and ('roof_height_source' in ev or any('roof_height' in r for r in ev['records'])):
        raise ValueError('Contrato AISI topo não pode ser rebaixado para histórico v1.')
    from .application import fingerprint
    from . import aisi_roof_height as roof_h4
    if (ev.get('schema') not in (SCHEMA,roof_h4.SCHEMA,roof_h4.DIRECT_SCHEMA) or fingerprint(result['input_data'])!=result.get('input_fingerprint')
            or ev.get('source_input_fingerprint')!=result.get('input_fingerprint')
            or ev.get('source_torsion_snapshot_sha256')!=digest(result.get('torsion_evidence'))
            or ev.get('snapshot_sha256')!=digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
            or ev.get('whole_member_approved') is not False or ev.get('NBR_capacities_used') is not False):
        raise ValueError('Componente AISI incompatível com o snapshot; recalcule explicitamente.')
    from .ue_catalog_reference import claims_reference, preserved as own_preserved
    if claims_reference(result['input_data']):
        source=own_preserved(result)
        if source is None or ev.get('ue_catalog_source_binding')!=source['source_binding'] or ev.get('H4_computed_cases') or any(r.get('H4') is not None for r in ev['records']):
            raise ValueError('Componente AISI não corresponde ao contorno próprio Ue ou herdou H4 indevido.')
    expected=_base(result)
    for key in ('load_basis','resistance_basis','source_editions_mixed','NBR_design_check',
                'physical_design_approved','whole_member_approved','NBR_capacities_used'):
        if ev.get(key)!=expected[key]:raise ValueError('Escopo/flag de aprovação AISI alterado: '+key)
    cap=ev.get('bimoment_capacity')
    if cap and (cap.get('phi_B')!=.90 or cap.get('physical_product_verified') is not False):
        raise ValueError('Fator ou qualificação G8.1 alterado.')
    material=ev.get('material');analysis=ev.get('analysis_material')
    if material and (material.get('E_MPa')!=E_AISI or material.get('G_MPa')!=G_AISI):
        raise ValueError('Material nominal AISI alterado.')
    if analysis and (analysis.get('stiffness_factor')!=STIFFNESS_FACTOR
            or analysis.get('E_MPa')!=STIFFNESS_FACTOR*E_AISI
            or analysis.get('G_MPa')!=STIFFNESS_FACTOR*G_AISI):
        raise ValueError('Fator de rigidez AISI alterado.')
    strong=ev.get('strong_flexural_capacity')
    if strong and strong.get('phi_b')!=.90:raise ValueError('Fator flexional AISI alterado.')
    if any(r.get('whole_member_approved') is not False or (r.get('H4') and r['H4'].get('whole_member_approved') is not False)
           for r in ev.get('records',[])):
        raise ValueError('Componente AISI não pode aprovar a barra inteira.')
    if ev.get('schema') in (roof_h4.SCHEMA,roof_h4.DIRECT_SCHEMA):
        try:roof_h4.validate_saved(result,ev)
        except (KeyError,TypeError,AttributeError,IndexError) as exc:
            raise ValueError('Registro AISI topo incompleto ou malformado.') from exc
    return copy.deepcopy(ev)
