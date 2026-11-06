"""Simple web-only shear checks on the existing 7DOF demand, never a new solve.

NBR §9.8.3/9.8.4 and EN §6.1.5/6.1.10 remain separate. Strong shear is
Vz_frame=-d(My_frame)/dx. Weak shear Vy_frame is never assigned web VRd.
The EN lower capacity uses sw<=hw conservatively; excess of this sufficient
capacity is inconclusive, not a demonstrated failure of the true capacity.
"""
import copy
import math
from numpy.polynomial import Polynomial
from .core.flt_vrd import vrd

SCHEMA='three_girt_web_shear_components_v1'
SOURCE_NBR='ABNT NBR14762:2010 §§9.8.3–9.8.4, pp.50–51'
SOURCE_EN='EN1993-1-3:2006 §§6.1.5, 6.1.10(1), pp.45–46,55'
SCOPE=('Componentes da alma no modelo nominal intacto. Não encerra cortante fraco, '
       'N+M+V+B+T, estabilidade da rede, forças locais, ligações ou ELS.')


def _positive(x,name):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<=0:
        raise ValueError(name+': valor positivo finito requerido')
    return float(x)


def en_web_lower_capacity(*,h_mm,t_mm,fyb_MPa,E_MPa=210000.,gamma_M0=1.):
    """§6.1.5: straight 90° web, no support/longitudinal stiffener credit.

    hw=h-t is measured between flange centrelines. The actual distance sw
    between bend midpoints is <=hw. Using sw_upper=hw increases lambda_w,
    never increases Table6.1 fbv. This explicitly conservative simplification
    avoids silently using the NBR flat-web width as the EN sw convention.
    """
    h,t,fy,E,g=[_positive(x,n) for x,n in ((h_mm,'h'),(t_mm,'t'),(fyb_MPa,'fyb'),(E_MPa,'E'),(gamma_M0,'gammaM0'))]
    hw=h-t
    if hw<=0:raise ValueError('Altura nominal incompatível com espessura')
    lam=.346*hw/t*math.sqrt(fy/E)
    if lam<=.83:f=.58*fy;branch='yield'
    elif lam<1.4:f=.48*fy/lam;branch='intermediate'
    else:f=.67*fy/lam**2;branch='elastic'
    # The printed Table6.1 branches are nonincreasing, including the small
    # downward jumps at .83 and 1.4. Thus sw_upper gives a lower capacity.
    return dict(Vw_Rd_lower_N=hw*t*f/g,hw_mm=hw,sw_upper_mm=hw,
        lambda_w_upper=lam,fbv_lower_MPa=f,branch=branch,E_MPa=E,fyb_MPa=fy,
        gamma_M0=g,source=SOURCE_EN,capacity_kind='conservative_lower_bound',
        support_stiffener_credit=False,longitudinal_stiffener_credit=False,
        reason='sw entre pontos médios das dobras não excede hw; ramo sem enrijecedores de apoio.')


def concomitant_mv(*,M_coeff,length_mm,MRd_local_Nmm,VRd_N,x_start_mm=0.):
    """Exact quartic envelope of M²/MRd² + V²/VRd² on one physical segment.

    M coefficients are in u=(x-x_start)/length. V=-dM/dx. Roots and both joint
    sides are retained; no component maxima from different stations are added.
    """
    length=_positive(length_mm,'length');mr=_positive(MRd_local_Nmm,'MRd_local');vr=_positive(VRd_N,'VRd')
    if not isinstance(M_coeff,list) or not 1<=len(M_coeff)<=3 or any(
            isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in M_coeff):
        raise ValueError('Polinômio de momento finito de grau até 2 requerido')
    if isinstance(x_start_mm,bool) or not isinstance(x_start_mm,(int,float)) or not math.isfinite(x_start_mm):
        raise ValueError('Posição inicial finita requerida')
    m=Polynomial(M_coeff);v=-m.deriv()/length;index=(m/mr)**2+(v/vr)**2
    points=[0.,1.]
    for z in index.deriv().roots():
        if abs(z.imag)<=1e-10 and 0.<z.real<1.:points.append(float(z.real))
    states=[dict(u=u,x_mm=x_start_mm+u*length,Mstrong_Nmm=float(m(u)),Vweb_N=float(v(u)),
        index_squared=float((m(u)/mr)**2+(v(u)/vr)**2),
        side='segment_start_right' if u==0 else 'segment_end_left' if u==1 else 'interior') for u in sorted(set(points))]
    return dict(maximum=max(states,key=lambda r:r['index_squared']),states=states,
        MRd_denominator_Nmm=mr,VRd_denominator_N=vr,MRd_basis='NBR14762 §9.8.2.1 only; not FLT/distortional minimum',
        source=SOURCE_NBR,whole_member_approved=False,N_M_V_B_T_qualified=False)


