# Report, review packet and sign-off

## Build

```bash
python scripts/iso27001.py validate <engagement> --final   # workpapers, QA, findings, ISMS scope
python scripts/iso27001.py render <engagement>
python scripts/iso27001.py packet <engagement>
```

`render` writes to `report/`:

- `iso27001-<type>-<org>-DRAFT.pdf` until sign-off, then `iso27001-<type>-<org>.pdf`: an AI Audit in the shape of a certification body's audit report (ISO/IEC 17021-1 9.4.8). The cover, header and Section I say it is not an ISO/IEC 27001 certification.
  - Section I, the audit report: audit details, objectives, scope, method, summary of findings, conformity and effectiveness of the ISMS, internal audit and management review, appropriateness of the scope, the conclusion, and the model's signature.
  - Section II, the organization's description of its ISMS scope and context.
  - Section III, the graded findings: requirement, statement, objective evidence.
  - Section IV, every requirement in scope with the units that address it, the procedures performed and the results.
  - Section V, the Statement of Applicability: every Annex A control, the organization's decision, its justification for an exclusion, and the audit result.
  - Section VI, the organization's response to findings.
- `workpapers.xlsx`: units, samples, deviations, findings, the SoA and the evidence register.
- `evidence-index.csv`: every artifact with its hash and the workpapers and findings that cite it.
- `report-data.json`: the exact data the PDF was built from.

Report text comes from `assets/report/report-text.yaml` and the workpapers; the layout is `assets/report/report.typ`. Replace the wording with your own reviewed templates by editing the YAML, and the branding by editing the Typst file. Neither requires code changes.

## What the PDF may identify

The PDF names the organization, its suppliers, `management.name` and title, and the model that signed. It names no one else. It contains no email address and no phone number. `validate --final` enforces this on every string the PDF can contain, and `signoff` and `render` both run that check.

- Section IV prints the workpaper `statement` when it is set, otherwise the control title from `controls.csv`. The source description stored in `control` is not printed.
- Section II prints `isms.yaml` at the engagement root. It prints `bundle/isms.yaml` only when that file is `management-approved`. A connector draft is omitted, and the section says the description was not provided.
- The same check covers procedures, deviation descriptions, design rationales, scope limitations, sample notes, findings (statement, objective evidence, response), the summary and the scope note.
- Statement of Applicability justifications are the organization's text; Section V prints them with any email address, phone number or person's name replaced by `[redacted]`. So do `report/evidence-index.csv` and the Evidence sheet of `workpapers.xlsx`. Files in `bundle/` are unchanged.

`review/packet.md` is the internal record. It quotes observations in full. Send the organization the PDF, not the packet and not the bundle.

## Sign-off

`review/packet.md` is the record of the conclusion, every finding, deviation, design gap and scope limitation, low- and medium-confidence conclusions, and auditor observations. Each entry links to the evidence files.

The model that ran the audit signs it:

```bash
python scripts/iso27001.py signoff <engagement> --model "Grok 4.7"
python scripts/iso27001.py render <engagement>
```

`signoff` re-validates everything and records the model name, today's date, and a digest of the workpapers, test plan, QA, findings, ISMS description and bundle manifest. `render` writes the AI Audit PDF without the draft watermark. Section I is signed:

```
Grok 4.7
AI Auditor
5 October 2026
Not an ISO/IEC 27001 certification.
```

Section I also names the organization's representative from `management.name` and `management.title`: the real person and role, taken from the evidence and written in `engagement.yaml` before sign-off. The report never prints a blank, a bracket, or a placeholder for a date, a name, or a title. Any later change to the work clears the signature and the next render is a draft again. Do not edit `signoff` by hand, and do not sign as a certification body or a person.

## The organization's part

- **ISMS scope and context.** The organization owns them. The file readers see is `isms.yaml` at the engagement root, written for the report and not copied from the connector draft. Put the approved version there with `status: management-approved`. The AI Audit can be signed before that; the report then says the description is not management-approved.
- **Statement of Applicability.** The organization's document. Review it; never edit `bundle/soa.csv`.
- **Responses to findings.** Record the organization's correction and corrective action in each finding's `management_response`; they print in Section VI. A certification body would expect them within its deadline (commonly 90 days for a major nonconformity); this AI Audit only reports them.
