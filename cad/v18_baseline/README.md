# V18 baseline files go here

The V18 archives were not attached to the conversation that created this repo, so the V18 airframe
templates are **not** in it yet. Unzip them here, keeping their own structure:

```
cad/v18_baseline/
  SKYFORGE_V18_FALCON_COMPLETE/     # baseline + source + native geometry
  SKYFORGE_V18_P1S_PRINT_FILES/     # print_3mf/, per-part STEP + STL
  SKYFORGE_V18_FIRST_PRINT_KIT/     # initial subset - NOT extra installed parts
```

Then:

1. Compare `docs/BOM_AND_BUDGET.md` from the archive against `bom/bom.csv`. Where V18 names a specific
   part this repo lists only as a candidate (notably the EDF), the V18 part wins - update the CSV row.
2. Replace the spar stations in `cad/src/params.py` (`SPAR_X`) with the real V18 rail positions and
   re-run `python3 cad/src/build.py`.
3. Reconcile the FIRST_PRINT_KIT against `config/PRINT_MANIFEST.json` so no stage-kit part is printed twice.

Large binaries: if the archives exceed ~50 MB, track `*.3mf`, `*.step` and `*.stl` with Git LFS
(`git lfs track "cad/v18_baseline/**"`).
