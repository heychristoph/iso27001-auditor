// ISO/IEC 27001 AI Audit report layout. Content comes from data.json, built by scripts/render.py.
// Change the look here; change wording in report-text.yaml.

#let d = json("data.json")
#let accent = rgb("#1d3557")
#let alert = rgb("#9b2226")
#let muted = luma(105)
#let hairline = luma(205)

#set document(title: d.title, author: d.auditor)
#set text(font: "Libertinus Serif", size: 10.5pt, lang: "en")
#set par(justify: true, leading: 0.62em, spacing: 0.95em)
#set list(indent: 1em, spacing: 0.6em)
#set enum(indent: 1em, spacing: 0.6em, numbering: "a.")

#set page(
  paper: "a4",
  margin: (x: 2.3cm, top: 2.4cm, bottom: 2.2cm),
  background: if not d.final {
    rotate(-40deg, text(size: 110pt, weight: "bold", fill: rgb(0, 0, 0, 14))[DRAFT])
  },
  header: context {
    if counter(page).get().first() > 1 {
      set text(8.5pt, fill: muted)
      d.org
      h(1fr)
      [AI Audit — not an ISO/IEC 27001 certification]
      v(-0.4em)
      line(length: 100%, stroke: 0.4pt + hairline)
    }
  },
  footer: context {
    if counter(page).get().first() > 1 {
      set text(8.5pt, fill: muted)
      if d.final [AI Audit. Not an ISO/IEC 27001 certification.] else [Draft AI Audit. Not signed. Not an ISO/IEC 27001 certification.]
      h(1fr)
      counter(page).display("1 of 1", both: true)
    }
  },
)

#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  block(below: 1.3em, {
    text(9.5pt, tracking: 0.12em, fill: muted, upper(it.supplement))
    v(0.1em)
    text(17pt, weight: "bold", fill: accent, it.body)
    v(-0.2em)
    line(length: 100%, stroke: 0.8pt + accent)
  })
}
#show heading: set text(hyphenate: false)
#show heading.where(level: 2): it => block(above: 1.3em, below: 0.7em, text(11.5pt, weight: "bold", fill: accent, it.body))
#show heading.where(level: 3): it => block(above: 1em, below: 0.5em, text(10.5pt, weight: "bold", style: "italic", it.body))
#show outline.entry.where(level: 1): it => block(above: 0.9em, link(it.element.location(), grid(
  columns: (5.5em, 1fr, auto),
  text(weight: "bold", it.element.supplement),
  [#it.element.body #box(width: 1fr, repeat[#h(0.25em).#h(0.25em)])],
  it.page(),
)))

