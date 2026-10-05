"""`validate`, `rollup`, `packet` and `signoff`.

`validate` is the gate between phases: every conclusion must cite evidence that
exists in the bundle, cover exactly the planned sample, and agree with its own
results; every deviation must be graded in findings.json, and the recommendation
must follow from the grades. Messages name the file and field so the agent can
fix them directly.
"""

from __future__ import annotations

import datetime as dt
import random
from collections import defaultdict

from core import AUDIT_TYPES, AuditError, Engagement, dump_json, dump_yaml, load_json, load_requirements, load_yaml, parse_date, schema_errors, sha256_file
from planning import expected_plan, surveillance_gaps
import privacy

DONE = ("conforming", "deviations", "design-gap", "not-audited")
GRADE_NAMES = {"major": "major nonconformity", "minor": "minor nonconformity", "ofi": "opportunity for improvement"}


def validate(eng: Engagement, final: bool = False) -> tuple[list[str], list[str]]:
    """Check workpapers (and, when `final`, findings, QA, scope and management). Returns (errors, warnings)."""
    errors, warnings = [], []
    plan_rows = {r["control_id"]: r for r in eng.testplan()}
    if not plan_rows:
        return ["No testplan.csv. Run `iso27001.py plan` and `iso27001.py sample` first."], []
    included = eng.included()
    workpapers = eng.load_workpapers()

    for cid in sorted(included):
        if cid not in workpapers:
            errors.append(f"{cid}: no workpaper; run `iso27001.py sample`")
    for cid, wp in workpapers.items():
        if cid in plan_rows and cid not in included:
            errors.append(f"workpapers/{eng.workpaper_path(cid).name}: {cid} is excluded in testplan.csv; run `iso27001.py sample` to remove it")
            continue
        e, w = _check_workpaper(eng, cid, wp, plan_rows.get(cid))
        errors += e
        warnings += w

    if final:
        e, w = _check_findings(eng, workpapers)
        errors += e
        warnings += w
        errors += _check_qa(eng, workpapers)
        isms = eng.isms
        if not isms:
            errors.append("no ISMS scope and context; the organization must provide isms.yaml (see references/reporting.md)")
        elif isms.get("status") != "management-approved":
            warnings.append("isms.yaml is not management-approved; the AI Audit will say so")
        errors += _check_management(eng)
        leaked, notes = privacy.check(eng)
        errors += leaked
        warnings += notes
    return errors, warnings


def _check_management(eng: Engagement) -> list[str]:
    """The report names a real representative and role, not a blank or a placeholder."""
    mgmt = eng.config.get("management") or {}
    name = str(mgmt.get("name") or "").strip()
    title = str(mgmt.get("title") or "").strip()
    if _placeholder(name) or _placeholder(title):
        return ["engagement.yaml needs management.name and management.title: the organization's real representative for this audit and their role, taken from the evidence. Do not use a placeholder."]
    return []


def _placeholder(value: str) -> bool:
    if not value:
        return True
    low = value.lower()
    return any(mark in low for mark in ("[", "]", "placeholder", "name, title", "todo", "tbd", "n/a"))


