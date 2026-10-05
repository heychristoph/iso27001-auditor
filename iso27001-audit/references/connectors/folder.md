# Folder connector

Builds the bundle from files on disk. Use it for platform exports, files the organization uploads, or any source without a dedicated connector.

## Configure

```yaml
source:
  connector: folder
  options:
    path: export          # relative to the engagement folder, or absolute
    obtained: client      # default provenance: client (provided) or direct (auditor pulled it)
```

## Expected layout

```
export/
├── controls.csv          required: id,title,description,criteria[,owner,frequency,nature,population]
├── soa.csv               Statement of Applicability: control,applicable,justification[,status,reference]
├── isms.yaml             ISMS scope and context (see ../engagement-folder.md)
├── populations/<name>.csv   first columns id,date; becomes PO-<name>
├── policies/<file>       policies, procedures and other ISMS documents (kind: policy)
├── evidence/<id>/<file>  evidence, grouped by the control ID or requirement ID it supports
└── evidence.csv          optional: path,controls,requirements,title,date,obtained,kind
```

- In `controls.csv`, `criteria` lists ISO/IEC 27001:2022 requirement IDs, space- or comma-separated: clauses as `4.1`, `6.1.2`, `9.3.2`, Annex A controls as `A.5.15`. A parent clause expands to its sub-clauses (`9.2` becomes `9.2.1 9.2.2`). Write Annex A controls with the `A.` prefix; a bare `5.1` means clause 5.1. Control IDs must not look like requirement IDs and must not start with `REQ-`.
- `population` names a file in `populations/` (`terminations` or `terminations.csv`).
- `soa.csv` has one row per Annex A control; `applicable` is `yes` or `no`. Without it, every Annex A control is treated as applicable and `check` asks for the SoA.
- Files under `evidence/<control-id>/` are linked to that control. Files under `evidence/<requirement-id>/` (e.g. `evidence/A.5.7/`, `evidence/9.3.2/`) are linked to that requirement, for requirements no control covers. Name item evidence with the item ID first (`T-003_offboarding-ticket.json`) so the auditor can find it.
- `evidence.csv` adds metadata for any file, keyed by its path relative to the export root: more controls, requirements, a title, the artifact's own date, and whether it was obtained directly.

## Converting a platform export

Most platforms can export an audit package (a zip of evidence plus a control list and the SoA). Unzip it, write `controls.csv` from its control list with each control's ISO/IEC 27001 mapping, write `soa.csv` from the Statement of Applicability, and move files into `evidence/<control-id>/`. Keep original file names after the item ID. Record `obtained: direct` in `evidence.csv` for files the auditor downloaded itself.
