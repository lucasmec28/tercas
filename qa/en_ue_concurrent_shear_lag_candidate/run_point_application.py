"""Regenerate four synthetic point-load application fixtures from their recipe.

This is a recovered recipe, not a reconstruction of the lost output bytes.
Running main() performs NEW original-application member solves, serially. The
subsequent candidate calculation and saved-record replay forbid new solves.
The current application dispatcher is used; no production source is modified.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
from time import perf_counter


OUTPUT = Path(__file__).resolve().parent
REPOSITORY = OUTPUT.parents[1]
MODEL_ORIGIN = "Synthetic concurrent candidate point-load application QA"
KIND = "SYNTHETIC_POINT_APPLICATION_NOT_USER_PROJECT_DATA"

# The final original recipe used N/mm for q, N for P, mm for positions.
# Earlier exploratory tiny P values are deliberately not used here.
CASES = (
    ("P_interior", 0.03, 12.0, 1742.5, 5.71),
    ("P_reversed", -0.22, -12.0, 1742.5, -5.71),
    ("P_near_left", 0.03, 12.0, 82.0, 5.71),
    ("P_opposes_uniform", 0.03, -300.0, 2050.0, 5.71),
)


def _write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_gzip(path, value):
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(gzip.compress(raw, mtime=0))
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Replace existing generated fixtures with a newly executed run.",
    )
    args = parser.parse_args()
    targets = [OUTPUT / (name + ".json.gz") for name, *_ in CASES]
    targets.append(OUTPUT / "point_application_summary.json")
    existing = [str(path) for path in targets if path.exists()]
    if existing and not args.overwrite:
        raise FileExistsError(
            "Existing generated outputs were not changed. Use --overwrite for "
            "an intentional new execution: " + ", ".join(existing)
        )

    # Set before NumPy/SciPy/application imports, matching the original run.
    os.environ["OPENBLAS_CORETYPE"] = "Haswell"
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[name] = "1"
    sys.path.insert(0, str(REPOSITORY))
    sys.path.insert(0, str(REPOSITORY / "tests"))

    from en_ue_test_helpers import inputs, run
    from tercas import ue_catalog_reference as own
    from tercas import isolated_en_ue_family_application as app
    from tercas import isolated_en_ue_family as legacy
    from tercas import isolated_en_ue_concurrent_candidate as candidate
    from tercas.en_ue_catalog_operators import _sha
    from tercas.torsion_vlasov import vlasov

    summary = {
        "kind": "FOUR_SYNTHETIC_DIRECT_APPLICATIONS_WITH_POINT_LOADS",
        "recipe_recovered_output_bytes_not_recovered": True,
        "execution_started_utc": datetime.now(timezone.utc).isoformat(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "candidate_technical_source_sha256": candidate.source_binding(),
        "new_application_solve_executed": False,
        "candidate_and_replay_new_solve_called": False,
        "production_source_files_modified_by_generator": False,
        "complete": False,
        "records": [],
    }
    _write_json(OUTPUT / "point_application_summary.json", summary)

    for name, q, point_force, station, angle in CASES:
        started = perf_counter()
        data = inputs(53, L=4100.0, angle=angle)
        data.update(
            q_uls=q,
            P_uls=point_force,
            x_uls=station,
            q_sls=q / 1.5,
            P_sls=point_force / 1.5,
            x_sls=station,
        )
        data["properties"].update(fy_MPa=300.0, fu_MPa=450.0)
        data = own.activate(data)
        data = app.activate(data, model_origin=MODEL_ORIGIN)

        # This is the only step that generates new application demand fields.
        original = run(data)
        summary["new_application_solve_executed"] = True
        before = _sha(original)
        saved = app.preserved(original)
        normal = saved["normal_snapshot"]
        application_check = saved["records"][0]["check"]
        if application_check is None:
            raise AssertionError(saved["records"][0])
        demand = application_check["source_demand"]

        states = []
        for index, element in enumerate(demand["elements"]):
            if element["b_mm"] == station:
                states.append(vlasov.evaluate(demand, index, 1.0))
            if element["a_mm"] == station:
                states.append(vlasov.evaluate(demand, index, 0.0))
        assert len(states) == 2
        assert {state["side"] for state in states} == {"left", "right"}
        left, right = sorted(states, key=lambda state: state["side"])
        point = next(action for action in demand["loads"] if action["kind"] == "point")
        for axis, key in enumerate(("Vx_N", "Vy_N")):
            assert abs(right[key] - left[key] + point["force_xy_N"][axis]) < 1e-10

        solve = vlasov.solve_member

        def forbidden(*_args, **_kwargs):
            raise AssertionError("Candidate/replay must not call a member solver")

        vlasov.solve_member = forbidden
        try:
            check = candidate.calculate(
                demand, normal_snapshot=normal,
                model_origin=application_check["model_origin"],
            )
            replay = candidate.validate_saved(
                check, legacy._compact_source(demand),
                normal_snapshot=normal, source_sha256=_sha(demand),
                model_origin=application_check["model_origin"],
            )
        finally:
            vlasov.solve_member = solve

        proof = check.get("concurrent_shear_lag_supplement", {})
        state_keys = (
            "s_mm", "side", "Vx_N", "Vy_N", "Mx_physical_Nmm",
            "My_physical_Nmm", "B_Nmm2", "T_Nmm",
        )
        receipt = {
            "name": name,
            "catalog_index": 53,
            "q_uls": q,
            "P_uls": point_force,
            "x_uls": station,
            "inclination_degrees": angle,
            "application_check_schema": application_check["schema"],
            "candidate_schema": check["schema"],
            "status": check["component_status"],
            "saved_replay_valid": replay,
            "proof_eligible": proof.get("eligible"),
            "source_unchanged": _sha(original) == before,
            "ceiling_MPa": proof.get("integral_local_D_design_ceiling_MPa"),
            "stress_bound_MPa": proof.get("simultaneous_normal_stress_upper_MPa"),
            "blocking_reasons": proof.get("blocking_reasons"),
            "point_sides": [
                {key: state[key] for key in state_keys} for state in states
            ],
            "signed_branches": proof.get("required_signed_branches"),
            "whole_member_approved": False,
            "physical_design_approved": False,
            "elapsed_seconds": perf_counter() - started,
        }
        assert replay and receipt["source_unchanged"]
        assert all(check[flag] is False for flag in legacy.FALSE_FLAGS)
        payload = {
            "kind": KIND,
            "application_snapshot": original,
            "candidate_check": check,
            "receipt": receipt,
        }
        target = OUTPUT / (name + ".json.gz")
        _write_gzip(target, payload)
        summary["records"].append(receipt)
        _write_json(OUTPUT / "point_application_summary.json", summary)
        print(json.dumps(receipt, ensure_ascii=False, allow_nan=False), flush=True)

    summary["complete"] = True
    summary["execution_finished_utc"] = datetime.now(timezone.utc).isoformat()
    summary["generated_file_sha256"] = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in targets if path.suffix == ".gz"
    }
    _write_json(OUTPUT / "point_application_summary.json", summary)


if __name__ == "__main__":
    main()
