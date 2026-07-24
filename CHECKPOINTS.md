# Author checkpoints

Two seed-0 model-only state dictionaries are distributed through Git LFS:

- Spatial-Mamba Tiny with the common FPN decoder, used as the primary frozen
  framewise predictor;
- ConvNeXt V2 Tiny with the same decoder design, used as the
  architecture-family replication.

The files contain PyTorch parameter tensors only. They do not contain optimizer
state, gradient-scaler state, training data, absolute paths, or a serialized
Python model object. File sizes, tensor counts, and SHA-256 digests are recorded
in [`CHECKPOINTS.json`](CHECKPOINTS.json).

Retrieve and validate them with:

```bash
git lfs pull --include="checkpoints/author/*.pth"
python tools/verify_release.py
```

Load a state dictionary with a recent PyTorch release:

```python
import torch

state_dict = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
model.load_state_dict(state_dict, strict=True)
```

The matching architecture uses a Spatial-Mamba Tiny or ConvNeXt V2 Tiny
backbone and a four-stage common FPN decoder with 128 decoder channels. Exact
inference additionally requires the corresponding upstream backbone
implementation and the preprocessing contract in the manuscript.
