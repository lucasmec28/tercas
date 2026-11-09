"""Exact synthetic diagnostics, NOT a resistance method or production provider.

The Table 7 values are source facts. Every proposed geometry/area placement
below is explicitly conditional and cannot qualify the production shear-lag gate.
Run with Python's standard library only; no solver, profile data, or network.
"""
from fractions import Fraction as F
import json
from pathlib import Path

SOURCE = {
    'title': 'ABNT NBR 14762:2010, 9.4 and Table 7',
    'sha256': 'c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407',
    'pdf_pages_one_based': [38, 39],
    'printed_pages': [32, 33],
    'visually_verified': True,
    'source_document_redistributed': False,
}
# Exact printed nodes, not an invented interpolation or extrapolation.
TABLE7 = ((6, F(55, 100)), (8, F(67, 100)), (10, F(73, 100)),
          (12, F(78, 100)), (14, F(82, 100)), (16, F(86, 100)),
          (18, F(89, 100)), (20, F(91, 100)), (25, F(96, 100)), (30, F(1)))


def printed_factor(ratio):
    """Diagnostic lookup at exact source nodes only; not a design API."""
    if not isinstance(ratio, F):
        raise TypeError('Use an explicit exact Fraction in this QA diagnostic.')
    for node, factor in TABLE7:
        if ratio == node:
            return factor
    raise ValueError('No printed node: interpolation/extrapolation not qualified here.')


def horizontal(width, y, t=F(2)):
    return (t*width, t*width*y, t*width*y*y)


def horizontal_interval(x0, x1, y, t=F(2)):
    # These are only A, Sy and Qy: x affects none of the three integrands.
    assert x1 > x0
    return horizontal(x1-x0, y, t)


def vertical(lo, hi, t=F(2)):
    return (t*(hi-lo), t*(hi*hi-lo*lo)/2, t*(hi**3-lo**3)/3)


def add(*rows):
    return tuple(sum((row[i] for row in rows), F(0)) for i in range(3))


def scale(row, factor):
    return tuple(v*factor for v in row)


def section(row):
    area, sy, qy = row
    assert area > 0
    cy = sy/area
    return {'area_mm2': area, 'centroid_y_mm': cy, 'Ix_mm4': qy-sy*sy/area}


def same_area_different_Ix():
    """Algebraic counterexamples, not proposed reduced Ue geometries.

    Sharp line model: web height 200, two horizontal flanges width 75,
    two vertical lips length 20, t=2. No rounded production contour is used.
    All distributions preserve the same area and y-centroid; Ix differs.
    """
    beta = printed_factor(F(20))
    b, d, y, t = F(75), F(20), F(100), F(2)
    loss = (1-beta)*(b+d)
    assert 0 < loss < min(b, d)
    web = vertical(-y, y, t)
    flanges = add(horizontal(b, y, t), horizontal(b, -y, t))
    lips = add(vertical(y-d, y, t), vertical(-y, -y+d, t))
    gross = add(web, flanges, lips)
    remove_flats = add(horizontal(loss, y, t), horizontal(loss, -y, t))
    remove_lip_tips = add(vertical(y-d, y-d+loss, t),
                          vertical(-y+d-loss, -y+d, t))
    distributions = {
        'remove_equal_area_from_horizontal_flats': section(add(gross, scale(remove_flats, F(-1)))),
        'remove_equal_area_from_vertical_lip_tips': section(add(gross, scale(remove_lip_tips, F(-1)))),
        'uniform_assembly_weight_counterexample_only': section(add(web, scale(add(flanges, lips), beta))),
    }
    assert len({r['area_mm2'] for r in distributions.values()}) == 1
    assert {r['centroid_y_mm'] for r in distributions.values()} == {F(0)}
    assert len({r['Ix_mm4'] for r in distributions.values()}) == 3
    return {
        'synthetic_sharp_line_model_not_production_contour': True,
        'distributions_are_not_engineering_methods': True,
        'ratio': F(20), 'factor_at_printed_node': beta,
        'removed_developed_length_per_flange_assembly_mm': loss,
        'gross': section(gross), 'distributions': distributions,
        'same_area_and_y_centroid_do_not_determine_Ix': True,
        'no_uniform_beta_method_is_adopted': True,
    }


