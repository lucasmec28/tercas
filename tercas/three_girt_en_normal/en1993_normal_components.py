"""Restricted EN 1993-1-3:2006 ULS normal-component section certificate.

The six pure actions use their respective ULS local/distortional checks. Only
sections proved INTEGRAL are returned. A failed proof never supplies gross
coefficients as an effective-section fallback. No NBR/AISI capacity is read.

R01 physical convention: tension positive; sigma=N/A+Mx*y/Ix-My*x/Iy.
Coordinates in returned coefficients are relative to the gross centroid.
This is the exact pinned polygon line-section model dA=t*ds, not an exterior
fibre/solid model, shear check, member stability check or complete EN design.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import numbers
from typing import Mapping

import numpy as np

SCHEMA = "en1993_1_3_2006_normal_component_sections_integral_v1"
MATERIAL = {"E_MPa": 210000.0, "nu": 0.3, "fyb_MPa": 250.0,
            "fya_MPa": 250.0, "gamma_M0": 1.0}
GEOMETRY_PINS = {
    1.2: '004c9cee5033877e4cf1c619627c968c02413aea26fe67a0a5422218ec003f7d',
    1.5: 'cd50bf66f299d1c072b5a45016cf2ffca777b390332d3386175c34d53c234931',
    2.0: '13c8bf700cce34d8fb2bc607e9ae06c305cc59cd7e0e67234a38fb0218704638',
    2.25: 'e30a0bd327deb1523b527a5737a9f14ac8f8fd189c884588c0339ef7c0b80e47',
    2.65: '243974742f83ef47937ec56c938718a37b3e037248c4016eddae0d42af062746',
    3.0: 'c3d1e69d48f6ad2980e6779eb2509e42e07a2b957ce71c158095fda6b71a4e00',
    3.35: '90bf516ec9761304d22aba266bdf9c2f06bf6f73bc6989b46194bbd5d218eab3',
}
PURE_ACTIONS = {
    "N_tension": (0, 1), "N_compression": (0, -1),
    "Mx_positive": (1, 1), "Mx_negative": (1, -1),
    "My_positive": (2, 1), "My_negative": (2, -1),
}
PANEL_NAMES = ["lower_lip", "lower_flange", "web", "upper_flange", "upper_lip"]


def _number(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise ValueError(name + ": finite real number required")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(name + ": finite real number required")
    return value


def _canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _line_integrals(nodes, t, intervals=None):
    """Exact polynomial integration of [1,x,y] outer product on line segments."""
    J = np.zeros((3, 3))
    if intervals is None:
        intervals = [(i, 0.0, 1.0) for i in range(len(nodes)-1)]
    for i, lo, hi in intervals:
        d = nodes[i+1]-nodes[i]
        a, b = nodes[i]+lo*d, nodes[i]+hi*d
        va, vb = np.r_[1.0, a], np.r_[1.0, b]
        area = t*float(np.linalg.norm(d))*(hi-lo)
        J += area*(2*np.outer(va, va)+np.outer(va, vb)
                   +np.outer(vb, va)+2*np.outer(vb, vb))/6.0
    return J


def _properties(J):
    A = float(J[0, 0]); cg = J[0, 1:]/A
    inertia = J[1:, 1:]-np.outer(J[1:, 0], J[0, 1:])/A
    return {"A_mm2": A, "Ix_strong_mm4": float(inertia[1, 1]),
            "Iy_weak_mm4": float(inertia[0, 0]), "Ixy_mm4": float(inertia[0, 1]),
            "centroid_xy_mm": cg.tolist()}


def _geometry(profile):
    if not isinstance(profile, Mapping) or profile.get("schema") != "Ue100_family_geometry_preparation_v1":
        raise ValueError("Exact frozen Ue100 family profile required")
    t = _number(profile.get("thickness_mm"), "thickness_mm")
    if t not in GEOMETRY_PINS:
        raise ValueError("Thickness outside the seven pinned Ue100x50x17 sections")
    nodes = np.asarray(profile["nodes_xy_mm"], dtype=float)
    if nodes.shape != (209, 2) or not np.isfinite(nodes).all():
        raise ValueError("Exact finite 209-node R01 contour required")
    actual_sha = _canonical_sha(profile["nodes_xy_mm"])
    identity = profile["geometry_identity"]
    if actual_sha != GEOMETRY_PINS[t] or identity["nodes_canonical_sha256"] != actual_sha:
        raise ValueError("Geometry does not match the independently pinned contour")
    expected_dims = dict(h=100.0, b=50.0, lip=17.0, t=t, ri=t)
    if profile.get("geometry_external_mm") != expected_dims:
        raise ValueError("Only Ue100x50x17 with ri=t is implemented")
    if identity.get("flat_segment_counts") != [12,24,72,24,12] or identity.get("arc_segment_counts") != [16]*4:
        raise ValueError("Pinned topology changed")
    if np.min(np.linalg.norm(np.diff(nodes, axis=0), axis=1)) <= 0:
        raise ValueError("Positive segment lengths required")
    props = _properties(_line_integrals(nodes, t))
    for key in ("A_mm2", "Ix_strong_mm4", "Iy_weak_mm4"):
        if not math.isclose(props[key], float(profile["own_properties"][key]), rel_tol=2e-12, abs_tol=1e-8):
            raise ValueError("Gross property not derived from the pinned contour: " + key)
    if not np.allclose(props["centroid_xy_mm"], profile["own_properties"]["centroid_xy_mm"], rtol=2e-12, atol=1e-10):
        raise ValueError("Gross centroid not derived from the pinned contour")
    if abs(props["Ixy_mm4"]) > 1e-12*math.sqrt(props["Ix_strong_mm4"]*props["Iy_weak_mm4"]):
        raise ValueError("Principal symmetric R01 axes required")
    # Splits at the actual polygon corner midpoints, EN 1993-1-3 Fig.5.1.
    bounds = [0, 20, 60, 148, 188, 208]
    groups = []
    for n in range(5):
        ids = list(range(bounds[n], bounds[n+1])); axis = 1 if n % 2 == 0 else 0
        values = nodes[bounds[n]:bounds[n+1]+1, axis]
        normal = float(np.median(nodes[ids, 1-axis]))
        groups.append({"panel": PANEL_NAMES[n], "ids": ids, "axis": axis,
            "lo": float(min(values)), "hi": float(max(values)),
            "b_mm": float(max(values)-min(values)), "normal_mm": normal})
    return nodes, t, props, groups, actual_sha


def _stress_ends(g, compression_coeff):
    result = []
    for val in (g["lo"], g["hi"]):
        point = np.zeros(2); point[g["axis"]] = val; point[1-g["axis"]] = g["normal_mm"]
        result.append(float(compression_coeff[0]+compression_coeff[1:]@point))
    return result


def _critical(k, t, b):
    return k*math.pi**2*MATERIAL["E_MPa"]/(12*(1-MATERIAL["nu"]**2))*(t/b)**2


def _internal_certificate(g, t, stress):
    """EN 1993-1-5 Table 4.1, Eq.4.2 at fyb, NOT at service stress."""
    s0, s1 = stress
    if max(stress) <= 1e-10:
        return {"panel": g["panel"], "branch": "tension", "rho": 1.0,
                "b_mm": g["b_mm"], "compression_stress_ends_MPa": stress}
    psi = min(stress)/max(stress)
    if psi < -3.0-1e-12 or psi > 1.0+1e-12:
        raise ValueError("Table4.1 stress ratio outside [-3,1]")
    psi = max(-3., min(1., psi))
    # Snap only numerical representations of the tabulated endpoints; this
    # prevents mirrored pure bending from selecting different k at psi=-1.
    if abs(psi-1.) <= 1e-12: k = 4.0
    elif abs(psi+1.) <= 1e-12: k = 23.9
    elif psi > 0.: k = 8.2/(1.05+psi)
    elif psi > -1.: k = 7.81-6.29*psi+9.78*psi**2
    else: k = 5.98*(1-psi)**2
    critical = _critical(k, t, g["b_mm"])
    slenderness = math.sqrt(MATERIAL["fyb_MPa"]/critical)
    limit = .5+math.sqrt(.085-.055*psi)
    rho = 1. if slenderness <= limit else min(1., (slenderness-.055*(3+psi))/slenderness**2)
    bc = 1. if psi >= 0. else 1./(1.-psi)
    first = rho*bc*(2./(5.-psi) if psi >= 0. else .4)
    second = rho*bc-first
    lip_start = 1.-first if s1 > s0 else 1.-second
    return {"panel": g["panel"], "branch": "EN1993-1-5_Table4.1_ULS_fyb",
            "b_mm": g["b_mm"], "compression_stress_ends_MPa": stress, "psi": psi,
            "k_sigma": k, "sigma_cr_MPa": critical, "lambda_p": slenderness,
            "lambda_p_integral_limit": limit, "rho": rho,
            "flange_lip_adjacent_start_fraction": lip_start,
            "slenderness_reference_stress_MPa": MATERIAL["fyb_MPa"]}


def _lip_certificate(g, flange, t, stress):
    if max(stress) <= 1e-10:
        return {"panel": g["panel"], "branch": "tension", "rho": 1.0,
                "b_mm": g["b_mm"], "compression_stress_ends_MPa": stress}
    if min(stress) < -1e-10:
        raise ValueError("Mixed-sign lip outside the implemented pure-component domain")
    ratio = g["b_mm"]/flange["b_mm"]
    if not .2 <= ratio <= .6:
        raise ValueError("Lip/flange ratio outside EN1993-1-3 Eq.5.2")
    k = .5 if ratio <= .35 else .5+.83*(ratio-.35)**(2./3.)
    critical = _critical(k, t, g["b_mm"])
    slenderness = math.sqrt(MATERIAL["fyb_MPa"]/critical)
    rho = 1. if slenderness <= .748 else min(1., (slenderness-.188)/slenderness**2)
    return {"panel": g["panel"], "branch": "EN1993-1-3_Eq5.13_ULS_fyb",
            "b_mm": g["b_mm"], "compression_stress_ends_MPa": stress,
            "bpc_over_bp": ratio, "k_sigma": k, "sigma_cr_MPa": critical,
            "lambda_p": slenderness, "lambda_p_integral_limit": .748, "rho": rho,
            "slenderness_reference_stress_MPa": MATERIAL["fyb_MPa"]}


def _interval_stresses(nodes, t, refs, compression_coeff):
    line, faces = [], []
    for i, lo, hi in refs:
        d = nodes[i+1]-nodes[i]
        normal = np.array([-d[1],d[0]])/np.linalg.norm(d)
        for u in (lo,hi):
            point = nodes[i]+u*d
            line.append(float(compression_coeff[0]+compression_coeff[1:]@point))
            for side in (-1,1):
                face = point+side*t/2*normal
                faces.append(float(compression_coeff[0]+compression_coeff[1:]@face))
    return {"min_line_compression_MPa":min(line),"max_line_compression_MPa":max(line),
            "min_offset_face_compression_MPa":min(faces),"max_offset_face_compression_MPa":max(faces)}


def _stiffener(nodes, t, lip, flange, flange_meta, compression_coeff):
    refs = [(i,0.,1.) for i in lip["ids"]]
    xcut = flange["lo"]+flange["b_mm"]*flange_meta["flange_lip_adjacent_start_fraction"]
    for i in flange["ids"]:
        dx = nodes[i+1,0]-nodes[i,0]
        lo, hi = 0., 1.
        if abs(dx) < 1e-14:
            if nodes[i,0] < xcut: continue
        else:
            cut = (xcut-nodes[i,0])/dx
            if dx > 0.: lo = max(lo,cut)
            else: hi = min(hi,cut)
        if hi > lo: refs.append((i,lo,hi))
    props = _properties(_line_integrals(nodes,t,refs))
    stress_audit = _interval_stresses(nodes,t,refs,compression_coeff)
    if stress_audit["min_line_compression_MPa"] < -1e-9 or stress_audit["min_offset_face_compression_MPa"] < -1e-9:
        raise ValueError("Stiffener As includes tensile line/offset-face material; no fallback permitted")
    center = np.array(props["centroid_xy_mm"])
    return {"flange": flange["panel"], "As_mm2": props["A_mm2"],
            "Is_mm4": props["Ix_strong_mm4"], "centroid_xy_mm": center.tolist(),
            "b1_mm": float(center[0]), "line_intervals": [list(x) for x in refs],
            "stress_domain_audit": stress_audit,
            "sigma_com_Ed_MPa": float(compression_coeff[0]+compression_coeff[1:]@center),
            "assembly_interpretation": ("For a mixed flange with a compressed lip, Eq.5.10b is applied to the wholly compressed physical As with kr=As2/As1; bounded interpretation, not an exact coupled distortion solution.")}



def _distortional_area_witness(chi, sigma_com_Ed_MPa):
    """EN13 Eq.5.17 at the PURE ULS field, with exact cap and no tolerance.

    chi<1 is permitted only if the actual effective-section stress at the
    stiffener centroid still gives As_red=As. In this integral-only route,
    unchanged local widths and unchanged As prove the trial is a fixed point.
    """
    chi = _number(chi,"chi_d")
    stress = _number(sigma_com_Ed_MPa,"sigma_com_Ed_MPa")
    if not 0. < chi <= 1. or stress <= 0.:
        raise ValueError("Positive compressed-assembly stress and 0<chi_d<=1 required")
    reduced_strength = chi*MATERIAL["fyb_MPa"]/MATERIAL["gamma_M0"]
    raw_ratio = reduced_strength/stress
    return raw_ratio, min(1.,raw_ratio), reduced_strength-stress


def _component(name, action, nodes, t, props, groups):
    axis, sign = action
    # Each vector multiplies the SIGNED physical effort, not its magnitude.
    coeff = np.zeros(3)
    if axis == 0: coeff[0] = 1./props["A_mm2"]
    elif axis == 1: coeff[2] = 1./props["Ix_strong_mm4"]
    else: coeff[1] = -1./props["Iy_weak_mm4"]
    cg = np.array(props["centroid_xy_mm"])
    xy = nodes-cg
    sigma = sign*(coeff[0]+xy@coeff[1:])
    scale = MATERIAL["fyb_MPa"]/MATERIAL["gamma_M0"]/max(abs(sigma))
    absolute_coeff = coeff.copy(); absolute_coeff[0] -= coeff[1:]@cg
    compression_coeff = -sign*scale*absolute_coeff
    base = {"action": name, "physical_action_axis": ("N_N","Mx_Nmm","My_Nmm")[axis],
            "physical_action_sign": sign, "eligible": False, "blocking_reasons": [],
            "sigma_coefficients_c0_cx_cy": None, "effective_properties": None,
            "ULS_pure_effort_signed": sign*scale,
            "ULS_pure_effort_role": "Pure-component line-stress normalization only, NOT a design resistance or exterior-fibre strength.",
            "ULS_max_abs_line_stress_MPa": float(max(abs(sigma))*scale),
            "local_panels": [], "stiffeners": [], "tension_assemblies": [],
            "distortional_stage": "not_applicable_to_uniform_tension",
            "scope": "Normal line stress of this pure component only; not complete section/member resistance."}
    if name == "N_tension":
        base["proof"] = "EN1993-1-3 6.1.2 gross-area normal yielding component only; net fracture is not checked."
    else:
        meta = {}
        try:
            for i in (1,2,3):
                meta[i] = _internal_certificate(groups[i],t,_stress_ends(groups[i],compression_coeff))
            for lip, flange in ((0,1),(4,3)):
                meta[lip] = _lip_certificate(groups[lip],groups[flange],t,_stress_ends(groups[lip],compression_coeff))
            base["local_panels"] = [meta[i] for i in range(5)]
            # An unloaded-in-compression lip is not by itself proof that its
            # adjacent assembly is wholly tensile. This minimal route accepts
            # omission only for a whole tensile flange AND lip, including
            # offset faces. Inverse weak bending has a mixed flange and stays
            # explicitly unqualified, even when its local rho happens to be 1.
            for lip,flange in ((0,1),(4,3)):
                if meta[lip]["branch"] == "tension":
                    refs = [(i,0.,1.) for i in groups[lip]["ids"]+groups[flange]["ids"]]
                    audit = _interval_stresses(nodes,t,refs,compression_coeff)
                    item = {"flange":PANEL_NAMES[flange],"lip":PANEL_NAMES[lip],
                            "audited_region":"entire flange and lip",**audit}
                    base["tension_assemblies"].append(item)
                    if audit["max_line_compression_MPa"] > 1e-9 or audit["max_offset_face_compression_MPa"] > 1e-9:
                        base["blocking_reasons"].append({
                            "code":"TENSION_LIP_MIXED_FLANGE_TOPOLOGY_NOT_QUALIFIED",
                            "flange":PANEL_NAMES[flange],
                            "detail":"The lip is tensile but the flange/assembly topology is not wholly tensile; no distortional qualification is inferred from the lip sign or a uniform-compression certificate."})
            for i in range(5):
                if meta[i]["rho"] < 1.0:
                    base["blocking_reasons"].append({"code":"ULS_LOCAL_REDUCTION_NOT_IMPLEMENTED",
                        "panel":PANEL_NAMES[i], "rho":meta[i]["rho"],
                        "detail":"ULS fyb proof requires a reduced local section; gross coefficients are withheld."})
            # Do not calculate distortional properties from an already-invalid
            # integral trial. A reduced assembly needs a separate implementation.
            base["distortional_stage"] = "not_attempted_because_local_or_topology_guard_failed"
            if not base["blocking_reasons"]:
                base["distortional_stage"] = "evaluated_in_restricted_assembly_domain"
                stiff = []
                for lip,flange in ((0,1),(4,3)):
                    stiff.append(None if meta[lip]["branch"] == "tension" else
                        _stiffener(nodes,t,groups[lip],groups[flange],meta[flange],compression_coeff))
                for i,st in enumerate(stiff):
                    if st is None: continue
                    other = stiff[1-i]
                    kr = other["As_mm2"]/st["As_mm2"] if other else 0.
                    b1 = st["b1_mm"]; b2 = other["b1_mm"] if other else 0.
                    hw = float(max(nodes[:,1])-min(nodes[:,1]))
                    K = MATERIAL["E_MPa"]*t**3/(4*(1-MATERIAL["nu"]**2))/(b1*b1*hw+b1**3+.5*b1*b2*hw*kr)
                    critical = 2*math.sqrt(K*MATERIAL["E_MPa"]*st["Is_mm4"])/st["As_mm2"]
                    ld = math.sqrt(MATERIAL["fyb_MPa"]/critical)
                    chi = min(1., 1. if ld <= .65 else 1.47-.723*ld if ld < 1.38 else .66/ld)
                    raw_ratio,ratio,margin = _distortional_area_witness(chi,st["sigma_com_Ed_MPa"])
                    st.update(kr_area=kr,hw_mm=hw,K_N_mm2=K,sigma_cr_MPa=critical,
                        lambda_d=ld,chi_d=chi,Eq5_17_As_red_over_As_at_ULS=ratio,
                        Eq5_17_unclamped_As_ratio_at_ULS=raw_ratio,
                        Eq5_17_reduced_strength_minus_stress_MPa=margin,
                        Eq5_17_reference="Pure-component ULS field, max absolute line stress=fyb/gammaM0; stress at physical As centroid.",
                        integral_fixed_point=(ratio == 1.))
                    base["stiffeners"].append(st)
                    # No numerical tolerance may promote As_red/As<1 to 1.
                    # Local rho=1 was already required before this stage.
                    if ratio != 1.:
                        base["blocking_reasons"].append({"code":"ULS_DISTORTIONAL_REDUCTION_REQUIRED",
                            "flange":st["flange"],"As_red_over_As_at_ULS":ratio,
                            "unclamped_As_ratio_at_ULS":raw_ratio,
                            "detail":"Eq.5.17 gives a reduced As in the pure ULS field; no reduced-section solver or gross fallback is implemented."})
        except ValueError as error:
            base["blocking_reasons"].append({"code":"PURE_COMPONENT_OUTSIDE_IMPLEMENTED_DOMAIN","detail":str(error)})
        base["proof"] = ("EN1993-1-3 5.5.1(3),5.5.2,5.5.3 and 6.1.3/6.1.4; local slenderness at fyb; "
            "integral local widths and exact Eq.5.17 As_red/As=1 required at the pure-component ULS field; "
            "chi_d may be below 1 only with this unchanged-section fixed-point witness. "
            "No actual-service-stress reduction law and no optional plastic/strength enhancement.")
    if not base["blocking_reasons"]:
        base.update(eligible=True,sigma_coefficients_c0_cx_cy=coeff.tolist(),
            effective_properties=copy.deepcopy(props),section_status="integral_demonstrated_at_ULS",
            centroid_shift_from_gross_mm=[0.,0.],additional_Mx_per_N_mm=0.,additional_My_per_N_mm=0.,
            effective_centroid_relative_to_gross_mm=[0.,0.],
            effective_centroid_property_origin="Original pinned polygon coordinates; stress coefficients use gross-centred coordinates.",
            fixed_point_statement="Every local rho=1 and every compressed As has Eq.5.17 As_red/As=1 exactly. Thus geometry, centroid, stiffness and pure ULS stresses remain unchanged on re-evaluation; this is an integral effective-section fixed point.")
    else:
        base["section_status"] = "blocked_no_effective_coefficients"
    return base


def build_component_sections(profile, *, fyb_MPa=250., fya_MPa=250., E_MPa=210000., nu=.3, gamma_M0=1.):
    """Build the restricted component certificate from one exact frozen profile.

    Invalid geometry/material raises ValueError. Unsupported ULS components
    return eligible=False, exact blocking reasons, and coefficients=None.
    Consumers must select the component by the actual nonzero action sign.
    Required external verifications (including shear lag when relevant) are
    not waived by an eligible local/distortional component.
    """
    for key,value in {"fyb_MPa":fyb_MPa,"fya_MPa":fya_MPa,"E_MPa":E_MPa,"nu":nu,"gamma_M0":gamma_M0}.items():
        if _number(value,key) != MATERIAL[key]:
            raise ValueError("Material outside fixed reviewed domain: "+key+" must equal "+str(MATERIAL[key]))
    nodes,t,props,groups,sha = _geometry(profile)
    components = {name:_component(name,action,nodes,t,props,groups) for name,action in PURE_ACTIONS.items()}
    result = {"schema":SCHEMA,"method_revision":"Eq5.17_integral_ULS_fixed_point_20261104",
        "profile_id":profile["profile_id"],"nodes_sha256":sha,
        "thickness_mm":t,"material":dict(MATERIAL),"gross_properties":props,
        "coordinate_system":"xy_R01 relative to gross centroid",
        "stress_convention":"Positive sigma/N=tension; sigma=c0+cx*x+cy*y per SIGNED physical action. Mx multiplies +y, My multiplies -x.",
        "frame_mapping":"Mx_R01=-My_frame; My_R01=-Mz_frame",
        "normal_yield_limit_MPa":fya_MPa/gamma_M0,"components":components,
        "all_normal_components_eligible":all(v["eligible"] for v in components.values()),
        "physical_geometry_verified":False,"whole_member_approved":False,
        "source_basis":["EN1993-1-3:2006 3.2.1(5),5.1,5.2,5.5,6.1.2,6.1.3,6.1.4,6.1.6(3)",
                        "EN1993-1-5:2006 4.4/Table4.1; EN1993-1-1:2005 3.2.6"],
        "not_checked":["net-section fracture/fasteners/connections","shear and shear-normal interaction",
            "global member stability and second-order effects","shear lag and flange curling applicability",
            "solid/exterior-fibre stress","material certification/coating/core-thickness tolerance",
            "warping B component (must use the SAME pinned gross omega/Cw externally)"]}
    result["content_sha256"] = _canonical_sha(result)
    return result


def verify_component_sections(certificate):
    """Reject a modified cached certificate, including eligibility/coefficients."""
    candidate = copy.deepcopy(certificate); expected = candidate.pop("content_sha256",None)
    if candidate.get("schema") != SCHEMA or expected != _canonical_sha(candidate):
        raise ValueError("EN normal-component certificate changed; rebuild from frozen geometry")


def require_component(certificate, axis, value):
    """Return an eligible signed-action record; zero needs no section branch.

    This helper never substitutes a different sign, thickness or gross record.
    """
    verify_component_sections(certificate)
    value = _number(value,axis)
    if axis not in ("N","Mx","My"):
        raise ValueError("Action axis must be N, Mx or My in R01 coordinates")
    if value == 0.: return None
    key = ("N_tension" if value>0 else "N_compression") if axis == "N" else axis+("_positive" if value>0 else "_negative")
    record = certificate["components"][key]
    if not record["eligible"]:
        raise ValueError(key+": "+json.dumps(record["blocking_reasons"],ensure_ascii=False))
    return copy.deepcopy(record)
