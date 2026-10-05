# Probo connector

Pulls from [Probo](https://github.com/getprobo/probo), hosted (`us.probo.com`, `eu.probo.com`) or self-hosted. The script calls Probo's MCP API over HTTP, so the agent does not need MCP support.

## Configure

1. In Probo, give the auditor a user in the organization, and create an OAuth access token with read scopes (at least `v1:org`, `v1:control`, `v1:document`, `v1:risk`, `v1:third-party`, `v1:iam`, `v1:access-review`, `v1:audit`).
2. Set the token in the environment: `export PROBO_TOKEN=...`
3. In `engagement.yaml`:

```yaml
source:
  connector: probo
  options:
    url: https://us.probo.com          # or the self-hosted root
    organization_id: "<Probo organization GID>"
    framework_id: "<optional; defaults to the framework whose name contains 27001>"
    soa_id: "<optional; defaults to the most recently updated Statement of Applicability>"
```

## What is pulled

| Probo | Bundle |
|---|---|
| Framework controls of ISO 27001 (`4.1` ... `10.2`, `A.5.1` ... `A.8.34`) | requirements; each measure inherits the requirements of the framework controls it is linked to |
| Measures | `controls.csv` rows with IDs `M-001`, `M-002`, ... (`source_ref` keeps the Probo ID) |
| Statement of Applicability and its applicability statements | `soa.csv`: applicability and justification per Annex A control; status derived from the states of the measures linked to that control |
| Measure evidence (files and links) | evidence artifacts, `obtained: direct` for files, `client` for links. An uploaded file often has an empty MCP `url`; the connector then reads `file.downloadUrl` and the original file name from the console API |
| Documents linked to a framework control or to a measure, and the SoA document | latest published version as a policy artifact, with `requirements` set from the framework control. The header names the approver (`Approval:`) and each signature (`Signatures:`). `not retrieved` means that call failed. It is not "none recorded" |
| People (contract start and end) | `PO-hires` and `PO-terminations` for the period |
| Third parties | `PO-vendors` |
| Findings (major and minor nonconformities) | `PO-nonconformities`, plus the full findings register as evidence for clause 10.2 |
| Audits and their reports | audit list and downloaded reports as evidence for clauses 9.2.1, 9.2.2 and A.5.35 |
| Risks, treatment plans | JSON exports for 6.1.2, 8.2, 6.1.3, 8.3 |
| Obligations, assets, data | JSON exports for A.5.31, A.5.9, A.5.12 |
| Access review campaigns and entries | one JSON file per campaign. Each row has the account, the decision, and `decision_note` (the reason on a defer, revoke or escalate). Use that note. A counts-only summary is not the review |
| Task comments | one JSON file per measure that has comments, linked to that control. Read them. A comment that an account has no email-and-password login means there is no 2FA setting |
| Organization context | draft `isms.yaml` (status `draft`). Evidence only. The report does not print it |

## Limits

- Measures carry no reliable frequency or nature for sampling; fill them in `testplan.csv`.
- Populations are linked to controls by keywords (termination, onboarding, screening, corrective action); confirm them in `testplan.csv`.
- Measures marked not applicable are excluded, and requested but unfulfilled evidence is skipped; both are listed as ingest warnings, which `check` repeats.
- The organization-context draft is not the ISMS description in the report. Write `isms.yaml` at the engagement root for readers. The organization reviews that file and sets `status: management-approved`.
- Tested against a local mock of Probo's published MCP API (`evals/test_probo_connector.py`), not yet against a live instance; check the ingest warnings on first use.
