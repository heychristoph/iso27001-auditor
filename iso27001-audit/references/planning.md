# Planning and sampling

`iso27001.py plan` creates `testplan.csv` with one row per unit: each control in the organization's matrix, plus a `REQ-` unit for each in-scope requirement no control maps to. Complete every row, then run `iso27001.py sample`, which draws the samples and writes workpaper skeletons. Sampling is seeded from `engagement.yaml`, so the same plan always gives the same sample, and anyone can reproduce it.

## Columns

| Column | Values | How to decide |
|---|---|---|
| `include` | `yes`, `no` | `yes` for every unit, except in a surveillance audit (see below). |
| `frequency` | `annual`, `semiannual`, `quarterly`, `monthly`, `weekly`, `daily`, `multiple-daily`, `event`, `continuous` | How often the activity happens, from its description and the policy. "Upon hire", "for each change", "when a nonconformity is raised" are `event`. A configuration that is always on, or a requirement met by a standing document, is `continuous`. |
| `nature` | `manual`, `automated`, `itdm` | `automated`: a system does it with no human step (MFA enforcement, encryption). `itdm`: a person acts on system output (reviewing a scan report). Otherwise `manual`. |
| `population` | `PO-...` artifact ID or empty | Required for `event` rows: the list of occurrences (e.g. `PO-terminations` for access removal, `PO-nonconformities` for corrective action). Look at the population files in `bundle/manifest.json`. |
| `sample_size` | number or empty | Leave empty to use the table in `assets/sampling.yaml`. Override only with a reason in `notes`. |
| `notes` | text | Why you chose an unusual frequency, population or sample size, or why a surveillance audit leaves a unit out. |

When the connector already filled a value, check it against the control description instead of trusting it. `REQ-` rows are prefilled from the catalog defaults in `assets/requirements.yaml` and say so in `notes`; confirm them. The ISMS clauses are mostly annual activities (risk assessment, internal audit, management review); an Annex A control audited directly is usually `continuous` (inspect the documented rule and one instance of it working).

## Records-based audits (stage2, surveillance, recertification)

- Periodic activities: `sample` generates the occurrences in the records period (months, quarters, ISO weeks, days) and samples from them. Items look like `2026-Q2`, `2026-03`, `2026-W14`, `2026-05-12`, or `2026` for annual activities.
- Event activities: items are rows of the population file whose date falls in the period.
- Automated and continuous controls: one item, `instance-1`. Testing one instance is enough only if change management (A.8.32) and access control (A.5.15 to A.5.18) are effective; note that dependency in the workpaper.
- An activity with no occurrences in the period gets an empty sample. Its workpaper concludes `not-audited`, with a scope limitation explaining that the circumstances requiring it did not occur.

A Stage 2 audit needs records of the ISMS operating: at least one internal audit and one management review completed, and enough months of operation for the controls to have run. If the records period is too short for that, say so to the user before sampling.

## Stage 1 (documentation and readiness as of a date)

Every unit gets one item. Periodic activities get the item `latest`: find the most recent performance on or before the as-of date and cite it. Event activities get one random item from their population. Automated controls get `instance-1`. Stage 1 confirms that the ISMS is documented, that the processes exist and have started, and that internal audit and management review are planned or done. There is no population completeness test.

## Surveillance audits

A surveillance audit is not a full audit. It must cover, every time (ISO/IEC 17021-1 9.6.2.2 and ISO/IEC 27006-1), the clauses marked `surveillance: true` in `assets/requirements.yaml`: risk treatment and the Statement of Applicability (6.1.3), objectives (6.2), changes (6.3), operational control (8.1), risk assessment and treatment (8.2, 8.3), monitoring (9.1), internal audit (9.2), management review (9.3), and improvement and corrective action (10.1, 10.2). `sample` refuses a plan that leaves any of them uncovered.

Set `include: no`, with a reason in `notes`, for the Annex A units you are not auditing this time. Choose them so the whole Statement of Applicability is covered over the three-year certification cycle: favour controls not audited at the last visit, controls affected by changes, and areas with previous nonconformities. Ask the user for the previous audit reports if they are not in the bundle. Every other audit type includes every unit.

## Changing the plan

If you change a row after sampling, run `sample` again. It refuses to overwrite or remove a workpaper that already has results unless you pass `--force`, which discards those results. Never edit a workpaper's `plan` block directly; `validate` recomputes it and will reject the workpaper.
