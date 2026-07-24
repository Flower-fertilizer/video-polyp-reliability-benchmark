#!/usr/bin/env python3
"""Verify integrity, portability, privacy boundaries, and headline results."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKSUMS = ROOT / "SHA256SUMS"
CHECKPOINTS = ROOT / "CHECKPOINTS.json"
RESULTS_INDEX = ROOT / "evidence/results_index.csv"

TEXT_SUFFIXES = {".csv", ".json", ".md", ".py", ".txt"}
RAW_OR_UNDECLARED_BINARY_SUFFIXES = {
    ".7z",
    ".avi",
    ".ckpt",
    ".gif",
    ".har",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp4",
    ".npy",
    ".npz",
    ".onnx",
    ".pdf",
    ".png",
    ".pt",
    ".pth",
    ".safetensors",
    ".svg",
    ".tar",
    ".zip",
}
FORBIDDEN_TEXT = (
    re.compile(r"/home/[^/\\s]+/"),
    re.compile(r"/data/[^\\s,;]+"),
    re.compile(r"\\$\\{PROJECT_ROOT\\}"),
    re.compile(r"research_logs/"),
    re.compile(r"(?<![A-Za-z_])output/"),
    re.compile(r"(?i)authorization\\s*:\\s*bearer"),
    re.compile(r"(?i)password\\s*[=:]"),
    re.compile(r"hf_[A-Za-z0-9]{16,}"),
    re.compile(r"(?i)\\bevidence_path\\b"),
    re.compile(r"(?i)\\bgate_pass_fail_matrix\\b"),
    re.compile(r"(?i)\\bfinal_evidence_table\\b"),
    re.compile(r"(?i)\\breproducibility_manifest\\b"),
    re.compile(r"(?i)\\bresearch_state\\.yaml\\b"),
    re.compile(r"(?i)\\bgenerated_at(?:_utc)?\\b"),
    re.compile(r"(?i)\\bruntime_seconds\\b"),
    re.compile(r"(?i)\\bstate_revision\\b"),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def close(actual: float | str, expected: float, atol: float = 1e-12) -> None:
    value = float(actual)
    require(
        math.isclose(value, expected, rel_tol=0.0, abs_tol=atol),
        f"{value} != {expected}",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(relative: str) -> list[dict[str, str]]:
    path = ROOT / relative
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    require(rows, f"empty CSV: {relative}")
    require(
        None not in rows[0],
        f"malformed CSV header or row width: {relative}",
    )
    return rows


def select(rows: list[dict[str, str]], **where: object) -> dict[str, str]:
    matches = [
        row
        for row in rows
        if all(row.get(key) == str(value) for key, value in where.items())
    ]
    require(len(matches) == 1, f"expected one row for {where}, found {len(matches)}")
    return matches[0]


def checkpoint_records() -> list[dict[str, object]]:
    payload = json.loads(CHECKPOINTS.read_text(encoding="utf-8"))
    records = payload.get("artifacts")
    require(isinstance(records, list) and len(records) == 2, "checkpoint manifest mismatch")
    return records


def declared_checkpoint_paths() -> set[Path]:
    return {
        (ROOT / str(record["repository_path"])).resolve()
        for record in checkpoint_records()
    }


def public_file_set() -> set[str]:
    checkpoint_set = declared_checkpoint_paths()
    return {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file()
        and path != CHECKSUMS
        and path.resolve() not in checkpoint_set
        and ".git" not in path.parts
        and "__pycache__" not in path.parts
    }


def verify_checksums() -> int:
    require(CHECKSUMS.is_file(), "SHA256SUMS is missing")
    records: dict[str, str] = {}
    for line in CHECKSUMS.read_text(encoding="utf-8").splitlines():
        require("  " in line, f"malformed checksum line: {line}")
        expected, relative = line.split("  ", 1)
        require(
            re.fullmatch(r"[0-9a-f]{64}", expected) is not None,
            f"invalid digest: {relative}",
        )
        require(relative not in records, f"duplicate checksum path: {relative}")
        path = ROOT / relative
        require(path.is_file(), f"missing checksummed file: {relative}")
        require(sha256(path) == expected, f"checksum mismatch: {relative}")
        records[relative] = expected
    require(set(records) == public_file_set(), "SHA256SUMS does not match public files")
    return len(records)


def verify_portability_and_privacy() -> int:
    declared = declared_checkpoint_paths()
    scanned = 0
    for path in ROOT.rglob("*"):
        if not path.is_file() or path == CHECKSUMS or ".git" in path.parts:
            continue
        if path.resolve() in declared:
            continue
        relative = path.relative_to(ROOT)
        require(
            re.match(r"^\\d{4}-\\d{2}-\\d{2}", path.name) is None,
            f"date-stamped audit filename is not public-facing: {relative}",
        )
        require(
            path.suffix.lower() not in RAW_OR_UNDECLARED_BINARY_SUFFIXES,
            f"undeclared binary or raw-media file: {relative}",
        )
        if path.suffix.lower() in TEXT_SUFFIXES and path.resolve() != Path(__file__).resolve():
            text = path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN_TEXT:
                require(
                    pattern.search(text) is None,
                    f"nonportable or private text in {relative}: {pattern.pattern}",
                )
            scanned += 1
    return scanned


def verify_results_index() -> int:
    rows = read_csv("evidence/results_index.csv")
    require(len({row["result_id"] for row in rows}) == len(rows), "duplicate result_id")
    for row in rows:
        relative = Path(row["public_file"])
        require(not relative.is_absolute(), f"absolute result path: {relative}")
        require(".." not in relative.parts, f"escaping result path: {relative}")
        resolved = (ROOT / relative).resolve()
        require(resolved.is_relative_to(ROOT.resolve()), f"external result path: {relative}")
        require(resolved.is_file(), f"missing indexed public file: {relative}")
        require(bool(row["row_selector"].strip()), f"missing row selector: {row['result_id']}")
    return len(rows)


def verify_local_markdown_links() -> int:
    checked = 0
    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for document in ROOT.rglob("*.md"):
        for target in pattern.findall(document.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            relative = target.split("#", 1)[0]
            if not relative:
                continue
            path = (document.parent / relative).resolve()
            require(path.is_relative_to(ROOT.resolve()), f"external Markdown link: {target}")
            require(path.exists(), f"broken Markdown link in {document.name}: {target}")
            checked += 1
    return checked


def verify_checkpoints(allow_missing: bool) -> tuple[int, int]:
    records = checkpoint_records()
    present: list[Path] = []
    for record in records:
        path = ROOT / str(record["repository_path"])
        if not path.is_file():
            continue
        present.append(path)
        require(
            path.stat().st_size == int(record["bytes"]),
            f"checkpoint is incomplete or an unsmudged LFS pointer: {path}",
        )
        require(
            sha256(path) == str(record["sha256"]),
            f"checkpoint digest mismatch: {path}",
        )
    require(
        not present or len(present) == len(records),
        "checkpoint checkout is partial; retrieve both files",
    )
    if not allow_missing:
        require(len(present) == len(records), "author checkpoints are missing; run git lfs pull")

    declared = declared_checkpoint_paths()
    undeclared = [
        path
        for path in ROOT.rglob("*.pth")
        if path.resolve() not in declared and ".git" not in path.parts
    ]
    require(not undeclared, f"undeclared checkpoint files: {undeclared}")
    return len(present), len(records)


def verify_headline_values() -> None:
    mask = read_csv("evidence/mask_audit/mask_audit_summary.csv")
    close(
        select(
            mask,
            system="Spatial-Mamba Tiny",
            dataset="CVC-ClinicDB",
            metric="mean Dice",
        )["value"],
        0.9433527173,
    )
    close(
        select(
            mask,
            system="ConvNeXt V2 Tiny",
            dataset="CVC-ClinicDB",
            metric="mean Dice",
        )["value"],
        0.9365825220426041,
    )
    close(
        select(
            mask,
            system="Spatial-Mamba Tiny",
            dataset="SUN-SEG",
            metric="foreground-frame prevalence",
        )["value"],
        0.893695284338,
    )
    close(
        select(
            mask,
            system="SALI causal replay",
            dataset="SUN-SEG",
            metric="foreground-frame prevalence",
        )["value"],
        0.991760464945,
    )

    colon = read_csv("evidence/mask_audit/colon_bench_summary.csv")[0]
    require(int(colon["clips"]) == 518, "Colon-Bench clip count mismatch")
    require(int(colon["frames"]) == 149685, "Colon-Bench frame count mismatch")
    require(
        int(colon["foreground_failure_frames"]) == 121099,
        "Colon-Bench failure count mismatch",
    )
    close(colon["frame_auroc"], 0.983411043110233)
    close(colon["frame_auprc"], 0.9957632392556038)

    editing = read_csv("evidence/editing/editing_summary.csv")
    run_length = select(
        editing,
        mask_source="Spatial-Mamba Tiny",
        slice="C6 confirmatory",
        editor="minimum-five-frame run length",
    )
    absence = select(
        editing,
        mask_source="Spatial-Mamba Tiny",
        slice="C6 confirmatory",
        editor="absence and run length",
    )
    close(run_length["target_positive_dice"], 0.7486655584)
    close(absence["target_positive_dice"], 0.6963629282)
    close(run_length["false_positive_frames_per_unit"], 5.625)
    close(absence["false_positive_frames_per_unit"], 4.5)
    require(int(run_length["erased_positive_frames"]) == 10, "C6 erasure mismatch")
    require(int(absence["erased_positive_frames"]) == 34, "C6 erasure mismatch")

    c6 = read_csv("evidence/editing/c6_endpoints_exact.csv")
    target = select(c6, endpoint_id="target_positive_dice")
    require(target["model_a"] == "absence_and_run_length", "C6 model A mismatch")
    require(target["model_b"] == "run_length_5", "C6 model B mismatch")
    require(int(target["sequence_units"]) == 8, "C6 sequence count mismatch")
    require(int(target["sign_assignments"]) == 256, "C6 assignment count mismatch")
    require(int(target["bh_hypothesis_count"]) == 930, "C6 family size mismatch")
    close(target["mean_delta"], -0.046749208572945955)
    close(target["exact_p_value"], 0.0625)
    close(target["p_value_bh_full_family"], 0.19246688741721854)

    c6_family = read_csv("evidence/editing/c6_hypothesis_family.csv")
    c6_inference = read_csv("evidence/editing/c6_inference.csv")
    c6_effects = read_csv("evidence/editing/c6_paired_effects.csv")
    require(len(c6_family) == len(c6_inference) == 930, "C6 family row mismatch")
    require(len(c6_effects) == 6480, "C6 paired-effect row mismatch")

    references = read_csv("evidence/risk_scores/reference_review_utility.csv")
    sali_easy = select(
        references,
        slice="sun_easy_unseen",
        system="SALI",
        temporal_mode="causal_previous_neighbor_raw",
        presence_stratum="lesion present",
        selection_mode="exact_rank",
        nominal_budget="0.2",
    )
    require(
        (int(sali_easy["frames"]), int(sali_easy["failures"]))
        == (12351, 1495),
        "SALI easy-unseen counts mismatch",
    )
    require(
        (int(sali_easy["caught_failures"]), int(sali_easy["remaining_failures"]))
        == (916, 579),
        "SALI easy-unseen review mismatch",
    )
    close(sali_easy["auroc"], 0.7619793810367647)
    close(sali_easy["auprc"], 0.3868809400719345)

    sam2_easy = select(
        references,
        slice="sam2_sun_easy_unseen",
        system="SAM2-SQA",
        presence_stratum="lesion present",
        selection_mode="exact_rank",
        nominal_budget="0.2",
    )
    require(
        (int(sam2_easy["failures"]), int(sam2_easy["caught_failures"]))
        == (132, 109),
        "SAM2-SQA easy-unseen review mismatch",
    )
    close(sam2_easy["auroc"], 0.966818843456398)
    close(sam2_easy["auprc"], 0.8873449248653621)

    sam2_negative = select(
        references,
        slice="sam2_polypgen_test",
        system="SAM2-SQA",
        presence_stratum="no lesion",
        selection_mode="exact_rank",
        nominal_budget="0.2",
    )
    require(
        (int(sam2_negative["failures"]), int(sam2_negative["caught_failures"]))
        == (64, 0),
        "SAM2-SQA no-lesion inversion mismatch",
    )
    close(sam2_negative["auroc"], 0.0)

    wrapper = read_csv("evidence/risk_scores/sali_top20_summary.csv")
    require(len(wrapper) == 8, "SALI wrapper row count mismatch")
    wrapper_expected = {
        ("sun_easy_unseen", "positive"): (12351, 1495, 2471, 916, 579),
        ("sun_hard_unseen", "positive"): (8640, 1086, 1728, 535, 551),
        ("cvc_sali_full", "positive"): (612, 56, 123, 26, 30),
        ("polypgen_test", "positive"): (478, 94, 96, 33, 61),
        ("sun_negative_case1_train", "negative"): (9961, 9897, 1993, 1988, 7909),
        ("sun_negative_case2_val", "negative"): (10073, 9946, 2015, 2008, 7938),
        ("sun_negative_case3_test", "negative"): (7152, 7119, 1431, 1428, 5691),
        ("polypgen_test", "negative"): (647, 647, 130, 130, 517),
    }
    for row in wrapper:
        key = (row["slice_id"], row["stratum"])
        require(key in wrapper_expected, f"unexpected SALI wrapper row: {key}")
        actual = tuple(
            int(row[column])
            for column in (
                "frames",
                "failures",
                "reviewed_frames",
                "caught_failures",
                "remaining_failures",
            )
        )
        require(actual == wrapper_expected[key], f"SALI wrapper mismatch: {key}")
        require(actual[2] == math.ceil(0.2 * actual[0]), f"budget mismatch: {key}")

    entropy = read_csv("evidence/risk_scores/mean_entropy_review_utility.csv")
    entropy_positive = select(
        entropy,
        slice="sun_test_positive_pooled",
        selection_mode="exact_rank",
        nominal_budget="0.2",
    )
    require(int(entropy_positive["remaining_failures"]) == 2173, "entropy residual mismatch")
    close(entropy_positive["failure_recall"], 0.36813027042744983)
    close(entropy_positive["auroc"], 0.5108292438460782)
    close(entropy_positive["auprc"], 0.24730139227651626)
    entropy_transfer = select(
        entropy,
        slice="polypgen_test_negative",
        selection_mode="sun_val_frozen_threshold",
        nominal_budget="0.2",
    )
    close(entropy_transfer["review_fraction"], 0.02472952086553323)
    close(entropy_transfer["failure_recall"], 0.03827751196172249)

    episodes = read_csv("evidence/episodes/primary_top20_gap0.csv")
    require(len(episodes) == 4, "primary episode row count mismatch")
    sun_positive = select(
        episodes,
        slice="sun_test_positive_pooled",
        selection_mode="exact_rank",
    )
    require(int(sun_positive["failure_episodes"]) == 778, "failure episode mismatch")
    require(int(sun_positive["captured_failure_episodes"]) == 422, "captured episode mismatch")
    require(int(sun_positive["residual_failure_episodes"]) == 356, "residual episode mismatch")
    require(int(sun_positive["referral_episodes"]) == 1286, "review episode mismatch")
    require(int(sun_positive["false_referral_episodes"]) == 850, "false review mismatch")

    coverage = read_csv("evidence/protocol/sam2_sampling_coverage.csv")
    easy_coverage = select(coverage, slice="SUN easy unseen")
    require(
        (int(easy_coverage["selected_target_frames"]), int(easy_coverage["selected_windows"]))
        == (819, 39),
        "SAM2-SQA coverage mismatch",
    )

    data_flow = read_csv("evidence/protocol/data_flow.csv")
    colon_flow = select(data_flow, source="Colon-Bench classification metadata")
    require(
        (int(colon_flow["source_records"]), int(colon_flow["eligible_records"]))
        == (790, 518),
        "Colon-Bench data flow mismatch",
    )

    recovered = read_csv("evidence/editing/convnextv2_temporal_controls_per_frame.csv")
    require(len(recovered) == 6948, "ConvNeXt V2 per-frame evidence mismatch")
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in recovered:
        grouped[(row["cohort"], row["control"])].append(row)
    for key, expected in {
        ("cvc_probe", "identity"): 0.9365825220426027,
        ("cvc_probe", "ema_a0_30"): 0.6185634878650241,
        ("test", "identity"): 0.3172915805041802,
        ("test", "ema_a0_30"): 0.43422097416275435,
    }.items():
        values = grouped[key]
        require(bool(values), f"missing ConvNeXt V2 group: {key}")
        close(
            sum(float(row["dice"]) for row in values) / len(values),
            expected,
            atol=5e-13,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-missing-checkpoints",
        action="store_true",
        help="verify metadata and evidence without requiring Git LFS objects",
    )
    args = parser.parse_args()

    checksum_count = verify_checksums()
    text_count = verify_portability_and_privacy()
    index_count = verify_results_index()
    link_count = verify_local_markdown_links()
    checkpoint_present, checkpoint_total = verify_checkpoints(
        args.allow_missing_checkpoints
    )
    verify_headline_values()
    print(
        "PASS "
        f"checksums={checksum_count} "
        f"text_files={text_count} "
        f"indexed_results={index_count} "
        f"local_links={link_count} "
        f"checkpoints={checkpoint_present}/{checkpoint_total}"
    )


if __name__ == "__main__":
    main()
