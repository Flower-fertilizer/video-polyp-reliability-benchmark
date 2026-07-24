# Benchmark contract

## 1. Inputs

Each evaluated frame has:

- a submitted binary mask or probability map;
- a reference presence state supplied by an annotation or declared provider
  metadata;
- a dataset, sequence or clip, and frame key; and
- optionally, an edited mask or a scalar risk score.

The submitted prediction does not determine the reference presence state.
Probabilities are binarized at 0.5 in the reference implementation.

## 2. Required presence-stratified mask audit

Every mask generator receives two separate endpoint families.

### Lesion-present stratum

The primary endpoints are Dice, boundary IoU, and complete lesion erasure. A
frame-level preservation failure is

```text
prediction is empty OR Dice < 0.50 OR boundary IoU < 0.20
```

The boundary band is the exclusive OR between a mask and its 3 x 3 binary
erosion after

```text
max(1, round(0.02 * sqrt(height^2 + width^2)))
```

iterations. Boundary IoU is one when both masks are empty and zero when exactly
one is empty.

### No-lesion stratum

The primary failure is any nonempty submitted mask. Secondary descriptors
measure:

- total foreground area;
- largest eight-connected component area;
- number of connected components; and
- uninterrupted foreground-run duration within a sequence or clip.

Area thresholds of 0.1%, 0.5%, and 1.0% of the frame and persistence thresholds
of three and five frames characterize severity without replacing the primary
any-foreground endpoint.

The two strata are reported separately; no pooled score replaces them.

## 3. Conditional edited-mask interface

An editor is evaluated only when it changes a submitted mask. The edited and
unedited outputs are compared on both presence strata.

The reference preservation criterion requires:

- sequence-macro target-positive Dice loss no greater than 0.005; and
- no increase in completely erased lesion-present frames.

False-foreground reduction is interpreted together with these preservation
results. An editor that improves no-lesion output while exceeding either
preservation limit does not satisfy this interface.

## 4. Conditional risk-score interface

A risk score orders unchanged submitted masks for external inspection. It does
not define a failure and it does not alter the mask.

For a slice of `n` frames and nominal budget `b`, the selected set contains
exactly

```text
ceil(b * n)
```

frames with highest risk. Stable dataset, sequence, frame, and image keys break
ties. The reference budgets are 1%, 5%, 10%, and 20%.

The report contains:

- AUROC and AUPRC;
- selected and caught failure counts;
- failure capture and review precision;
- failures remaining outside review;
- residual failure rate among all and unreviewed frames;
- calibration where a probability interpretation is claimed;
- the action rate under an unchanged cross-source threshold; and
- episode-level review burden.

The primary episode rule groups consecutive flagged frames within a sequence
or clip. Sensitivity settings permit gaps of up to two or five unflagged
frames. A failure episode is captured when at least one of its failed frames is
selected.

## 5. Required report fields

A complete system record identifies:

- dataset and presence stratum;
- submitted output type;
- temporal access: current-only, causal history, or symmetric context;
- frame count and highest available independent unit;
- required mask-audit endpoints;
- edited-mask preservation results, when applicable;
- risk-score capture and residual burden, when applicable; and
- uncertainty at the available sequence, case, or clip level.

Reference functions for the mask endpoints, exact-budget selection, and
episode grouping are provided in `code/reliability_metrics.py`.
