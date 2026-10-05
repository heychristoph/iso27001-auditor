"""`check`: bundle integrity, Statement of Applicability and coverage, before any testing starts.

Produces review/coverage.md (requirement -> controls -> evidence) and
review/requests.csv (the information request list for the organization).
"""

from __future__ import annotations

from collections import defaultdict

from core import REQ_PREFIX, Engagement, load_requirements, parse_date, sha256_file, truthy, write_csv

ISMS_FIELDS = ["scope_statement", "boundaries", "context", "interested_parties"]
NOT_DONE = ("not-implemented", "not implemented", "planned", "not-started", "not started", "no")


def run(eng: Engagement) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    arts = eng.artifacts
    catalog = {r["id"]: r for r in load_requirements()}
    in_scope = {r["id"] for r in eng.requirements}
    start, end = eng.period
    requests = []

    def request(control: str, requirement: str, text: str, reason: str) -> None:
        requests.append({"id": f"R-{len(requests) + 1:03d}", "control": control, "requirement": requirement, "request": text, "reason": reason})

    # Integrity: every registered file is present and unchanged since ingest.
    for a in arts.values():
        path = eng.bundle / a["path"]
        if not path.exists():
            errors.append(f"{a['id']}: file {a['path']} is missing from the bundle")
        elif sha256_file(path) != a["sha256"]:
            errors.append(f"{a['id']}: file {a['path']} changed after ingest (hash mismatch); re-run ingest")
    registered = {a["path"] for a in arts.values()} | {"manifest.json"}
    for path in eng.bundle.rglob("*"):
        if path.is_file() and path.relative_to(eng.bundle).as_posix() not in registered:
            warnings.append(f"bundle/{path.relative_to(eng.bundle).as_posix()} is not in the manifest and will be ignored")
    warnings += [f"ingest: {w}" for w in eng.manifest.get("warnings", [])]

    # Control matrix.
    controls = eng.client_controls
    seen = set()
    by_requirement = defaultdict(list)
    for c in controls:
        cid = c["id"]
        if cid in seen:
            errors.append(f"controls.csv: duplicate control ID {cid}")
        seen.add(cid)
        if cid.startswith(REQ_PREFIX):
            errors.append(f"{cid}: control IDs starting with {REQ_PREFIX} are reserved for requirements audited directly")
        if not c.get("description"):
            errors.append(f"{cid}: control has no description")
        unknown = [x for x in c["criteria"] if x not in catalog]
        if unknown:
            errors.append(f"{cid}: unknown requirements {unknown} (use IDs like 9.2.1, A.5.18)")
        if not c["criteria"]:
            warnings.append(f"{cid}: control is not mapped to any requirement")
        elif not any(x in in_scope for x in c["criteria"]):
            warnings.append(f"{cid}: maps only to Annex A controls the Statement of Applicability excludes ({' '.join(c['criteria'])})")
        for x in c["criteria"]:
            by_requirement[x].append(cid)
        pop = c.get("population")
        if pop and pop not in arts:
            errors.append(f"{cid}: population {pop} is not in the bundle")

    # Statement of Applicability (clause 6.1.3 d).
    soa = eng.soa
    annex = [r for r in load_requirements() if r["kind"] == "annex"]
    if soa is None:
        warnings.append("no Statement of Applicability in the bundle; every Annex A control is treated as applicable")
        request("", "6.1.3", "Provide the Statement of Applicability: every Annex A control, whether it is applicable, the justification, and its implementation status.", "missing")
    else:
        for cid, row in soa.items():
            if cid not in catalog or catalog[cid]["kind"] != "annex":
                errors.append(f"soa.csv: {cid} is not an ISO/IEC 27001:2022 Annex A control")
        missing = [r["id"] for r in annex if r["id"] not in soa]
        if missing:
            warnings.append(f"soa.csv: no decision for {len(missing)} Annex A controls ({', '.join(missing[:8])}{' ...' if len(missing) > 8 else ''}); clause 6.1.3 d needs one for each")
        for r in annex:
            row = soa.get(r["id"])
            if not row:
                continue
            applicable = truthy(row.get("applicable", "yes"))
            if not applicable and not (row.get("justification") or "").strip():
                warnings.append(f"soa.csv: {r['id']} is excluded without a justification")
            if not applicable and by_requirement.get(r["id"]):
                warnings.append(f"soa.csv: {r['id']} is excluded but controls {by_requirement[r['id']]} are mapped to it")
            if applicable and (row.get("status") or "").strip().lower() in NOT_DONE:
                warnings.append(f"soa.csv: {r['id']} is applicable but its status is '{row['status']}'")

    # Requirements without a mapped control become REQ- units, audited directly.
    evidence_by_control = defaultdict(list)
    evidence_by_requirement = defaultdict(list)
    for a in arts.values():
        for cid in a.get("controls", []):
            evidence_by_control[cid].append(a["id"])
            if cid not in seen:
                warnings.append(f"{a['id']}: linked to unknown control {cid}")
        for rid in a.get("requirements", []):
            evidence_by_requirement[rid].append(a["id"])
    direct = [r["id"] for r in eng.requirements if not by_requirement.get(r["id"])]
    if direct:
        warnings.append(f"{len(direct)} in-scope requirements have no mapped control and will be audited directly as {REQ_PREFIX} units: "
                        + ", ".join(direct[:12]) + (" ..." if len(direct) > 12 else ""))
    for rid in direct:
        if not evidence_by_requirement.get(rid):
            request(f"{REQ_PREFIX}{rid}", rid, f"Provide the documented information and records that show how {rid} ({catalog[rid]['title']}) is met.",
                    "no control mapped and no evidence linked")
    for c in controls:
        if not evidence_by_control.get(c["id"]) and not c.get("population"):
            request(c["id"], " ".join(c["criteria"]), f"Provide evidence that control {c['id']} is in place ({c.get('title') or c['description'][:80]}).",
                    "no evidence linked")

    # Populations: dates and IDs.
    for a in arts.values():
        if a["kind"] != "population":
            continue
        rows = eng.population(a["id"])
        ids = [r["id"] for r in rows]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            errors.append(f"{a['id']}: duplicate item IDs {sorted(dupes)[:5]}")
        if not eng.stage1:
            outside = [r["id"] for r in rows if (d := parse_date(r["date"])) and not (start <= d <= end)]
            if outside:
                warnings.append(f"{a['id']}: {len(outside)} items dated outside the records period ({', '.join(outside[:5])}); they will be excluded from sampling")

    # ISMS scope and context (the organization's documented information, clause 4.3).
    isms = eng.isms
    if not isms:
        warnings.append("no ISMS scope and context; Section II cannot be rendered until the organization provides isms.yaml")
        request("", "4.3", "Provide the ISMS scope statement, boundaries, context and interested parties (isms.yaml).", "missing")
    else:
        empty = [f for f in ISMS_FIELDS if not isms.get(f)]
        if empty:
            warnings.append(f"{eng.isms_path.relative_to(eng.root)}: empty fields {empty}; the organization must complete them")
        if isms.get("status") != "management-approved":
            warnings.append("isms.yaml: status is not 'management-approved'; the AI Audit will say the scope description is not management-approved")

    _write_coverage(eng, by_requirement, evidence_by_control, evidence_by_requirement)
    write_csv(eng.review / "requests.csv", requests, ["id", "control", "requirement", "request", "reason"])
    return errors, warnings


def _write_coverage(eng: Engagement, by_requirement, evidence_by_control, evidence_by_requirement) -> None:
    lines = [f"# Coverage: {eng.config['organization']}", "",
             "| Requirement | Title | Applicable | Controls | Evidence items |", "|---|---|---|---|---|"]
    for req in load_requirements():
        applicable = eng.applicable(req)
        cids = by_requirement.get(req["id"], [])
        ev = sum(len(evidence_by_control.get(c, [])) for c in cids) + len(evidence_by_requirement.get(req["id"], []))
        if not applicable:
            cell = ", ".join(cids) or "-"
        else:
            cell = ", ".join(cids) or f"**none** (audited as {REQ_PREFIX}{req['id']})"
        lines.append(f"| {req['id']} | {req['title']} | {'yes' if applicable else 'excluded'} | {cell} | {ev} |")
    eng.review.mkdir(parents=True, exist_ok=True)
    (eng.review / "coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