def _check_workpaper(eng: Engagement, cid: str, wp: dict, plan_row: dict | None) -> tuple[list[str], list[str]]:
    where = f"workpapers/{eng.workpaper_path(cid).name}"
    errors = [f"{where}: {m}" for m in schema_errors(wp, "workpaper")]
    warnings: list[str] = []
    if errors:
        return errors, warnings
    if plan_row is None:
        return [f"{where}: unit {cid} is not in testplan.csv"], warnings
    if wp["plan"] != expected_plan(eng, plan_row):
        errors.append(f"{where}: plan does not match testplan.csv and the sampling seed; do not edit `plan`, re-run `iso27001.py sample`")

    concl = wp["conclusion"]
    if concl == "pending":
        return [f"{where}: conclusion is still 'pending'"], warnings
    for field in ("confidence", "prepared_by"):
        if not wp.get(field):
            errors.append(f"{where}: {field} is required")

    cite = lambda ids, label: [f"{where}: {label} cites {i}, which is not in bundle/manifest.json" for i in ids if i not in eng.artifacts]

    design = wp["design"]
    if design["effective"] is None:
        errors.append(f"{where}: design.effective must be true or false")
    if not design["rationale"].strip():
        errors.append(f"{where}: design.rationale is empty")
    if not design["evidence"]:
        errors.append(f"{where}: design.evidence must cite at least one artifact (policy, procedure, record or configuration)")
    errors += cite(design["evidence"], "design.evidence")
    if design["effective"] is False and concl != "design-gap":
        errors.append(f"{where}: design.effective is false, so conclusion must be 'design-gap'")
    deviated = {x["item"] for x in wp["deviations"]}
    if concl == "design-gap" and "design" not in deviated:
        errors.append(f"{where}: a design gap needs a deviation with item 'design' stating which requirement the design does not meet")

    if concl == "not-audited":
        if not (wp.get("scope_limitation") or "").strip():
            errors.append(f"{where}: conclusion 'not-audited' needs scope_limitation (why the unit could not be audited)")
        return errors, warnings

    if not wp["procedures"]:
        errors.append(f"{where}: procedures is empty; list what was done (inquiry, inspection, observation, reperformance)")
    elif all(p["method"] == "inquiry" for p in wp["procedures"]):
        errors.append(f"{where}: inquiry alone does not support a conclusion; add inspection, observation or reperformance")
    if concl != "design-gap":
        if not wp["attributes"]:
            errors.append(f"{where}: attributes is empty; define what must be true for each sampled item")
        planned = wp["plan"]["sample"]
        tested = [i["id"] for i in wp["items"]]
        if sorted(tested) != sorted(planned):
            missing, extra = sorted(set(planned) - set(tested)), sorted(set(tested) - set(planned))
            errors.append(f"{where}: items must match plan.sample exactly (missing {missing}, unexpected {extra})")
        failed_items = set()
        start, end = eng.period
        for item in wp["items"]:
            missing_attrs = sorted(set(wp["attributes"]) - set(item["results"]))
            if missing_attrs:
                errors.append(f"{where}: item {item['id']} has no result for attributes {missing_attrs}")
            if not item["evidence"] and any(v == "pass" for v in item["results"].values()):
                errors.append(f"{where}: item {item['id']} passes an attribute but cites no evidence; a pass must be supported")
            errors += cite(item["evidence"], f"item {item['id']}")
            if any(v == "n/a" for v in item["results"].values()) and not item.get("note"):
                errors.append(f"{where}: item {item['id']} marks an attribute n/a without a note explaining why")
            if any(v == "fail" for v in item["results"].values()):
                failed_items.add(item["id"])
            for ev in item["evidence"]:
                d = parse_date(eng.artifacts.get(ev, {}).get("date"))
                if d and not eng.stage1 and not (start - dt.timedelta(days=31) <= d <= end + dt.timedelta(days=31)):
                    warnings.append(f"{where}: item {item['id']} relies on {ev} dated {d}, outside the records period")
        for item_id in sorted(failed_items - deviated):
            errors.append(f"{where}: item {item_id} failed an attribute but has no entry in deviations")
        pop = wp["plan"]["population"]
        if pop and pop["source"].startswith("PO-") and not eng.stage1:
            pc = wp.get("population_check")
            if not pc:
                errors.append(f"{where}: population_check is required; test completeness of {pop['source']} against an independent record")
            else:
                errors += cite(pc["evidence"], "population_check")
                if pc["complete"] is False and "population" not in deviated:
                    errors.append(f"{where}: population_check.complete is false, so add a deviation with item 'population'")

    for x in wp["deviations"]:
        errors += cite(x["evidence"], f"deviation on {x['item']}")
        if x["item"] not in wp["plan"]["sample"] and x["item"] not in ("design", "population"):
            errors.append(f"{where}: deviation item '{x['item']}' is not in the sample (use 'design' or 'population' for other deviations)")
    if wp["deviations"] and concl == "conforming":
        errors.append(f"{where}: deviations are listed, so conclusion cannot be 'conforming'")
    if not wp["deviations"] and concl == "deviations":
        errors.append(f"{where}: conclusion is 'deviations' but the deviations list is empty")
    return errors, warnings


