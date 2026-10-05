# The engagement folder

One folder per audit. Every step reads and writes files here, so any step can be rerun or resumed, by any agent. JSON Schemas for each file are in `assets/schemas/`.

## Contents
- Layout
- engagement.yaml
- bundle/ (written by the connector)
- Units of work
- testplan.csv
- workpapers/
- findings.json, review/, report/

## Layout

```
<engagement>/
├── engagement.yaml        scope and settings (you or the user)
├── isms.yaml              ISMS scope and context printed in the report; not a copy of the connector draft
├── bundle/                evidence, written once by `ingest`, then read-only
│   ├── manifest.json      every artifact: id, path, sha256, kind, controls, requirements, date, obtained
│   ├── controls.csv       the organization's control matrix, mapped to ISO/IEC 27001 requirements
│   ├── soa.csv            the Statement of Applicability, as pulled from the source
│   ├── isms.yaml          ISMS scope and context inputs as pulled from the source
│   ├── populations/*.csv  hires, terminations, changes, incidents, nonconformities ... (id, date, ...)
│   └── evidence/          files, prefixed with their artifact ID
├── testplan.csv           include, frequency, nature and population per unit (auditor)
├── workpapers/<id>.json   one per unit (auditor)
├── findings.json          graded findings and the conclusion
├── review/                coverage.md, requests.csv, rollup.md, qa.json, packet.md
└── report/                PDF, workpapers.xlsx, evidence-index.csv, report-data.json
```

## engagement.yaml

```yaml
schema_version: 1
organization: Northwind Analytics, Inc.            # legal name, as printed
scope: >-                                          # the ISMS scope as a certificate would print it
  The information security management system supporting the development, operation and support of
  the Northwind Insights Platform, in accordance with Statement of Applicability version 3.
auditor: AI Audit                                  # always this; the model name is in signoff
audit_type: stage2                                 # stage1 | stage2 | surveillance | recertification
period: {start: 2026-01-01, end: 2026-06-30}       # records period sampled (all types but stage1)
# as_of: 2026-06-30                                # stage1: date of the documentation review
source:
  connector: probo                                 # folder | probo | vanta | drata
  options: {organization_id: "..."}                # connector-specific, never secrets
management:                                        # the organization's representative, from the evidence
  name: Ada Lovelace
  title: Chief Executive Officer
sampling_seed: 483920117                           # set by init; never change after sampling
signoff: null                                      # written only by `signoff --model`
```

Secrets (API tokens) go in environment variables, never in this file.

| audit_type | What it is | Evidence |
|---|---|---|
| `stage1` | Documentation and readiness review before certification | One item per unit, the latest performance as of `as_of` |
| `stage2` | Implementation and effectiveness, for initial certification | Records sampled over `period` |
| `surveillance` | Yearly check between certifications; covers the mandatory clauses and a sample of Annex A | Records sampled over `period`; units may be left out |
| `recertification` | Full audit before the certificate expires | Records sampled over `period` |

## bundle/

**manifest.json** lists every artifact. The fields that matter when auditing:

| Field | Meaning |
|---|---|
| `id` | `EV-0001` for evidence and policies, `PO-<name>` for populations, `SY-...` for the control matrix, SoA and ISMS inputs |
| `path` | file location relative to `bundle/` |
| `kind` | `evidence`, `policy`, `population`, `controls`, `soa`, `isms` |
| `controls` | control IDs the source linked this artifact to (a hint, not a limit) |
| `requirements` | ISO/IEC 27001 requirement IDs the source linked this artifact to, e.g. an internal audit report to `9.2.1` (a hint, not a limit) |
| `date` | the date the artifact refers to, when the source knows it |
| `obtained` | `direct` (pulled from the system of record) or `client` (provided by the organization); direct evidence is more reliable |

**controls.csv** columns: `id, title, description, criteria, owner, frequency, nature, population, source_ref`. `criteria` is a space-separated list of requirement IDs: clauses as `4.1` to `10.2`, Annex A controls as `A.5.1` to `A.8.34`. The full list, with titles and paraphrased summaries, is `assets/requirements.yaml`.

**soa.csv** columns: `control, applicable, justification, status, reference`. One row per Annex A control. `applicable` is `yes` or `no`; `status` is the organization's implementation status. A missing row or a missing file means the control is treated as applicable.

**isms.yaml** holds the organization's description of its ISMS:

```yaml
status: draft | management-approved
scope_statement: ...      # clause 4.3
boundaries: ...           # organizational, technological, physical
sites: [{name: ..., activities: ...}]
context: ...              # internal and external issues (4.1), including the climate change determination
interested_parties: [...] # and their requirements (4.2)
interfaces: ...           # interfaces and dependencies with other organizations
outsourced: [{name: ..., services: ...}]
soa_version: ...          # version of the Statement of Applicability in force
changes: ...              # significant changes since the last audit
```

**populations/*.csv** always start with `id,date`; other columns vary by source.

## Units of work

A unit is either a control from `controls.csv` or a `REQ-<requirement>` unit. `plan` creates a `REQ-` unit for every in-scope requirement (every clause, and every applicable Annex A control) that no control maps to. A `REQ-` unit is audited directly against the requirement, using artifacts whose `requirements` include it, policies, and anything else relevant in the bundle.

## testplan.csv

`control_id, include, frequency, nature, population, sample_size, notes`. See [planning.md](planning.md).

## workpapers/<unit>.json

Created by `sample` with the `plan` block filled in and `conclusion: pending`. The auditor fills in everything else, including an optional `statement` when the control title is not the sentence the report should print. See [control-testing.md](control-testing.md) for each field and `assets/schemas/workpaper.schema.json` for the exact shape.

## findings.json, review/, report/

- `findings.json`: see [evaluating.md](evaluating.md).
- `review/qa.json`: written by `iso27001.py qa`, never by hand.
- `review/packet.md`, `report/*`: generated by `packet` and `render`.
