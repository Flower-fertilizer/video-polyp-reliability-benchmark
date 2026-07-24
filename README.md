# Presence-Stratified Reliability Benchmark for Video Polyp Segmentation

This repository accompanies the manuscript *Presence-Stratified Reliability
Benchmarking for Video Polyp Segmentation*. It evaluates frozen segmentation
outputs in two reference-defined states:

1. lesion-present frames, where target preservation is measured; and
2. no-lesion frames, where any predicted foreground is a false-foreground
   event and its area, connectivity, and persistence are characterized.

The mask audit is required. Two conditional interfaces extend it when a system
provides additional outputs:

- an edited mask is evaluated for no-lesion benefit **and** lesion
  preservation;
- a scalar risk score is evaluated by exact-budget failure capture, failures
  left outside review, episode burden, calibration, and threshold transfer.

The benchmark contract is specified in [`BENCHMARK.md`](BENCHMARK.md).

## Repository contents

| Path | Contents |
| --- | --- |
| `evidence/results_index.csv` | Direct map from manuscript results to files in this repository |
| `evidence/protocol/` | Dataset roles, system roles, data flow, and SAM2-SQA sampling coverage |
| `evidence/mask_audit/` | Presence-stratified mask results and no-lesion severity analyses |
| `evidence/editing/` | Editing summaries, eight-sequence C6 effects, and exact inference inputs |
| `evidence/risk_scores/` | SALI, SAM2-SQA, and mean-entropy review-utility results |
| `evidence/episodes/` | Frame-to-episode accounting and gap-rule sensitivity |
| `evidence/sensitivity/` | Positive-failure endpoint grids and clustered intervals |
| `code/` | Standalone reference metrics and the reproducible C6 exact analysis |
| `checkpoints/author/` | Model-only author checkpoints stored with Git LFS |
| `tools/` | Integrity, privacy-boundary, and checksum verification |

The evidence index contains only repository-relative paths. It does not refer
to local experiment directories, research histories, or server files.

## Quick verification

Python 3.10 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests
python tools/verify_release.py
```

If the checkpoint files are not present after cloning, install Git LFS and
retrieve them first:

```bash
git lfs install
git lfs pull --include="checkpoints/author/*.pth"
python tools/verify_release.py
```

A metadata-and-evidence checkout can be checked without the large model files
by adding `--allow-missing-checkpoints`.

## Reproduce the C6 exact analysis

```bash
python code/reproduce_c6_exact.py \
  --inference-csv evidence/editing/c6_inference.csv \
  --effects-csv evidence/editing/c6_paired_effects.csv \
  --output-dir /tmp/c6_exact
```

This command reconstructs the six paper-facing endpoints, enumerates all 256
paired sign assignments for each eight-sequence endpoint, and writes the
complete 930-comparison Benjamini--Hochberg family.

## Data and software boundary

No medical images, videos, provider annotations, authentication material,
third-party checkpoints, or full training states are redistributed here.
End-to-end training and inference require the provider-governed datasets and
upstream implementations listed in
[`DATA_AND_ASSETS.md`](DATA_AND_ASSETS.md). The analyses that can be run from a
clean checkout are listed in [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md).

Original repository material is covered by [`LICENSE`](LICENSE). Third-party
assets retain their providers' terms.