def _check_findings(eng: Engagement, workpapers: dict) -> tuple[list[str], list[str]]:
    if not eng.findings_path.exists():
        return ["findings.json is missing; see references/evaluating.md"], []
    doc = load_json(eng.findings_path)
    errors = [f"findings.json: {m}" for m in schema_errors(doc, "findings")]
    if errors:
        return errors, []
    warnings: list[str] = []
    in_scope = {r["id"] for r in eng.requirements}
    findings = doc["findings"]

    ids = [f["id"] for f in findings]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"findings.json: duplicate finding ID {dup}")
    graded: dict[tuple[str, str], set[str]] = defaultdict(set)
    for f in findings:
        where = f"findings.json {f['id']}"
        if (f["grade"] == "ofi") != f["id"].startswith("OFI-"):
            errors.append(f"{where}: use NC-.. for major and minor nonconformities and OFI-.. for opportunities for improvement")
        if f["requirement"] not in in_scope:
            errors.append(f"{where}: requirement {f['requirement']} is not in scope (unknown, or excluded by the Statement of Applicability)")
        errors += [f"{where}: evidence cites {i}, which is not in bundle/manifest.json" for i in f["evidence"] if i not in eng.artifacts]
        if f["grade"] != "ofi" and not (f["deviations"] or f["evidence"]):
            errors.append(f"{where}: a nonconformity rests on objective evidence; link its workpaper deviations or cite artifacts")
        for link in f["deviations"]:
            wp = workpapers.get(link["control"])
            if not wp:
                errors.append(f"{where}: links unknown workpaper {link['control']}")
            elif link["item"] not in {x["item"] for x in wp["deviations"]}:
                errors.append(f"{where}: {link['control']} has no deviation on item '{link['item']}'")
            else:
                graded[(link["control"], link["item"])].add(f["grade"])

    for cid, wp in sorted(workpapers.items()):
        for x in wp.get("deviations") or []:
            grades = graded.get((cid, x["item"]))
            if not grades:
                errors.append(f"findings.json: deviation {cid} / {x['item']} is not graded; link it from a finding (major, minor or ofi)")
            elif grades == {"ofi"}:
                if x["item"] == "design":
                    errors.append(f"findings.json: the design gap in {cid} is a nonconformity; grade it major or minor, not ofi")
                else:
                    warnings.append(f"findings.json: deviation {cid} / {x['item']} is only an opportunity for improvement; the statement must say why the requirement is still met")
        if wp.get("conclusion") == "not-audited" and any(c.startswith(("9.2", "9.3")) for c in wp["criteria"]) and not eng.stage1:
            warnings.append(f"{cid}: internal audit and management review are reported on in every audit; if they were not performed, that is a nonconformity, not a scope limitation")

    # Coverage: a full audit covers every requirement in scope; a surveillance audit the mandatory clauses.
    covered = {x for wp in workpapers.values() for x in wp["criteria"]}
    if eng.audit_type == "surveillance":
        gaps = surveillance_gaps(eng, set(workpapers))
        if gaps:
            errors.append(f"findings.json: a surveillance audit must cover {gaps}; include units mapped to them")
    else:
        missing = [r for r in sorted(in_scope - covered, key=_order)]
        if missing:
            errors.append(f"findings.json: requirements {missing} have no workpaper; run `iso27001.py plan` and `sample`")

    majors = sum(f["grade"] == "major" for f in findings)
    minors = sum(f["grade"] == "minor" for f in findings)
    limits = bool(doc["scope_limitations"])
    rec = doc["recommendation"]
    if rec == "recommended" and (majors or minors or limits):
        errors.append("findings.json: 'recommended' needs no nonconformities and no scope limitations")
    if rec == "recommended-with-actions" and (majors or not (minors or limits)):
        errors.append("findings.json: 'recommended-with-actions' is for minor nonconformities (or limited scope) and no major nonconformity")
    if rec == "not-recommended" and not majors:
        errors.append("findings.json: 'not-recommended' needs at least one major nonconformity")
    if rec == "no-conclusion" and not limits:
        errors.append("findings.json: 'no-conclusion' needs scope_limitations")
    if majors and rec not in ("not-recommended", "no-conclusion"):
        errors.append("findings.json: a major nonconformity means 'not-recommended' (or 'no-conclusion' when scope limitations prevent any conclusion)")
    if not doc["scope_appropriate"] and not (doc.get("scope_note") or "").strip():
        errors.append("findings.json: scope_note must explain why the ISMS scope is not appropriate")
    return errors, warnings


