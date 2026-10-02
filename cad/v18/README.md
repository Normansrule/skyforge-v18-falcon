# V18 source geometry

`V18_EQUIPMENT_ASSEMBLY_VIEW_ONLY.3mf` is your V18 assembly (90 objects: printed shells, covers, trays,
controls, carbon, G10, gear, motor envelopes, equipment keep-outs, prop references). It is **view only**:
print from the V18 P1S print files, not from this assembly.

| File | Made by | What |
|---|---|---|
| `V18_EQUIPMENT_ASSEMBLY_VIEW_ONLY.3mf` | you (V18) | source of truth |
| `V18_BOM_AND_BUDGET_original.md` | you (V18) | the V18 BOM, carried forward into `bom/bom.csv` |
| `parts.json` | `tools/v18_extract.py` | per-object data, P1S placement, summary |
| `dxf/` | `tools/v18_extract.py` | 1:1 G10 cutting profiles with modelled holes |
| `carbon_cut_list.json` | `tools/v18_extract.py` | tubes packed onto 1 m stock |

To add the rest of the V18 archives (`SKYFORGE_V18_FALCON_COMPLETE`, `SKYFORGE_V18_P1S_PRINT_FILES`,
`SKYFORGE_V18_FIRST_PRINT_KIT`), unzip them here in their own folders. If they are larger than about 50 MB,
track them with Git LFS (`git lfs track "cad/v18/**/*.3mf"`). Reconcile the first-print kit against the print
manifest so no stage-kit part is printed twice.
