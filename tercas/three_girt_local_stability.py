"""Central-girt local B1 reference; never a network-stability approval.

NBR 8800:2008 D.2.2 / 2024 C.2.2: B1=max(1,Cm/(1-Nc/Ne)).
Use Cm=1 and full-span flexural Euler loads in each plane. Piecewise N is
reported explicitly: Nmax defines the uniform equivalent local member reference.
This component does not alter first-order demands or resistance indices.
"""
import copy
import hashlib
import json
import math

SCHEMA='three_girt_central_local_B1_reference_v2'
LEGACY_SCHEMA='three_girt_central_local_B1_reference_v1'
FIELD='central_local_B1_component'
SOURCE=dict(clause='NBR 8800:2024 C.2.2; antecedente NBR 8800:2008 D.2.2',
    url_2008='https://engcivil20142.wordpress.com/wp-content/uploads/2018/03/nbr8800_2008_1.pdf',
    url_2024='https://studylib.net/doc/28489089/nbr-8800--2024-',
    uniform_axial_reference='AS 4100:2020 8.2 and 4.4.2.2; Hancock, Design of Cold-Formed Steel Structures, chapter 8, 8.2',
    url_as4100='https://sarah.com.au/wp-content/uploads/2024/09/4100_AS_2020_Steel_Structure.pdf',
    url_cold_formed='https://www.steel.org.au/resources/elibrary/resources/cold-formed-members-in-combined-axial-compressive/?view=download',
    note='2024 consulted as a secondary reproduction; no universal B1<=1.10 exemption.')
PLANS=(('strong','My_strong_Nmm','I_strong_mm4','uz','ry'),
       ('weak','Mz_weak_Nmm','I_weak_mm4','uy','rz'))
SAFE_FALSE=('whole_member_approved','network_stability_qualified',
    'analysis_8_1_qualified','applied_to_original_resistance','tie_strength_checked',
    'outer_girt_strength_checked','panel_restraint_credit','tie_restraint_credit')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
        allow_nan=False,separators=(',',':')).encode()).hexdigest()


