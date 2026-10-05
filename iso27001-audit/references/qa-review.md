# QA review

An independent reviewer challenges each workpaper before the findings are graded. The goal is to find the conclusions that would not survive a careful reading.

Run this in a fresh context: a separate agent, a new session, or a different model from the one that audited the units. A reviewer who shares the auditor's context tends to repeat its mistakes.

## For each workpaper

1. **Re-open the evidence.** For at least two sampled items (all items if there are five or fewer), open the cited files yourself and confirm they show what the workpaper claims: the right person, system, dates and values.
2. **Check the attributes against the requirements.** Do they test everything the control description promises and everything each requirement in `criteria` asks? A unit mapped to clause 9.3.2 needs every listed input checked, not only that a meeting took place. A unit mapped to 9.2.2 needs the auditor's objectivity checked.
3. **Look for missed deviations.** Compare dates and thresholds against the organization's documented information. Look for evidence dated outside the records period, approvals by the same person who made the change, an internal auditor auditing their own process, Statement of Applicability exclusions with no justification, and items marked `pass` with thin or unrelated evidence.
4. **Check `REQ-` units.** A requirement audited directly still needs documented information and a record of it working. A policy sentence alone is design evidence, not implementation evidence.
5. **Check the population test** (records-based audits): was the population compared to an independent source, and does the comparison hold up?
6. **Check the wording.** Deviation descriptions must be factual and specific enough to print. Disagree when `statement`, a deviation description, `scope_limitation`, or `design.rationale` names anyone other than `management.name`, or contains an email address or a phone number. Those belong in `observations`.
7. **Record the verdict:**

```bash
python scripts/iso27001.py qa <engagement> <unit> --verdict agree --checked EV-0012 EV-0013 --by "<agent / model>"
python scripts/iso27001.py qa <engagement> <unit> --verdict disagree --issue "Minutes omit clause 9.3.2 f inputs but attribute B is marked pass" --checked EV-0044 --by "<agent / model>"
```

The command binds the verdict to the workpaper's current hash. If the workpaper changes after review, `validate --final` reports the review as stale and it must be reviewed again.

## After a disagreement

The workpaper goes back to auditing. The auditor fixes it, runs `validate`, and the reviewer reviews it again. A reviewer does not edit workpapers.
