"""Restricted, explicit §9.6.2 connection inputs, not connection design.

One common reference detail only. No connection inventory and no automatic
changes to physical restraint, demand, bending or EN intact-section models.
"""
import copy
import math
from . import backend as a

SCHEMA='three_girt_tension_simple_detail_v1'
WELD_U_MODE='lower_flange_longitudinal_u_hypothesis'
MODES=('web_bolt_single_transverse_row','lower_flange_weld',WELD_U_MODE)


def blank_detail(mode):
    if mode not in MODES:raise ValueError('Unsupported simple tension detail')
    geometry=(dict(count=None,diameter_mm=None,clearance_mm=2.,pitch_mm=None,
                   single_row_in_flat_web_confirmed=False,no_other_losses_confirmed=False)
              if mode==MODES[0] else
              dict(arrangement='undefined',An_mm2=None,Ct=None,length_mm=None,
                   eccentricity_mm=None,ct_origin=''))
    if mode==WELD_U_MODE:
        geometry=dict(length_mm=None,eccentricity_mm=None,
            two_equal_continuous_longitudinal_welds_confirmed=False,
            no_holes_or_losses_confirmed=False,extrapolation_accepted=False)
    return dict(schema=SCHEMA,mode=mode,geometry=geometry,origin='',
                reference_scope_confirmed=False,outside_mode='manual',
                outside_unperforated_confirmed=False)


def _shape(value,expected,name):
    if not isinstance(value,dict) or set(value)!=set(expected):
        raise ValueError(name+': explicit fields required')


def _boolean(value,name):
    if not isinstance(value,bool):raise ValueError(name+': boolean required')
    return value


def _text(value,name):
    if not isinstance(value,str):raise ValueError(name+': text required')
    return value.strip()


def _optional(value,name):
    return None if value is None else a._number(value,name,positive=True)


def longitudinal_u_weld_hypothesis(*,A_mm2,length_mm,eccentricity_mm):
    """Explicit extrapolation of the welded-U expression to flange-welded Ue.

    L is EACH of the two equal, continuous longitudinal weld lengths, never
    their sum. x is perpendicular from the complete Ue centroid (including
    lips and bends) to the actual connection plane, not a web eccentricity.
    The lower limit rejects the arrangement; it does not increase Ct to .5.
    """
    A=a._number(A_mm2,'A',positive=True)
    L=a._number(length_mm,'each longitudinal weld length',positive=True)
    x=a._number(eccentricity_mm,'centroid to connection plane',nonnegative=True)
    raw=1.-.36*x/L
    if not math.isfinite(raw):raise ValueError('Weld x/L exceeds finite arithmetic domain')
    admissible=raw>=.5
    return dict(An_mm2=A,Ct=min(raw,.9) if admissible else None,raw_Ct=raw,
        Ct_formula='min(1-0.36*x/L,0.9); raw Ct<0.5 is inadmissible, never clamped upward',
        An_formula='An=A; no holes, notches or other section losses',
        Ct_upper_limit=.9,Ct_lower_admissibility_limit=.5,Ct_admissible=admissible,
        weld_arrangement='two_equal_continuous_longitudinal',weld_count=2,
        length_mm=L,length_definition='longitudinal length of each weld, not the sum',
        eccentricity_mm=x,eccentricity_definition='perpendicular distance from full Ue centroid to actual connection plane',
        extrapolated_hypothesis=True,normative_applicability_demonstrated=False,
        ct_origin='Explicit design hypothesis: longitudinal welded-U Ct applied to flange-welded Ue',
        clause='NBR14762:2010 9.6.2 welded-U expression; extrapolated hypothesis for Ue connected only by one flange, not an explicit normative rule for this Ue detail',
        connection_strength_verified=False,applied_force_eccentricity_removed=False)