def number(value,name,positive=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError(name+': finite number required')
    if positive and value<=0:raise ValueError(name+': positive number required')
    return float(value)


def flexural_B1(*,compression_N,E_MPa,I_mm4,L_mm):
    """Scalar pin-ended, prismatic reference. No cap or N>=Ne fallback."""
    nc=number(compression_N,'compression_N')
    if nc<0:raise ValueError('compression_N must be nonnegative')
    E=number(E_MPa,'E',True);I=number(I_mm4,'I',True);L=number(L_mm,'L',True)
    ne=math.pi**2*E*I/L**2
    if not math.isfinite(ne) or ne<=0:raise ValueError('Euler load outside finite positive domain')
    ratio=nc/ne
    b1=None if ratio>=1 else 1/(1-ratio)
    return dict(Ne_flexural_N=ne,Nc_over_Ne=ratio,Cm=1.,K_flexural=1.,
        effective_length_mm=L,B1_reference=b1,
        status='at_or_above_Euler' if b1 is None else 'finite_local_reference')


def _supports(model,L):
    """Document K=1 only for the isolated member's declared end conditions."""
    nodes=sorted((n for n in model['nodes'] if n['xyz_CG_mm'][1]==0.),
                 key=lambda n:n['xyz_CG_mm'][0])
    if len(nodes)<2 or nodes[0]['xyz_CG_mm'][0]!=0. or nodes[-1]['xyz_CG_mm'][0]!=L:
        raise ValueError('Central nodes do not cover the full physical span')
    if any(n['xyz_CG_mm'][2]!=0. for n in nodes):
        raise ValueError('Only the declared straight central member is supported')
    ids=[n['id'] for n in nodes]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate central node identity')
    fixed={(r['node'],r['dof']) for r in model['fixed_dofs']}
    ends=[ids[0],ids[-1]];interior=ids[1:-1]
    planes={}
    for plane,_,_,translation,rotation in PLANS:
        compatible=(all((i,translation) in fixed and (i,rotation) not in fixed for i in ends)
            and not any((i,d) in fixed for i in interior for d in (translation,rotation)))
        planes[plane]=dict(compatible=compatible,K=1. if compatible else None,
            translation=translation,rotation=rotation,
            justification='End translations fixed and flexural rotations free; full span with no intermediate support credit.'
                if compatible else 'Declared constraints differ from the supported pin-ended full-span reference.')
    torsion=(all((i,'rx') in fixed and (i,'psi') not in fixed for i in ends)
             and not any((i,d) in fixed for i in interior for d in ('rx','psi')))
    return dict(end_nodes=ends,planes=planes,
        Kt_classical_free_warping_reference=1. if torsion else None,
        torsional_reference_only=True,
        torsion_note='Kt=1 applies only to the isolated classical twist-restrained, free-warping ends; it does not qualify the coupled network.')


def _case(case):
    model=case['model'];inp=model['inputs'];s=inp['section'];L=number(inp['L_mm'],'L',True)
    supports=_supports(model,L)
    beams=sorted((b for b in model['beams'] if b['girt']=='middle'),key=lambda b:b['x_start_mm'])
    if not beams or beams[0]['x_start_mm']!=0. or beams[-1]['x_end_mm']!=L:
        raise ValueError('Missing central physical member')
    segments=[]
    for j,b in enumerate(beams):
        if b['x_end_mm']<=b['x_start_mm'] or (j and beams[j-1]['x_end_mm']!=b['x_start_mm']):
            raise ValueError('Central segment gap/overlap')
        p=b['normal_action_polynomials'];n=p['N_N']
        if not isinstance(n,list) or len(n)!=1:raise ValueError('Piecewise constant signed N field required')
        segments.append(dict(id=b['id'],x_start_mm=b['x_start_mm'],x_end_mm=b['x_end_mm'],
            N_tension_positive_N=number(n[0],'N'),
            moment_polynomials={key:[number(v,key) for v in p[key]] for _,key,_,_,_ in PLANS}))
    forces=[b['N_tension_positive_N'] for b in segments];nmin=min(forces);nmax=max(forces)
    nc=max(0.,-nmin)
    # Numerical equality only, not a structural acceptance tolerance.
    uniform=math.isclose(nmin,nmax,rel_tol=1e-10,abs_tol=1e-8)
    issues=[];planes={}
    for plane,_,inertia,_,_ in PLANS:
        if not supports['planes'][plane]['compatible']:
            planes[plane]=dict(B1_reference=None,status='unsupported_end_conditions')
            issues.append('unsupported_end_conditions_'+plane)
            continue
        planes[plane]=flexural_B1(compression_N=nc,E_MPa=s['E_MPa'],I_mm4=s[inertia],L_mm=L)
        if planes[plane]['B1_reference'] is None:issues.append('compression_at_or_above_Euler_'+plane)
    local_formula_applicable=not issues
    amplified=None
    if local_formula_applicable:
        # Separate reference polynomials only: original M, N, B, T, V untouched.
        amplified=[dict(segment_id=b['id'],x_start_mm=b['x_start_mm'],x_end_mm=b['x_end_mm'],
            **{key:[v*planes[plane]['B1_reference'] for v in b['moment_polynomials'][key]]
               for plane,key,_,_,_ in PLANS}) for b in segments]
    return dict(combination_id=case['combination']['id'],girt='middle',physical_span_mm=L,
        N_min_tension_positive_N=nmin,N_max_tension_positive_N=nmax,
        N_compression_max_N=nc,uniform_axial_force=uniform,
        uniform_N_numeric_tolerance=dict(relative=1e-10,absolute_N=1e-8),
        supports=supports,planes=planes,segments=segments,issues=issues,
        status='local_formula_reference_only' if local_formula_applicable else 'estimate_or_inconclusive',
        local_formula_reference_applicable=local_formula_applicable,
        amplified_local_reference_moment_polynomials=amplified,
        global_redistribution_assessed=False,stability_criterion=None,
        axial_reference='uniform_equivalent_maximum_by_combination',
        note='Approximate local beam-column reference with maximum compression, Cm=1 and full span. '
             'Variable N alone does not block the method. This does not certify network redistribution.')


def calculate_validated(demand,nbr_component=None):
    """Called after the NBR adapter validates the current complete demand."""
    rows=[_case(c) for c in demand['cases'] if c['combination']['limit_state']=='ELU']
    if not rows:raise ValueError('No ELU combination for local B1')
    candidates=[(p['B1_reference'],r['combination_id'],name) for r in rows for name,p in r['planes'].items()
                if p['B1_reference'] is not None]
    maximum=max(candidates) if candidates else None
    out=dict(schema=SCHEMA,source_demand_sha256=fingerprint(demand),source=copy.deepcopy(SOURCE),
        status='inconclusive_network',verified_members=['middle'],ELU_combinations=len(rows),cases=rows,
        maximum_B1_reference=None if maximum is None else dict(B1=maximum[0],combination_id=maximum[1],plane=maximum[2]),
        local_formula_cases=sum(r['local_formula_reference_applicable'] for r in rows),
        diagnostic_or_blocked_cases=sum(not r['local_formula_reference_applicable'] for r in rows),
        conclusion='Local flexural amplification quantified; global redistribution and combined stability remain unqualified.',
        limits=['B1 only affects the corresponding local bending-moment reference.',
            'No automatic change to N, bimoment, torque, shear, reactions or resistance indices.',
            'B1<=1.10 is not used as a normative pass or exemption.',
            'Full-span reference has no intermediate bracing credit and is not a network eigenvalue.'],
        **{k:False for k in SAFE_FALSE})
    out['local_NM_reference']=None if nbr_component is None else _local_interaction(out,nbr_component)
    out['content_sha256']=fingerprint(out)
    return out


def _local_interaction(out,nbr):
    """Separate conservative member envelope, never a physical concomitant state.

    Use maximum compression/tension of this combination as uniform equivalent
    axial branches. The two signed bending diagrams remain concomitant with each
    other, and are amplified per plane. Do not mix different combinations.
    """
    from .three_girt_axial import backend as a
    original={(r['combination_id'],r['segment_id']):r for r in nbr['rows'] if r['girt']=='middle'}
    rows=[];blocked=[]
    for case in out['cases']:
        cid=case['combination_id']
        if not case['local_formula_reference_applicable']:
            blocked.append(cid);continue
        nc=case['N_compression_max_N'];nt=max(0.,case['N_max_tension_positive_N'])
        branches=[('compression',-nc)] if nc else []
        if nt:branches.append(('tension',nt))
        if not branches:branches=[('zero',0.)]
        for segment in case['amplified_local_reference_moment_polynomials']:
            old=original[(cid,segment['segment_id'])]
            for branch,n in branches:
                row=a.interaction_segment(N_coeff=[n],Mstrong_coeff=segment['My_strong_Nmm'],
                    Mweak_coeff=segment['Mz_weak_Nmm'],capacities=old['denominators'],
                    combination_id=cid,section_id=old['section_id'],
                    stability_member_id=old['stability_member_id'],region_id=old['region_id'],
                    segment_id=old['segment_id'],x_start_mm=segment['x_start_mm'],
                    length_mm=segment['x_end_mm']-segment['x_start_mm'],
                    origin='Uniform equivalent axial envelope in this combination; local B1 bending; no network approval.')
                row.update(girt='middle',axial_branch=branch,physical_concomitant_state=False)
                rows.append(row)
    ready=[r for r in rows if r['maximum'] is not None]
    winner=max(ready,key=lambda r:r['maximum']['numeric_index']) if ready else None
    return dict(method='uniform_axial_envelopes_with_local_B1',rows=rows,
        source_NBR_capacities_sha256=fingerprint(nbr['capacities']),
        blocked_combinations=blocked,complete=bool(rows) and not blocked and len(ready)==len(rows),
        maximum_available=None if winner is None else dict(combination_id=winner['combination_id'],
            segment_id=winner['segment_id'],axial_branch=winner['axial_branch'],state=winner['maximum']),
        missing_capacity_keys=sorted({k for r in rows for k in r['missing_capacity_keys']}),
        member_issues=sorted({k for r in rows for k in r['member_issues']}),
        physical_concomitant_state=False,whole_member_approved=False,
        note='Spatial axial envelopes are intentional design approximations, not solved force states. '
             'Tension and compression branches are separate; missing tension resistance is not filled with gross area. '
             'N/M reference only; no T/B, shear interaction or network approval.')


def saved(nbr_component,demand=None):
    """Validate saved evidence without solving or regenerating an envelope.

    With the complete source demand, the moment coefficients and supports are
    linked exactly. Without it, this is a diagnostic read of the saved NBR
    witness states; two witnesses alone do not determine a quadratic diagram.
    The v1 record keeps its original, more limited meaning without migration.
    """
    out=nbr_component.get(FIELD)
    if out is None:return None
    legacy=isinstance(out,dict) and out.get('schema')==LEGACY_SCHEMA
    flags=tuple('applied_to_resistance' if legacy and k=='applied_to_original_resistance' else k for k in SAFE_FALSE)
    if (not isinstance(out,dict) or out.get('schema') not in (SCHEMA,LEGACY_SCHEMA)
        or out.get('content_sha256')!=fingerprint({k:v for k,v in out.items() if k!='content_sha256'})
        or out.get('source_demand_sha256')!=nbr_component.get('source_demand_sha256')
        or out.get('verified_members')!=['middle'] or out.get('status')!='inconclusive_network'
        or not isinstance(out.get('cases'),list)
        or any(out.get(k) is not False for k in flags)
        or any(not isinstance(r,dict) or r.get('global_redistribution_assessed') is not False or r.get('stability_criterion') is not None
               for r in out.get('cases',[]))):
        raise ValueError('Invalid or scope-expanded saved central B1 reference')
    try:
        _validate_saved_inventory(out,nbr_component,demand=demand,legacy=legacy)
        local=out.get('local_NM_reference')
        if legacy:
            if local is not None:raise ValueError('Historical B1 reference acquired a new N/M envelope')
        elif local is None:
            raise ValueError('Saved B1 v2 reference is missing its separate N/M envelope')
        else:_validate_saved_interaction(out,nbr_component)
    except (KeyError,TypeError,IndexError,OverflowError) as exc:
        raise ValueError('Malformed saved central B1 reference') from exc
    return out


def _coefficients(values):
    if not isinstance(values,list) or not 1<=len(values)<=3:
        raise ValueError('Finite saved moment polynomial of degree at most two required')
    return [number(v,'saved moment coefficient') for v in values]+[0.]*(3-len(values))


def _value(coeff,u):return (coeff[2]*u+coeff[1])*u+coeff[0]


def _close(actual,expected,absolute=1e-7):
    return math.isclose(number(actual,'saved witness'),expected,rel_tol=2e-10,abs_tol=absolute)


def _validate_saved_inventory(out,nbr,demand=None,legacy=False):
    """Read-only linkage/arithmetic checks; never solve or regenerate history."""
    source=None
    if demand is not None:
        from .three_girt_axial.application import FIELD as NBR_FIELD
        if fingerprint({k:v for k,v in demand.items() if k!=NBR_FIELD})!=out['source_demand_sha256']:
            raise ValueError('Saved B1 reference differs from the complete source demand')
        source={c['combination']['id']:c for c in demand['cases'] if c['combination']['limit_state']=='ELU'}
    expected={}
    for r in nbr['rows']:
        if r['girt']=='middle':
            expected.setdefault(r['combination_id'],{})[r['segment_id']]=r
    cases=out['cases']
    if (not cases or len(cases)!=len(expected) or out['ELU_combinations']!=len(cases)
        or {r.get('combination_id') for r in cases}!=set(expected)):
        raise ValueError('Saved B1 ELU inventory differs from the central NBR reference')
    candidates=[]
    for r in cases:
        rows=expected[r['combination_id']];segments=r['segments']
        source_beams=None
        if source is not None:
            model=source[r['combination_id']]['model']
            source_beams={b['id']:b for b in model['beams'] if b['girt']=='middle'}
            if r['supports']!=_supports(model,r['physical_span_mm']):
                raise ValueError('Saved B1 supports differ from the complete source demand')
        if (r['girt']!='middle' or len(segments)!=len(rows)
            or {s['id'] for s in segments}!=set(rows)):
            raise ValueError('Saved B1 member/segment identity differs from central reference')
        forces=[]
        for s in segments:
            original=rows[s['id']]
            if (r['physical_span_mm']!=original['physical_member_length_mm']
                or s['x_start_mm']!=min(p['x_mm'] for p in original['states'])
                or s['x_end_mm']!=max(p['x_mm'] for p in original['states'])
                or any(not math.isclose(s['N_tension_positive_N'],p['N_tension_positive_N'],
                    rel_tol=2e-10,abs_tol=1e-7) for p in original['states'])):
                raise ValueError('Saved B1 axial field/span differs from central NBR reference')
            for (_,field,_,_,_),state_field in zip(PLANS,('Mstrong_Nmm','Mweak_Nmm')):
                coeff=_coefficients(s['moment_polynomials'][field])
                if any(not _close(p[state_field],_value(coeff,p['x_normalized'])) for p in original['states']):
                    raise ValueError('Saved B1 moment field differs from central NBR witness states')
                if source_beams is not None and s['moment_polynomials'][field]!=source_beams[s['id']]['normal_action_polynomials'][field]:
                    raise ValueError('Saved B1 moment coefficients differ from the complete source demand')
            forces.append(number(s['N_tension_positive_N'],'saved N'))
        nmin,nmax=min(forces),max(forces);nc=max(0.,-nmin)
        uniform=math.isclose(nmin,nmax,rel_tol=1e-10,abs_tol=1e-8)
        if (r['N_min_tension_positive_N']!=nmin or r['N_max_tension_positive_N']!=nmax
            or r['N_compression_max_N']!=nc or r['uniform_axial_force']!=uniform):
            raise ValueError('Saved B1 axial envelope/uniformity differs from its field')
        issues=[]
        for plane,ne_key in (('strong','Nex_N'),('weak','Ney_N')):
            p=r['planes'][plane]
            if not r['supports']['planes'][plane]['compatible']:
                issues.append('unsupported_end_conditions_'+plane)
                if p['B1_reference'] is not None:raise ValueError('Unsupported B1 plane acquired a factor')
                continue
            ne=nbr['capacities']['compression']['elastic'][ne_key]
            ratio=nc/ne;factor=None if ratio>=1 else 1/(1-ratio)
            if (not math.isclose(p['Ne_flexural_N'],ne,rel_tol=2e-12)
                or not math.isclose(p['Nc_over_Ne'],ratio,rel_tol=2e-12,abs_tol=1e-15)
                or p['Cm']!=1. or p['K_flexural']!=1.
                or p['effective_length_mm']!=r['physical_span_mm']
                or (factor is None and p['B1_reference'] is not None)
                or (factor is not None and (p['B1_reference'] is None
                    or not math.isclose(p['B1_reference'],factor,rel_tol=2e-12)))):
                raise ValueError('Saved B1 arithmetic differs from its flexural reference')
            if factor is None:issues.append('compression_at_or_above_Euler_'+plane)
            else:candidates.append((p['B1_reference'],r['combination_id'],plane))
        if legacy and nc>0 and not uniform:
            issues.append('nonuniform_axial_force_extension_not_qualified')
        if not legacy and r.get('axial_reference')!='uniform_equivalent_maximum_by_combination':
            raise ValueError('Saved B1 axial reference changed')
        expected_amplified=None if issues else [dict(segment_id=b['id'],x_start_mm=b['x_start_mm'],x_end_mm=b['x_end_mm'],
            **{key:[v*r['planes'][plane]['B1_reference'] for v in b['moment_polynomials'][key]]
                for plane,key,_,_,_ in PLANS}) for b in segments]
        if r['amplified_local_reference_moment_polynomials']!=expected_amplified:
            raise ValueError('Saved B1 amplified moment fields differ from their reference')
        if (r['issues']!=issues or r['local_formula_reference_applicable']!=(not issues)
            or (issues and r['amplified_local_reference_moment_polynomials'] is not None)):
            raise ValueError('Saved B1 applicability/estimate scope was changed')
    count=sum(r['local_formula_reference_applicable'] for r in cases)
    maximum=max(candidates) if candidates else None
    maximum=None if maximum is None else dict(B1=maximum[0],combination_id=maximum[1],plane=maximum[2])
    if (out['local_formula_cases']!=count or out['diagnostic_or_blocked_cases']!=len(cases)-count
        or out['maximum_B1_reference']!=maximum):
        raise ValueError('Saved B1 summary differs from its cases')


def _require_stationary_witness(coeff,lo,hi,positions):
    """A quadratic's derivative is linear: a sign change needs a saved zero.

    Only inspect derivatives at existing positions. No roots are calculated,
    and no new witness or envelope is generated while reading a snapshot.
    """
    tolerance=2e-10*max(1.,abs(coeff[1]),2*abs(coeff[2]))
    derivative=lambda u:coeff[1]+2*coeff[2]*u
    left,right=derivative(lo),derivative(hi)
    crossing=(left < -tolerance and right > tolerance) or (right < -tolerance and left > tolerance)
    if crossing and not any(lo<u<hi and abs(derivative(u))<=tolerance for u in positions):
        raise ValueError('Saved B1 interaction is missing an interior stationary witness')


def _validate_interaction_row(row,case,segment,original,branch,n):
    """Check existing candidates, values and extrema coverage without roots."""
    for key in ('combination_id','section_id','stability_member_id','region_id','segment_id'):
        if row[key]!=original[key]:raise ValueError('Saved B1 interaction identity differs from central NBR')
    if (row['girt']!='middle' or row['axial_branch']!=branch
        or any(row.get(k) is not False for k in ('physical_concomitant_state','whole_member_approved',
            'analysis_8_1_qualified','torsion_warping_shear_qualified','second_order_automatically_imposed'))):
        raise ValueError('Saved B1 interaction scope was expanded')
    coeffs=[[n,0.,0.],_coefficients(segment['My_strong_Nmm']),_coefficients(segment['Mz_weak_Nmm'])]
    axes=(('Nt','Nc'),('Mstrong_pos','Mstrong_neg'),('Mweak_pos','Mweak_neg'))
    active=[any(v!=0. for v in c) for c in coeffs]
    caps=original['denominators'];states=row['states']
    if not isinstance(states,list) or not states:raise ValueError('Missing saved B1 interaction witnesses')
    groups=[]
    for state in states:
        interval=state['interval']
        if not isinstance(interval,list) or len(interval)!=2:raise ValueError('Invalid saved B1 sign interval')
        lo,hi=(number(v,'saved interval') for v in interval)
        if not 0.<=lo<hi<=1.:raise ValueError('Saved B1 interval outside its segment')
        if not groups or groups[-1][0]!=(lo,hi):groups.append(((lo,hi),[]))
        groups[-1][1].append(state)
    if groups[0][0][0]!=0. or groups[-1][0][1]!=1. or any(
        previous[0][1]!=following[0][0] for previous,following in zip(groups,groups[1:])):
        raise ValueError('Saved B1 sign intervals have a gap, overlap or reordering')
    missing=set();issues=set();intervals=[]
    for (lo,hi),witnesses in groups:
        signs=[1 if _value(c,(lo+hi)/2)>=0. else -1 for c in coeffs]
        keys=[pair[0 if sign>0 else 1] if used else None for pair,sign,used in zip(axes,signs,active)]
        for key in keys:
            if key is None:continue
            cap=caps.get(key)
            if cap is None or cap.get('value') is None:missing.add(key)
            if cap is not None:
                issues.update(cap.get('member_issues',[]))
                if cap.get('value') is not None:number(cap['value'],'saved capacity',True)
        intervals.append((lo,hi,witnesses,signs,keys))
    if row['missing_capacity_keys']!=sorted(missing) or row['member_issues']!=sorted(issues):
        raise ValueError('Saved B1 interaction denominator coverage changed')
    expected_status='incomplete_denominators' if missing else 'concomitant_arithmetic_only'
    if row['status']!=expected_status:raise ValueError('Saved B1 interaction arithmetic status changed')
    start=segment['x_start_mm'];length=segment['x_end_mm']-start
    for lo,hi,witnesses,signs,keys in intervals:
        positions=[number(s['x_normalized'],'saved normalized position') for s in witnesses]
        if positions!=sorted(set(positions)) or positions[0]!=lo or positions[-1]!=hi:
            raise ValueError('Saved B1 interaction interval lacks ordered end witnesses')
        for coeff in coeffs:_require_stationary_witness(coeff,lo,hi,positions)
        if not missing:
            weighted=[sum(sign*c[i]/caps[key]['value'] for c,sign,key in zip(coeffs,signs,keys)
                          if key is not None) for i in range(3)]
            _require_stationary_witness(weighted,lo,hi,positions)
        for state,u in zip(witnesses,positions):
            if not lo<=u<=hi or not _close(state['x_mm'],start+length*u):
                raise ValueError('Saved B1 interaction witness is outside its physical segment')
            if state['capacity_keys']!=keys:raise ValueError('Saved B1 signed capacity branch changed')
            expected_side='segment_start_right' if u==0. else 'segment_end_left' if u==1. else 'interior'
            if state['side']!=expected_side:raise ValueError('Saved B1 interaction side changed')
            values=[_value(c,u) for c in coeffs]
            for field,value in zip(('N_tension_positive_N','Mstrong_Nmm','Mweak_Nmm'),values):
                if not _close(state[field],value):raise ValueError('Saved B1 interaction witness differs from its field')
            # Endpoints and every quadratic extremum establish each sign over
            # the entire interval, so an omitted sign-changing root cannot hide.
            if any(sign*value < -(1e-7+2e-10*sum(abs(v) for v in coeff))
                   for coeff,sign,value in zip(coeffs,signs,values)):
                raise ValueError('Saved B1 interval crosses an unrepresented moment sign change')
            index=None if missing else sum(abs(v)/caps[k]['value'] for v,k in zip(values,keys) if k is not None)
            if (index is None and state['numeric_index'] is not None) or (index is not None and not _close(state['numeric_index'],index,1e-12)):
                raise ValueError('Saved B1 interaction index differs from its saved witness')
    maximum=None if missing else max(states,key=lambda s:s['numeric_index'])
    if row['maximum']!=maximum:raise ValueError('Saved B1 interaction maximum differs from its complete witnesses')


def _validate_saved_interaction(out,nbr):
    """Validate the saved N/M inventory and witnesses without regeneration."""
    local=out['local_NM_reference']
    if (not isinstance(local,dict) or local.get('method')!='uniform_axial_envelopes_with_local_B1'
        or local.get('source_NBR_capacities_sha256')!=fingerprint(nbr['capacities'])
        or local.get('physical_concomitant_state') is not False or local.get('whole_member_approved') is not False):
        raise ValueError('Invalid or scope-expanded saved B1 N/M reference')
    original={(r['combination_id'],r['segment_id']):r for r in nbr['rows'] if r['girt']=='middle'}
    expected={};blocked=[]
    for case in out['cases']:
        cid=case['combination_id']
        if not case['local_formula_reference_applicable']:
            blocked.append(cid);continue
        nc=case['N_compression_max_N'];nt=max(0.,case['N_max_tension_positive_N'])
        branches=([('compression',-nc)] if nc else [])+([('tension',nt)] if nt else [])
        if not branches:branches=[('zero',0.)]
        for segment in case['amplified_local_reference_moment_polynomials']:
            for branch,n in branches:
                expected[(cid,segment['segment_id'],branch)]=(case,segment,n)
    rows=local['rows']
    if not isinstance(rows,list):raise ValueError('Missing saved B1 N/M rows')
    identities=[(r['combination_id'],r['segment_id'],r['axial_branch']) for r in rows]
    if identities!=list(expected):raise ValueError('Saved B1 N/M branch inventory is incomplete or changed')
    for row,identity in zip(rows,identities):
        case,segment,n=expected[identity]
        _validate_interaction_row(row,case,segment,original[identity[:2]],identity[2],n)
    ready=[r for r in rows if r['maximum'] is not None]
    winner=max(ready,key=lambda r:r['maximum']['numeric_index']) if ready else None
    maximum=None if winner is None else dict(combination_id=winner['combination_id'],
        segment_id=winner['segment_id'],axial_branch=winner['axial_branch'],state=winner['maximum'])
    if (local['blocked_combinations']!=blocked
        or local['complete'] is not (bool(rows) and not blocked and len(ready)==len(rows))
        or local['maximum_available']!=maximum
        or local['missing_capacity_keys']!=sorted({k for r in rows for k in r['missing_capacity_keys']})
        or local['member_issues']!=sorted({k for r in rows for k in r['member_issues']})):
        raise ValueError('Saved B1 N/M summary differs from its rows')


def presentation_rows(nbr_component,demand=None):
    out=saved(nbr_component,demand=demand)
    if out is None:return []
    return _presentation_rows(out)


def _presentation_rows(out):
    return [dict(Combinação=r['combination_id'],Travessa='Central',
        Nc_máx_kN=r['N_compression_max_N']/1000.,N_uniforme=r['uniform_axial_force'],
        B1_forte=r['planes']['strong']['B1_reference'],B1_fraco=r['planes']['weak']['B1_reference'],
        Escopo='Referência local com N máximo' if r['local_formula_reference_applicable'] else 'Estimativa / inconclusivo',
        Estabilidade_da_rede='Inconclusiva') for r in out['cases']]


def render_saved(st,nbr_component,demand=None):
    out=saved(nbr_component,demand=demand)
    if out is None:return
    st.subheader('Segunda ordem local da central (B1)')
    st.caption('Vão integral, Euler flexional em cada plano e Cm=1. K=1 é relacionado aos vínculos extremos declarados, não à posição dos tirantes.')
    st.dataframe(_presentation_rows(out),hide_index=True)
    if out['schema']==LEGACY_SCHEMA:
        st.info('Registro histórico B1 v1: N variável permanece estimativa sem aplicação aos momentos. Não foi recalculado nem convertido para a referência N/M atual.')
    else:
        st.info('N variável é tratado por barra equivalente com compressão máxima da mesma combinação. A referência N/M abaixo usa envelopes axiais de compressão e tração separados; não representa um estado físico resolvido.')
    if demand is None:st.caption('Leitura diagnóstica do registro salvo: a demanda integral não foi fornecida para conferir todos os coeficientes dos momentos.')
    ref=out.get('local_NM_reference')
    if ref is not None and ref['maximum_available'] is not None:
        st.write('Índice N/M local com B1: '+format(ref['maximum_available']['state']['numeric_index'],'.6f')+(' (aritmética completa; limites de barra separados)' if ref['complete'] else ' (parcial; ver pendências)'))
    st.caption('Os esforços e índices resistentes originais foram preservados. A influência dos deslocamentos na redistribuição da rede permanece inconclusiva; B1 próximo de 1 não é aprovação global.')
    with st.expander('Memória da amplificação local B1 da central'):
        st.json(out)


def append_report(doc,nbr_component,demand=None):
    out=saved(nbr_component,demand=demand)
    if out is None:return
    from .three_girt_report import _table
    doc.add_heading('Segunda ordem local da central: referência B1',2)
    doc.add_paragraph('B1 = 1/(1 − Nc/Ne), com Cm=1 e Ne flexional de cada plano no vão integral. K=1 é deduzido dos vínculos biapoiados declarados na referência isolada; não há crédito de contenção dos tirantes ou da telha.')
    rows=[]
    for r in out['cases']:
        b=lambda name:'Inconclusivo' if r['planes'][name]['B1_reference'] is None else f"{r['planes'][name]['B1_reference']:.6f}"
        rows.append([r['combination_id'],f"{r['N_compression_max_N']/1000:.6f}",
            'Sim' if r['uniform_axial_force'] else 'Não',b('strong'),b('weak'),
            'Referência local' if r['local_formula_reference_applicable'] else 'Estimativa / inconclusivo'])
    _table(doc,['Combinação','Nc máx [kN]','N uniforme','B1 forte','B1 fraco','Escopo'],rows,[1.2,1.,.7,.9,.9,1.6])
    if out['schema']==LEGACY_SCHEMA:
        doc.add_paragraph('Registro histórico B1 v1: N variável permanece estimativa sem aplicação aos momentos. Não foi recalculado nem convertido para a referência N/M atual.')
    else:
        doc.add_paragraph('N variável: aproximação por compressão uniforme equivalente máxima na combinação, Cm=1 e vão integral. A referência N/M usa envelopes axiais de compressão e tração separados, preservando os dois momentos concomitantes entre si. N>=Ne ou vínculos incompatíveis bloqueiam o fator. Base auxiliar: AS4100:2020 8.2/4.4.2.2 e Hancock, capítulo 8, 8.2; não se declara aprovação literal da rede pela norma australiana.')
    if demand is None:doc.add_paragraph('Leitura diagnóstica do registro salvo: demanda integral indisponível para conferir todos os coeficientes dos momentos.')
    ref=out.get('local_NM_reference')
    if ref is not None and ref['maximum_available'] is not None:
        doc.add_paragraph('Índice N/M local com B1: '+format(ref['maximum_available']['state']['numeric_index'],'.6f')+(' (aritmética completa; limites de barra separados).' if ref['complete'] else ' (parcial; há pendências).'))
    doc.add_paragraph('A rede permanece inconclusiva. Os esforços, reações e índices resistentes originais estão preservados; não há multiplicação automática de N, B, T ou V. B1<=1,10 não foi usado como dispensa normativa. '+SOURCE['clause']+'.')
