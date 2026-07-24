# Data and external assets

## Evaluated data

| Source | Public reference | Use in the study |
| --- | --- | --- |
| SUN-SEG | [VPS repository](https://github.com/GewelsJI/VPS), [doi:10.1007/s11633-022-1371-y](https://doi.org/10.1007/s11633-022-1371-y) | Lesion-present development/test material and the no-lesion material supplied by the dataset authors |
| PolypGen | [doi:10.1038/s41597-023-01981-y](https://doi.org/10.1038/s41597-023-01981-y) | Video slices, C6 preservation analysis, and cross-source no-lesion evaluation |
| CVC-ClinicDB | [doi:10.1016/j.compmedimag.2015.02.007](https://doi.org/10.1016/j.compmedimag.2015.02.007) | Positive-lesion preservation probe and independent SQA subset |
| Colon-Bench | [Hugging Face dataset](https://huggingface.co/datasets/ajhamdi/colon-bench), [arXiv:2603.25645](https://arxiv.org/abs/2603.25645) | External provider-label no-lesion stress test |
| REAL-Colon | [doi:10.1038/s41597-024-03359-0](https://doi.org/10.1038/s41597-024-03359-0) | Source recordings underlying Colon-Bench |

No source frames, videos, masks, annotations, provider identifiers, or
download credentials are included in this repository.

## Colon-Bench label scope

The study used the classification configuration and included all 518 records
whose provider metadata assigned `lesion == 0` (`no_lesion`). All selected
files passed file-size and decode checks before inference.

This is a clip-level provider label. The study did not add independent
clinician or frame-level relabelling, and the public metadata did not provide a
validated patient/procedure map for these clips. Results are therefore grouped
by clip and described as a provider-label no-lesion stress test.

## External software and checkpoints

The repository does not redistribute:

- Spatial-Mamba or ConvNeXt V2 initialization weights;
- the SALI implementation or checkpoint;
- the SAM 2 implementation or Hiera-L checkpoint; or
- third-party dataset tooling.

The two author-trained model-only parameter states are the only `.pth` files
declared for this repository. Their identities and hashes are recorded in
[`CHECKPOINTS.json`](CHECKPOINTS.json).

All datasets, software, and third-party checkpoints remain governed by their
respective providers.