def web_bolt_row(*,A_mm2,t_mm,web_flat_mm,count,diameter_mm,pitch_mm,clearance_mm=2.):
    """Single transverse row, uniform thickness, circular holes only.

    Fig.4b explicitly includes Ue. A/t is the full developed width, not just
    the web depth. Edge sums include flanges, bends and lips. Geometry checks
    below are necessary, not a complete fastening/edge-detail verification.
    """
    A=a._number(A_mm2,'A',positive=True);t=a._number(t_mm,'t',positive=True)
    web=a._number(web_flat_mm,'flat web',positive=True)
    if t>4.75:raise ValueError('Automatic hole-detail geometry limited to profile t<=4.75 mm; use an audited manual detail for thicker profiles')
    if isinstance(count,bool) or not isinstance(count,int) or count<1:
        raise ValueError('Bolt count must be a positive integer')
    d=a._number(diameter_mm,'bolt diameter',positive=True)
    clearance=a._number(clearance_mm,'hole clearance',positive=True)
    if clearance!=2.:raise ValueError('This detail uses the explicitly selected 2 mm clearance only')
    if d<12.5:raise ValueError('d+2 exceeds Table15 enlarged-hole maximum for d<12.5 mm; use an audited manual detail')
    df=d+clearance;B=A/t
    if df>web:raise ValueError('Circular hole does not fit within the flat web')
    if count==1:
        if pitch_mm is not None:raise ValueError('Single bolt must not have a transverse pitch')
        p=None;span=0.;g=B;edges=B
    else:
        p=a._number(pitch_mm,'vertical pitch',positive=True)
        # NBR §10.3.3.1: clear hole-to-hole distance >= 2d.
        if p<df+2*d-1e-10:raise ValueError('Vertical pitch fails the minimum clear hole-to-hole distance 2d')
        span=(count-1)*p
        if span+df>web+1e-10:raise ValueError('Bolt row cannot fit wholly within the flat web')
        edges=B-span
        if edges<=0:raise ValueError('Invalid equivalent developed edge sum')
        g=max(p,edges)
    An=.9*(A-count*df*t)
    if An<=0:raise ValueError('Net area must remain positive')
    Ct=min(2.5*d/g,1.)
    return dict(An_mm2=An,Ct=Ct,A_mm2=A,t_mm=t,web_flat_mm=web,
                bolt_count=count,bolt_diameter_mm=d,hole_diameter_mm=df,
                clearance_mm=clearance,hole_classification='circular_enlarged_actual_d_plus_2_not_standard',
                developed_width_mm=B,vertical_pitch_mm=p,extreme_bolt_span_mm=span,
                developed_edge_sum_mm=edges,g_effective_mm=g,net_area_factor=.9,
                Ct_formula='min(2.5*d/max(p,A/t-(n-1)*p),1); n=1: g=A/t',
                An_formula='0.9*(A-n*(d+2)*t)',
                clause='NBR14762:2010 9.6.2, Fig.4b; Table15 and 10.3.3.1 geometry limits',
                longitudinal_bolt_positions=1,profile_thickness_domain_mm='t<=4.75',geometry_fully_verified=False,
                connection_strength_verified=False,applied_force_eccentricity_removed=False)


