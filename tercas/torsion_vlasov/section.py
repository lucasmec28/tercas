"""Thin-wall section demand, one consistent polygon and sectorial convention.

Cross-section coordinates x,y; beam coordinate s, (x,y,s) right handed.
Positive N is tension, Mx=int(y*sigma)dA, My=-int(x*sigma)dA.
omega=int(x dy-y dx), normalized orthogonal to 1,x,y; uw=-omega*phi'.
Hence B=-ECw*phi'', sigma_w=B*omega/Cw, Tw=B'.
The result is a LINE-MIDSURFACE stress, not an exterior-fibre resistance.
"""
import copy
import hashlib
import json
import math
import numbers
from pathlib import Path

import numpy as np
from numpy.polynomial import polynomial as poly
from .bounded_polynomial import real_roots_open_unit_interval


def finite(v, name, positive=False):
    if isinstance(v, (bool, np.bool_)) or not isinstance(v, numbers.Real):
        raise ValueError(name + ': real numeric value required')
    f = float(v)
    if not math.isfinite(f) or (positive and f <= 0):
        raise ValueError(name + ': finite value outside domain')
    return f


def product(f, g, weights):
    return math.fsum((weights*(2*f[:-1]*g[:-1]+f[:-1]*g[1:]+
                              f[1:]*g[:-1]+2*f[1:]*g[1:])/6).tolist())


