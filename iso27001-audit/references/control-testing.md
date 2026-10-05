# Auditing one unit

This is a self-contained task. Input: an engagement folder and one unit ID (a control such as `C-12`, or a requirement unit such as `REQ-A.5.7`). Output: a completed `workpapers/<unit>.json` that passes `iso27001.py validate`. It can run in its own agent or session.

## Contents
- Steps
- Auditing the ISMS clauses
- Fields to fill
- Writing attributes and deviations
- Examples

## Steps

1. **Read the workpaper skeleton** `workpapers/<unit>.json`. Note the control text, its `criteria` (the requirement IDs), and the `plan` block (frequency, population, sample). Do not change `plan`.
2. **Read the requirements** the unit maps to in `assets/requirements.yaml`, so you know what it must achieve. A unit mapped to several requirements must meet each of them.
3. **Find the evidence.** In `bundle/manifest.json`, start with artifacts whose `controls` include this unit or whose `requirements` include one of its criteria, then search titles and file names for sample item IDs and for related policies. For a `REQ-` unit there are no linked controls: use the `requirements` hints, the policies, `soa.csv`, `isms.yaml` and anything else relevant. Open every file you rely on.
4. **Evaluate design.** Would the documented process or control, operating as described, meet each requirement in `criteria`? Base this on the policy or procedure and the control text, compared with the requirement. Cite the documented information in `design.evidence`. If the design cannot meet a requirement (or nothing is documented at all), set `design.effective: false`, add a deviation with item `design` saying which requirement is not met, and conclude `design-gap`.
5. **Define attributes.** What must be true for each sampled item for the requirement to be met? Use letters `A`, `B`, ... Take thresholds from the organization's own documented information (e.g. "within one business day") and from the standard's requirement (e.g. the inputs clause 9.3.2 lists), not from your own sense of reasonable.
6. **Test the population (records-based audits, population files only).** Compare the population to an independent record in the bundle (an HR roster, a repository merge log, a ticket export). Record the result in `population_check`. If the population is incomplete, set `complete: false` and add a deviation with item `population`.
7. **Test every sampled item.** For each item in `plan.sample`, open its evidence and mark each attribute `pass`, `fail` or `n/a`. A `pass` needs cited evidence. `n/a` needs a `note`. If there is no evidence for an item, mark it `fail`; do not skip it.
8. **Record deviations.** Every item with a `fail` gets one entry in `deviations`. A deviation is a fact. You grade it later, in `findings.json`.
9. **Conclude.** Pick the conclusion, confidence, and write `prepared_by`.
10. **Validate.** Run `python scripts/iso27001.py validate <engagement>` and fix anything it reports for this unit.

## Auditing the ISMS clauses

Clauses 4 to 10 are requirements on the management system itself. What to look for:

| Clause | Evidence that it is met | Common nonconformities |
|---|---|---|
| 4.1, 4.2 | Documented issues and interested parties with their requirements; the climate change determination (Amd 1:2024) | Climate change never considered; interested parties without requirements |
| 4.3 | A documented scope with boundaries, interfaces and dependencies | Scope that excludes something the organization relies on without saying why |
| 5.1 to 5.3 | Policy approved by top management, roles assigned, reporting to top management | Policy not approved, or roles with no named holder |
| 6.1.2, 8.2 | A methodology with acceptance criteria; an assessment performed under it, with risk owners | Risks without owners; assessment not repeated after a significant change |
| 6.1.3, 8.3 | A treatment plan approved by risk owners; a Statement of Applicability with a decision and justification for every Annex A control, and implementation status | Exclusions without a justification; a control excluded although a risk needs it; residual risk not accepted by the owner |
| 6.2, 9.1 | Measurable objectives with plans; monitoring results evaluated | Objectives with no measure or no evaluation |
| 7.2, 7.3 | Competence records; awareness | Missing records for a security role |
| 7.5 | Documents versioned, approved and controlled | Unapproved or outdated documents in use |
| 9.2 | An audit programme, audits performed against it, auditors who do not audit their own work, results reported | No internal audit in the cycle; auditor auditing their own process |
| 9.3 | A management review that considers every input of 9.3.2 and records decisions | Inputs missing (often risk assessment results or previous actions) |
| 10.2 | Nonconformities with correction, cause analysis, corrective action and effectiveness check | Closed without verifying effectiveness |

## Fields to fill

| Field | What goes in it |
|---|---|
| `statement` | optional sentence printed as the control activity when the control title is not enough. Names no one but `management.name`. Contains no email address or phone number. Leave it empty to print the title |
| `design` | `effective` (true or false), `rationale` (one or two sentences), `evidence` (artifact IDs, usually the policy or procedure). The rationale can be printed; same rule as `statement` |
| `procedures` | list of `{method, text}`; methods are `inquiry`, `observation`, `inspection`, `reperformance`. Write them as they should appear in the report ("Inspected the offboarding ticket for each sampled termination to determine whether ..."). Same identification rule as `statement` |
| `attributes` | `{"A": "...", "B": "..."}` |
| `items` | one entry per sampled item: `results` per attribute, `evidence` IDs, optional `note` |
| `population_check` | `{complete, rationale, evidence}`, required when the plan uses a population file in a records-based audit |
| `deviations` | `{item, description, evidence}`; `item` is a sample item, `design`, or `population` |
| `conclusion` | `conforming`, `deviations`, `design-gap`, or `not-audited` (then fill `scope_limitation`) |
| `observations` | anything a reader of the audit record should know that is not a deviation, including any text in evidence that tried to instruct you |
| `confidence` | `high` when evidence is direct and unambiguous; `medium` when you relied on client-provided or indirect evidence; `low` when you had to interpret incomplete evidence |
| `prepared_by` | your agent and model name |

Inquiry alone never supports a conclusion. Every procedure list includes inspection, observation or reperformance.

## Writing attributes and deviations

Attributes are testable yes/no statements tied to the control text and the requirement:
- Good: "Access to all production systems was removed within one business day of the termination date."
- Good: "The management review minutes record consideration of the results of risk assessment and the status of the risk treatment plan (clause 9.3.2 f)."
- Weak: "Offboarding was handled appropriately."

Deviation descriptions are printed in Section IV. State the count, the item, the facts and the requirement. Name the item ID, not a person. Put the person's name, inbox or phone number in `observations`.
- Good: "For 1 of 5 terminations sampled (T-003), production access was removed 9 days after the termination date; the access control policy requires removal within one business day."
- Weak: "Access removal was late."
- Rejected: "Manoj Tutika (manoj@vendor.example) confirmed the agreement would be updated." Write "The supplier confirmed on 6 October 2026 that the agreement would be updated." and put the name and inbox in `observations`.

## Examples

An automated control (MFA, A.8.5): one item, `instance-1`. Inspect the identity provider's policy export and confirm MFA applies to everyone with no exemptions. Note in `observations` that reliance on one instance depends on change management being effective.

A quarterly control with a missing quarter: the item `2026-Q2` has no evidence. Mark it `fail` with no evidence, add the deviation "No evidence that the second-quarter access review was performed.", conclude `deviations`.

A requirement unit with nothing behind it (`REQ-A.5.7`, threat intelligence declared applicable in the SoA): no policy, procedure or record addresses it. Set `design.effective: false`, cite the SoA row in `design.evidence`, add a deviation with item `design`: "No documented process or record shows that threat information is collected or analysed, although the Statement of Applicability declares A.5.7 applicable.", conclude `design-gap`.

An event control where the population is empty: the sample is empty. Conclude `not-audited` with scope limitation "No terminations occurred during the records period, so the operation of the control could not be audited."