def resolve(detail,manual,*,A_mm2,t_mm,h_mm,ri_mm):
    """Resolve a reviewed common detail into existing backend inputs.

    Missing confirmations never release Nt. The manual input route remains
    unchanged when this optional detail is absent.
    """
    mode=detail.get('mode') if isinstance(detail,dict) else None
    template=blank_detail(mode);_shape(detail,template,'simple detail')
    if detail['schema']!=SCHEMA:raise ValueError('Unsupported tension detail schema')
    _shape(detail['geometry'],template['geometry'],'detail geometry')
    if manual['An_mm2'] is not None or manual['Ct'] is not None:
        raise ValueError('Do not mix the simple connection detail with manual An/Ct')
    A=a._number(A_mm2,'A',positive=True);t=a._number(t_mm,'t',positive=True)
    h=a._number(h_mm,'h',positive=True);ri=a._number(ri_mm,'ri',nonnegative=True)
    missing=[];origin=_text(detail['origin'],'detail origin')
    if not origin:missing.append('origem do detalhe da ligação')
    if not _boolean(detail['reference_scope_confirmed'],'reference scope'):
        missing.append('aplicabilidade deste detalhe à referência comum das travessas')
    outside=detail['outside_mode'];confirmed=_boolean(detail['outside_unperforated_confirmed'],'outside declaration')
    if outside not in ('manual','confirmed_unperforated'):raise ValueError('Unknown outside-section mode')
    inputs=copy.deepcopy(manual);inputs['An_mm2']=None;inputs['Ct']=None
    outside_origin=manual.get('outside_area_origin')
    if outside=='confirmed_unperforated':
        if manual['An0_mm2'] is not None:raise ValueError('Do not mix derived An0 with manual An0')
        if confirmed and isinstance(outside_origin,str) and outside_origin.strip():inputs['An0_mm2']=A
        else:
            inputs['An0_mm2']=None;missing.append('ausência de furos/recortes externos confirmada com origem')
    elif confirmed:raise ValueError('Unperforated declaration conflicts with manual An0 mode')
    if inputs['An0_mm2'] is not None and not (isinstance(outside_origin,str) and outside_origin.strip()):
        inputs['An0_mm2']=None;missing.append('origem da área líquida fora das ligações')
    g=detail['geometry'];derived=None
    if mode==MODES[0]:
        for k in ('single_row_in_flat_web_confirmed','no_other_losses_confirmed'):
            if not _boolean(g[k],k):missing.append(k)
        if g['count'] is None or g['diameter_mm'] is None or (g['count']!=1 and g['pitch_mm'] is None):
            missing.append('quantidade, diâmetro e passo vertical dos parafusos')
        else:
            derived=web_bolt_row(A_mm2=A,t_mm=t,web_flat_mm=h-2*(ri+t),count=g['count'],
                diameter_mm=g['diameter_mm'],pitch_mm=g['pitch_mm'],clearance_mm=g['clearance_mm'])
    elif mode==WELD_U_MODE:
        confirmations={
            'two_equal_continuous_longitudinal_welds_confirmed':'dois cordões longitudinais contínuos de igual comprimento na mesma mesa, sem cordões transversais',
            'no_holes_or_losses_confirmed':'ausência de furos, recortes e outras perdas na seção da ligação',
            'extrapolation_accepted':'adoção explícita da hipótese extrapolada de Ct de U para Ue ligado pela mesa'}
        for key,label in confirmations.items():
            if not _boolean(g[key],key):missing.append(label)
        length=_optional(g['length_mm'],'each longitudinal weld length')
        x=None if g['eccentricity_mm'] is None else a._number(g['eccentricity_mm'],'centroid to connection plane',nonnegative=True)
        if length is None or x is None:missing.append('L de cada cordão e distância perpendicular x do centróide completo do Ue ao plano da ligação')
        else:
            derived=longitudinal_u_weld_hypothesis(A_mm2=A,length_mm=length,eccentricity_mm=x)
            if not derived['Ct_admissible']:
                missing.append('Ct calculado inferior a 0,5: detalhe inadmissível nesta hipótese; não elevado artificialmente a 0,5')
    else:
        arr=g['arrangement']
        if arr not in ('undefined','transverse_only','longitudinal','mixed'):raise ValueError('Unknown weld arrangement')
        area=_optional(g['An_mm2'],'weld An');ct=_optional(g['Ct'],'weld Ct')
        length=_optional(g['length_mm'],'weld length')
        x=None if g['eccentricity_mm'] is None else a._number(g['eccentricity_mm'],'weld eccentricity',nonnegative=True)
        ct_source=_text(g['ct_origin'],'weld Ct source')
        if area is not None and area>A:raise ValueError('Weld An must not exceed A')
        if ct is not None and ct>1:raise ValueError('Weld Ct must not exceed 1')
        if arr=='undefined':missing.append('orientação dos cordões da mesa inferior')
        elif arr=='transverse_only':
            if ct is not None:raise ValueError('Transverse-only weld derives Ct=1; do not mix manual Ct')
            ct=1.
            if area is None:missing.append('área bruta somente das partes efetivamente conectadas')
        else:
            if area is None or ct is None:missing.append('An e Ct auditados para solda apenas na mesa inferior')
            if not ct_source:missing.append('método auditado de Ct para a mesa inferior; a hipótese extrapolada tem opção separada')
            if length is None or x is None:missing.append('comprimento longitudinal e excentricidade reais da solda')
        if area is not None and ct is not None and arr!='undefined':
            derived=dict(An_mm2=area,Ct=ct,weld_arrangement=arr,length_mm=length,
                eccentricity_mm=x,ct_origin=ct_source,
                clause='NBR14762:2010 9.6.2, transverse-only connected parts' if arr=='transverse_only' else 'User-audited method for lower-flange-only weld; no automatic Fig.4d extension',
                connection_strength_verified=False,applied_force_eccentricity_removed=False)
    if derived is not None and not missing:
        inputs.update(An_mm2=derived['An_mm2'],Ct=derived['Ct'],connection_origin=origin+'; '+derived['clause'])
    inputs['origin']='Detalhe simples declarado para a referência comum; resistência da ligação não verificada.'
    return dict(inputs=inputs,missing=missing,derived=derived,input=copy.deepcopy(detail),
                scope='Axial section resistance only; no connection inventory, connection design or physical restraint modification',
                connection_strength_verified=False,holes_transferred_to_bending_or_EN=False)


def capacity(detail,manual,*,A_mm2,t_mm,h_mm,ri_mm,fy_MPa,fu_MPa):
    r=resolve(detail,manual,A_mm2=A_mm2,t_mm=t_mm,h_mm=h_mm,ri_mm=ri_mm)
    out=a.tension_capacity(Ag_mm2=A_mm2,fy_MPa=fy_MPa,fu_MPa=fu_MPa,**r['inputs'])
    out['connection_detail']=r
    if r['missing']:
        out['missing'].extend(r['missing']);out['Nt_Rd_N']=None;out['status']='partial'
    return out
