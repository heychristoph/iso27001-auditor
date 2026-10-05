# Grading findings and concluding

Run `python scripts/iso27001.py rollup <engagement>` to see each requirement with its units and their conclusions, every deviation still to grade, and the Annex A controls the Statement of Applicability excludes (`review/rollup.md`). Then group the deviations into findings, grade each one, and write `findings.json`.

## From deviations to findings

A deviation is a fact in one workpaper. A finding is your judgment about a requirement. One finding can grade several deviations (three late access removals are one nonconformity against A.5.18), and one deviation can belong to only the finding that best describes it.

Each finding is recorded against **one** requirement, the one that was not fulfilled, with:
- a **statement** of the nonconformity: the requirement and what was not fulfilled;
- the **objective evidence**: counts, item IDs, dates and documents, specific enough that the organization can check it;
- links to the workpaper **deviations** it grades, and the **evidence** artifact IDs.

Do not suggest the cause of a nonconformity or its solution (ISO/IEC 17021-1 9.4.5.3). The organization analyses the cause.

Every deviation must be graded, and every `design-gap` must be a major or minor nonconformity. `validate --final` checks both.

## Grades

| Grade | ID | When |
|---|---|---|
| `major` | `NC-01` | The nonconformity affects the capability of the ISMS to achieve its intended results. Typical: a required process is absent or has broken down (no internal audit or no management review in the cycle, no risk assessment, no Statement of Applicability); several minor nonconformities against the same requirement that together show a systemic failure; a control failure that left a significant risk untreated (a terminated user keeping production access for months). |
| `minor` | `NC-02` | A requirement was not fulfilled, but the ISMS can still achieve its intended results: an isolated lapse, a missing record, an incomplete input. |
| `ofi` | `OFI-01` | The requirement is met, but something could be better. Use it for a deviation only when the requirement is still met, for example when the organization's own monitoring already found the lapse and corrective action under clause 10.2 is in progress; say so in the statement. |

When unsure between two grades, choose the more serious one and explain the judgment in the statement. At Stage 1, findings are areas of concern; grade them as they would be graded if still present at Stage 2.

For each requirement with deviations, weigh:
- **Rate and pattern.** One late item in a large sample may be isolated; repeated failures, or failures in a small population, point to a process that did not operate.
- **Cause.** A one-off human error is different from a missing process (a quarterly review that never happened).
- **Detection.** Did the organization's own internal audit, monitoring or corrective action process find and handle it? That is evidence the ISMS works.
- **Impact.** Could the failure have allowed the risk the requirement addresses?

## The conclusion

| `recommendation` | When | Printed (Stage 2) |
|---|---|---|
| `recommended` | No nonconformities and no scope limitations. OFIs are allowed. | A certification body could recommend certification. |
| `recommended-with-actions` | Minor nonconformities only (or a limited scope), no major. | Recommendation depends on acceptable correction and corrective action plans. |
| `not-recommended` | At least one major nonconformity. | Certification not recommended until corrections and corrective actions are implemented and verified. |
| `no-conclusion` | Scope limitations so significant that no conclusion can be formed. | No conclusion. |

The printed wording changes with the audit type: readiness for Stage 2 after a Stage 1, continued certification after a surveillance, renewal after a recertification. `validate --final` checks that the recommendation follows from the grades.

## findings.json

```json
{
  "schema_version": 1,
  "findings": [
    {
      "id": "NC-01",
      "grade": "minor",
      "requirement": "A.5.18",
      "statement": "Access rights were not removed in line with the access control policy, which requires removal within one business day of termination.",
      "objective_evidence": "For 1 of 5 terminations sampled (T-003), production access was removed 9 days after the termination date. The termination population also omitted one employee shown as terminated on 20 May 2026 in the HR system export.",
      "deviations": [{"control": "C-16", "item": "T-003"}, {"control": "C-16", "item": "population"}],
      "evidence": ["EV-0044", "EV-0051"],
      "management_response": null
    }
  ],
  "scope_limitations": [],
  "recommendation": "recommended-with-actions",
  "summary": "The ISMS is established, documented and operating. Internal audit and management review have been performed, risks are assessed and treated, and the controls in the Statement of Applicability are in place, except as described in the minor nonconformities in Section III.",
  "scope_appropriate": true,
  "scope_note": "",
  "prepared_by": "<agent / model>"
}
```

- `summary` is printed as the statement on the conformity and effectiveness of the ISMS (ISO/IEC 17021-1 9.4.8.3 a). Write it in the auditor's voice: what is in place, how effective it is, and where it falls short.
- `scope_appropriate` and `scope_note` are the conclusion on the appropriateness of the ISMS scope (9.4.8.3 b). A scope that leaves out a process, location or service the organization's information security depends on, without justification, is not appropriate.
- `management_response` stays `null` unless the organization provided its correction and corrective action; it prints in Section VI.
- Every string here is printed. It names no one but `management.name`, and contains no email address or phone number.
