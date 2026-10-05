# iso27001-auditor

An agent skill that runs an AI Audit of an information security management system against ISO/IEC 27001:2022 (with Amendment 1:2024). It is modeled on a certification body's Stage 1, Stage 2, surveillance or recertification audit: it pulls evidence from the organization's compliance platform, audits every ISMS clause and every Annex A control the Statement of Applicability declares applicable, grades findings as major or minor nonconformities or opportunities for improvement, and produces a PDF signed by the model that ran it. The report says it is an AI Audit, not an ISO/IEC 27001 certification.

It follows the open [Agent Skills](https://agentskills.io/specification) format, so the same `iso27001-audit/` folder works with Claude Code, Codex, Gemini CLI, Cursor, GitHub Copilot and other agents that read `SKILL.md`. All deterministic work runs in plain Python scripts, so nothing depends on one vendor's agent features. It is the ISO/IEC 27001 counterpart of [soc2-auditor](https://github.com/heychristoph/soc2-auditor) and shares its design.

## How an audit runs

```
init ──> ingest ──> check ──> plan ──> sample ──> audit ──> validate ──> QA ──> findings ──> signoff (model) ──> render + packet
          │           │                            │                     │         │
     connector     SoA review,             agent writes one        fresh context   grade major / minor / OFI,
     writes        REQ- units for          workpaper per unit      or another      conclude per audit type
     bundle/       uncovered requirements                          model reviews
```

- **Connectors** (`folder`, `probo`, `vanta`, `drata`) turn a source into an evidence bundle, including the Statement of Applicability where the source has one. Every file is hashed at ingest.
- **Units of work** are the organization's controls, each mapped to clauses and Annex A controls, plus a `REQ-` unit for every in-scope requirement no control covers. Certification audits cover the standard, not only what a platform models.
- **The agent** judges: evaluates design, audits each sampled item, records deviations, grades findings and forms the conclusion.
- **Scripts** count: seeded sampling, the surveillance coverage rule, validation, the requirement rollup, the link from every deviation to a graded finding, the consistency of the recommendation with the grades, and rendering the report from workpapers.
- **The model** signs `signoff --model` with its own name. Until then every PDF is watermarked DRAFT. Any later change to the work clears the signature.

## Audit types

| Type | Evidence | Conclusion |
|---|---|---|
| `stage1` | Documentation and readiness as of a date; one item per unit | Ready for Stage 2, ready with areas of concern, or not ready |
| `stage2` | Records sampled over a period | Certification could be recommended, recommended with corrective action plans, or not recommended |
| `surveillance` | Records over a period; the mandatory clauses plus a sample of Annex A | Continued certification |
| `recertification` | Records over a period; everything | Renewal of certification |

## Install

```bash
git clone git@github.com:heychristoph/iso27001-auditor.git
pip install -r iso27001-auditor/iso27001-audit/scripts/requirements.txt
```

Then make `iso27001-audit/` visible to your agent: copy or symlink it into the agent's skills directory (for Claude Code, `~/.claude/skills/iso27001-audit`), or tell the agent to read `iso27001-audit/SKILL.md`.

## Quick start

```bash
python iso27001-audit/scripts/iso27001.py init ./acme-2026 --type stage2 --start 2026-01-01 --end 2026-06-30 \
  --org "Acme, Inc." --scope "The ISMS supporting the development and operation of the Acme Platform, in accordance with Statement of Applicability version 2." \
  --connector probo --option organization_id=<id>
export PROBO_TOKEN=...
```

Then ask your agent: *"Run the AI Audit in ./acme-2026."* The agent signs the report with the model that ran it. `iso27001.py status ./acme-2026` shows progress and the next step at any time.

## The report

The PDF follows the content ISO/IEC 17021-1 (9.4.8) requires of a certification audit report:

1. **Audit report**: audit details, objectives and scope for the audit type, method and sampling disclaimer, summary of findings, statement on the conformity and effectiveness of the ISMS, internal audit and management review, appropriateness of the scope, the conclusion, and the model's signature.
2. **Scope and context of the ISMS**, as the organization documents it.
3. **Findings**, each recorded against one requirement with a statement and the objective evidence.
4. **Requirements, controls and results** for every clause and applicable Annex A control.
5. **Statement of Applicability**: all 93 Annex A controls, the organization's decision, its exclusion justifications, and the audit result.
6. **The organization's response** to findings.

## Design guidelines

1. **One contract: the engagement folder.** All state is files described by JSON Schemas in `iso27001-audit/assets/schemas/`. Any step can be rerun or resumed by any agent.
2. **Vendor names stay in the connectors.** A new source is one Python module with a `pull()` function plus one reference page. Nothing downstream changes.
3. **Scripts count, agents judge.** Hashing, sampling, validation and report text are code. Evidence inspection, design evaluation, grading and the conclusion are the agent's.
4. **No conclusion without evidence.** Every pass cites hashed artifacts; the validator rejects anything uncited, and the plan block is recomputed so samples can't be changed.
5. **Every deviation is graded.** A deviation in a workpaper must be linked from a finding in `findings.json`, and the recommendation must follow from the grades.
6. **The report is rendered, never written.** Report text comes from `assets/report/report-text.yaml` plus the workpapers and findings, so the PDF cannot disagree with the work. Replace the wording and the Typst layout without touching code.
7. **Evals before claims.** Synthetic engagements with planted defects measure what any agent and model actually catches.

## Repository layout

```
iso27001-audit/              the skill (self-contained, spec-valid)
├── SKILL.md                 workflow and rules
├── references/              one page per step and per connector
├── scripts/                 iso27001.py CLI, connectors/
└── assets/                  requirements catalog, sampling table, schemas, report template and wording
evals/                       fixtures, oracle, graders, agent runner, Probo mock
```

## Evals

```bash
python evals/make_fixture.py                     # synthetic Stage 1 and Stage 2 engagements
python evals/run.py --case stage2 --agent oracle # model-free regression test of the scripts
python evals/run.py --case stage2 --agent 'claude -p --permission-mode bypassPermissions {prompt}'
python evals/test_probo_connector.py             # Probo connector against a local mock
```

See [evals/README.md](evals/README.md).

## Status

- Tested: the full pipeline with the oracle on both fixtures (score 1.0), the surveillance coverage rule, the folder connector, and the Probo connector against a mock built from Probo's published MCP specification.
- Not yet tested: Probo, Vanta and Drata against live accounts; a full run by a real agent on the fixtures.
- Not included yet: multi-site sampling (IAF MD 1), audit time calculation (ISO/IEC 27006-1 Annex C), transfer audits, integrated audits with other management system standards, and surveillance and recertification fixtures.

## Professional responsibility

This tool produces an AI Audit. It is not an ISO/IEC 27001 certification audit, it is not performed by a certification body accredited to ISO/IEC 17021-1 and ISO/IEC 27006-1, and no certificate can be issued on it. The model that ran the work signs the PDF, and the report says so. The requirement summaries in `assets/requirements.yaml` are paraphrases; the authoritative text of ISO/IEC 27001 is published by ISO and IEC.