def calculate_validated(demand,reference):
    """Called only after the existing own-Ue demand/source validation.

    The caller supplies the complete freshly verified reference, not user
    denominators. No hidden section/capacity or zero weak action is invented.
    """
    from .three_girt_axial.application import _polynomials,fingerprint
    p=demand['input_data']['properties']
    h,t,ri,fy,E=(_positive(p[k],k) for k in ('h','t','ri_mm','fy_MPa','E_MPa'))
    flat=h-2*(ri+t)
    if flat<=0 or p.get('lip',0)<=0:raise ValueError('Subconjunto Ue próprio de alma plana requerido')
    cap=vrd(flat,t,fy,E)
    en_source=demand.get('EN_normal_N_M_B_component')
    en_declared=False
    if en_source is not None:
        from .three_girt_en_normal.application import saved_component
        en_source=saved_component(demand)
        en_declared=(en_source['configuration']['intact_section_model_declared'] is True and fy==250.)
    en_cap=en_web_lower_capacity(h_mm=h,t_mm=t,fyb_MPa=fy) if en_declared else None
    positive=reference['resistances_exterior_primary']['strong_positive']['MRd_local_Nmm']
    negative=reference['resistances_exterior_primary']['strong_negative']['MRd_local_Nmm']
    if positive!=negative:raise ValueError('Este envelope requer MRd local forte igual nos dois sentidos')
    rows=[]
    for case in demand['cases']:
        if case['combination']['limit_state']!='ELU':continue
        for beam in case['model']['beams']:
            fields=_polynomials(beam);length=beam['x_end_mm']-beam['x_start_mm']
            strong=Polynomial(fields['My_strong_Nmm']);weak=Polynomial(fields['Mz_weak_Nmm'])
            web=-strong.deriv()/length;secondary=weak.deriv()/length
            for state in beam['states']:
                u=(state['x_mm']-beam['x_start_mm'])/length
                for key,poly in (('Vz_N',web),('Vy_N',secondary)):
                    if not math.isclose(float(poly(u)),state[key],rel_tol=2e-10,abs_tol=1e-7):
                        raise ValueError('Cortante salvo diverge da derivada do momento: '+key)
            peak=max((dict(u=u,x_mm=beam['x_start_mm']+u*length,Vweb_N=float(web(u)),
                side='segment_start_right' if u==0 else 'segment_end_left') for u in (0.,1.)),key=lambda r:abs(r['Vweb_N']))
            value=abs(peak['Vweb_N']);ratio=value/cap['VRd_N']
            mv=concomitant_mv(M_coeff=fields['My_strong_Nmm'],length_mm=length,
                MRd_local_Nmm=positive,VRd_N=cap['VRd_N'],x_start_mm=beam['x_start_mm'])
            weak_zero=all(v==0. for v in secondary.coef)
            entry=dict(combination_id=case['combination']['id'],girt=beam['girt'],segment_id=beam['id'],
                x_start_mm=beam['x_start_mm'],x_end_mm=beam['x_end_mm'],
                N_N=fields['N_N'][0],Mstrong_coeff=fields['My_strong_Nmm'],Mweak_coeff=fields['Mz_weak_Nmm'],
                Vweb_coeff=list(map(float,web.coef)),Vweak_coeff=list(map(float,secondary.coef)),
                weak_shear_identically_zero=weak_zero,web_shear_witness=peak,
                NBR_web_shear=dict(index=ratio,status='fails' if ratio>1 else 'meets',source=SOURCE_NBR),
                NBR_MV=mv,EN_web_shear=None,EN_no_web_shear_reduction=None,
                N_M_V_B_T_qualified=False,whole_member_approved=False)
            if en_cap:
                er=value/en_cap['Vw_Rd_lower_N']
                entry['EN_web_shear']=dict(index_upper=er,status='meets' if er<=1 else 'inconclusive',
                    source=SOURCE_EN,capacity_kind='conservative_lower_bound')
                entry['EN_no_web_shear_reduction']=dict(ratio_upper=er,threshold=.5,
                    status='meets' if er<=.5 else 'pending',source=SOURCE_EN,
                    scope='Dispensa somente da redução adicional por V na alma; não aprova N/M/B/T nem cortante fraco.')
            rows.append(entry)
    if not rows:raise ValueError('Nenhum trecho ELU para cortante')
    out=dict(schema=SCHEMA,source_input_fingerprint=demand['input_fingerprint'],source_demand_sha256=fingerprint(demand),
        source_reference_id=reference['id'],source_geometry=copy.deepcopy(demand['source_geometry']),
        source_NBR=SOURCE_NBR,source_EN=SOURCE_EN,scope=SCOPE,
        NBR_capacity=dict(cap,h_flat_mm=flat,t_mm=t,fy_MPa=fy,E_MPa=E),EN_capacity=en_cap,
        EN_reason=None if en_cap else 'Componente EN intacta não declarada/qualificada com fyb=250 MPa; sem transferência de denominador NBR.',
        rows=rows,ELU_segments=len(rows),ELS_combinations_excluded=sum(c['combination']['limit_state']=='ELS' for c in demand['cases']),
        all_weak_shear_zero=all(r['weak_shear_identically_zero'] for r in rows),
        first_order_network_stability_qualified=False,tie_strength_checked=False,tie_slenderness_checked=False,
        panel_restraint_credit=False,whole_member_approved=False,N_M_V_B_T_qualified=False,
        stability_scope='NBR §§8.1–8.2: comprimentos efetivos não provam estabilidade de rede; posições de tirantes não criam vínculos de torção.')
    out['content_sha256']=fingerprint(out)
    return out


