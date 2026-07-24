"""Reference metrics for the presence-stratified reliability benchmark."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Hashable, Iterable, Sequence

import numpy as np
from scipy.ndimage import binary_erosion, label


@dataclass(frozen=True)
class Episode:
    sequence_id: Hashable
    start_index: int
    stop_exclusive: int
    flagged_frames: int

    @property
    def span_frames(self) -> int:
        return self.stop_exclusive - self.start_index


def _binary_2d(value: np.ndarray | Sequence[Sequence[bool]]) -> np.ndarray:
    result = np.asarray(value, dtype=bool)
    if result.ndim != 2:
        raise ValueError(f"expected a two-dimensional mask, got {result.shape}")
    return result


def dice(prediction: np.ndarray, reference: np.ndarray) -> float:
    prediction = _binary_2d(prediction)
    reference = _binary_2d(reference)
    if prediction.shape != reference.shape:
        raise ValueError("prediction and reference must have the same shape")
    prediction_sum = int(prediction.sum())
    reference_sum = int(reference.sum())
    if prediction_sum + reference_sum == 0:
        return 1.0
    intersection = int(np.logical_and(prediction, reference).sum())
    return 2.0 * intersection / (prediction_sum + reference_sum)


def boundary_band(mask: np.ndarray, ratio: float = 0.02) -> np.ndarray:
    mask = _binary_2d(mask)
    if ratio <= 0:
        raise ValueError("ratio must be positive")
    height, width = mask.shape
    iterations = max(1, int(round(ratio * math.hypot(height, width))))
    eroded = binary_erosion(
        mask,
        structure=np.ones((3, 3), dtype=bool),
        iterations=iterations,
        border_value=0,
    )
    return np.logical_xor(mask, eroded)


def boundary_iou(
    prediction: np.ndarray,
    reference: np.ndarray,
    ratio: float = 0.02,
) -> float:
    prediction = _binary_2d(prediction)
    reference = _binary_2d(reference)
    if prediction.shape != reference.shape:
        raise ValueError("prediction and reference must have the same shape")
    if not prediction.any() and not reference.any():
        return 1.0
    if not prediction.any() or not reference.any():
        return 0.0
    prediction_boundary = boundary_band(prediction, ratio)
    reference_boundary = boundary_band(reference, ratio)
    intersection = np.logical_and(prediction_boundary, reference_boundary).sum()
    union = np.logical_or(prediction_boundary, reference_boundary).sum()
    return float(intersection / union) if union else 1.0


def connected_component_summary(mask: np.ndarray) -> dict[str, float | int]:
    mask = _binary_2d(mask)
    components, count = label(mask, structure=np.ones((3, 3), dtype=np.uint8))
    if count == 0:
        largest = 0
    else:
        sizes = np.bincount(components.ravel())[1:]
        largest = int(sizes.max())
    pixels = int(mask.size)
    foreground = int(mask.sum())
    return {
        "component_count": int(count),
        "foreground_pixels": foreground,
        "foreground_fraction": foreground / pixels,
        "largest_component_pixels": largest,
        "largest_component_fraction": largest / pixels,
    }


def audit_mask(
    prediction: np.ndarray,
    reference: np.ndarray,
    *,
    boundary_ratio: float = 0.02,
) -> dict[str, object]:
    """Return the state-specific audit for one binarized prediction."""

    prediction = _binary_2d(prediction)
    reference = _binary_2d(reference)
    if prediction.shape != reference.shape:
        raise ValueError("prediction and reference must have the same shape")

    lesion_present = bool(reference.any())
    result: dict[str, object] = {
        "presence_stratum": "lesion_present" if lesion_present else "no_lesion",
        "prediction_nonempty": bool(prediction.any()),
    }
    if lesion_present:
        overlap = dice(prediction, reference)
        boundary = boundary_iou(prediction, reference, boundary_ratio)
        erased = not bool(prediction.any())
        result.update(
            {
                "dice": overlap,
                "boundary_iou": boundary,
                "complete_erasure": erased,
                "preservation_failure": bool(
                    erased or overlap < 0.50 or boundary < 0.20
                ),
            }
        )
    else:
        result.update(connected_component_summary(prediction))
        result["false_foreground"] = bool(prediction.any())
    return result


def exact_budget_selection(
    risk: Iterable[float],
    budget: float,
    tie_keys: Sequence[object] | None = None,
) -> np.ndarray:
    """Select exactly ceil(budget * n) highest-risk items with stable ties."""

    values = np.asarray(list(risk), dtype=float)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("risk must be a nonempty one-dimensional sequence")
    if not np.isfinite(values).all():
        raise ValueError("risk contains a non-finite value")
    if not 0 < budget <= 1:
        raise ValueError("budget must lie in (0, 1]")
    if tie_keys is None:
        tie_keys = list(range(values.size))
    if len(tie_keys) != values.size:
        raise ValueError("tie_keys must have the same length as risk")

    selected_count = int(math.ceil(budget * values.size))
    order = sorted(
        range(values.size),
        key=lambda index: (-values[index], tie_keys[index]),
    )
    selected = np.zeros(values.size, dtype=bool)
    selected[order[:selected_count]] = True
    return selected


def group_episodes(
    flags: Iterable[bool],
    sequence_ids: Sequence[Hashable],
    *,
    max_gap: int = 0,
) -> list[Episode]:
    """Group flagged rows in temporally ordered, sequence-contiguous input."""

    values = np.asarray(list(flags), dtype=bool)
    if values.ndim != 1 or values.size != len(sequence_ids):
        raise ValueError("flags and sequence_ids must be one-dimensional and aligned")
    if max_gap < 0:
        raise ValueError("max_gap must be nonnegative")

    closed_sequences: set[Hashable] = set()
    previous_sequence: Hashable | None = None
    for sequence_id in sequence_ids:
        if sequence_id != previous_sequence:
            if sequence_id in closed_sequences:
                raise ValueError("each sequence must occupy one contiguous block")
            if previous_sequence is not None:
                closed_sequences.add(previous_sequence)
            previous_sequence = sequence_id

    episodes: list[Episode] = []
    active_sequence: Hashable | None = None
    start = last_flag = flagged_count = -1
    for index, (flagged, sequence_id) in enumerate(zip(values, sequence_ids)):
        if not flagged:
            continue
        can_extend = (
            active_sequence == sequence_id
            and last_flag >= 0
            and index - last_flag - 1 <= max_gap
        )
        if not can_extend:
            if active_sequence is not None:
                episodes.append(
                    Episode(
                        active_sequence,
                        start,
                        last_flag + 1,
                        flagged_count,
                    )
                )
            active_sequence = sequence_id
            start = index
            flagged_count = 1
        else:
            flagged_count += 1
        last_flag = index

    if active_sequence is not None:
        episodes.append(
            Episode(active_sequence, start, last_flag + 1, flagged_count)
        )
    return episodes


def review_summary(
    failures: Iterable[bool],
    risk: Iterable[float],
    budget: float,
    tie_keys: Sequence[object] | None = None,
) -> dict[str, float | int]:
    failures_array = np.asarray(list(failures), dtype=bool)
    selected = exact_budget_selection(risk, budget, tie_keys)
    if failures_array.shape != selected.shape:
        raise ValueError("failures and risk must have the same length")
    total_failures = int(failures_array.sum())
    reviewed = int(selected.sum())
    caught = int(np.logical_and(failures_array, selected).sum())
    remaining = total_failures - caught
    return {
        "frames": int(selected.size),
        "failures": total_failures,
        "reviewed_frames": reviewed,
        "review_fraction": reviewed / selected.size,
        "caught_failures": caught,
        "failure_capture": caught / total_failures if total_failures else math.nan,
        "review_precision": caught / reviewed if reviewed else math.nan,
        "remaining_failures": remaining,
        "residual_failure_rate_all_frames": remaining / selected.size,
    }


def episode_rows(episodes: Iterable[Episode]) -> list[dict[str, object]]:
    return [asdict(episode) | {"span_frames": episode.span_frames} for episode in episodes]
