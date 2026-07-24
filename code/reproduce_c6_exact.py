#!/usr/bin/env python3
"""Reconstruct the paper-facing C6 exact paired analysis."""

from __future__ import annotations

import argparse
import csv
import itertools
import math
from collections import defaultdict
from pathlib import Path

import numpy as np


PAPER_ENDPOINTS = (
    ("all_frame_dice", "frame_sequence_mean", "all_frames", "dice"),
    ("target_positive_dice", "frame_sequence_mean", "target_positive_frames", "dice"),
    (
        "all_frame_boundary_iou",
        "frame_sequence_mean",
        "all_frames",
        "boundary_iou",
    ),
    ("sequence_mean_dice", "sequence", "all_sequences", "mean_dice"),
    (
        "false_positive_frames",
        "sequence",
        "all_sequences",
        "false_positive_frames",
    ),
    (
        "prediction_fragments",
        "sequence",
        "all_sequences",
        "prediction_fragment_count",
    ),
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"cannot write an empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def sign_matrix(n: int) -> np.ndarray:
    if n > 20:
        raise ValueError("exact sign enumeration is capped at 20 pairs")
    return np.asarray(
        list(itertools.product((-1.0, 1.0), repeat=n)),
        dtype=np.float64,
    )


def exact_p_value(delta: np.ndarray, theta: float = 0.0) -> float:
    centered = np.asarray(delta, dtype=np.float64) - float(theta)
    signs = sign_matrix(centered.size)
    observed = abs(float(centered.mean()))
    randomized = np.abs((signs * centered).mean(axis=1))
    tolerance = np.finfo(np.float64).eps * max(1.0, observed) * 32.0
    return float(np.mean(randomized >= observed - tolerance))


def invert_exact_signflip(
    delta: np.ndarray,
    *,
    alpha: float = 0.05,
) -> tuple[float, float, int]:
    values = np.asarray(delta, dtype=np.float64)
    signs = sign_matrix(values.size)
    mean_delta = float(values.mean())
    mean_sign = signs.mean(axis=1)
    mean_signed_delta = (signs * values).mean(axis=1)

    roots: list[float] = []
    denominator = 1.0 - mean_sign
    valid = np.abs(denominator) > 1e-14
    roots.extend(
        ((mean_delta - mean_signed_delta[valid]) / denominator[valid]).tolist()
    )
    denominator = 1.0 + mean_sign
    valid = np.abs(denominator) > 1e-14
    roots.extend(
        ((mean_signed_delta[valid] + mean_delta) / denominator[valid]).tolist()
    )
    transitions = np.unique(np.round(np.asarray(roots, dtype=np.float64), 15))
    if transitions.size == 0:
        return -math.inf, math.inf, 0

    span = max(1.0, float(np.ptp(values)), abs(mean_delta)) * 4.0
    extended = np.concatenate(
        ([transitions[0] - span], transitions, [transitions[-1] + span])
    )
    accepted: list[float] = []
    for value in transitions:
        if exact_p_value(values, float(value)) >= alpha - 1e-15:
            accepted.append(float(value))
    for lower, upper in zip(extended[:-1], extended[1:]):
        midpoint = float((lower + upper) / 2.0)
        if exact_p_value(values, midpoint) >= alpha - 1e-15:
            accepted.extend((float(lower), float(upper)))
    if not accepted:
        raise RuntimeError("the exact confidence set is empty")
    lower = min(accepted)
    upper = max(accepted)
    if lower == extended[0] or upper == extended[-1]:
        raise RuntimeError("an unbounded confidence set requires explicit handling")
    return lower, upper, int(signs.shape[0])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inference-csv", type=Path, required=True)
    parser.add_argument("--effects-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-a", default="absence_and_run_length")
    parser.add_argument("--model-b", default="run_length_5")
    args = parser.parse_args()

    inference = read_csv(args.inference_csv)
    effects = read_csv(args.effects_csv)
    if len(inference) != 930:
        raise ValueError(f"expected 930 inference rows, found {len(inference)}")

    by_hypothesis: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in effects:
        by_hypothesis[row["hypothesis_id"]].append(row)

    endpoint_rows: list[dict[str, object]] = []
    sequence_rows: dict[str, dict[str, object]] = {}
    for endpoint_id, scope, stratum, metric in PAPER_ENDPOINTS:
        matches = [
            row
            for row in inference
            if row["model_a"] == args.model_a
            and row["model_b"] == args.model_b
            and (row["scope"], row["stratum"], row["metric"])
            == (scope, stratum, metric)
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"expected one inference row for {endpoint_id}, found {len(matches)}"
            )
        row = matches[0]
        endpoint_effects = sorted(
            by_hypothesis[row["hypothesis_id"]],
            key=lambda item: item["sequence_id"],
        )
        if len(endpoint_effects) != 8:
            raise RuntimeError(f"{endpoint_id} does not contain eight sequences")
        delta = np.asarray([float(item["delta"]) for item in endpoint_effects])
        exact_p = exact_p_value(delta)
        if not math.isclose(exact_p, float(row["p_value"]), abs_tol=1e-15):
            raise RuntimeError(f"exact p-value mismatch for {endpoint_id}")
        ci_lower, ci_upper, assignments = invert_exact_signflip(delta)
        endpoint_rows.append(
            {
                "model_a": args.model_a,
                "model_b": args.model_b,
                "endpoint_id": endpoint_id,
                "hypothesis_id": row["hypothesis_id"],
                "scope": scope,
                "stratum": stratum,
                "metric": metric,
                "sequence_units": 8,
                "mean_a": float(row["mean_a"]),
                "mean_b": float(row["mean_b"]),
                "mean_delta": float(row["mean_delta"]),
                "exact_ci95_lower": ci_lower,
                "exact_ci95_upper": ci_upper,
                "exact_p_value": exact_p,
                "p_value_bh_full_family": float(row["p_value_bh"]),
                "bh_hypothesis_count": len(inference),
                "sign_assignments": assignments,
                "bootstrap_ci95_lower_descriptive": float(row["ci95_lower"]),
                "bootstrap_ci95_upper_descriptive": float(row["ci95_upper"]),
                "bootstrap_iterations": int(row["iterations"]),
                "bootstrap_seed": int(row["seed"]),
            }
        )
        for item in endpoint_effects:
            sequence_id = item["sequence_id"]
            target = sequence_rows.setdefault(
                sequence_id,
                {
                    "model_a": args.model_a,
                    "model_b": args.model_b,
                    "sequence_id": sequence_id,
                },
            )
            target[f"{endpoint_id}_a"] = float(item["value_a"])
            target[f"{endpoint_id}_b"] = float(item["value_b"])
            target[f"{endpoint_id}_delta"] = float(item["delta"])

    family_rows = [
        {
            "hypothesis_id": row["hypothesis_id"],
            "model_a": row["model_a"],
            "model_b": row["model_b"],
            "scope": row["scope"],
            "stratum": row["stratum"],
            "metric": row["metric"],
            "sequence_units": int(row["sequence_units"]),
            "exact_p_value": float(row["p_value"]),
            "p_value_bh": float(row["p_value_bh"]),
        }
        for row in inference
    ]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "c6_endpoints_exact.csv", endpoint_rows)
    write_csv(
        args.output_dir / "c6_sequence_effects.csv",
        [sequence_rows[key] for key in sorted(sequence_rows)],
    )
    write_csv(args.output_dir / "c6_hypothesis_family.csv", family_rows)
    print(
        "WROTE "
        f"endpoints={len(endpoint_rows)} "
        f"sequences={len(sequence_rows)} "
        f"family={len(family_rows)}"
    )


if __name__ == "__main__":
    main()
