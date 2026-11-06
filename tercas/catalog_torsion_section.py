"""Parametric gross torsion sections for exact nominal Pierin catalogue rows.

This is an explicit geometry preparation API. It neither replaces a project's
catalogue scalars nor qualifies its pure-bending/EN certificates. Pierin's
sharp-corner criticals are not claimed to originate from this rounded contour.
"""
import copy
import hashlib
import json
import math

import numpy as np

from .catalogs import catalog_entry, entries
from .weak_pierin import reference_for_index
from .torsion_vlasov.section import finite, from_polyline

SCHEMA = 'pierin_nominal_torsion_geometry_v1'
CONVENTION = ('External h/bf/lip/t and published inner radius ri; uniform thin wall '
              'on the rounded midsurface, quarter-circles approximated by chords. '
              'Origin is the intersection of the unrounded web/lower-flange '
              'midlines, x toward the open side and y upward. J=integral(t^3 ds)/3. '
              'Gross elastic geometry, not effective widths or an INSTAB reconstruction.')


def nominal_channel_nodes(*, h_mm, bf_mm, lip_mm, t_mm, ri_mm, arc_segments=32):
    """External-dimension U/Ue channel; exact straight parts, chord-faceted arcs."""
    h = finite(h_mm, 'h', True)
    b = finite(bf_mm, 'bf', True)
    lip = finite(lip_mm, 'lip')
    t = finite(t_mm, 't', True)
    ri = finite(ri_mm, 'ri')
    if lip < 0 or ri < 0:
        raise ValueError('lip and ri must be nonnegative')
    if isinstance(arc_segments, bool) or not isinstance(arc_segments, int) or not 2 <= arc_segments <= 256:
        raise ValueError('arc_segments must be integer 2..256; operational mesh scope')
    a, radius = h-t, ri+t/2
    width = b-t if lip else b-t/2
    end = lip-t/2
    if (a <= 2*radius or width <= (2*radius if lip else radius)
            or (lip and not radius < end < a/2)):
        raise ValueError('Rounded channel flats/lips overlap or have nonpositive length')
    points = []
    def line(x, y):
        points.append([float(x), float(y)])
    def arc(cx, cy, begin, finish):
        for angle in np.linspace(begin, finish, arc_segments+1)[1:]:
            line(cx+radius*math.cos(angle), cy+radius*math.sin(angle))
    if lip:
        line(width, end)
        line(width, radius)
        arc(width-radius, radius, 0., -math.pi/2)
    else:
        line(width, 0.)
    line(radius, 0.)
    arc(radius, radius, -math.pi/2, -math.pi)
    line(0., a-radius)
    arc(radius, a-radius, math.pi, math.pi/2)
    if lip:
        line(width-radius, a)
        arc(width-radius, a-radius, math.pi/2, 0.)
        line(width, a-end)
    else:
        line(width, a)
    return points


def available_indices():
    """207 nominal exact matches, no replacement by a neighboring thickness."""
    return [i for i in range(len(entries()))
            if reference_for_index(i)['status'] == 'tabulated_adopted_reference']


def prepare(index, *, arc_segments=32):
    """Create a self-consistent gross section, retaining catalogue differences.

    Only nominal rows present in Pierin's table are admitted in this extension.
    All section properties and omega are recomputed from ONE declared contour;
    rounded catalogue scalars are comparison data, never solver substitutions.
    """
    entry = catalog_entry(index)
    reference = reference_for_index(index)
    if reference['status'] != 'tabulated_adopted_reference':
        raise ValueError('No exact nominal Pierin row; interpolation/extrapolation disabled')
    d, published = entry['dimensions_mm'], entry['published_properties']
    nodes = nominal_channel_nodes(h_mm=d['h'], bf_mm=d['bf'], lip_mm=d['lip'],
                                 t_mm=d['t'], ri_mm=published['ri_mm'], arc_segments=arc_segments)
    identity = dict(catalog_id=entry['id'], dimensions_mm=d, inner_radius_mm=published['ri_mm'],
                    arc_segments=arc_segments, convention=CONVENTION)
    sha = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    profile_id = 'OWN_PIERIN_NOMINAL_' + entry['id'] + '_' + sha[:16]
    section = from_polyline(nodes_xy_mm=nodes, thickness_mm=d['t'], profile_id=profile_id,
                            source=CONVENTION + ' Nominal geometric source: ' + entry['source_url'])
    props = section['properties']
    compare = {}
    for name, original in (
        ('A_mm2', published['A_cm2']*100),
        ('Ix_strong_mm4', published['Ix_cm4']*10000),
        ('Iy_weak_mm4', published['Iy_cm4']*10000),
        ('J_mm4', published['J_mm4']), ('Cw_mm6', published['Cw_mm6'])):
        value = props[name]
        compare[name] = dict(computed=value, catalogue=original,
                             relative_difference=None if not original else value/original-1)
    raw = entry['raw_source_values']
    # xg is measured from the exterior web back; x0 is CG-to-SC distance.
    # Explicit comparison only: catalogue conventions are NOT solver inputs.
    compare['xg_from_outer_back_mm'] = dict(
        computed=props['centroid_xy_mm'][0]+d['t']/2,
        catalogue=raw.get('xg cm')*10 if raw.get('xg cm') is not None else None)
    compare['CG_to_SC_distance_mm'] = dict(
        computed=props['centroid_xy_mm'][0]-props['shear_center_xy_mm'][0],
        catalogue=raw.get('x0 cm')*10 if raw.get('x0 cm') is not None else None)
    return dict(schema=SCHEMA, section=section, nominal_identity=copy.deepcopy(identity),
                nominal_identity_sha256=sha, pierin_nominal_row_id=reference['id'],
                pierin_source_url=reference['url'], catalogue_comparison=compare,
                properties_used='gross coherent contour; no effective-section properties',
                catalogue_replaced=False, effective_properties_qualified=False,
                pierin_criticals_transferred=False, H4_flexural_denominators_qualified=False,
                physical_product_verified=False, whole_member_approved=False)
