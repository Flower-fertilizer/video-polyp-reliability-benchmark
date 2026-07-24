# Evidence tables

`results_index.csv` is the entry point. Each row maps a manuscript result to a
file in this repository and gives a human-readable row selector. Every
`public_file` value is relative to the repository root and is checked by
`tools/verify_release.py`.

## Conventions

- Proportions are stored on the 0--1 scale unless a column explicitly contains
  `percent`.
- Blank cells mean that the quantity is not applicable or was not estimated.
- `frames` is the evaluated frame count, not an independent-sample count.
- `independent_units` and `independent_unit_type` identify the grouping level
  used for interpretation or resampling.
- Exact-budget review uses `ceil(budget * frames)` selected frames.
- `remaining_failures` counts known failures outside the selected review set.
- Colon-Bench values use the provider's clip-level class-0 label; they do not
  imply independent frame-level clinical adjudication.

The package contains no raw images, videos, patient identifiers, authentication
records, or machine-local file paths.