def conditional_geometry():
    # All dimensional numbers are synthetic, not catalogue or project data.
    b, d, t, ri, L = F(75), F(20), F(2), F(3), F(2700)
    r = ri+t/2
    x_inner_web_face = t/2
    x_outer_lip_face = b-t/2
    x_flange_flat_start, x_flange_flat_end = r, b-t-r
    face_distance = x_outer_lip_face-x_inner_web_face
    flat_width = x_flange_flat_end-x_flange_flat_start
    assert face_distance == b-t and flat_width == b-2*(ri+t)
    proposals = {
        'existing_external_upper_bound': b+d,
        'unqualified_face_distance_plus_nominal_lip': face_distance+d,
        'unqualified_flat_width_plus_nominal_lip': flat_width+d,
    }
    rows = {name: {'width_mm': width, 'thirty_times_width_mm': 30*width,
                   'physical_span_over_assumed_width': L/width,
                   'span_ge_thirty_times_assumed_width': L >= 30*width}
            for name, width in proposals.items()}
    assert rows['unqualified_face_distance_plus_nominal_lip']['span_ge_thirty_times_assumed_width'] is False
    assert rows['unqualified_flat_width_plus_nominal_lip']['span_ge_thirty_times_assumed_width'] is True
    return {
        'synthetic_external_dimensions_mm': {'h': F(200), 'bf': b, 'lip': d, 't': t, 'ri': ri},
        'physical_span_mm': L,
        'coordinate_distances_exact_but_normative_mapping_not_qualified': True,
        'coordinates_mm': {'inner_web_face_x': x_inner_web_face, 'outer_lip_face_x': x_outer_lip_face,
                           'flange_flat_start_x': x_flange_flat_start, 'flange_flat_end_x': x_flange_flat_end},
        'conditional_widths': rows, 'none_of_the_proposals_is_an_exact_bf0_certificate': True,
    }


def run():
    # x-location within one horizontal flat is immaterial to scalar Ix.
    # Thus a universal 2D stress operator is NOT a necessary prerequisite.
    flat_loss_at_root = horizontal_interval(F(0), F(5), F(100))
    flat_loss_at_tip = horizontal_interval(F(70), F(75), F(100))
    assert flat_loss_at_root == flat_loss_at_tip
    # A Table 7 factor must not be multiplied onto a local width blindly.
    local, lag = F(70), F(80)
    assert min(local, lag) == 70 and local*lag/100 == 56
    # Inspect table nodes without pretending that non-nodal policy is sourced.
    assert len(TABLE7) == 10 and printed_factor(F(30)) == 1
    for unsupported in (F(5), F(7), F(31)):
        try:
            printed_factor(unsupported)
        except ValueError:
            pass
        else:
            raise AssertionError('Unsupported ratio silently accepted.')
    return {
        'schema': 'NBR_shear_lag_R22_contract_diagnostics_v1',
        'source': SOURCE,
        'printed_table_nodes': [{'L_over_bf0': F(x), 'factor': y} for x, y in TABLE7],
        'interpolation_or_extrapolation_used': False,
        'conditional_geometry': conditional_geometry(),
        'same_area_counterexample': same_area_different_Ix(),
        'horizontal_flat_x_placement_irrelevant_to_scalar_Ix': True,
        'blind_double_reduction_example_mm': {'local_width': local, 'shear_lag_width': lag,
                                             'minimum_width_cap': min(local, lag), 'blind_product': local*lag/100},
        'production_files_changed': False, 'production_eligibility_extended': False,
        'bf0_exact_mapping_qualified': False, 'reduced_resistance_qualified': False,
        'historical_replay_changed': False, 'whole_member_approved': False,
    }


def encode(value):
    if isinstance(value, F):
        return str(value)
    raise TypeError(type(value).__name__)


if __name__ == '__main__':
    out = Path(__file__).with_name('exact_diagnostics.json')
    out.write_text(json.dumps(run(), default=encode, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print('Exact synthetic diagnostics passed; no new resistance or production eligibility.')
