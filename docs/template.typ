#import "@preview/ctheorems:1.1.3": thmrules, thmplain, thmproof

#let theorem = thmplain("theorem", "Theorem", base_level: 1, separator: [.], inset: 0pt, padding: (top: 1em, bottom: 1em), titlefmt: strong, namefmt: strong, bodyfmt: emph)

#let lemma = thmplain("theorem", "Lemma", base_level: 1, separator: [. ], inset: 0pt, padding: (top: 1em, bottom: 1em), titlefmt: strong, namefmt: strong, bodyfmt: emph)

#let proposition = thmplain("theorem", "Proposition", base_level: 1, separator: [. ], inset: 0pt, padding: (top: 1em, bottom: 1em), titlefmt: strong, namefmt: strong, bodyfmt: emph)

#let corollary = thmplain("theorem", "Corollary", base_level: 1, separator: [. ], inset: 0pt, padding: (top: 1em, bottom: 1em), titlefmt: strong, namefmt: strong, bodyfmt: emph)

#let conjecture = thmplain("theorem", "Conjecture", base_level: 1, separator: [. ], inset: 0pt, padding: (top: 1em, bottom: 1em), titlefmt: strong, namefmt: strong, bodyfmt: emph)

#let definition = thmplain("theorem", "Definition", base_level: 1, separator: [. ], inset: 0pt, padding: (top: 1em, bottom: 1em), namefmt: strong, titlefmt: strong, bodyfmt: emph)

#let remark = thmplain("theorem", "Remark", base_level: 1, separator: [. ], inset: 0pt, padding: (top: 0em, bottom: 1em), namefmt: strong, titlefmt: strong)

#let proof = thmproof("proof", "Proof", separator: [. ], inset: 0pt, padding: (top: 0em, bottom: 1em), titlefmt: emph, namefmt: strong)

#let square(color: none, nudge: false, body) = box(
  stroke: if color != none { 0.4pt + color } else { 0.4pt },
  inset: 3pt,
  fill: color,
  baseline: if nudge {0.12em} else {0em},
  body
)

#let article(
  title: none,
  authors: (),
  affiliations: (),
  abstract: none,
  keywords: (),
  msc: (),
  body
) = {
  set document(title: title)
  set page(paper: "a4", margin: 1.25in, numbering: "1")

  set text(font: "New Computer Modern", size: 10pt)
  set par(justify: true, first-line-indent: (amount: 1.5em, all: true))
  
  show math.equation.where(block: true): set block(spacing: 1.5em)
  set math.mat(row-gap: 5pt, column-gap: 9pt)
  set block(spacing: 0.5em) 
    
  if title != none {
    align(center)[
      #v(1em)
      #text(size: 16pt)[#title]
      #v(1.5em)
    ]
  }

  if authors.len() > 0 {
    align(center)[
      #let author-nodes = authors.map(a => [
        #text(a.name)#super[#a.affil]
      ])
      #text(size: 11pt)[
        #let groups = author-nodes.chunks(3)
        #let rows = groups.map(row => row.join(", "))
        #rows.join([,\ ])
      ]
    ]
    v(0.5em)
  }

  if affiliations.len() > 0 {
    align(center)[
      #set text(size: 9pt, style: "italic")
      #for aff in affiliations [
        #super[#aff.id] #aff.dept \
        #if "emails" in aff [
          #aff.emails \
        ]
      ]
    ]
    v(1.5em)
  }

  if abstract != none {
    v(0.5em)
    pad(x: 2em)[
      #set text(size: 9pt)
      #set par(justify: true, first-line-indent: 0em)
      #text[*Abstract.*]
      #abstract
    ]
    v(1em)
  }

  if keywords.len() > 0 {
    v(0.5em)
    pad(x: 2em)[
      #text(size: 9pt)[
        *Keywords.* #keywords.join("·") \
      ]
    ]
  }

  v(0.5em)
  
  set heading(numbering: "1.1")
  show heading: set block(below: 1.25em, above: 2em)
  show heading.where(level: 1): set text(size: 11pt)
  show heading.where(level: 2): set text(size: 10pt)
  
  show figure.where(kind: "thmenv"): set par(first-line-indent: (amount: 1.5em, all: false))

  show: thmrules
  
  body
}