#let blocks(items) = for b in items {
  if b.kind == "heading" {
    heading(level: b.at("level", default: 2), outlined: false, b.text)
  } else if b.kind == "para" {
    if b.at("strong", default: false) { par(strong(b.text)) } else { par(b.text) }
  } else if b.kind == "list" {
    if b.at("enum", default: false) { enum(..b.items) } else { list(..b.items) }
  } else if b.kind == "facts" {
    block(above: 0.6em, below: 1em, {
      set text(size: 9.5pt)
      set par(justify: false)
      table(
        columns: (4.2cm, 1fr),
        stroke: none,
        inset: (x: 0pt, y: 4pt),
        ..b.rows.map(r => (text(fill: muted, r.at(0)), r.at(1))).flatten(),
      )
    })
  } else if b.kind == "signature" {
    v(1.6em)
    block(breakable: false, for line in b.lines.filter(l => l != "") [#line \ ])
  }
}

// Cover
#page(header: none, footer: none, margin: (x: 2.6cm, y: 2.8cm), {
  image("logo.svg", width: 3.6cm)
  v(0.85em)
  text(10pt, tracking: 0.14em, fill: muted)[AI AUDIT · ISO/IEC 27001:2022]
  v(0.35em)
  text(11pt, weight: "bold", fill: alert)[Not an ISO/IEC 27001 certification]
  v(0.6em)
  text(28pt, weight: "bold", fill: accent, d.org)
  v(0.2em)
  line(length: 35%, stroke: 1.2pt + accent)
  v(1.2em)
  text(13pt, d.title)
  v(0.8em)
  text(12pt, d.type_label)
  v(0.2em)
  text(11pt, fill: muted, d.period)
  v(1em)
  block(width: 100%, inset: (left: 0.8em), stroke: (left: 1.2pt + hairline), text(10pt, fill: muted, [ISMS scope: #d.scope]))
  v(1fr)
  text(10pt)[Signed by: *#d.signer_name*, #d.signer_title]
  v(0.25em)
  text(10pt)[#d.report_date]
  v(0.35em)
  text(9pt, fill: muted, d.disclaimer)
  v(0.6em)
  text(9pt, fill: muted, d.restricted)
  if not d.final {
    v(0.8em)
    text(9pt, fill: alert, weight: "bold")[DRAFT. Generated #d.generated. Not yet signed by the model that ran the audit.]
  }
})

#block(below: 1.3em, {
  text(17pt, weight: "bold", fill: accent)[Contents]
  v(-0.2em)
  line(length: 100%, stroke: 0.8pt + accent)
})
#outline(title: none, depth: 1, indent: 0pt)

#let numerals = ("I", "II", "III", "IV", "V", "VI")

#for (i, s) in d.sections.enumerate() {
  heading(level: 1, supplement: [Section #numerals.at(i)], s.title)
  blocks(s.blocks)
}

// Section III: findings
#let s3 = d.section3
#heading(level: 1, supplement: [Section III], s3.title)
#par(s3.intro)
#if s3.findings.len() == 0 {
  par(text(style: "italic", s3.none))
} else {
  for f in s3.findings {
    let colour = if f.grade == "ofi" { accent } else { alert }
    block(above: 1.2em, breakable: false, {
      block(below: 0.5em, text(11.5pt, weight: "bold", fill: colour, [#f.id #h(0.4em) #f.grade_name]))
      set text(size: 9.5pt)
      set par(justify: false)
      table(
        columns: (3.6cm, 1fr),
        stroke: 0.5pt + hairline,
        inset: 6pt,
        align: left + top,
        ..f.rows.map(r => (table.cell(fill: luma(244), text(weight: "bold", r.at(0))), r.at(1))).flatten(),
      )
    })
  }
}

// Section IV: requirements, units and results
#let s4 = d.section4
#heading(level: 1, supplement: [Section IV], s4.title)
#for p in s4.intro { par(p) }

#for g in s4.groups {
  heading(level: 2, outlined: false, g.title)
  let cells = g.rows.map(r => {
    let first = table.cell(rowspan: r.units.len(), [*#r.id* \ #text(size: 8pt, fill: muted, r.title)])
    r.units.enumerate().map(((i, u)) => {
      let row = (
        text(weight: "bold", u.control),
        u.activity,
        u.tests.map(t => [#t]).join(parbreak()),
        if u.flag { text(fill: alert, u.result) } else { u.result },
      )
      if i == 0 { (first, ..row) } else { row }
    }).flatten()
  }).flatten()
  block(above: 0.6em, {
    set text(size: 8.5pt, hyphenate: true)
    set par(justify: false)
    table(
      columns: (2.4cm, 1.5cm, 1.3fr, 1.8fr, 1.1fr),
      stroke: 0.5pt + hairline,
      inset: 5pt,
      align: left + top,
      table.header(..s4.columns.map(x => table.cell(fill: accent, text(fill: white, size: 8.5pt, weight: "bold", x)))),
      ..cells,
    )
  })
}

// Section V: Statement of Applicability
#let s5 = d.section5
#heading(level: 1, supplement: [Section V], s5.title)
#par(s5.intro)
#block(above: 0.6em, {
  set text(size: 8.5pt, hyphenate: true)
  set par(justify: false)
  table(
    columns: (1.4cm, 1.5fr, 1.9cm, 1.5fr, 1.1fr),
    stroke: 0.5pt + hairline,
    inset: 4.5pt,
    align: left + top,
    table.header(..s5.columns.map(x => table.cell(fill: accent, text(fill: white, size: 8.5pt, weight: "bold", x)))),
    ..s5.rows.map(r => (
      text(weight: "bold", r.id),
      r.title,
      r.applicable,
      text(fill: muted, r.justification),
      if r.flag { text(fill: alert, r.result) } else { r.result },
    )).flatten(),
  )
})

// Section VI: the organization's response
#let s6 = d.section6
#heading(level: 1, supplement: [Section VI], s6.title)
#par(s6.intro)
#if s6.responses.len() == 0 {
  par(text(style: "italic", s6.none))
} else {
  for r in s6.responses {
    heading(level: 2, outlined: false, [#r.finding: #r.grade_name])
    par[*Finding:* #r.statement]
    par[*Organization's response:* #r.response]
  }
}
