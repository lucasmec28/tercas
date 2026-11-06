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
