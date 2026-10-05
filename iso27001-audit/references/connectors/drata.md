# Drata connector

Pulls a workspace through the Drata public API (v2).

## Configure

1. In Drata, create an API key with read access (Settings, API keys).
2. `export DRATA_API_KEY=...`
3. In `engagement.yaml`:

```yaml
source:
  connector: drata
  options:
    workspace_id: "<optional when the account has one workspace>"
    api_url: https://public-api.drata.com   # EU: https://public-api.eu.drata.com, APAC: https://public-api.apac.drata.com
    framework_tag: ISO270012022             # Drata's tag for ISO/IEC 27001:2022 (default)
```

## What is pulled

| Drata | Bundle |
|---|---|
| Controls and their ISO 27001:2022 requirements | `controls.csv` with Drata control codes as IDs; controls mapped to no ISO requirement are left out |
| Evidence library, current versions | evidence artifacts, linked by control |
| Personnel (start and separation dates) | `PO-hires`, `PO-terminations` |
| Monitoring tests | one JSON export, current state only |

## Limits

- The connector does not pull the ISMS scope and context or the Statement of Applicability. Ask the organization for both (export the SoA as `soa.csv`, see [folder.md](folder.md)) and write `isms.yaml` at the engagement root. Until then `check` treats every Annex A control as applicable.
- Monitoring tests show the state at pull time, not a history across the records period. Do not use them alone as evidence for a Stage 2, surveillance or recertification audit.
- Not yet run against a live Drata account; check the ingest warnings on first use.