def from_frozen_profile(profile):
    """Recompute from source nodes; reject scalar properties from other models.

This consumer does not authorize a physical geometry or inherit an acceptance
of nonzero-torsion resistance from the pure-bending critical-value register.
"""
    p = copy.deepcopy(profile)
    if p.get('schema') != 'Ue100_family_geometry_preparation_v1':
        raise ValueError('Frozen Ue100 family geometry schema required')
    nodes = np.asarray(p['nodes_xy_mm'], float)
    t = finite(p['thickness_mm'], 'thickness', True)
    if nodes.shape != (209, 2) or not np.isfinite(nodes).all():
        raise ValueError('Exact 209-node R01 geometry required')
    digest = hashlib.sha256(json.dumps(p['nodes_xy_mm'], sort_keys=True,
        separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    if digest != p['geometry_identity']['nodes_canonical_sha256']:
        raise ValueError('Frozen geometry identity mismatch')
    result = _construct(nodes, t, p['profile_id'], digest)
    props = result['properties']
    for k in ('A_mm2','Ix_strong_mm4','Iy_weak_mm4','J_mm4','Cw_mm6'):
        if not math.isclose(props[k], p['own_properties'][k], rel_tol=2e-12, abs_tol=1e-9):
            raise ValueError('Section property not from the frozen contour: '+k)
    for k in ('centroid_xy_mm','shear_center_xy_mm'):
        if not np.allclose(props[k],p['own_properties'][k],rtol=2e-12,atol=1e-10):
            raise ValueError('Section coordinate mismatch: '+k)
    return result


def _construct(nodes, t, profile_id, digest):
    """Exact line integrals for the supplied piecewise-straight thin wall."""
    length = np.linalg.norm(np.diff(nodes, axis=0), axis=1)
    if min(length) <= 0 or np.linalg.norm(nodes[-1]-nodes[0]) <= 0:
        raise ValueError('Simple non-closed positive-length contour required')
    area = length*t
    A = math.fsum(area.tolist())
    cg = np.array([math.fsum((area*(nodes[:-1,k]+nodes[1:,k])/2).tolist())/A for k in (0,1)])
    xy = nodes-cg; x,y = xy.T
    Ix, Iy, Ixy = product(y,y,area), product(x,x,area), product(x,y,area)
    raw = np.r_[0., np.cumsum(x[:-1]*y[1:]-y[:-1]*x[1:])]
    c = np.linalg.solve([[A,0.,0.],[0.,Iy,Ixy],[0.,Ixy,Ix]], -np.array([
        math.fsum((area*(raw[:-1]+raw[1:])/2).tolist()),
        product(raw,x,area), product(raw,y,area)]))
    omega = raw+c[0]+c[1]*x+c[2]*y
    Cw = product(omega,omega,area)
    sc = cg+[-c[2],c[1]]
    J = math.fsum(length.tolist())*t**3/3
    props = dict(A_mm2=A, Ix_strong_mm4=Ix, Iy_weak_mm4=Iy, Ixy_mm4=Ixy,
                 J_mm4=J, Cw_mm6=Cw, centroid_xy_mm=cg.tolist(), shear_center_xy_mm=sc.tolist())
    if abs(Ixy) > 1e-12*math.sqrt(Ix*Iy):
        raise ValueError('Current route requires principal symmetric section axes')
    # Exact quadratic primitives in the normalized segment coordinate u.
    cum = np.zeros(3); static = []
    for i,l in enumerate(length):
        vals = np.array([x[i:i+2],y[i:i+2],omega[i:i+2]])
        coeff = np.column_stack([cum,t*l*vals[:,0],t*l*(vals[:,1]-vals[:,0])/2])
        static.append(coeff.tolist());cum = coeff.sum(axis=1)
    result={'schema':'vlasov_section_v1','profile_id':profile_id,
            'nodes_sha256':digest,'properties':props,'nodes_xy_mm':nodes.tolist(),
            'thickness_mm':t,'omega_nodes_mm2':omega.tolist(),
            'segment_static_coefficients':static,'static_terminal':cum.tolist(),
            'physical_geometry_verified':False,
            'normalization':'integral omega*[1,x-CGx,y-CGy] t ds=0; uw=-omega phi_prime',
            'stress_scope':'gross elastic midsurface line stresses; no exterior-fibre or strength qualification'}
    result['content_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,
        separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    return result


def from_polyline(*, nodes_xy_mm, thickness_mm, profile_id, source):
    """Build a coherent open thin-wall section without a Ue100/node-count gate.

    x/y must be principal axes. All A/I/J/Cw/CG/SC/omega and shear primitives
    come from this contour, never scalar substitutions from a catalogue.
    The source is an explicit geometric idealization, not a product approval.
    """
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise ValueError('Explicit section profile identity required')
    if not isinstance(source, str) or not source.strip():
        raise ValueError('Explicit geometric source/idealization required')
    t = finite(thickness_mm, 'thickness', True)
    try:
        raw_objects = np.asarray(nodes_xy_mm, dtype=object)
        if any(isinstance(v, (bool, np.bool_)) for v in raw_objects.flat):
            raise ValueError('Boolean contour coordinates are not permitted')
        raw = np.asarray(nodes_xy_mm)
        if raw.dtype.kind not in 'fiu':
            raise ValueError('Real numeric contour coordinates required')
        nodes = np.asarray(raw, dtype=float)
    except (TypeError, OverflowError) as exc:
        raise ValueError('Real numeric contour coordinates required') from exc
    if nodes.ndim != 2 or nodes.shape[1] != 2 or not 3 <= len(nodes) <= 2049 or not np.isfinite(nodes).all():
        raise ValueError('Finite 3..2049-node contour required; node limit is operational')
    # A simple open chain is necessary for the free-edge shear-flow primitive.
    q = nodes - nodes[0]
    scale = float(np.max(np.abs(q)))
    if scale <= 0 or not math.isfinite(scale):
        raise ValueError('Non-degenerate open contour required')
    q = q / scale
    d = np.diff(q, axis=0)
    tol = 1e-12
    if np.min(np.linalg.norm(d, axis=1)) <= tol:
        raise ValueError('Zero-length or numerically unresolved contour segment')
    def cross(a, b):
        return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]
    for i, delta in enumerate(d):
        if i+1 < len(d) and abs(cross(delta, d[i+1])) <= tol and delta @ d[i+1] < 0:
            raise ValueError('Backtracking contour')
        if i+2 >= len(d):
            continue
        a, b = q[i:i+2]
        c, e = q[i+2:-1], q[i+3:]
        overlap = np.all(np.maximum(np.minimum(a, b), np.minimum(c, e)) <=
                         np.minimum(np.maximum(a, b), np.maximum(c, e)) + tol, axis=1)
        # Coordinate-scaled orientation tests avoid using a dimensional epsilon.
        intersects = ((cross(b-a, c-a)*cross(b-a, e-a) <= tol**2) &
                      (cross(e-c, a-c)*cross(e-c, b-c) <= tol**2))
        if np.any(overlap & intersects):
            raise ValueError('Closed or self-intersecting contour')
    canonical = nodes.tolist()
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True,
        separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    try:
        result = _construct(nodes, t, profile_id, digest)
    except np.linalg.LinAlgError as exc:
        raise ValueError('Non-degenerate principal-axis section required') from exc
    for key in ('A_mm2', 'Ix_strong_mm4', 'Iy_weak_mm4', 'J_mm4', 'Cw_mm6'):
        finite(result['properties'][key], key, True)
    result['geometry_source'] = source
    result.pop('content_sha256')
    result['content_sha256'] = hashlib.sha256(json.dumps(result, sort_keys=True,
        separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return result


def verify_section(section):
    d=copy.deepcopy(section);expected=d.pop('content_sha256',None)
    actual=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':'),
        ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    if d.get('schema')!='vlasov_section_v1' or actual!=expected:
        raise ValueError('Constructed coherent section changed; rebuild from the frozen profile')


def load_profile(path):
    return from_frozen_profile(json.loads(Path(path).read_text()))


def section_demands(section, *, N_N, Mx_Nmm, My_Nmm, Vx_N, Vy_N, Tsv_Nmm, Tw_Nmm, B_Nmm2):
    """Concomitant stress fields and exact segmentwise midsurface envelopes.

Shear flow follows q=-int(d sigma/ds)t dl from the free edge, Mx'=Vy,
My'=-Vx, B'=Tw. It independently recovers Vx,Vy,Tw about the shear centre.
Saint-Venant surface magnitudes are +/-Tsv*t/J, kept distinct from q/t.
No stress/yield ratio, effective-width reduction or normative verdict is made.
"""
    values = {k:finite(v,k) for k,v in locals().copy().items() if k != 'section'}
    verify_section(section)
    p=section['properties'];t=section['thickness_mm']
    nodes=np.asarray(section['nodes_xy_mm']);xy=nodes-np.asarray(p['centroid_xy_mm'])
    omega=np.asarray(section['omega_nodes_mm2']);A=p['A_mm2'];Ix=p['Ix_strong_mm4'];Iy=p['Iy_weak_mm4'];Cw=p['Cw_mm6']
    # Explicit principal-axis model. Through-thickness bending normal stress is not reconstructed.
    sigma=N_N/A+Mx_Nmm*xy[:,1]/Ix-My_Nmm*xy[:,0]/Iy+B_Nmm2*omega/Cw
    sv=Tsv_Nmm*t/p['J_mm4']
    segs=[]; max_tau=None;max_sigma=None; max_vm=None
    quadrature_x, quadrature_w=np.polynomial.legendre.leggauss(4)
    uq=(quadrature_x+1)/2;wq=quadrature_w/2
    rec=np.zeros(3);normal=np.zeros(4)
    for i,(a,b) in enumerate(zip(nodes[:-1],nodes[1:])):
        static=np.asarray(section['segment_static_coefficients'][i])
        qcoef=-(Vx_N*static[0]/Iy+Vy_N*static[1]/Ix+Tw_Nmm*static[2]/Cw)
        sigcoef=np.array([sigma[i],sigma[i+1]-sigma[i]])
        record={'segment':i,'sigma_midline_MPa_coeff':sigcoef.tolist(),
                'shear_flow_N_mm_coeff':qcoef.tolist(),'tau_mean_MPa_coeff':(qcoef/t).tolist(),
                'tau_SaintVenant_face_increment_MPa':sv}
        segs.append(record)
        for u in (0.,1.):
            z=float(poly.polyval(u,sigcoef))
            if max_sigma is None or abs(z)>abs(max_sigma['value_MPa']):
                max_sigma=dict(value_MPa=z,segment=i,u=u,xy_mm=(a+u*(b-a)).tolist())
        for face in (-1,1):
            tau=qcoef/t;tau=tau.copy();tau[0]+=face*sv
            roots=real_roots_open_unit_interval(poly.polyder(tau))
            for u in [0.,1.]+roots:
                z=float(poly.polyval(u,tau))
                if max_tau is None or abs(z)>abs(max_tau['value_MPa']):
                    max_tau=dict(value_MPa=z,segment=i,u=u,face=face,xy_mm=(a+u*(b-a)).tolist())
            eq=poly.polyadd(poly.polymul(sigcoef,sigcoef),3*poly.polymul(tau,tau))
            for u in [0.,1.]+real_roots_open_unit_interval(poly.polyder(eq)):
                z=math.sqrt(max(0.,float(poly.polyval(u,eq))))
                if max_vm is None or z>max_vm['value_MPa']:
                    max_vm=dict(value_MPa=z,segment=i,u=u,face=face,
                                sigma_midline_MPa=float(poly.polyval(u,sigcoef)),
                                tau_face_MPa=float(poly.polyval(u,tau)))
        dx,dy=b-a;length=float(np.linalg.norm(b-a));qv=poly.polyval(uq,qcoef)
        xq=a[0]+uq*dx;yq=a[1]+uq*dy
        rec += [float(wq@qv)*dx,float(wq@qv)*dy,
                float(wq@(qv*((xq-p['shear_center_xy_mm'][0])*dy-(yq-p['shear_center_xy_mm'][1])*dx)))]
        sigq=poly.polyval(uq,sigcoef);w=omega[i]+uq*(omega[i+1]-omega[i])
        normal += t*length*np.array([float(wq@sigq),float(wq@(sigq*(yq-p['centroid_xy_mm'][1]))),
            -float(wq@(sigq*(xq-p['centroid_xy_mm'][0]))),float(wq@(sigq*w))])
    return {'schema':'vlasov_section_demands_v1','profile_id':section['profile_id'],
        'actions':values,'segments':segs,'max_abs_sigma_midline':max_sigma,
        'max_abs_tau_face':max_tau,'max_equivalent_midline_plus_face_shear':max_vm,
        'recovered_normal_N_Mx_My_B':normal.tolist(),'recovered_flow_Vx_Vy_Tw':rec.tolist(),
        'scope':'Elastic demand only. Equivalent stress is a diagnostic, not a code check or a physical exterior-fibre bound.',
        'resistance_qualified':False,'whole_member_approved':False}
