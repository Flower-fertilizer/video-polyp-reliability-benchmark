# Reproducibility

## Supported by a clean checkout

The repository supports:

1. verification of every public file against `SHA256SUMS`;
2. verification of the public result index and both author-checkpoint hashes;
3. unit-tested reference implementations of Dice, boundary IoU, no-lesion
   component measurements, exact-budget selection, and episode grouping;
4. reconstruction of the C6 exact paired sign-flip analysis and its
   930-comparison multiple-testing family;
5. audit of the reported mask, editing, risk-score, calibration, transfer,
   sensitivity, and episode summaries; and
6. audit of data-flow counts and SAM2-SQA sampling coverage.

Run:

```bash
python -m unittest discover -s tests
python tools/verify_release.py
```

## Requires separately obtained assets

Complete training and inference require:

- provider-distributed medical frames, videos, masks, and metadata;
- the cited Spatial-Mamba, ConvNeXt V2, SALI, SAM 2, and SAM2-SQA software;
- third-party initialization or inference checkpoints; and
- per-frame predictions for rebuilding every aggregate table from raw model
  output.

Those assets are not redistributed by this repository. The included
model-only author checkpoints reproduce the frozen parameter states, but they
do not include the provider data or upstream implementation dependencies.

The public package therefore supports the benchmark reference implementation,
compact-result verification, and selected statistical reconstruction. It is
not a self-contained redistribution of the complete medical-data inference
pipeline.
