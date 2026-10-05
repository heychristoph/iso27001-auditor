# Vanta connector

Pulls one audit through the Vanta Auditor API. Available to audit firms registered as Vanta audit partners; the firm sees only audits assigned to it.

## Configure

1. In Vanta, open the Auditor API section and create an application. Note the client ID and secret.
2. `export VANTA_CLIENT_ID=... VANTA_CLIENT_SECRET=...`
3. In `engagement.yaml`:

```yaml
source:
  connector: vanta
  options:
    audit_id: "<optional when the firm has one active audit>"
    api_url: https://api.vanta.com     # https://api.vanta-gov.com for Vanta Gov
```

The token is requested with the scopes `auditor-api.audit:read auditor-api.auditor:read`.

## What is pulled

| Vanta | Bundle |
|---|---|
| Audit controls | `controls.csv`; ISO/IEC 27001 requirement IDs parsed from the control's framework sections (`A.5.15`, `9.2`) |
| Audit evidence and its download URLs | evidence artifacts, linked by related control name |
| In-scope people (start and end dates) | `PO-hires`, `PO-terminations` |
| Code changes | `PO-changes` |

## Limits

- The connector does not pull the ISMS scope and context or the Statement of Applicability. Ask the organization for both (export the SoA as `soa.csv`, see [folder.md](folder.md)) and write `isms.yaml` at the engagement root. Until then `check` treats every Annex A control as applicable.
- Automated test results reflect Vanta's snapshot at the time they were shared with the audit, not a history across the records period. Confirm snapshots were taken during the period, or treat the control as audited at one point in time.
- A bare section number in Vanta's data is read as a clause when one exists (`5.1` Leadership); Annex A controls are recognised by their `A.` prefix. Check `controls.csv` after the first pull.
- Not yet run against a live Vanta tenant; check the ingest warnings on first use.