def saved(component):
    """Read nested snapshot without mechanics or retroactive migration."""
    from .three_girt_axial.application import fingerprint
    out=component.get('web_shear_component')
    if out is None:return None
    if not isinstance(out,dict) or out.get('schema')!=SCHEMA or out.get('content_sha256')!=fingerprint({k:v for k,v in out.items() if k!='content_sha256'}):
        raise ValueError('Snapshot de cortante salvo alterado')
    if (out.get('source_demand_sha256')!=component['source_demand_sha256']
        or out.get('source_input_fingerprint')!=component['source_input_fingerprint']
        or out.get('source_geometry')!=component['source_geometry']):
        raise ValueError('Cortante não corresponde à mesma demanda/seção')
    keys=('first_order_network_stability_qualified','tie_strength_checked','tie_slenderness_checked','panel_restraint_credit','whole_member_approved','N_M_V_B_T_qualified')
    if any(out.get(k) is not False for k in keys):raise ValueError('Escopo salvo de cortante indevidamente ampliado')
    if len(out['rows'])!=out['ELU_segments'] or [(r['combination_id'],r['girt'],r['segment_id']) for r in out['rows']] != [(r['combination_id'],r['girt'],r['segment_id']) for r in component['rows']]:
        raise ValueError('Inventário de cortante incompleto')
    return out


