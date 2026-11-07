"""Declared resistance lengths; never supports or a replacement of physical L."""
import copy
import math

FIELD = 'resistance_effective_lengths'
SCHEMA = 'resistance_effective_lengths_v1'
SOURCE = 'NBR14762:2010 9.7.2.1, 9.8.2.2 and Annex E.2'


def positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(name + ': positive finite value required')
    return float(value)


def existing_declaration(data):
    """Read already declared fields on new calculation; no migration or support.

    First policy: one physical full-span segment and common effective Ly.
    Flange-specific fields take precedence over the legacy common Ly field.
    """
    segments = data.get('segments', [])
    if not isinstance(segments, list) or len(segments) != 1:
        return None
    segment = segments[0]
    if not isinstance(segment, dict) or segment.get('start_mm') != 0 or segment.get('end_mm') != data['L_mm']:
        return None
    origin = segment.get('restraint_provenance')
    if not isinstance(origin, str) or not origin.strip():
        return None
    if any(k in segment for k in ('Ly_top_effective_mm', 'Ly_bottom_effective_mm')):
        ly = segment.get('Ly_top_effective_mm')
        if ly is None or ly != segment.get('Ly_bottom_effective_mm'):
            return None
    else:
        ly = segment.get('Ly_effective_mm')
    lz = segment.get('Lz_effective_mm')
    weak = data.get('weak_catalog', {})
    lx = weak.get('Lx_mm', data['L_mm']) if isinstance(weak, dict) else data['L_mm']
    if any(v is None for v in (lx, ly, lz)):
        return None
    return dict(schema=SCHEMA, Lx_mm=lx, Ly_mm=ly, Lz_mm=lz, origin=origin)


def configuration(data):
    length = positive(data['L_mm'], 'physical span')
    cfg = data[FIELD] if FIELD in data else existing_declaration(data)
    if cfg is None and FIELD not in data:
        return None
    keys = {'schema', 'Lx_mm', 'Ly_mm', 'Lz_mm', 'origin'}
    if not isinstance(cfg, dict) or set(cfg) != keys or cfg.get('schema') != SCHEMA:
        raise ValueError('Unsupported resistance-only effective-length declaration')
    if not isinstance(cfg['origin'], str) or not cfg['origin'].strip() or len(cfg['origin']) > 2000:
        raise ValueError('Declare the calculation hypothesis/source of the effective lengths')
    return dict(schema=SCHEMA, physical_span_mm=length,
                **{k: positive(cfg[k], k) for k in ('Lx_mm', 'Ly_mm', 'Lz_mm')},
                origin=cfg['origin'], source=SOURCE,
                scope='Resistance lengths only; no supports or changes to physical demand/deflection/Vlasov domain',
                physical_restraint_verified=False)


def declare(data, *, Lx_mm, Ly_mm, Lz_mm, origin):
    out = copy.deepcopy(data)
    out[FIELD] = dict(schema=SCHEMA, Lx_mm=Lx_mm, Ly_mm=Ly_mm, Lz_mm=Lz_mm, origin=origin)
    configuration(out)
    return out


def annex_e_forces(*, E_MPa, G_MPa, Ix_mm4, J_mm4, Cw_mm6, r0_squared_mm2, Lx_mm, Lz_mm):
    """Family-independent arithmetic; caller retains section/sign qualification."""
    E, G, Ix, J, Cw, r2, lx, lz = [positive(v, k) for k, v in (
        ('E', E_MPa), ('G', G_MPa), ('Ix', Ix_mm4), ('J', J_mm4),
        ('Cw', Cw_mm6), ('r0 squared', r0_squared_mm2), ('Lx', Lx_mm), ('Lz', Lz_mm))]
    nx = E*Ix*(math.pi/lx)**2
    nz = (G*J+E*Cw*(math.pi/lz)**2)/r2
    return dict(Nex_N=positive(nx, 'Nex'), Nez_N=positive(nz, 'Nez'))
