"""Signed Bernstein superset restricted by exact source equilibrium; N=0."""
import itertools
import numpy as np
from .torsion_vlasov.intervals import Interval as I, stack, power_to_bernstein, elevate_bernstein
from .torsion_vlasov.yield_envelope import _member_polynomials

def _field_controls(demand, certificate):
    """Yield signed-operator supersets; no fictitious control is a witness."""
    pol, identities = _member_polynomials(demand)
    section = demand['section']; p = section['properties']; th = section['thickness_mm']
    nodes = I(section['nodes_xy_mm']); xy = nodes - I(p['centroid_xy_mm'])
    delta = nodes[1:] - nodes[:-1]
    length = (delta[:, 0].square() + delta[:, 1].square()).sqrt()
    normal = stack([-delta[:, 1] / length, delta[:, 0] / length], axis=-1)
    omega = I(section['omega_nodes_mm2'])
    w = stack([omega[:-1], omega[1:] - omega[:-1]], axis=-1)
    static = I(section['segment_static_coefficients'])
    def outer(a, b):
        return a[:, None, :, None] * b[None, :, None, :]
    flow = -(outer(pol['Vx'] / p['Iy_weak_mm4'], static[:, 0, :])
        + outer(pol['Vy'] / p['Ix_strong_mm4'], static[:, 1, :])
        + outer(pol['Tw'] / p['Cw_mm6'], static[:, 2, :])) / th
    constant = I(np.column_stack([np.ones(len(xy.lo) - 1), np.zeros((len(xy.lo) - 1, 2))]))
    sv = outer(pol['Tsv'] * th / p['J_mm4'], constant)
    from . import isolated_en_ue_catalog_application as arithmetic
    from . import en_signed_partial_interaction as core
    required={axis:set() for axis in ('Mx','My')}
    for piece in arithmetic._source_pieces(demand):
        fields=arithmetic._fields(demand,piece)
        for axis in required:
            for pair in core._bernstein([(v,v) for v in fields[axis]]):
                required[axis].update(core._required(axis,pair))
    for mx,my in itertools.product(sorted(required['Mx']) or [None],sorted(required['My']) or [None]):
        selected=dict(Mx=mx,My=my)
        coefficients = {}
        for action, key in selected.items():
            if key is None:
                coefficients[action]=I([0.,0.,0.]);continue
            component = certificate['components'][key]
            if not component['eligible']:
                raise ValueError('EN signed effective section unavailable: ' + key + '; ' + str(component.get('blocking_reasons',[])))
            coefficients[action] = I(component['sigma_coefficients_c0_cx_cy'])
        for face in (-1, 1):
            position = xy[:-1] + normal * (face * th / 2)
            sigma = outer(pol['B'] / p['Cw_mm6'], w)
            for action, coefficient in coefficients.items():
                section_power = stack([coefficient[0] + coefficient[1] * position[:, 0]
                    + coefficient[2] * position[:, 1],
                    coefficient[1] * delta[:, 0] + coefficient[2] * delta[:, 1]], axis=-1)
                sigma = sigma + outer(pol[action], section_power)
            # Face sign is geometric: n=(-dy,dx)/length, tauSV=-face*Tsv*t/J.
            tau = flow - face * sv
            sigma = elevate_bernstein(power_to_bernstein(sigma), -1, 2)
            tau = elevate_bernstein(power_to_bernstein(tau), -2, 3)
            yield selected, face, sigma, tau, identities
