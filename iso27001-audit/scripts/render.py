"""`render`: build the report PDF, workpaper spreadsheet and evidence index from the workpapers.

All report text comes from assets/report/report-text.yaml plus the validated
workpapers, findings and ISMS description. Nothing is written freehand here, so
the PDF cannot disagree with the work behind it.
"""

from __future__ import annotations

import csv
import datetime as dt
import re
import shutil
import tempfile
from pathlib import Path

from core import ASSETS, AuditError, Engagement, dump_json, fmt_date, load_catalog, load_json, load_yaml, parse_date
from review import signed_off, validate
import privacy

GRADE_ORDER = {"major": 0, "minor": 1, "ofi": 2}


class _Keep(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def render(eng: Engagement) -> dict:
    errors, warnings = validate(eng, final=True)
    if errors:
        raise AuditError("Fix validation errors before rendering:\n  " + "\n  ".join(errors[:30]))
    final = signed_off(eng)
    text = load_yaml(ASSETS / "report" / "report-text.yaml")
    data = _report_data(eng, text, final)
    eng.report.mkdir(parents=True, exist_ok=True)
    stem = f"iso27001-{eng.audit_type}-{re.sub(r'[^a-z0-9]+', '-', eng.config['organization'].lower()).strip('-')}"
    pdf = eng.report / f"{stem}{'' if final else '-DRAFT'}.pdf"
    _compile_pdf(data, pdf)
    dump_json(data, eng.report / "report-data.json")
    xlsx = eng.report / "workpapers.xlsx"
    _write_xlsx(eng, xlsx)
    index = eng.report / "evidence-index.csv"
    _write_evidence_index(eng, index)
    return {"pdf": pdf, "xlsx": xlsx, "evidence_index": index, "final": final, "warnings": warnings}


# --- report content --------------------------------------------------------------


def _fill(s: str, v: _Keep) -> str:
    for _ in range(3):  # placeholders can contain placeholders
        s = s.format_map(v)
    s = re.sub(r"(?<!\.)\.\.(?!\.)", ".", s)  # "Inc." at the end of a sentence
    return " ".join(s.split())


class _Results:
    """What the audit concluded about each requirement, from workpapers and findings."""

    def __init__(self, eng: Engagement, findings: list[dict]):
        self.eng = eng
        self.workpapers = eng.load_workpapers()
        self.findings = findings
        self.surveillance = eng.audit_type == "surveillance"

    def units(self, req_id: str) -> list[dict]:
        return [wp for _, wp in sorted(self.workpapers.items()) if req_id in wp["criteria"]]

    def direct(self, req_id: str) -> list[dict]:
        """Findings recorded against this requirement."""
        return [f for f in self.findings if f["requirement"] == req_id]

    def related(self, req_id: str) -> list[dict]:
        """Findings recorded against another requirement that grade a deviation in a unit mapped to this one."""
        ids = {wp["control_id"] for wp in self.units(req_id)}
        return [f for f in self.findings if f["requirement"] != req_id and any(d["control"] in ids for d in f["deviations"])]

    @staticmethod
    def label(findings: list[dict]) -> str:
        ordered = sorted(findings, key=lambda f: (GRADE_ORDER[f["grade"]], f["id"]))
        return ", ".join(f["id"] if f["grade"] == "ofi" else f"{f['id']} ({f['grade']})" for f in ordered)

    def result(self, req_id: str, labels: dict) -> tuple[str, bool]:
        """Short result for a requirement and whether a nonconformity is recorded against it."""
        units = self.units(req_id)
        direct = self.direct(req_id)
        related = [f for f in self.related(req_id) if f["grade"] != "ofi"]
        see = f"; see {', '.join(f['id'] for f in related)}" if related else ""
        ncs = [f for f in direct if f["grade"] != "ofi"]
        if ncs:
            return self.label(ncs) + see, True
        if not units:
            return (labels["not_sampled"] if self.surveillance else labels["not_audited"]), False
        if all(wp["conclusion"] == "not-audited" for wp in units):
            return labels["not_audited"] + see, False
        ofis = [f for f in direct if f["grade"] == "ofi"]
        return labels["conforming"] + (f"; {self.label(ofis)}" if ofis else "") + see, False


def _report_data(eng: Engagement, text: dict, final: bool) -> dict:
    doc = load_json(eng.findings_path)
    cfg = eng.config
    catalog = load_catalog()
    reqs = {r["id"]: r for r in catalog["requirements"]}
    std = text["standards"]
    atype = text["audit_types"][eng.audit_type]
    s1, s3 = text["section1"], text["section3"]
    signoff = cfg.get("signoff") or {}
    model = (signoff.get("model") or "").strip()
    if not model or not signoff.get("date"):
        raise AuditError("Run `iso27001.py signoff --model \"<model name>\"` before render. The report is signed with that model name, the title AI Auditor, and the date of the signature.")
    report_date = fmt_date(parse_date(signoff["date"]))
    mgmt = cfg.get("management") or {}
    representative = f"{str(mgmt.get('name') or '').strip()}, {str(mgmt.get('title') or '').strip()}"
    isms = privacy.report_isms(eng) or {}
    findings = sorted(doc["findings"], key=lambda f: (GRADE_ORDER[f["grade"]], f["id"]))
    results = _Results(eng, findings)
    annex = [r for r in catalog["requirements"] if r["kind"] == "annex"]
    applicable = [r for r in annex if eng.applicable(r)]
    sampled = [r for r in applicable if results.units(r["id"])]
    start, end = eng.period
    counts = {g: sum(f["grade"] == g for f in findings) for g in GRADE_ORDER}
    soa_version = str(isms.get("soa_version") or "").strip()

    v = _Keep(
        org=cfg["organization"], scope=cfg["scope"].strip(), model=model, representative=representative,
        type_label=atype["label"], period=eng.period_label,
        period_dates=fmt_date(end) if eng.stage1 else f"{fmt_date(start)} to {fmt_date(end)}",
        standard=std["short"], standard_full=std["iso27001"], certification=std["certification"],
        soa_version=f" ({soa_version})" if soa_version else "",
        applicable=str(len(applicable)), excluded=str(len(annex) - len(applicable)), sampled=str(len(sampled)),
        majors=str(counts["major"]), minors=str(counts["minor"]), ofis=str(counts["ofi"]),
    )
    f = lambda s: _fill(s, v)

    # Section I: the report and its conclusion, signed by the model.
    facts = s1["facts"]
    b = [{"kind": "para", "text": f(s1["notice"] if signoff.get("model") else s1["notice_unsigned"])},
         {"kind": "para", "text": f(s1["addressee"])},
         {"kind": "heading", "text": s1["facts_heading"]},
         {"kind": "facts", "rows": [
             [facts["organization"], cfg["organization"]],
             [facts["representative"], representative],
             [facts["audit_type"], atype["label"]],
             [facts["criteria"], f(s1["criteria"])],
             [facts["records"], f(f"{atype['period_heading']} {{period_dates}}")],
             [facts["method"], facts["method_value"]],
             [facts["auditor"], f"{model}, AI Auditor"],
         ]},
         {"kind": "heading", "text": s1["objectives_heading"]}, {"kind": "para", "text": s1["objectives_intro"]},
         {"kind": "list", "items": [f(x) for x in atype["objectives"]]},
         {"kind": "heading", "text": s1["scope_heading"]}, {"kind": "para", "text": f(s1["scope"])},
         {"kind": "para", "text": f(s1["coverage"]["surveillance" if eng.audit_type == "surveillance" else "full"])},
         {"kind": "heading", "text": s1["method_heading"]}, {"kind": "para", "text": f(s1["method"])}, {"kind": "para", "text": f(s1["sampling"])},
         {"kind": "heading", "text": s1["summary_heading"]}, {"kind": "para", "text": f(s1["summary_counts"])},
         {"kind": "list", "items": [s1["grades"][g] for g in GRADE_ORDER]}]
    if eng.stage1:
        b.append({"kind": "para", "text": s1["stage1_grades"]})
    b += [{"kind": "heading", "text": s1["conformity_heading"]}, {"kind": "para", "text": doc["summary"].strip()}]
    ia = results_text(results, ["9.2.1", "9.2.2"], text)
    mr = results_text(results, ["9.3.1", "9.3.2", "9.3.3"], text)
    b += [{"kind": "heading", "text": s1["ia_mr_heading"]},
          {"kind": "list", "items": [_fill(s1["ia_mr"]["internal_audit"], _Keep(v, result=ia)), _fill(s1["ia_mr"]["management_review"], _Keep(v, result=mr))]},
          {"kind": "heading", "text": s1["scope_appropriate_heading"]},
          {"kind": "para", "text": s1["scope_appropriate"]["yes" if doc["scope_appropriate"] else "no"] + (" " + doc["scope_note"].strip() if (doc.get("scope_note") or "").strip() else "")},
          {"kind": "heading", "text": s1["objectives_met_heading"]},
          {"kind": "para", "text": s1["objectives_met"]["no" if doc["scope_limitations"] else "yes"]}]
    if doc["scope_limitations"]:
        b += [{"kind": "heading", "text": s1["limitations_heading"]}, {"kind": "list", "items": [x.strip() for x in doc["scope_limitations"]]}]
    b += [{"kind": "heading", "text": s1["recommendation_heading"]},
          {"kind": "para", "text": f(s1["recommendation"][eng.audit_type][doc["recommendation"]]), "strong": True},
          {"kind": "para", "text": f(s1["ai_disclaimer"])},
          {"kind": "heading", "text": s1["independence_heading"]}, {"kind": "para", "text": f(s1["independence"])},
          {"kind": "heading", "text": s1["restricted_use_heading"]}, {"kind": "para", "text": f(s1["restricted_use"])},
          {"kind": "signature", "lines": [model, "AI Auditor", report_date, s1["signature_footer"]]}]
    section1 = {"title": f(s1["title"]), "blocks": b}

    # Section II: the organization's own description of its ISMS.
    s2 = text["section2"]
    blocks = []
    if not isms:
        blocks.append({"kind": "para", "text": f(s2["omitted"])})
    else:
        blocks.append({"kind": "para", "text": f(s2["intro"])})
        if isms.get("status") != "management-approved":
            blocks.append({"kind": "para", "text": f(s2["unapproved"])})
        for key, heading in s2["headings"].items():
            value = isms.get(key)
            if value:
                blocks.append({"kind": "heading", "text": f(heading)})
                blocks += _prose(value)
    section2 = {"title": f(s2["title"]), "blocks": blocks}

    # Section III: graded findings.
    labels = s3["labels"]
    section3 = {"title": f(s3["title"]), "intro": f(s3["intro_stage1"] if eng.stage1 else s3["intro"]), "none": s3["none"], "findings": [
        {"id": x["id"], "grade": x["grade"], "grade_name": s3["grade_names"][x["grade"]],
         "rows": [[labels["requirement"], f"{x['requirement']} {reqs[x['requirement']]['title']}"],
                  [labels["statement_ofi"] if x["grade"] == "ofi" else labels["statement"], x["statement"].strip()],
                  [labels["evidence"], x["objective_evidence"].strip()]]
                 + ([[labels["units"], ", ".join(sorted({d["control"] for d in x["deviations"]}))]] if x["deviations"] else [])}
        for x in findings]}

    # Section IV: every requirement in scope, the units that address it, and results.
    s4 = text["section4"]
    groups = []
    for code, title in catalog["groups"].items():
        rows = []
        for req in eng.requirements:
            if req["group"] != code:
                continue
            units = results.units(req["id"])
            rows.append({"id": req["id"], "title": req["title"], "units": [_unit_row(eng, wp, s4, results) for wp in units]
                         or [{"control": "—", "activity": "", "tests": [], "result": s4["not_sampled"] if results.surveillance else s4["not_audited"].format(reason=""), "flag": False}]})
        if rows:
            groups.append({"title": (f"Clause {code}: {title}" if not code.startswith("A.") else title), "rows": rows})
    section4 = {"title": f(s4["title"]), "intro": [f(s4["intro"]), f(s4["methods"])], "columns": s4["columns"], "groups": groups}

    # Section V: the Statement of Applicability and what the audit found for each control.
    s5 = text["section5"]
    res = s5["results"]
    soa = eng.soa or {}
    soa_rows = []
    for r in annex:
        row = soa.get(r["id"]) or {}
        if eng.applicable(r):
            result, flag = results.result(r["id"], res)
            soa_rows.append({"id": r["id"], "title": r["title"], "applicable": "Yes", "justification": "", "result": result, "flag": flag})
        else:
            soa_rows.append({"id": r["id"], "title": r["title"], "applicable": "No",
                             "justification": privacy.redact((row.get("justification") or "").strip(), eng) or "None given.",
                             "result": res["excluded"], "flag": False})
    section5 = {"title": f(s5["title"]), "intro": f(s5["intro"] if eng.soa is not None else s5["missing"]), "columns": s5["columns"], "rows": soa_rows}

    # Section VI: the organization's response.
    s6 = text["section6"]
    responses = [{"finding": x["id"], "grade_name": s3["grade_names"][x["grade"]], "statement": x["statement"].strip(), "response": x["management_response"].strip()}
                 for x in findings if (x.get("management_response") or "").strip()]
    section6 = {"title": f(s6["title"]), "intro": f(s6["intro"]), "responses": responses, "none": s6["none"]}

    cover = text["cover"]
    return {
        "final": final,
        "org": cfg["organization"], "scope": cfg["scope"].strip(), "auditor": "AI Audit",
        "model": model, "signer_name": model, "signer_title": "AI Auditor", "report_date": report_date,
        "type_label": atype["label"], "period": f(f"{atype['period_heading']} {{period_dates}}"),
        "title": f(cover["title"]), "disclaimer": f(cover["disclaimer"]), "restricted": f(cover["restricted"]),
        "counts": counts, "recommendation": doc["recommendation"],
        "generated": dt.date.today().isoformat(),
        "sections": [section1, section2], "section3": section3, "section4": section4, "section5": section5, "section6": section6,
    }


def results_text(results: _Results, req_ids: list[str], text: dict) -> str:
    """One sentence on a clause for Section I (internal audit, management review)."""
    labels = text["section5"]["results"]
    direct = {f["id"]: f for rid in req_ids for f in results.direct(rid) if f["grade"] != "ofi"}
    if direct:
        return "nonconforming. See " + results.label(list(direct.values())) + "."
    related = {f["id"]: f for rid in req_ids for f in results.related(rid) if f["grade"] != "ofi"}
    states = [results.result(rid, labels)[0].split(";")[0] for rid in req_ids]
    if all(s == labels["conforming"] for s in states):
        tail = f" A related finding is recorded against another requirement: {results.label(list(related.values()))}." if related else ""
        return "conforming. No nonconformity was raised against this clause." + tail
    return "; ".join(f"{rid} {s.lower()}" for rid, s in zip(req_ids, states)) + "."


def _unit_row(eng: Engagement, wp: dict, s4: dict, results: _Results) -> dict:
    tests = [p["text"] for p in wp["procedures"]]
    plan = wp["plan"]
    if plan["population"] and plan["population"]["size"] > 1:
        tests.append(f"Sample of {plan['sample_size']} selected from a population of {plan['population']['size']}.")
    concl = wp["conclusion"]
    linked = [f for f in results.findings if any(d["control"] == wp["control_id"] for d in f["deviations"])]
    if concl == "conforming":
        result = s4["conforming"]
    elif concl == "not-audited":
        result = _fill(s4["not_audited"], _Keep(reason=wp.get("scope_limitation") or ""))
    elif concl == "design-gap":
        result = _fill(s4["design_gap"], _Keep(reason=wp["design"]["rationale"]))
    else:
        result = " ".join(x["description"] for x in wp["deviations"] if x["item"] != "design")
    if linked and concl != "conforming":
        result += f" See {', '.join(x['id'] for x in sorted(linked, key=lambda x: x['id']))}."
    flag = concl in ("deviations", "design-gap") and any(x["grade"] != "ofi" for x in linked)
    return {"control": wp["control_id"], "activity": privacy.activity(eng, wp), "tests": tests, "result": result.strip(), "flag": flag}


def _prose(value) -> list[dict]:
    """Turn an isms.yaml value (text, list of text, or list of named entries) into report blocks."""
    if isinstance(value, str):
        return [{"kind": "para", "text": " ".join(p.split())} for p in value.split("\n\n") if p.strip()]
    if isinstance(value, list) and all(isinstance(x, dict) for x in value):
        items = []
        for x in value:
            name = x.get("name") or x.get("title") or ""
            rest = "; ".join(str(v) for k, v in x.items() if k not in ("name", "title") and v and not isinstance(v, (list, dict)))
            items.append(f"{name}: {rest}" if name and rest else name or rest)
        return [{"kind": "list", "items": items}]
    if isinstance(value, list):
        return [{"kind": "list", "items": [str(x) for x in value]}]
    if isinstance(value, dict):
        return [{"kind": "list", "items": [f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in value.items() if v]}]
    return [{"kind": "para", "text": str(value)}]


# --- PDF -------------------------------------------------------------------------


def _compile_pdf(data: dict, out: Path) -> None:
    try:
        import typst
    except ImportError as e:
        raise AuditError("The `typst` Python package is required: pip install -r scripts/requirements.txt") from e
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copyfile(ASSETS / "report" / "report.typ", Path(tmp) / "report.typ")
        shutil.copyfile(ASSETS / "report" / "logo.svg", Path(tmp) / "logo.svg")
        dump_json(data, Path(tmp) / "data.json")
        typst.compile(str(Path(tmp) / "report.typ"), output=str(out))


# --- spreadsheet and index -----------------------------------------------------------


def _write_xlsx(eng: Engagement, path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Units"
    ws.append(["Unit", "Requirements", "Frequency", "Nature", "Population", "Sample", "Design effective", "Conclusion",
               "Deviations", "Confidence", "Prepared by", "Control activity"])
    samples = wb.create_sheet("Samples")
    samples.append(["Unit", "Item", "Results", "Evidence", "Note"])
    devs = wb.create_sheet("Deviations")
    devs.append(["Unit", "Item", "Description", "Evidence"])
    for cid, wp in sorted(eng.load_workpapers().items()):
        p = wp["plan"]
        ws.append([cid, " ".join(wp["criteria"]), p["frequency"], p["nature"],
                   f"{p['population']['source']} ({p['population']['size']})" if p["population"] else "",
                   p["sample_size"], wp["design"]["effective"], wp["conclusion"], len(wp["deviations"]),
                   wp.get("confidence"), wp.get("prepared_by"), privacy.activity(eng, wp)])
        for item in wp["items"]:
            samples.append([cid, item["id"], ", ".join(f"{k}={r}" for k, r in sorted(item["results"].items())),
                            " ".join(item["evidence"]), item.get("note", "")])
        for x in wp["deviations"]:
            devs.append([cid, x["item"], x["description"], " ".join(x["evidence"])])
    fs = wb.create_sheet("Findings")
    fs.append(["ID", "Grade", "Requirement", "Statement", "Objective evidence", "Deviations", "Evidence", "Organization's response"])
    doc = load_json(eng.findings_path)
    for x in doc["findings"]:
        fs.append([x["id"], x["grade"], x["requirement"], x["statement"], x["objective_evidence"],
                   " ".join(f"{d['control']}/{d['item']}" for d in x["deviations"]), " ".join(x["evidence"]), x.get("management_response") or ""])
    soa = wb.create_sheet("SoA")
    soa.append(["Control", "Applicable", "Justification", "Status", "Units"])
    workpapers = eng.load_workpapers()
    for r in load_catalog()["requirements"]:
        if r["kind"] != "annex":
            continue
        row = (eng.soa or {}).get(r["id"]) or {}
        soa.append([r["id"], "yes" if eng.applicable(r) else "no", privacy.redact(row.get("justification") or "", eng), row.get("status") or "",
                    " ".join(cid for cid, wp in sorted(workpapers.items()) if r["id"] in wp["criteria"])])
    ev = wb.create_sheet("Evidence")
    ev.append(["ID", "Title", "Kind", "Path", "SHA-256", "Obtained", "Date", "Controls", "Requirements"])
    for a in eng.manifest["artifacts"]:
        ev.append([a["id"], privacy.redact(a["title"], eng), a["kind"], privacy.redact(a["path"], eng), a["sha256"], a["obtained"], a.get("date", ""),
                   " ".join(a.get("controls", [])), " ".join(a.get("requirements", []))])
    for sheet in wb.worksheets:
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        sheet.freeze_panes = "A2"
    wb.save(path)


def _write_evidence_index(eng: Engagement, path: Path) -> None:
    cited = {}
    for cid, wp in eng.load_workpapers().items():
        ids = set(wp["design"]["evidence"]) | {e for i in wp["items"] for e in i["evidence"]} | {e for x in wp["deviations"] for e in x["evidence"]}
        if wp.get("population_check"):
            ids |= set(wp["population_check"]["evidence"])
        for e in ids:
            cited.setdefault(e, []).append(cid)
    for x in load_json(eng.findings_path)["findings"]:
        for e in x["evidence"]:
            cited.setdefault(e, []).append(x["id"])
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "title", "kind", "path", "sha256", "obtained", "date", "cited_by"])
        for a in eng.manifest["artifacts"]:
            w.writerow([a["id"], privacy.redact(a["title"], eng), a["kind"], privacy.redact(a["path"], eng), a["sha256"], a["obtained"], a.get("date", ""),
                        " ".join(sorted(set(cited.get(a["id"], []))))])