def presentation_rows(component, demand=None):
    out=saved(component)
    if out is None:return []
    labels={'upper':'Superior','middle':'Central','lower':'Inferior'}
    rows=[]
    from .three_girt_scope import members
    for level in (members(demand) if demand is not None else labels):
        rr=[r for r in out['rows'] if r['girt']==level]
        if not rr:continue
        shear=max(rr,key=lambda r:r['NBR_web_shear']['index'])
        mv=max(rr,key=lambda r:r['NBR_MV']['maximum']['index_squared'])
        er=[r for r in rr if r['EN_web_shear'] is not None]
        rows.append(dict(Travessa=labels[level],Cortante_NBR=shear['NBR_web_shear']['index'],
            M_V_NBR=mv['NBR_MV']['maximum']['index_squared'],
            Combinação_M_V=mv['combination_id'],Posição_M_V_mm=mv['NBR_MV']['maximum']['x_mm'],
            Teto_cortante_EN=max(r['EN_web_shear']['index_upper'] for r in er) if len(er)==len(rr) else None,
            Redução_por_V_EN='Limiar da alma ≤0,5; registro histórico restrito' if len(er)==len(rr) and all(r['EN_no_web_shear_reduction']['status']=='meets' for r in er) else 'Pendente',
            Cortante_fraco='Identicamente nulo' if all(r['weak_shear_identically_zero'] for r in rr) else 'Pendente; VRd da alma não reutilizado'))
    return rows


def render_saved(st,component, demand=None):
    try:out=saved(component)
    except (ValueError,TypeError,KeyError) as exc:
        st.warning('Cortante salvo não exibido: '+str(exc));return
    if out is None:
        if component.get('web_shear_error'):st.warning('Cortante da alma não calculado: '+component['web_shear_error'])
        return
    st.subheader('Cortante e interação M–V da alma')
    st.dataframe(presentation_rows(component,demand=demand),hide_index=True)
    st.caption(SCOPE)
    st.caption('M–V NBR usa MRd local de §9.8.2.1 e M/V da mesma seção; não é a interação completa quando N, B ou T estão presentes. O índice EN é um teto suficiente; acima de 1 não demonstra falha.')
    st.caption('Registro restrito à alma: não demonstra dispensa de §6.1.10 para a seção completa. A componente EN6.27 adicional, quando salva, é apresentada no grupo EN independente da referência NBR.')
    st.caption(out['stability_scope'])
    with st.expander('Memória completa do cortante (inclui contexto superior/inferior)'):
        st.json(out)


def append_report(doc,component, demand=None):
    try:out=saved(component)
    except (ValueError,TypeError,KeyError) as exc:
        doc.add_paragraph('Cortante salvo não incluído: '+str(exc));return
    if out is None:return
    doc.add_heading('Cortante e interação M–V da alma',1)
    doc.add_paragraph(SCOPE)
    doc.add_paragraph('NBR: kv=5, sem crédito de enrijecedores transversais. M–V é o máximo concomitante de (M/MRd,local)²+(V/VRd)², com os dois lados de cada junta. Não se usa MRd reduzido por FLT/distorcional no denominador de §9.8.4.')
    for row in presentation_rows(component,demand=demand):
        doc.add_paragraph('; '.join(str(k)+' = '+str(v) for k,v in row.items()))
    doc.add_paragraph('Registro histórico restrito à alma: sw<=hw produz piso de Vw,Rd sem resistência NBR. O limiar transversal não demonstra dispensa de §6.1.10 para a seção completa e não foi reclassificado. A componente EN6.27 adicional, quando salva, é apresentada no grupo EN independente. Valores acima do teto suficiente são inconclusivos, não falhas demonstradas.')
    doc.add_paragraph(out['stability_scope'])
    doc.add_paragraph('Sem contribuição de rigidez da telha; tirantes não recebem verificação resistente nem de esbeltez. A rigidez axial declarada continua no modelo, mas não vira vínculo lateral/torsional ideal automaticamente.')
