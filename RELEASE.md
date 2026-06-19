# Release Checklist

This file records the release process for research-artifact snapshots.

## v0.1.0 Artifact Release

Before publishing a GitHub release:

- Run `bash scripts/run_smoke_tests.sh`.
- Confirm `README.md`, `CITATION.cff`, `CHANGELOG.md`, and `LICENSE` are
  current.
- Confirm checked hardware-result tables and synthesis reports are the intended
  public artifacts.
- Create an annotated tag, for example `v0.1.0`.
- Publish the GitHub release with the changelog summary and attach any
  intentionally archived artifacts.
- Add DOI/Zenodo metadata only after the archived release exists.

## Versioning Notes

- Patch releases should be used for documentation fixes and reproducibility
  script corrections.
- Minor releases should be used when new verification cases, hardware reports,
  or artifact datasets are added.
- Major releases should be reserved for incompatible model or workflow changes.
