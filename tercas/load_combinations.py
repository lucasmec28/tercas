"""Fixed user-supplied combinations and characteristic area-load conversion.

No material/resistance checks here. Positive load is downward; wind inputs are
nonnegative magnitudes. Linear effects may be superposed; utilization and ELS
deflection with load-dependent effective inertia must be recalculated per case.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

GRAVITY_M_S2 = 9.80665
COMBINATION_TYPES = (
    "ELU normal", "ELS rara", "ELS frequente", "ELS quase permanente",
)
CASE_IDS = ("PP", "CP", "SC", "V_Cima", "V_Baixo")
TABLE_PATH = Path(__file__).parent / "data" / "combinations_lucas_20261031.json"


def _number(value, label, *, positive=False, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label}: informe um número finito.")
    value = float(value)
    if positive and value <= 0:
        raise ValueError(f"{label}: deve ser positivo.")
    if nonnegative and value < 0:
        raise ValueError(f"{label}: informe o módulo, sem sinal negativo.")
    return value


def fixed_combinations(selected_types=None):
    """Return new objects in the original order, filtered by the four labels.

    None means all; [] means none. No numeric duplicate removal: identical
    factors under different requested ELS families retain their identities.
    """
    if selected_types is None:
        selected_types = list(COMBINATION_TYPES)
    if not isinstance(selected_types, (list, tuple)) or any(
        not isinstance(t, str) or t not in COMBINATION_TYPES for t in selected_types
    ):
        raise ValueError("Tipo de combinação não reconhecido.")
    if len(set(selected_types)) != len(selected_types):
        raise ValueError("Tipos de combinações repetidos.")
    table = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
    records = table["combinations"]
    expected = {"ELU normal": 32, "ELS rara": 8, "ELS frequente": 6,
                "ELS quase permanente": 2}
    if table.get("schema") != "tercas_fixed_combinations_v1" or len(records) != 48:
        raise ValueError("Tabela de combinações incompleta.")
    if len({r["id"] for r in records}) != 48:
        raise ValueError("Identificadores de combinações repetidos.")
    for typ, count in expected.items():
        if sum(r["type"] == typ for r in records) != count:
            raise ValueError("Contagem de combinações incompatível com a fonte.")
    for r in records:
        coeff = r["coefficients"]
        if r["type"] not in COMBINATION_TYPES or set(coeff) - set(CASE_IDS):
            raise ValueError("Caso ou família de combinação inválido.")
        if r["limit_state"] != ("ELU" if r["type"] == "ELU normal" else "ELS"):
            raise ValueError("Estado-limite incompatível com a família.")
        if "V_Cima" in coeff and "V_Baixo" in coeff:
            raise ValueError("Vento para cima e para baixo são alternativas incompatíveis.")
        if set(("PP", "CP")) - set(coeff):
            raise ValueError("Combinação sem as ações permanentes da fonte.")
        for c in coeff.values():
            _number(c, "Coeficiente", positive=True)
    return copy.deepcopy([r for r in records if r["type"] in selected_types])


def characteristic_area_cases(*, spacing_m, permanent_kgf_m2,
                              live_kgf_m2, wind_up_kgf_m2,
                              wind_down_kgf_m2, mass_kg_m):
    """Convert tributary area pressure and catalog mass into signed kN/m.

    For the app's mm/N units the returned kN/m is numerically N/mm. Spacing is
    the tributary width declared by the user: this function does not infer half
    widths, roof projection or inclined load components.
    """
    width = _number(spacing_m, "Distância entre terças", positive=True)
    mass = _number(mass_kg_m, "Massa linear do perfil", positive=True)
    pressures = {
        "CP": _number(permanent_kgf_m2, "Carga permanente", nonnegative=True),
        "SC": _number(live_kgf_m2, "Sobrecarga", nonnegative=True),
        "V_Cima": _number(wind_up_kgf_m2, "Vento para cima", nonnegative=True),
        "V_Baixo": _number(wind_down_kgf_m2, "Vento para baixo", nonnegative=True),
    }
    result = {"PP": mass * GRAVITY_M_S2 / 1000.0}
    for case, p in pressures.items():
        result[case] = p * width * GRAVITY_M_S2 / 1000.0 * (-1 if case == "V_Cima" else 1)
    if not all(math.isfinite(x) for x in result.values()):
        raise ValueError("A conversão das cargas excedeu o intervalo numérico.")
    return result


def uniform_effects(q_N_mm, L_mm, x_mm=None):
    """Signed static effects of full-span UDL on a simply supported beam.

    R is upward-positive for downward-positive q; positive bending is sagging.
    Values at x keep signs. Maxima are not combined independently.
    """
    q = _number(q_N_mm, "Carga linear")
    L = _number(L_mm, "Vão", positive=True)
    if x_mm is None:
        x_mm = L / 2.0
    x = _number(x_mm, "Posição")
    if not 0 <= x <= L:
        raise ValueError("Posição fora do vão.")
    R = q * L / 2.0
    values = {"left_reaction_N": R, "right_reaction_N": R,
              "V_N": R - q * x, "M_Nmm": q * x * (L - x) / 2.0,
              "midspan_moment_Nmm": q * L * L / 8.0,
              "max_abs_shear_N": abs(R)}
    if not all(math.isfinite(v) for v in values.values()):
        raise ValueError("Os esforços excederam o intervalo numérico.")
    return values


def combine_area_actions(*, L_mm, selected_types=None, **area_inputs):
    """Build only the requested combinations and their signed linear effects.

    Every row must be independently evaluated for resistance and deflection by
    the caller. No fictitious zero ELU/ELS is created for an unselected family.
    No concentrated load is automatically added to the user-supplied matrix.
    """
    L = _number(L_mm, "Vão", positive=True)
    cases = characteristic_area_cases(**area_inputs)
    base_effects = {case: uniform_effects(q, L) for case, q in cases.items()}
    records = []
    for combo in fixed_combinations(selected_types):
        coeff = combo["coefficients"]
        q = math.fsum(coeff.get(c, 0.0) * cases[c] for c in CASE_IDS)
        effects = {
            key: math.fsum(coeff.get(c, 0.0) * base_effects[c][key] for c in CASE_IDS)
            for key in ("left_reaction_N", "right_reaction_N", "V_N",
                        "M_Nmm", "midspan_moment_Nmm")
        }
        # An absolute maximum is taken after combining signed effects.
        effects["max_abs_shear_N"] = abs(effects["left_reaction_N"])
        direct = uniform_effects(q, L)
        for key in effects:
            if not math.isclose(effects[key], direct[key], rel_tol=1e-11, abs_tol=1e-7):
                raise ValueError("Inconsistência na superposição dos esforços.")
        combo.update(q_N_mm=q, q_kN_m=q, P_N=0.0, x_mm=L/2.0,
                     sign="descendente" if q > 0 else "ascendente" if q < 0 else "nulo",
                     effects_at_midspan=effects,
                     expression=" + ".join(f"{factor:g} {case}" for case, factor in coeff.items()),
                     origin="Matriz de 48 combinações fornecida por Lucas em 31/10/2026")
        records.append(combo)
    return {"schema": "tercas_area_actions_v1", "L_mm": L,
            "inputs": copy.deepcopy(area_inputs), "case_q_N_mm": cases,
            "case_effects_at_midspan": base_effects, "combinations": records,
            "notes": ["PP somado uma única vez, a partir da massa linear do perfil.",
                      "Vento para cima é negativo; os dois sentidos nunca coexistem na mesma combinação.",
                      "Dimensionamento e flecha devem ser recalculados para cada combinação.",
                      "Esta matriz reproduz a escolha fornecida pelo usuário, não é gerador normativo universal."]}