def _order(requirement_id: str):
    order = {r["id"]: i for i, r in enumerate(load_requirements())}
    return order.get(requirement_id, 999)


def _check_qa(eng: Engagement, workpapers: dict) -> list[str]:
    if not eng.qa_path.exists():
        return ["review/qa.json is missing; run the QA review (references/qa-review.md)"]
    qa = load_json(eng.qa_path)
    errors = [f"review/qa.json: {m}" for m in schema_errors(qa, "qa")]
    if errors:
        return errors
    latest = {r["control_id"]: r for r in qa["reviews"]}
    for cid in workpapers:
        r = latest.get(cid)
        if not r:
            errors.append(f"{cid}: no QA review")
        elif r["workpaper_sha256"] != sha256_file(eng.workpaper_path(cid)):
            errors.append(f"{cid}: workpaper changed after QA review; QA must review it again")
        elif r["verdict"] != "agree":
            errors.append(f"{cid}: QA disagrees ({'; '.join(r['issues'])[:200]}); resolve, then re-review")
    return errors


def record_qa(eng: Engagement, control_id: str, verdict: str, issues: list[str], checked: list[str], reviewer: str) -> None:
    """Add or replace the QA review of one workpaper, bound to the workpaper's current hash."""
    path = eng.workpaper_path(control_id)
    if not path.exists():
        raise AuditError(f"No workpaper for {control_id}.")
    if verdict == "disagree" and not issues:
        raise AuditError("A 'disagree' verdict needs at least one --issue explaining what is wrong.")
    unknown = [e for e in checked if e not in eng.artifacts]
    if unknown:
        raise AuditError(f"--checked cites artifacts not in the bundle: {unknown}")
    qa = load_json(eng.qa_path) if eng.qa_path.exists() else {"schema_version": 1, "reviews": []}
    qa["reviews"] = [r for r in qa["reviews"] if r["control_id"] != control_id]
    qa["reviews"].append({"control_id": control_id, "workpaper_sha256": sha256_file(path), "verdict": verdict,
                          "issues": issues, "evidence_checked": checked, "reviewed_by": reviewer})
    qa["reviews"].sort(key=lambda r: r["control_id"])
    dump_json(qa, eng.qa_path)


# --- rollup ------------------------------------------------------------------


