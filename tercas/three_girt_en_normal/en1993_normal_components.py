"""Restricted EN 1993-1-3:2006 ULS normal-component section certificate.

The six pure actions use their respective ULS local/distortional checks. Only
sections proved integral or explicit pinned axial/pure-moment reductions are returned.
A failed proof never supplies gross
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

LEGACY_SCHEMA = "en1993_1_3_2006_normal_component_sections_integral_v1"
PREVIOUS_SCHEMA = "en1993_1_3_2006_normal_component_sections_effective_v2"
AXIAL_SCHEMA = "en1993_1_3_2006_normal_component_sections_effective_v3"
MY150_SCHEMA = "en1993_1_3_2006_normal_component_sections_effective_v4"
SCHEMA = "en1993_1_3_2006_normal_component_sections_effective_v5"
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


def _tension_lip_outstand_bound(nodes, t, lip, flange, compression_coeff):
    """Sufficient integral-panel proof, no restraint/strength credit to the lip.

    EN1993-1-5 Table4.2, LAST orientation: supported web edge in compression,
    free lip-side edge unloaded. A triangular compression field [fyb,0]
    (psi=0, k_sigma=1.70) is required to dominate the actual pure ULS field
    pointwise. The lip itself must be noncompressive at every line/face vertex.
    Its elastic stiffness and stabilizing tensile geometric stiffness are then
    ignored. Rotation at the web/flange junction is free, not clamped.

    This is the usual panel model with supported translation at junctions;
    it is not a universal eigenmode certificate for translating junctions or
    global/member instability. Eq.5.17 is NOT evaluated at negative stress.
    """
    lip_refs=[(i,0.,1.) for i in lip['ids']]
    lip_audit=_interval_stresses(nodes,t,lip_refs,compression_coeff)
    differences=[];actual=[]
    for i in flange['ids']:
        d=nodes[i+1]-nodes[i];normal=np.array([-d[1],d[0]])/np.linalg.norm(d)
        for point in (nodes[i],nodes[i+1]):
            for side in (-1,0,1):
                face=point+side*t/2*normal
                z=(face[flange['axis']]-flange['lo'])/flange['b_mm']
                bound=MATERIAL['fyb_MPa']*(1.-z)
                stress=float(compression_coeff[0]+compression_coeff[1:]@face)
                actual.append(stress);differences.append(stress-bound)
    critical=_critical(1.70,t,flange['b_mm'])
    slenderness=math.sqrt(MATERIAL['fyb_MPa']/critical)
    rho=1. if slenderness<=.748 else min(1.,(slenderness-.188)/slenderness**2)
    no_lip_compression=max(lip_audit['max_line_compression_MPa'],
                           lip_audit['max_offset_face_compression_MPa'])<=0.
    dominated=bool(max(differences)<=0.)
    return dict(panel=flange['panel'],branch='EN1993-1-5_Table4.2_unstiffened_outstand_bound',
        b_mm=flange['b_mm'],supported_edge='web_flange_junction',free_edge='lip_side_no_restraint_credit',
        bound_stress_ends_MPa=[MATERIAL['fyb_MPa'],0.],bound_psi=0.,k_sigma=1.70,
        sigma_cr_MPa=critical,lambda_p=slenderness,lambda_p_integral_limit=.748,rho=rho,
        slenderness_reference_stress_MPa=MATERIAL['fyb_MPa'],
        actual_min_compression_MPa=min(actual),actual_max_compression_MPa=max(actual),
        maximum_actual_minus_bound_MPa=max(differences),pointwise_dominance_demonstrated=dominated,
        lip_stress_domain_audit=lip_audit,lip_is_noncompressive=no_lip_compression,
        integral_bound=bool(no_lip_compression and dominated and rho==1.),
        physical_As_assumed_wholly_tensile=False,Eq5_17_used=False,
        junction_model='Supported transverse translation at panel junction; free flange rotation; no rotational spring from web or lip credited',
        scope='Conservative panel/flange-rotation proof only; translating-junction coupled modes and member stability are outside this certificate')


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



def _web_integral_ULS_trial(nodes,t,web,compression_coeff,meta):
    """EN15 Eq4.4 trial, ONLY in the normalized pure negative-My ULS state.

    A uniform compression bound includes all line/face vertices of this web.
    No reduced geometry is returned: if lambda_red requires rho<1 the trial
    stays blocked. If every other panel/bound also remains integral, the trial
    section is the effective section and reapplication is an exact fixed point.
    """
    audit=_interval_stresses(nodes,t,[(i,0.,1.) for i in web['ids']],compression_coeff)
    stress=max(audit['max_line_compression_MPa'],audit['max_offset_face_compression_MPa'])
    if not 0.<stress<=MATERIAL['fyb_MPa']/MATERIAL['gamma_M0']:
        raise ValueError('Pure negative-My web ULS stress outside the Eq4.4 integral trial')
    reduced=meta['lambda_p']*math.sqrt(stress/(MATERIAL['fyb_MPa']/MATERIAL['gamma_M0']))
    rho=1. if reduced<=meta['lambda_p_integral_limit'] else min(1.,(reduced-.055*(3+meta['psi']))/reduced**2)
    out=copy.deepcopy(meta)
    out['Eq4_4_ULS_integral_trial']=dict(lambda_p_at_fyb=meta['lambda_p'],rho_at_fyb=meta['rho'],
        sigma_com_Ed_MPa=stress,lambda_p_reduced=reduced,rho_reduced_trial=rho,
        stress_domain_audit=audit,integral_trial=(rho==1.),
        reference='EN1993-1-5 4.4(4)/Eq4.4; EN1993-1-3 6.1.4.1(4): pure moment state with max absolute line stress fyb/gammaM0',
        condition='Accepted only if ALL section panels/bounds remain integral, so geometry, stresses and this evaluation remain unchanged; never a reduced-section or service-stress fallback')
    if rho==1.:
        out.update(branch='EN1993-1-5_Table4.1_Eq4.4_pure_ULS_integral_fixed_point',
            lambda_p=reduced,rho=1.,slenderness_reference_stress_MPa=stress,
            flange_lip_adjacent_start_fraction=.5)
    return out

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
    reduced_web = name == "N_compression" and t in (2., 2.25)
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
    if reduced_web:
        # Uniform ULS reference is exact, independent of roundoff in A*(1/A).
        compression_coeff = np.array([MATERIAL["fyb_MPa"]/MATERIAL["gamma_M0"],0.,0.])
    base = {"action": name, "physical_action_axis": ("N_N","Mx_Nmm","My_Nmm")[axis],
            "physical_action_sign": sign, "eligible": False, "blocking_reasons": [],
            "sigma_coefficients_c0_cx_cy": None, "effective_properties": None,
            "ULS_pure_effort_signed": sign*scale,
            "ULS_pure_effort_role": "Pure-component line-stress normalization only, NOT a design resistance or exterior-fibre strength.",
            "ULS_max_abs_line_stress_MPa": float(max(abs(sigma))*scale),
            "local_panels": [], "stiffeners": [], "tension_assemblies": [],
            "distortional_stage": "not_applicable_to_uniform_tension",
            "scope": "Normal line stress of this pure component only; not complete section/member resistance."}
    if name == "My_negative" and t in (1.2, 1.5):
        try:
            return _negative_my_web_reduced(base, nodes, t, props, groups)
        except ValueError as error:
            base["blocking_reasons"].append({"code":"NEGATIVE_MY_REDUCED_FIXED_POINT_NOT_QUALIFIED", "detail":str(error)})
            base["section_status"] = "blocked_no_effective_coefficients"
            return base
    if name in ("Mx_positive", "Mx_negative") and t == 1.2:
        try:
            return _pure_mx_local_flange_reduced(base, nodes, t, props, groups)
        except ValueError as error:
            base["blocking_reasons"].append({"code":"PURE_MX_REDUCED_SECTION_NOT_QUALIFIED", "detail":str(error)})
            base["section_status"] = "blocked_no_effective_coefficients"
            return base
    if name == "N_compression" and t in (1.2, 1.5):
        try:
            return _uniform_local_distortional_reduced(base, nodes, t, props, groups)
        except ValueError as error:
            base["blocking_reasons"].append({"code":"UNIFORM_LOCAL_DISTORTIONAL_SECTION_NOT_QUALIFIED", "detail":str(error)})
            base["section_status"] = "blocked_no_effective_coefficients"
            return base
    if name == "N_tension":
        base["proof"] = "EN1993-1-3 6.1.2 gross-area normal yielding component only; net fracture is not checked."
    else:
        meta = {}
        try:
            for i in (1,2,3):
                meta[i] = _internal_certificate(groups[i],t,_stress_ends(groups[i],compression_coeff))
            for lip, flange in ((0,1),(4,3)):
                meta[lip] = _lip_certificate(groups[lip],groups[flange],t,_stress_ends(groups[lip],compression_coeff))
            if name=="My_negative" and meta[2]["rho"]<1.:
                meta[2]=_web_integral_ULS_trial(nodes,t,groups[2],compression_coeff,meta[2])
            base["local_panels"] = [meta[i] for i in range(5)]
            # A tensile lip alone is not a proof about the connected As.
            # For pure inverse weak bending, a separate free-outstand panel
            # bound may prove integrality without credit to the lip. It does
            # not pretend the mixed connected As is wholly tensile.
            for lip,flange in ((0,1),(4,3)):
                if meta[lip]["branch"] == "tension":
                    refs = [(i,0.,1.) for i in groups[lip]["ids"]+groups[flange]["ids"]]
                    audit = _interval_stresses(nodes,t,refs,compression_coeff)
                    item = {"flange":PANEL_NAMES[flange],"lip":PANEL_NAMES[lip],
                            "audited_region":"entire flange and lip",**audit}
                    base["tension_assemblies"].append(item)
                    if audit["max_line_compression_MPa"] > 1e-9 or audit["max_offset_face_compression_MPa"] > 1e-9:
                        if name == "My_negative":
                            bound=_tension_lip_outstand_bound(nodes,t,groups[lip],groups[flange],compression_coeff)
                            base.setdefault("outstand_flange_bounds",[]).append(bound)
                            if not bound["integral_bound"]:
                                base["blocking_reasons"].append({
                                    "code":"TENSION_LIP_OUTSTAND_INTEGRAL_BOUND_NOT_DEMONSTRATED",
                                    "flange":PANEL_NAMES[flange],"rho":bound["rho"],
                                    "detail":"The free-outstand triangular ULS bound or noncompressive-lip proof failed; no effective coefficients are supplied."})
                        else:
                            base["blocking_reasons"].append({
                                "code":"TENSION_LIP_MIXED_FLANGE_TOPOLOGY_NOT_QUALIFIED",
                                "flange":PANEL_NAMES[flange],
                                "detail":"Mixed topology outside the pure negative-My outstand bound; no waiver is inferred from the lip sign."})
            for i in range(5):
                if meta[i]["rho"] < 1.0 and not (reduced_web and i == 2):
                    base["blocking_reasons"].append({"code":"ULS_LOCAL_REDUCTION_NOT_IMPLEMENTED",
                        "panel":PANEL_NAMES[i], "rho":meta[i]["rho"],
                        "detail":"ULS fyb proof requires a reduced local section; gross coefficients are withheld."})
            # Do not calculate distortional properties from an already-invalid
            # integral trial. A reduced assembly needs a separate implementation.
            base["distortional_stage"] = "not_attempted_because_local_or_topology_guard_failed"
            if not base["blocking_reasons"]:
                base["distortional_stage"] = ("outstand_panel_flange_rotation_bound_no_lip_restraint"
                    if base.get("outstand_flange_bounds") else "evaluated_in_restricted_assembly_domain")
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
    if base.get("outstand_flange_bounds"):
        base["proof"] = ("EN1993-1-3 5.5.1/5.5.2 and EN1993-1-5 4.4/Table4.1/4.2: web checked at fyb or by Eq4.4 at its maximum pure-ULS compression with an unchanged-section fixed point; "
            "each mixed flange additionally bounded by an unstiffened outstand under triangular compression [fyb,0], psi=0/k=1.70. "
            "The bound dominates every line/face vertex and requires rho=1; lips are everywhere noncompressive. "
            "No elastic or tensile-stabilization credit to lips, no Eq.5.17 at negative stress and no claim As is wholly tensile. "
            "Standard panel junction translations retained, rotation free; translating-junction coupled modes and global stability remain separate.")
    if reduced_web and not base["blocking_reasons"]:
        try:
            return _uniform_web_reduced(base, nodes, t, props, groups)
        except ValueError as error:
            base["blocking_reasons"].append({"code":"REDUCED_WEB_GEOMETRY_OR_AS_NOT_QUALIFIED", "detail":str(error)})
    if not base["blocking_reasons"]:
        base.update(eligible=True,sigma_coefficients_c0_cx_cy=coeff.tolist(),
            effective_properties=copy.deepcopy(props),section_status="integral_demonstrated_at_ULS",
            centroid_shift_from_gross_mm=[0.,0.],additional_Mx_per_N_mm=0.,additional_My_per_N_mm=0.,
            effective_centroid_relative_to_gross_mm=[0.,0.],
            effective_centroid_property_origin="Original pinned polygon coordinates; stress coefficients use gross-centred coordinates.",
            fixed_point_statement="Every local rho=1 and every compressed As has Eq.5.17 As_red/As=1 exactly. Thus geometry, centroid, stiffness and pure ULS stresses remain unchanged on re-evaluation; this is an integral effective-section fixed point.")
        if base.get("outstand_flange_bounds"):
            base["fixed_point_statement"] = ("Web and local panels have rho=1; both pointwise-dominating free-outstand flange bounds also have rho=1, with noncompressive lips. "
                "No geometry/centroid/stiffness changes arise in the stated panel model, so the pure ULS field is unchanged on re-evaluation.")
    else:
        base["section_status"] = "blocked_no_effective_coefficients"
    return base



def _my_refs_for(nodes,groups,rho):
    refs=[]
    for j,g in enumerate(groups):
        bands=[(0,rho/2),(1-rho/2,1)] if j==2 else [(0,1)]
        for i in g['ids']:
            u=(nodes[i,g['axis']]-g['lo'])/g['b_mm']; v=(nodes[i+1,g['axis']]-g['lo'])/g['b_mm']
            for a,b in bands:
                if abs(v-u)<1e-14:
                    if a<=u<=b: refs.append((i,0.,1.))
                else:
                    lo,hi=sorted(((a-u)/(v-u),(b-u)/(v-u)));lo=max(0,lo);hi=min(1,hi)
                    if hi>lo:refs.append((i,lo,hi))
    return refs

def _my_vertices(nodes,t,refs):
    pts=[]
    for i,lo,hi in refs:
        d=nodes[i+1]-nodes[i];normal=np.array([-d[1],d[0]])/np.linalg.norm(d)
        for s in (lo,hi):
            for side in (-1,0,1):pts.append(nodes[i]+s*d+side*t/2*normal)
    return np.array(pts)
def _negative_my_outstand_bounds(nodes,t,groups,compression,psi=0.):
    """Signed pointwise comparison on complete panels, including q<=0.

    Table4.2 last orientation: supported web edge compressed, free lip edge
    in tension for psi<0. Lip stiffness/tensile stabilization is not credited.
    """
    if not -1. <= _number(psi, "outstand bound psi") <= 0.:
        raise ValueError("Outstand bound psi outside audited Table4.2 [-1,0] branch")
    k=1.70-5.*psi+17.1*psi**2
    flanges=[]
    for lip,flange in [(0,1),(4,3)]:
        g=groups[flange];p=_my_vertices(nodes,t,[(i,0.,1.) for i in g['ids']]);s=compression[0]+p@compression[1:];q=1-(1.-psi)*(p[:,0]-g['lo'])/g['b_mm']
        # Constraints a*q>=s. Positive q -> lower bound; negative q -> upper.
        lower=max(0.,max(s[q>0]/q[q>0]));upper=min(s[q<0]/q[q<0]) if any(q<0) else float('inf')
        amplitude=float(math.ceil(lower))
        if not (amplitude<=upper and all(s[q==0]<=0)): raise ValueError('Flange zero/negative ordinate bound failed')
        lamf=math.sqrt(amplitude/_critical(k,t,g['b_mm']));rhof=1. if lamf<=.748 else min(1.,(lamf-.188)/lamf**2)
        lp=_my_vertices(nodes,t,[(i,0.,1.) for i in groups[lip]['ids']]);lipmax=max(compression[0]+lp@compression[1:])
        if not math.isfinite(lamf) or lamf>.748 or rhof != 1. or lipmax>0. or max(s-amplitude*q)>0.: raise ValueError('Integral flange or tensile lip not demonstrated')
        flanges.append(dict(panel=g['panel'],branch='EN1993-1-5_Table4.2_Eq4.4_ULS_outstand_bound',
            b_mm=g['b_mm'],bound_stress_ends_MPa=[amplitude,psi*amplitude],bound_psi=psi,k_sigma=k,
            sigma_cr_MPa=_critical(k,t,g['b_mm']),lambda_p=lamf,lambda_p_integral_limit=.748,
            slenderness_reference_stress_MPa=amplitude,pointwise_dominance_demonstrated=True,
            lip_is_noncompressive=True,integral_bound=True,physical_As_assumed_wholly_tensile=False,Eq5_17_used=False,
            lip_stress_domain_audit=_interval_stresses(nodes,t,[(i,0.,1.) for i in groups[lip]['ids']],compression),
            minimum_amplitude_MPa=float(lower),amplitude_MPa=amplitude,maximum_actual_minus_bound_MPa=float(max(s-amplitude*q)),lambda_red=lamf,rho=rhof,lip_max_compression_MPa=float(lipmax)))
        if psi != 0.:
            flanges[-1].update(supported_edge='web_flange_junction',
                free_edge='lip_side_no_restraint_credit',maximum_amplitude_MPa=float(upper),
                dominance_includes_negative_q=True,dominance_includes_line_and_both_faces=True,
                lip_elastic_restraint_credit=False,lip_tensile_stabilization_credit=False,
                flange_tension_is_used=True)
    return flanges


def _negative_my_web_reduced(base,nodes,t,gross,groups,initial_rho=1.,max_iterations=100):
    """Restricted EN15 Eq4.4/Note1 fixed point with free-outstand bounds."""
    if t not in (1.2,1.5) or base["action"] != "My_negative" or _canonical_sha(nodes.tolist()) != GEOMETRY_PINS[t]:
        raise ValueError("Only pinned t1.20/t1.50 pure negative My is qualified")
    if not 0. < _number(initial_rho,"initial_rho") <= 1.: raise ValueError("Invalid initial rho")
    rho=initial_rho;history=[]
    for n in range(max_iterations):
        refs=_my_refs_for(nodes,groups,rho);J=_line_integrals(nodes,t,refs); eff=_properties(J)
        if not all(math.isfinite(eff[k]) and eff[k]>0. for k in ('A_mm2','Ix_strong_mm4','Iy_weak_mm4')) or not math.isfinite(eff['Ixy_mm4']):
            raise ValueError('Invalid effective properties')
        cx,cy=eff['centroid_xy_mm']; pts=_my_vertices(nodes,t,refs)
        # My negative: tension grows towards lip x. Exact pure line-section field N=0.
        maxdist=max(abs(pts[:,0]-cx)); compression=np.array([cx,-1.,0.])*250/maxdist
        webpts=_my_vertices(nodes,t,[(i,0.,1.) for i in groups[2]['ids']])
        webstress=max(compression[0]+webpts@compression[1:]);lam=math.sqrt(webstress/_critical(4,t,groups[2]['b_mm']))
        target=1. if lam<=.5+math.sqrt(.03) else (lam-.22)/lam**2
        reflected=nodes[::-1].copy(); reflected[:,1]=2*gross['centroid_xy_mm'][1]-reflected[:,1]
        mirrored=sorted((len(nodes)-2-i,1-hi,1-lo) for i,lo,hi in refs)
        if np.max(abs(nodes-reflected))>1e-10 or np.max(abs(np.array(sorted(refs))-np.array(mirrored)))>1e-10 or abs(cy-gross['centroid_xy_mm'][1])>1e-10 or abs(eff['Ixy_mm4'])>1e-7:
            raise ValueError('Reduced geometry symmetry failed')
        if not 0.<target<=1. or not 0.<webstress<=250.: raise ValueError('Invalid Eq4.4 web domain')
        if t == 1.2:
            _negative_my_outstand_bounds(nodes,t,groups,compression,psi=-.25)
        history.append(dict(iteration=n,rho=rho,target=target,centroid_x=cx,web_bound_MPa=webstress,lambda_red=lam,residual=target-rho))
        if abs(target-rho)<1e-13:break
        rho=target
    else:raise ValueError('No convergence')
    # Reintegrate the final retained geometry and recompute the residual.
    refs=_my_refs_for(nodes,groups,rho)
    J=_line_integrals(nodes,t,refs);eff=_properties(J)
    if not all(math.isfinite(eff[k]) and eff[k]>0. for k in ('A_mm2','Ix_strong_mm4','Iy_weak_mm4')) or not math.isfinite(eff['Ixy_mm4']):
        raise ValueError('Invalid final effective properties')
    cx,cy=eff['centroid_xy_mm'];pts=_my_vertices(nodes,t,refs)
    compression=np.array([cx,-1.,0.])*250/max(abs(pts[:,0]-cx))
    webstress=max(compression[0]+webpts@compression[1:])
    lam=math.sqrt(webstress/_critical(4,t,groups[2]['b_mm']))
    target=1. if lam<=.5+math.sqrt(.03) else (lam-.22)/lam**2
    if not math.isfinite(target) or not 0.<webstress<=250. or abs(target-rho)>=1e-13 or not 0.<rho<1.: raise ValueError('Final fixed-point residual failed')
    flanges=_negative_my_outstand_bounds(nodes,t,groups,compression,psi=-.25 if t==1.2 else 0.)
    # Exact J equilibrium, plus independent Gauss quadrature for resultants.
    tension=-compression; quad=np.zeros(3)
    for i,lo,hi in refs:
        d=nodes[i+1]-nodes[i]
        for z in (-1/math.sqrt(3),1/math.sqrt(3)):
            p=nodes[i]+(lo+(hi-lo)*(1+z)/2)*d; sig=tension[0]+tension[1:]@p
            quad+=t*np.linalg.norm(d)*(hi-lo)/2*sig*np.array([1,p[1]-gross['centroid_xy_mm'][1],-(p[0]-gross['centroid_xy_mm'][0])])
    if not np.isfinite(quad).all() or abs(quad[0])>=1e-7 or abs(quad[1])>=1e-6: raise ValueError('Pure moment equilibrium failed')
    if abs(eff['Ixy_mm4'])>=1e-7: raise ValueError('Inertia symmetry failed')
    if abs(eff['centroid_xy_mm'][1]-gross['centroid_xy_mm'][1])>=1e-10: raise ValueError('Centroid symmetry failed')
    mirrored=sorted((len(nodes)-2-i,1-hi,1-lo) for i,lo,hi in refs)
    if np.max(abs(np.array(sorted(refs))-np.array(mirrored)))>=1e-10: raise ValueError('Retained symmetry failed')
    # Coefficients above are in absolute coordinates; convert for gross-centred consumers.
    unitcoeff_gross=[(cx-gross['centroid_xy_mm'][0])/eff['Iy_weak_mm4'],-1/eff['Iy_weak_mm4'],0.]

    face_max=float(max(abs(compression[0]+pts@compression[1:])))
    effort=-250/max(abs(pts[:,0]-cx))*eff['Iy_weak_mm4']
    if not math.isclose(face_max,250.,rel_tol=0.,abs_tol=1e-10) or not math.isclose(quad[2],effort,rel_tol=0.,abs_tol=1e-7):
        raise ValueError('Final normalization or My resultant failed')
    if not 0.<eff['A_mm2']<gross['A_mm2']: raise ValueError('Invalid reduced area')
    raw_Ixy=eff['Ixy_mm4'];raw_ey=cy-gross['centroid_xy_mm'][1]
    eff['Ixy_mm4']=0.;eff['centroid_xy_mm'][1]=gross['centroid_xy_mm'][1]
    retained=[]
    for j,g in enumerate(groups):
        bands=[(0.,rho/2.),(1.-rho/2.,1.)] if j==2 else [(0.,1.)]
        retained.append(dict(panel=g['panel'],projected_axis='xy'[g['axis']],
            projected_width_mm=g['b_mm'],retained_fraction_bands=[list(v) for v in bands],
            retained_absolute_coordinate_bands_mm=[[g['lo']+a*g['b_mm'],g['lo']+b*g['b_mm']] for a,b in bands],
            physical_line_intervals=[list(v) for v in refs if v[0] in g['ids']]))
    panels=[dict(panel=groups[i]['panel'],branch='tension',rho=1.,b_mm=groups[i]['b_mm']) for i in range(5)]
    panels[1]=copy.deepcopy(flanges[0]);panels[3]=copy.deepcopy(flanges[1])
    panels[2]=dict(panel='web',branch='EN1993-1-5_Table4.1_Eq4.4_ULS_reduced_fixed_point',
        b_mm=groups[2]['b_mm'],psi=1.,k_sigma=4.,sigma_cr_MPa=_critical(4,t,groups[2]['b_mm']),
        lambda_p=lam,lambda_p_integral_limit=.5+math.sqrt(.03),rho=rho,slenderness_reference_stress_MPa=webstress)
    audit=_interval_stresses(nodes,t,refs,compression)
    ex=cx-gross['centroid_xy_mm'][0]
    base.update(eligible=True,section_status='effective_web_reduced_negative_My_ULS',
        sigma_coefficients_c0_cx_cy=unitcoeff_gross,effective_properties=eff,
        ULS_pure_effort_signed=effort,
        ULS_pure_effort_role='Pure moment normalized by retained line/offset faces; NOT a design resistance.',
        ULS_max_abs_line_stress_MPa=max(abs(audit[k]) for k in ('min_line_compression_MPa','max_line_compression_MPa')),
        ULS_max_abs_line_or_face_stress_MPa=face_max,
        local_panels=panels,outstand_flange_bounds=flanges,
        distortional_stage='outstand_panel_flange_rotation_bound_no_lip_restraint',
        centroid_shift_from_gross_mm=[ex,0.],effective_centroid_relative_to_gross_mm=[ex,0.],
        additional_Mx_per_N_mm=0.,additional_My_per_N_mm=0.,moment_transport_required=False,
        effective_centroid_property_origin='Original polygon coordinates; pure-My coefficients use gross-centred coordinates and N=0.',
        retained_bands=retained,effective_line_intervals=[list(v) for v in refs],
        symmetry_audit=dict(raw_Ixy_mm4=raw_Ixy,raw_ey_mm=raw_ey,
            gross_mirror_max_error_mm=float(np.max(abs(nodes-reflected))),
            retained_mirror_max_error=float(np.max(abs(np.array(sorted(refs))-np.array(mirrored))))),
        effective_stress_domain_audit=audit,ULS_resultants_N_Mx_My_about_gross=quad.tolist(),
        pure_ULS_compression_coefficients_absolute=compression.tolist(),
        fixed_point_iteration_audit=dict(converged=True,iterations=len(history),history=history,residual=target-rho,
            tolerance=1e-13,final_recheck=True,initial_rho=initial_rho),
        proof='EN1993-1-5 4.4(4), Eq4.4 and Note1 iteration; Table4.1 uniform web bound and Table4.2 psi0/k1.70 free-outstand flange bounds. EN1993-1-3 6.1.4.1(4) pure moment ULS. No Eq5.17 negative stress or service-stress reduction.',
        fixed_point_statement='Reduced web geometry and ULS field rechecked after convergence; both flange bounds remain exactly integral without lip restraint credit. Translating-junction coupled modes and member stability remain outside this certificate.')
    if t == 1.2:
        base['proof']='EN1993-1-5 4.4(4), Eq4.4 and Note1 iteration; Table4.1 uniform web bound and Table4.2 psi=-0.25/k=4.01875 signed free-outstand flange bounds. All line/face vertices, including tensile comparison ordinates, checked at every iteration and finally. EN1993-1-3 6.1.4.1(4) pure moment ULS. No lip restraint, no Eq5.17 negative stress and no service-stress reduction.'
        base['fixed_point_iteration_audit']['integral_flange_bounds_checked_each_iteration']=True
    return base


def _panel_retained_intervals(nodes, group, bands):
    """Project notional retained bands onto the existing physical facets."""
    refs = []
    for i in group['ids']:
        u = (nodes[i, group['axis']] - group['lo']) / group['b_mm']
        v = (nodes[i + 1, group['axis']] - group['lo']) / group['b_mm']
        for a, b in bands:
            if abs(v - u) < 1e-14:
                if a <= u <= b:
                    refs.append((i, 0., 1.))
            else:
                lo, hi = sorted(((a - u) / (v - u), (b - u) / (v - u)))
                lo, hi = max(0., lo), min(1., hi)
                if hi > lo:
                    refs.append((i, lo, hi))
    return refs


def _pure_resultants_quadrature(nodes, t, refs, absolute_coeff, gross_cg):
    """Independent Gauss-3 quadrature, not the analytical J assembly."""
    xi, wi = np.polynomial.legendre.leggauss(3)
    resultant = np.zeros(3)
    for i, lo, hi in refs:
        d = nodes[i + 1] - nodes[i]
        for z, w in zip(xi, wi):
            u = (lo + hi) / 2 + z * (hi - lo) / 2
            p = nodes[i] + u * d
            stress = absolute_coeff[0] + absolute_coeff[1:] @ p
            dA = t * np.linalg.norm(d) * (hi - lo) / 2 * w
            resultant += dA * stress * np.array([1., p[1] - gross_cg[1], -(p[0] - gross_cg[0])])
    return resultant


def _pure_mx_local_flange_reduced(base,nodes,t,gross,groups):
    """Pinned pure Mx: local flange reduction and exact Eq5.17 As cap.

    Gross-section psi is permitted by EN13 5.5.2(3); no optional width or
    distortional step-3 refinement is taken. The web and complete physical
    assembly domains are rechecked in the final face-normalized ULS field.
    """
    sign=base.get('physical_action_sign')
    if (t != 1.2 or _canonical_sha(nodes.tolist()) != GEOMETRY_PINS[1.2]
            or isinstance(sign,bool) or sign not in (-1,1)
            or base.get('action') != ('Mx_positive' if sign==1 else 'Mx_negative')):
        raise ValueError('Only pinned t1.20 signed pure Mx is qualified')
    fy = MATERIAL['fyb_MPa'] / MATERIAL['gamma_M0']
    cg = np.array(gross['centroid_xy_mm'])
    lip, flange = (0, 1) if sign == 1 else (4, 3)
    other_lip, other_flange = (4, 3) if sign == 1 else (0, 1)

    # Gross principal pure bending supplies permitted flange psi=1. Step 1
    # local slenderness remains referenced to fyb, not actual service stress.
    gross_comp = sign * np.array([cg[1], 0., -1.]) * fy / max(abs(nodes[:, 1] - cg[1]))
    local = {i: _internal_certificate(groups[i], t, _stress_ends(groups[i], gross_comp))
             for i in (1, 2, 3)}
    for l, f in ((0, 1), (4, 3)):
        local[l] = _lip_certificate(groups[l], groups[f], t, _stress_ends(groups[l], gross_comp))
    rho = local[flange]['rho']
    if not 0. < rho < 1. or any(local[i]['rho'] != 1. for i in range(5) if i != flange):
        raise ValueError('Unexpected local-reduction topology')
    retained, bands_out = [], []
    for j, group in enumerate(groups):
        bands = [(0., rho / 2), (1 - rho / 2, 1.)] if j == flange else [(0., 1.)]
        rr = _panel_retained_intervals(nodes, group, bands)
        retained.extend(rr)
        bands_out.append(dict(panel=group['panel'], projected_width_mm=group['b_mm'],
                              retained_fraction_bands=bands,
                              projected_retained_width_mm=sum(b-a for a,b in bands)*group['b_mm'],
                              physical_line_intervals=rr))

    # As is the actual lip plus only its adjacent effective flange strip.
    stiffener = _stiffener(nodes, t, groups[lip], groups[flange], local[flange], gross_comp)
    b1 = stiffener['b1_mm']
    hw = float(np.ptp(nodes[:, 1]))
    K = MATERIAL['E_MPa'] * t**3 / (4 * (1 - MATERIAL['nu']**2)) / (b1*b1*hw + b1**3)
    sig_cr = 2 * math.sqrt(K*MATERIAL['E_MPa']*stiffener['Is_mm4']) / stiffener['As_mm2']
    ld = math.sqrt(MATERIAL['fyb_MPa'] / sig_cr)
    chi = 1. if ld <= .65 else 1.47 - .723*ld if ld < 1.38 else .66/ld

    J = _line_integrals(nodes, t, retained)
    effective = _properties(J)
    # J integrates [1,x,y] in absolute polygon coordinates. Since N=My=0,
    # its RHS [0,0,1] is exactly a unit physical Mx about any parallel origin.
    if not all(math.isfinite(effective[k]) and effective[k]>0. for k in
               ('A_mm2','Ix_strong_mm4','Iy_weak_mm4')) or not math.isfinite(effective['Ixy_mm4']):
        raise ValueError('Invalid pure-Mx effective properties')
    try:
        absolute_unit_coeff = np.linalg.solve(J, np.array([0., 0., 1.]))
    except np.linalg.LinAlgError as error:
        raise ValueError('Singular effective pure-Mx section') from error
    if not np.isfinite(absolute_unit_coeff).all():
        raise ValueError('Nonfinite pure-Mx inverse')
    points = _my_vertices(nodes, t, retained)
    scale = fy / max(abs(absolute_unit_coeff[0] + points @ absolute_unit_coeff[1:]))
    signed_effort = sign * scale
    compression = -signed_effort * absolute_unit_coeff
    unit_gross_coeff = absolute_unit_coeff.copy()
    unit_gross_coeff[0] += unit_gross_coeff[1:] @ cg

    # An independent closed-form condensed inversion guards against a silent
    # y/Ix substitution or dropping the constant term after origin conversion.
    Ix, Iy, Ixy = (effective[k] for k in ('Ix_strong_mm4', 'Iy_weak_mm4', 'Ixy_mm4'))
    D = Ix*Iy - Ixy**2
    ex, ey = np.array(effective['centroid_xy_mm']) - cg
    condensed = np.array([(Ixy*ex - Iy*ey)/D, -Ixy/D, Iy/D])
    if not math.isfinite(D) or D <= 0. or not np.allclose(condensed, unit_gross_coeff, rtol=5e-12, atol=1e-17):
        raise ValueError('Full inertia inversion or origin shift failed')

    # Pointwise panel-domain audit uses complete physical panels, not just
    # retained fragments. Linear stress extrema occur at these facet endpoints.
    domain = {}
    for j, group in enumerate(groups):
        rr = [(i, 0., 1.) for i in group['ids']]
        domain[group['panel']] = _interval_stresses(nodes, t, rr, compression)
    for j in (flange, lip):
        audit = domain[groups[j]['panel']]
        if audit['min_line_compression_MPa'] <= 0. or audit['min_offset_face_compression_MPa'] <= 0.:
            raise ValueError('Compressed flange/lip physical domain failed')
        if max(audit['max_line_compression_MPa'], audit['max_offset_face_compression_MPa']) > fy + 1e-10:
            raise ValueError('Uniform fyb local bound does not dominate compressed panel')
    for j in (other_flange, other_lip):
        audit = domain[groups[j]['panel']]
        if max(audit['max_line_compression_MPa'], audit['max_offset_face_compression_MPa']) >= 0.:
            raise ValueError('Opposite flange/lip is not wholly tensile; kr=0 invalid')

    web_final = _internal_certificate(groups[2], t, _stress_ends(groups[2], compression))
    lip_final = _lip_certificate(groups[lip], groups[flange], t, _stress_ends(groups[lip], compression))
    if web_final['rho'] != 1. or lip_final['rho'] != 1.:
        raise ValueError('Final web/lip must remain wholly effective')
    sigma_as = float(compression[0] + compression[1:] @ np.array(stiffener['centroid_xy_mm']))
    raw_ratio, ratio, margin = _distortional_area_witness(chi, sigma_as)
    # NO tolerance may promote an As_red/As < 1 into this pinned integral-As route.
    if ratio != 1.:
        raise ValueError('Eq5.17 requires reduced As: this proof must not fall back to full thickness')
    weighted = _weighted_retained_intervals(retained,
        [dict(chi_d=ratio, line_intervals=stiffener['line_intervals'])], t)
    J_weighted = sum((_line_integrals(nodes, tt, [(i,a,b)]) for i,a,b,tt in weighted), np.zeros((3,3)))
    if not np.allclose(J, J_weighted, rtol=3e-13, atol=1e-8):
        raise ValueError('Physical As partition double-applied or omitted material')
    As_final_audit = _interval_stresses(nodes, t, stiffener['line_intervals'], compression)
    if min(As_final_audit['min_line_compression_MPa'], As_final_audit['min_offset_face_compression_MPa']) <= 0.:
        raise ValueError('Physical As is not wholly compressed')

    unit_resultants = _pure_resultants_quadrature(nodes, t, retained, absolute_unit_coeff, cg)
    uls_resultants = _pure_resultants_quadrature(nodes, t, retained, signed_effort*absolute_unit_coeff, cg)
    expected = np.array([0., signed_effort, 0.])
    if not np.allclose(unit_resultants, [0.,1.,0.], rtol=0., atol=2e-13):
        raise ValueError('Pure unit Mx resultant check failed')
    if not np.allclose(uls_resultants, expected, rtol=0., atol=2e-8):
        raise ValueError('Pure ULS moment resultant check failed')
    full_audit = _interval_stresses(nodes, t, retained, compression)
    max_all = max(abs(v) for v in full_audit.values())
    if not math.isclose(max_all, fy, rel_tol=0., abs_tol=2e-10):
        raise ValueError('Final line/offset-face normalization failed')

    # Counterexamples quantify the defects the complete operator prevents.
    naive_y_only = np.array([-effective['centroid_xy_mm'][1]/Ix, 0., 1./Ix])
    no_constant_gross = np.array([-unit_gross_coeff[1:]@cg, *unit_gross_coeff[1:]])
    naive_resultants = _pure_resultants_quadrature(nodes,t,retained,signed_effort*naive_y_only,cg)
    missing_c0_resultants = _pure_resultants_quadrature(nodes,t,retained,signed_effort*no_constant_gross,cg)

    stiffener.update(kr_area=0., hw_mm=hw, K_N_mm2=K, sigma_cr_MPa=sig_cr,
        lambda_d=ld, chi_d=chi, sigma_com_Ed_MPa=sigma_as,
        Eq5_17_unclamped_As_ratio_at_ULS=raw_ratio, Eq5_17_As_red_over_As_at_ULS=ratio,
        Eq5_17_reduced_strength_minus_stress_MPa=margin, t_red_mm=t,
        stress_domain_audit=As_final_audit, step3_optional_refinement_used=False,
        integral_fixed_point=True,
        Eq5_17_reference='Pure-component ULS field, max absolute retained line/offset-face stress=fyb/gammaM0; stress at physical As centroid.',
        assembly_interpretation='Physical complete compressed lip plus the retained adjacent flange strip, with polygon corners included once; opposite flange/lip wholly tensile, kr=0.',
        centreline_interpretation='EN13 Eq5.17 centreline stress evaluated at centroid of effective physical As, as in the inherited stiffener-as-column model.')
    base.update(eligible=True, section_status='effective_local_flange_reduced_pure_Mx_ULS',
        sigma_coefficients_c0_cx_cy=unit_gross_coeff.tolist(),
        coefficient_origin='Original gross centroid; coefficients multiply SIGNED physical Mx.',
        effective_properties=effective,
        centroid_shift_from_gross_mm=[float(ex),float(ey)],
        effective_centroid_relative_to_gross_mm=[float(ex),float(ey)], moment_transport_required=False,
        additional_Mx_per_N_mm=0.,additional_My_per_N_mm=0.,
        effective_centroid_property_origin='Original pinned polygon coordinates; pure-Mx coefficients use gross-centred coordinates and N=My=0.',
        pure_moment_explanation='N=My=0 by complete section inversion. Centroid shift is already in c0; no extra N*e is introduced for this pure moment.',
        local_panels=[local[i] for i in range(5)], final_web_certificate=web_final,
        final_lip_certificate=lip_final, full_physical_panel_domain_audit=domain,
        local_flange_basis='EN13 5.5.2(3) gross psi=1, initial uniform fyb/gammaM0 local bound. No optional psi refinement. Final full physical compressed flange and lip lie below this bound.',
        retained_bands=bands_out, effective_line_intervals=retained,
        effective_weighted_line_intervals=weighted, stiffeners=[stiffener],
        ULS_pure_effort_signed=signed_effort,
        ULS_pure_effort_role='Pure-component polygon line/offset-face normalization only; NOT a design resistance.',
        ULS_max_abs_line_stress_MPa=max(abs(full_audit[k]) for k in ('min_line_compression_MPa','max_line_compression_MPa')),
        ULS_max_abs_line_or_face_stress_MPa=max_all,
        pure_ULS_compression_coefficients_absolute=compression.tolist(),
        effective_stress_domain_audit=full_audit,
        unit_resultants_N_Mx_My_about_gross=unit_resultants.tolist(),
        ULS_resultants_N_Mx_My_about_gross=uls_resultants.tolist(),
        distortional_stage='evaluated_on_local_flange_reduced_pure_Mx_ULS',
        proof='EN1993-1-3 5.5.2(3), 5.5.3.1 Eq5.10b/5.12, 5.5.3.2 Eq5.17 and 6.1.4.1; EN1993-1-5 4.4/Table4.1. Gross psi flange widths, final web/lip/As domains, exact Eq5.17 cap=1. Full effective inertia inversion with Ixy and c0, N=My=0. No service-stress law or optional refinements.',
        fixed_point_statement='Final local reduced section gives exactly min(1, chi_d*fyb/(gammaM0*sigma_As))=1. Retaining full As thickness therefore leaves section, stress field and ratio unchanged; local widths remain the prescribed gross-psi step-1 widths.',
        checks=dict(complete_inertia_inversion=True, independent_Gauss3_resultants=True,
            physical_As_subset_of_local_retained=True, physical_As_disjoint=True,
            all_weighted_thicknesses_equal_original_t=all(v[3]==t for v in weighted),
            As_ratio_cap_exactly_one_without_tolerance=ratio==1.,
            uniform_local_fyb_majorant=True, opposite_assembly_wholly_tensile=True,
            final_web_and_lip_integral=True,
            weighted_versus_unweighted_J_max_residual=float(np.max(abs(J-J_weighted))),
            full_inverse_versus_condensed_max_residual=float(np.max(abs(condensed-unit_gross_coeff)))),
        failure_counterexamples=dict(y_over_Ix_with_effective_centroid_resultants=naive_resultants.tolist(),
            full_gradients_but_omitted_gross_c0_resultants=missing_c0_resultants.tolist()),
        scope='Pinned Ue100x50x17 t1.20, ri=t, E210000, fyb=fya250, nu0.3, gammaM0=1. Polygon dA=t*ds only. No NBR whole-member approval, global stability, shear/torsion/warping, connections, solid fibre resistance or new material/geometries.')

    return base

def _uniform_web_reduced(base, nodes, t, gross, groups):
    """Uniform fyb ULS section; axial coefficient deliberately excludes N*e.

    Only the central flat web is removed. Physical As and the gross torsion
    contour are unchanged. Uniform stress makes Eq5.17 As_red/As=chi_d.
    """
    panels = base["local_panels"]
    rho = panels[2]["rho"]
    if not 0. < rho < 1. or any(panels[i]["rho"] != 1. for i in (0,1,3,4)):
        raise ValueError("Only a reduced web with integral flanges/lips is implemented")
    if len(base["stiffeners"]) != 2 or any(st["chi_d"] != 1. for st in base["stiffeners"]):
        raise ValueError("Both physical As require chi_d=1 under uniform ULS compression")
    refs = []; retained = []
    for j,g in enumerate(groups):
        bands = [(0.,rho/2.),(1.-rho/2.,1.)] if j == 2 else [(0.,1.)]
        local = []
        for i in g["ids"]:
            u = (nodes[i,g["axis"]]-g["lo"])/g["b_mm"]
            v = (nodes[i+1,g["axis"]]-g["lo"])/g["b_mm"]
            for a,b in bands:
                if abs(v-u) < 1e-14:
                    if a <= u <= b: local.append((i,0.,1.))
                else:
                    lo,hi = sorted(((a-u)/(v-u),(b-u)/(v-u)))
                    lo,hi = max(0.,lo),min(1.,hi)
                    if hi > lo: local.append((i,lo,hi))
        refs.extend(local)
        retained.append(dict(panel=g["panel"],projected_axis="xy"[g["axis"]],
            projected_width_mm=g["b_mm"],retained_fraction_bands=[list(v) for v in bands],
            retained_absolute_coordinate_bands_mm=[[g["lo"]+a*g["b_mm"],g["lo"]+b*g["b_mm"]] for a,b in bands],
            physical_line_intervals=[list(v) for v in local]))
    eff = _properties(_line_integrals(nodes,t,refs))
    cg = np.array(gross["centroid_xy_mm"]); raw = np.array(eff["centroid_xy_mm"])
    # Pin-verified contour is mirror-symmetric. Check the actual retained
    # facets too before imposing its exact symmetry identity ey=Ixy=0.
    reflected = nodes[::-1].copy(); reflected[:,1] = 2*cg[1]-reflected[:,1]
    mirror_error = float(np.max(abs(nodes-reflected)))
    original = sorted(refs)
    mirrored = sorted((len(nodes)-2-i,1.-hi,1.-lo) for i,lo,hi in refs)
    band_error = float(np.max(abs(np.array(original)-np.array(mirrored))))
    if mirror_error > 1e-10 or band_error > 1e-10 or abs(raw[1]-cg[1]) > 1e-10:
        raise ValueError("Retained geometry does not demonstrate exact horizontal symmetry")
    raw_Ixy = eff["Ixy_mm4"]
    if abs(raw_Ixy) > 1e-12*math.sqrt(eff["Ix_strong_mm4"]*eff["Iy_weak_mm4"]):
        raise ValueError("Effective inertia violates demonstrated symmetry")
    eff["centroid_xy_mm"][1] = float(cg[1]); eff["Ixy_mm4"] = 0.
    ex = float(raw[0]-cg[0]); A = eff["A_mm2"]
    if not 0. < A < gross["A_mm2"] or ex <= 0.:
        raise ValueError("Expected reduced area and positive physical centroid shift")
    for st in base["stiffeners"]:
        st.update(t_red_mm=t,step3_optional_refinement_used=False,
            assembly_interpretation="Actual lip plus adjacent retained flange half including polygon corners; uniform fyb compression, As_red/As=chi_d=1")
    base.update(eligible=True,section_status="effective_web_reduced_uniform_compression_ULS",
        sigma_coefficients_c0_cx_cy=[1./A,0.,0.],effective_properties=eff,
        ULS_pure_effort_signed=-A*MATERIAL["fyb_MPa"]/MATERIAL["gamma_M0"],
        centroid_shift_from_gross_mm=[ex,0.],effective_centroid_relative_to_gross_mm=[ex,0.],
        additional_Mx_per_N_mm=0.,additional_My_per_N_mm=ex,
        moment_transport_required=True,
        moment_transport="Mx_corr=Mx-N*ey; My_corr=My+N*ex; select flexural branches by corrected signs",
        sigma_N_contract="sigma_N=N/Aeff,N; no eccentricity or flexural gradient included; external moment transport is mandatory",
        effective_centroid_property_origin="Original pinned polygon coordinates; sigma_N is uniform in every coordinate origin.",
        retained_bands=retained,effective_line_intervals=[list(v) for v in refs],
        symmetry_audit=dict(gross_mirror_max_error_mm=mirror_error,retained_mirror_max_error=band_error,
            raw_effective_centroid_xy_mm=raw.tolist(),raw_ey_mm=float(raw[1]-cg[1]),raw_Ixy_mm4=raw_Ixy,
            identity="Pinned contour and retained strips mirror about y=Cg_y; hence ey=Ixy=0 exactly, without erasing ex"),
        uniform_unit_N_resultants_about_gross=[1.,0.,-ex],
        effective_stress_domain_audit=_interval_stresses(nodes,t,refs,np.array([250.,0.,0.])),
        proof="EN1993-1-3 6.1.3 uniform ULS compression; EN1993-1-5 Table4.1 psi=1 web effective strips; EN1993-1-3 5.5.3.2 physical As with chi_d=1. No service-stress reduction.",
        fixed_point_statement="Uniform compression determines the reduced web independently of N magnitude; retained flanges/lips and physical As remain integral. This is not an integral whole section.")
    return base


def _weighted_retained_intervals(refs, stiffeners, t):
    """Partition physical retained material; each As is a disjoint subset.

    The returned [segment, lo, hi, thickness_mm] records apply Eq.5.17 once.
    Their thickness is not an extra multiplier for an already-reduced area.
    """
    by_segment = {}
    for i, lo, hi in refs:
        if not 0. <= lo < hi <= 1.:
            raise ValueError("Invalid retained interval")
        by_segment.setdefault(i, []).append((lo, hi))
    for intervals in by_segment.values():
        ordered = sorted(intervals)
        if any(a[1] > b[0] for a,b in zip(ordered, ordered[1:])):
            raise ValueError("Overlapping retained intervals")
    assemblies = {}
    for st in stiffeners:
        chi = st["chi_d"]
        if not 0. < chi <= 1.:
            raise ValueError("Invalid distortional thickness factor")
        for i, lo, hi in st["line_intervals"]:
            if not 0. <= lo < hi <= 1. or not any(a <= lo+1e-12 and b >= hi-1e-12 for a,b in by_segment.get(i, [])):
                raise ValueError("Physical As is not a subset of retained local material")
            assemblies.setdefault(i, []).append((lo, hi, chi))
    for intervals in assemblies.values():
        ordered = sorted(intervals)
        if any(a[1] > b[0]+1e-12 for a,b in zip(ordered, ordered[1:])):
            raise ValueError("Overlapping physical As would double-apply reduction")
    weighted = []
    for i, lo, hi in refs:
        cuts = sorted({lo, hi} | {v for a,b,_ in assemblies.get(i, []) for v in (a,b) if lo < v < hi})
        for a,b in zip(cuts, cuts[1:]):
            mid = (a+b)/2
            factors = [chi for aa,bb,chi in assemblies.get(i, []) if aa < mid < bb]
            if len(factors) > 1:
                raise ValueError("Overlapping As thickness factors")
            weighted.append([i, a, b, t*(factors[0] if factors else 1.)])
    return weighted


def _uniform_local_distortional_reduced(base, nodes, t, gross, groups):
    """Pinned t1.20/1.50 uniform ULS, EN13 5.5.3.2 steps 1 and 2.

    Optional step 3 is not used. No service stress, iterative neutral-axis law,
    flexural coefficients or gross torsional properties are introduced here.
    """
    if t not in (1.2, 1.5) or base["action"] != "N_compression":
        raise ValueError("Only pinned thin uniform-compression branches are qualified")
    comp = np.array([MATERIAL["fyb_MPa"]/MATERIAL["gamma_M0"], 0., 0.])
    meta = {i:_internal_certificate(groups[i],t,[comp[0],comp[0]]) for i in (1,2,3)}
    for lip,flange in ((0,1),(4,3)):
        meta[lip] = _lip_certificate(groups[lip],groups[flange],t,[comp[0],comp[0]])
    if any(meta[i]["rho"] != 1. for i in (0,4)):
        raise ValueError("Reduced lips are outside the pinned thin axial branch")
    refs = []; retained = []
    for j,g in enumerate(groups):
        rho = meta[j]["rho"]
        if not 0. < rho <= 1.:
            raise ValueError("Invalid local effective width")
        bands = [(0.,1.)] if rho == 1. else [(0.,rho/2.),(1.-rho/2.,1.)]
        local = []
        for i in g["ids"]:
            u = (nodes[i,g["axis"]]-g["lo"])/g["b_mm"]
            v = (nodes[i+1,g["axis"]]-g["lo"])/g["b_mm"]
            for a,b in bands:
                if abs(v-u) < 1e-14:
                    if a <= u <= b: local.append((i,0.,1.))
                else:
                    lo,hi = sorted(((a-u)/(v-u),(b-u)/(v-u)))
                    lo,hi = max(0.,lo),min(1.,hi)
                    if hi > lo: local.append((i,lo,hi))
        refs.extend(local)
        retained.append(dict(panel=g["panel"],projected_axis="xy"[g["axis"]],
            projected_width_mm=g["b_mm"],retained_fraction_bands=[list(v) for v in bands],
            retained_absolute_coordinate_bands_mm=[[g["lo"]+a*g["b_mm"],g["lo"]+b*g["b_mm"]] for a,b in bands],
            physical_line_intervals=[list(v) for v in local]))
    stiff = [_stiffener(nodes,t,groups[l],groups[f],meta[f],comp) for l,f in ((0,1),(4,3))]
    Jlocal = _line_integrals(nodes,t,refs); J = Jlocal.copy()
    for st,other in zip(stiff,stiff[::-1]):
        b1,b2 = st["b1_mm"],other["b1_mm"]
        hw = float(np.ptp(nodes[:,1])); kr = other["As_mm2"]/st["As_mm2"]
        K = MATERIAL["E_MPa"]*t**3/(4*(1-MATERIAL["nu"]**2))/(b1*b1*hw+b1**3+.5*b1*b2*hw*kr)
        critical = 2*math.sqrt(K*MATERIAL["E_MPa"]*st["Is_mm4"])/st["As_mm2"]
        ld = math.sqrt(MATERIAL["fyb_MPa"]/critical)
        chi = 1. if ld <= .65 else 1.47-.723*ld if ld < 1.38 else .66/ld
        raw_ratio,ratio,margin = _distortional_area_witness(chi,st["sigma_com_Ed_MPa"])
        if not math.isclose(ratio,chi,rel_tol=0.,abs_tol=2e-16):
            raise ValueError("Uniform ULS must give As_red/As=chi_d")
        st.update(kr_area=kr,hw_mm=hw,K_N_mm2=K,sigma_cr_MPa=critical,
            lambda_d=ld,chi_d=chi,Eq5_17_As_red_over_As_at_ULS=ratio,
            Eq5_17_unclamped_As_ratio_at_ULS=raw_ratio,
            Eq5_17_reduced_strength_minus_stress_MPa=margin,
            Eq5_17_reference="Uniform pure compression ULS at fyb/gammaM0 on all retained physical material.",
            integral_fixed_point=False,t_red_mm=t*chi,step3_optional_refinement_used=False,
            assembly_interpretation="Actual complete lip and only the effective flange strip adjacent to it, including physical polygon corners; uniform fyb ULS, reduced once by chi_d.")
        J -= (1.-chi)*_line_integrals(nodes,t,st["line_intervals"])
    weighted = _weighted_retained_intervals(refs,stiff,t)
    Jweighted = sum((_line_integrals(nodes,tt,[(i,a,b)]) for i,a,b,tt in weighted),np.zeros((3,3)))
    if not np.allclose(J,Jweighted,rtol=2e-13,atol=1e-8):
        raise ValueError("Weighted integration disagrees with single As subtraction")
    eff = _properties(Jweighted)
    cg = np.array(gross["centroid_xy_mm"]); raw = np.array(eff["centroid_xy_mm"])
    reflected = nodes[::-1].copy(); reflected[:,1] = 2*cg[1]-reflected[:,1]
    mirror_error = float(np.max(abs(nodes-reflected)))
    mirrored = sorted([len(nodes)-2-i,1.-b,1.-a,tt] for i,a,b,tt in weighted)
    ordered = sorted(weighted)
    if len(mirrored) != len(ordered):
        raise ValueError("Weighted interval mirror cardinality mismatch")
    mirror_delta = np.abs(np.array(ordered)-np.array(mirrored))
    band_error = float(np.max(mirror_delta[:,:3])); thickness_error = float(np.max(mirror_delta[:,3]))
    raw_Ixy = eff["Ixy_mm4"]
    if mirror_error > 1e-10 or band_error > 1e-10 or thickness_error > 1e-12 or abs(raw[1]-cg[1]) > 1e-10:
        raise ValueError("Retained geometry and thickness do not demonstrate horizontal symmetry")
    if abs(raw_Ixy) > 1e-12*math.sqrt(eff["Ix_strong_mm4"]*eff["Iy_weak_mm4"]):
        raise ValueError("Effective weighted inertia violates demonstrated symmetry")
    eff["centroid_xy_mm"][1] = float(cg[1]); eff["Ixy_mm4"] = 0.
    ex = float(raw[0]-cg[0]); A = eff["A_mm2"]
    if not 0. < A < Jlocal[0,0] < gross["A_mm2"] or ex <= 0.:
        raise ValueError("Expected local and distortional area reductions and positive centroid shift")
    base.update(eligible=True,section_status="effective_local_distortional_reduced_uniform_compression_ULS",
        sigma_coefficients_c0_cx_cy=[1./A,0.,0.],effective_properties=eff,
        ULS_pure_effort_signed=-A*comp[0],ULS_max_abs_line_stress_MPa=float(comp[0]),
        local_panels=[meta[i] for i in range(5)],stiffeners=stiff,
        distortional_stage="uniform_ULS_steps1_2_physical_As_thickness_reduction",
        centroid_shift_from_gross_mm=[ex,0.],effective_centroid_relative_to_gross_mm=[ex,0.],
        additional_Mx_per_N_mm=0.,additional_My_per_N_mm=ex,moment_transport_required=True,
        moment_transport="Mx_corr=Mx-N*ey; My_corr=My+N*ex; select flexural branches by corrected signs",
        sigma_N_contract="sigma_N=N/Aeff,N; no eccentricity or flexural gradient included; external moment transport is mandatory",
        effective_centroid_property_origin="Original pinned polygon coordinates; sigma_N is uniform in every coordinate origin.",
        retained_bands=retained,effective_line_intervals=[list(v) for v in refs],
        effective_weighted_line_intervals=weighted,
        effective_weighted_line_interval_columns=["segment_index","lo_fraction","hi_fraction","thickness_mm"],
        local_only_properties=_properties(Jlocal),
        distortional_reduction_audit=dict(physical_As_subset_of_local_retained=True,physical_As_disjoint=True,
            thickness_reduction_applied_once=True,step3_optional_refinement_used=False,
            subtraction_vs_weighted_max_residual=float(np.max(abs(J-Jweighted)))),
        symmetry_audit=dict(gross_mirror_max_error_mm=mirror_error,retained_mirror_max_error=band_error,
            retained_thickness_mirror_max_error_mm=thickness_error,
            raw_effective_centroid_xy_mm=raw.tolist(),raw_ey_mm=float(raw[1]-cg[1]),raw_Ixy_mm4=raw_Ixy,
            identity="Pinned contour, retained intervals and their thicknesses mirror about y=Cg_y; hence ey=Ixy=0 exactly, without erasing ex"),
        uniform_unit_N_resultants_about_gross=[1.,0.,-ex],
        effective_stress_domain_audit=_interval_stresses(nodes,t,refs,comp),
        proof="EN1993-1-3 6.1.3 uniform ULS compression; EN1993-1-5 Table4.1 psi=1 effective web/flange strips; EN1993-1-3 5.5.3.2 steps1-2, Eq5.17 and (12): t_red=t*chi_d only on disjoint physical As retained in local section. Optional step3 omitted. No service-stress reduction.",
        fixed_point_statement="Uniform ULS compression determines local widths and As reduction independently of N magnitude or centroid. Steps1-2 are used without optional step3 refinement; this is not an integral effective section.")
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
    result = {"schema":SCHEMA,"method_revision":"remaining_t120_pure_moments_face_ULS_20261105",
        "profile_id":profile["profile_id"],"nodes_sha256":sha,
        "thickness_mm":t,"material":dict(MATERIAL),"gross_properties":props,
        "coordinate_system":"xy_R01 relative to gross centroid",
        "stress_convention":"Positive sigma/N=tension; sigma=c0+cx*x+cy*y per SIGNED physical action. Mx multiplies +y, My multiplies -x.",
        "frame_mapping":"Mx_R01=-My_frame; My_R01=-Mz_frame",
        "normal_yield_limit_MPa":fya_MPa/gamma_M0,"components":components,
        "all_normal_components_eligible":all(v["eligible"] for v in components.values()),
        "physical_geometry_verified":False,"whole_member_approved":False,
        "source_basis":["EN1993-1-3:2006 3.2.1(5),5.1,5.2,5.5,6.1.2,6.1.3,6.1.4,6.1.6(3)",
                        "EN1993-1-5:2006 4.4/Table4.1/Table4.2; EN1993-1-1:2005 3.2.6"],
        "not_checked":["net-section fracture/fasteners/connections","shear and shear-normal interaction",
            "global member stability and second-order effects","coupled modes with translation of panel junctions outside the stated panel/stiffener models","shear lag and flange curling applicability",
            "solid/exterior-fibre stress","material certification/coating/core-thickness tolerance",
            "warping B component (must use the SAME pinned gross omega/Cw externally)"]}
    result["content_sha256"] = _canonical_sha(result)
    return result


def verify_component_sections(certificate):
    """Check schema/self-hash only, not independent operator authority.

    The v6 reader separately binds the complete certificate to the local
    qualified-reference registry, even without optional EN6.27 records.
    """
    candidate = copy.deepcopy(certificate); expected = candidate.pop("content_sha256",None)
    if candidate.get("schema") not in (SCHEMA, MY150_SCHEMA, AXIAL_SCHEMA, PREVIOUS_SCHEMA, LEGACY_SCHEMA) or expected != _canonical_sha(candidate):
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