def rollup(eng: Engagement) -> str:
    """Requirement-level summary and the list of deviations to grade. Written to review/rollup.md."""
    workpapers = eng.load_workpapers()
    by_req = defaultdict(list)
    for cid, wp in workpapers.items():
        for c in wp["criteria"]:
            by_req[c].append((cid, wp["conclusion"], len(wp["deviations"])))
    surveillance = eng.audit_type == "surveillance"
    lines = [f"# Requirement rollup: {eng.config['organization']} ({AUDIT_TYPES[eng.audit_type]} audit)", "",
             "| Requirement | Title | Units (conclusion, deviations) | Needs judgment |", "|---|---|---|---|"]
    for req in eng.requirements:
        entries = by_req.get(req["id"], [])
        cell = "; ".join(f"{cid} {concl} ({n})" for cid, concl, n in entries) or ("not in this surveillance sample" if surveillance else "**no unit**")
        flag = ""
        if not entries:
            flag = "" if surveillance else "No unit covers this requirement"
        elif any(c == "design-gap" for _, c, _ in entries):
            flag = "Design gap: a nonconformity"
        elif any(n for _, _, n in entries):
            flag = "Deviations: grade them in findings.json"
        elif all(c == "not-audited" for _, c, _ in entries):
            flag = "Not audited: scope limitation or no occurrences?"
        lines.append(f"| {req['id']} | {req['title']} | {cell} | {flag} |")

    lines += ["", "## Deviations to grade", "", "| Unit | Item | Requirements | Description |", "|---|---|---|---|"]
    for cid, wp in sorted(workpapers.items()):
        for x in wp["deviations"]:
            lines.append(f"| {cid} | {x['item']} | {' '.join(wp['criteria'])} | {x['description']} |")

    if eng.soa:
        excluded = [(cid, row) for cid, row in eng.soa.items() if cid not in {r['id'] for r in eng.requirements}]
        lines += ["", f"## Annex A controls the Statement of Applicability excludes ({len(excluded)})", "",
                  "Check each justification against the risk assessment and the scope (clause 6.1.3).", "",
                  "| Control | Justification |", "|---|---|"]
        lines += [f"| {cid} | {(row.get('justification') or '**none**').replace('|', '/')} |" for cid, row in excluded]
    text = "\n".join(lines) + "\n"
    eng.review.mkdir(parents=True, exist_ok=True)
    (eng.review / "rollup.md").write_text(text, encoding="utf-8")
    return text


# --- review packet -------------------------------------------------------------

SPOT_CHECKS = 5  # Conforming units to re-read; enough to catch systematic errors cheaply.


def packet(eng: Engagement) -> str:
    """The record of what the AI Audit concluded. Written to review/packet.md."""
    workpapers = eng.load_workpapers()
    doc = load_json(eng.findings_path) if eng.findings_path.exists() else None
    errors, warnings = validate(eng, final=True)

    def ev_links(ids):
        return ", ".join(f"[{i}](../bundle/{eng.artifacts[i]['path']})" for i in ids if i in eng.artifacts) or "none"

    out = [f"# Review packet: {eng.config['organization']}, AI Audit ({AUDIT_TYPES[eng.audit_type]} audit procedures, ISO/IEC 27001:2022)", "",
           "This packet supports an AI Audit. It is not an ISO/IEC 27001 certification audit. It is the internal record: it quotes observations and the source control text, and it is not the report for the organization.", "",
           f"Scope: {eng.config['scope']} Records: {eng.period_label}. Digest: `{eng.digest()[:16]}`.", ""]
    if errors:
        out += ["## Blocking issues", "", *[f"- {e}" for e in errors], ""]
    out += ["## Recommendation", ""]
    if doc:
        out += [f"**{doc['recommendation']}** (prepared by {doc['prepared_by']}).", "", doc["summary"], ""]
        out += [f"## Findings ({len(doc['findings'])})", ""]
        for f in doc["findings"]:
            out.append(f"### {f['id']} ({GRADE_NAMES[f['grade']]}) against {f['requirement']}")
            out.append(f"- Statement: {f['statement']}")
            out.append(f"- Objective evidence: {f['objective_evidence']} Evidence: {ev_links(f['evidence'])}")
            if f["deviations"]:
                out.append("- Deviations: " + ", ".join(f"{d['control']} / {d['item']}" for d in f["deviations"]))
            out.append("")
    else:
        out += ["Not yet decided.", ""]

    sections = [
        ("Deviations", [w for w in workpapers.values() if w["deviations"]]),
        ("Design gaps", [w for w in workpapers.values() if w["conclusion"] == "design-gap"]),
        ("Not audited (scope limitations)", [w for w in workpapers.values() if w["conclusion"] == "not-audited"]),
        ("Low or medium confidence conclusions", [w for w in workpapers.values() if w.get("confidence") in ("low", "medium")]),
        ("Observations raised by the auditor", [w for w in workpapers.values() if w.get("observations")]),
    ]
    for title, wps in sections:
        out += [f"## {title} ({len(wps)})", ""]
        for w in wps:
            out.append(f"### {w['control_id']}: {privacy.activity(eng, w)}")
            out.append(f"Conclusion: {w['conclusion']}, confidence: {w.get('confidence')}. Requirements: {', '.join(w['criteria'])}.")
            for x in w["deviations"]:
                out.append(f"- Deviation ({x['item']}): {x['description']} Evidence: {ev_links(x['evidence'])}")
            if w.get("scope_limitation"):
                out.append(f"- Scope limitation: {w['scope_limitation']}")
            for o in w.get("observations") or []:
                out.append(f"- Observation: {o}")
            out.append("")

    passing = sorted(cid for cid, w in workpapers.items() if w["conclusion"] == "conforming")
    rng = random.Random(eng.digest())
    picks = sorted(rng.sample(passing, min(SPOT_CHECKS, len(passing))))
    out += [f"## Spot checks ({len(picks)} conforming units, chosen at random)", "",
            "Re-perform one sample item for each and confirm the evidence supports the conclusion.", ""]
    for cid in picks:
        w = workpapers[cid]
        item = w["items"][0] if w["items"] else None
        out.append(f"- **{cid}**: {privacy.activity(eng, w)}. " + (f"Item {item['id']}: evidence {ev_links(item['evidence'])}" if item else "No items."))
    if warnings:
        out += ["", "## Warnings", "", *[f"- {w}" for w in warnings]]
    out += ["", "## Sign-off", "",
            "Set management.name and management.title to the organization's real representative and role, then sign with "
            "`iso27001.py signoff <engagement> --model \"<model name>\"` and `iso27001.py render`. "
            "The PDF shows that model name, the title AI Auditor, the representative's name and title, and the signature date. "
            "It is an AI Audit, not an ISO/IEC 27001 certification. Any later change to the work clears the signature.", ""]
    text = "\n".join(out)
    eng.review.mkdir(parents=True, exist_ok=True)
    (eng.review / "packet.md").write_text(text, encoding="utf-8")
    return text


# --- sign-off ------------------------------------------------------------------


def signoff(eng: Engagement, model: str) -> str:
    """Record the model that ran the AI Audit, bound to the digest of the work."""
    model = (model or "").strip()
    if not model:
        raise AuditError("Sign-off needs --model, the name of the model that ran the AI Audit.")
    errors, _ = validate(eng, final=True)
    if errors:
        raise AuditError("Cannot sign off while validation fails:\n  " + "\n  ".join(errors[:20]))
    config = load_yaml(eng.config_path)
    config["auditor"] = "AI Audit"
    config["signoff"] = {"model": model, "date": dt.date.today().isoformat(), "digest": ""}
    dump_yaml(config, eng.config_path)
    # auditor is part of the digest. Compute it after writing, then store it.
    digest = eng.digest()
    config["signoff"]["digest"] = digest
    dump_yaml(config, eng.config_path)
    return digest


def signed_off(eng: Engagement) -> bool:
    s = load_yaml(eng.config_path).get("signoff") or {}
    return bool(s.get("model")) and s.get("digest") == eng.digest()
