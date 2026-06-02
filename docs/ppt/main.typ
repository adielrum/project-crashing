#import "@preview/touying:0.6.1": *
#import "university.typ" : *
#import "@preview/theorion:0.4.0": *
#import "@preview/cetz:0.5.2"
#import "@preview/gantty:0.5.1" as gantty: gantt
#import "@preview/tdtr:0.5.5" : *
#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge

#import cosmos.fancy: *
#show: show-theorion
#set page(fill: rgb("FFFFFF"))

#set-theorion-numbering("1")

#let remove-deps(data) = {
  let new-data = data
  new-data.tasks = new-data.tasks.map(t => {
    let clean-task = (:)
    for (key, value) in t.pairs() {
      if key != "dependencies" {
        clean-task.insert(key, value)
      }
    }
    return clean-task
  })
  return new-data
}

#let add-deadline(data, deadline-date) = {
  let new-data = data
  let ms = new-data.at("milestones", default: ())
  new-data.milestones = ms + ((name: "Target Deadline", date: deadline-date),)
  return new-data
}

#show: university-theme.with(
  aspect-ratio: "16-9",
  header: [#h(1em) #utils.display-current-heading()],
  header-right: self => box(utils.display-current-heading(level: 1)),
  // align: horizon,
  // config-common(handout: true),
  config-common(frozen-counters: (theorem-counter,)),  // freeze theorem counter for animation
  config-info(
    title: [Resource-Constrained Time-Cost Tradeoff Problem in Project Crashing],
    subtitle: [Presentasi 2],
    author: [K13 Pemodelan Matematika],
    date: [Selasa, 2 Juni 2026],
    institution: [ MA3251 Pemodelan Matematika \
    Institut Teknologi Bandung],
    logo: {
      grid(
        columns: 2,
        gutter: 2em,
        align: horizon,
        image("itb.png", height: 3cm),
        image("idsc.png", height: 2cm),
      )
    }
  ),
  config-page(
    header-ascent: 0em,
    margin: (top: 4em, bottom: 1.25em, x: 2em)
  ),
  config-colors(
      // iDSC Color Scheme - Updated
      primary: rgb("#5B9BD5"),        // Blue (from logo text and vertical lines)
      secondary: rgb("#A0B89E"),      // Sage Green (from logo horizontal lines and dots)
      tertiary: rgb("#4A90C0"),       // Darker Blue (for accents)
      neutral-lightest: rgb("F5F5F5"), // Very light gray (background)
      neutral-darkest: rgb("#2C3E50"), // Dark blue-gray (text)
    ),
)
#let proof = proof.with(title: "Bukti")
#let proof-sketch = proof.with(title: "Sketsa Bukti")
// #show: magic.bibliography-as-footnote.with(bibliography("bib.bib", title: none))
// #set page(margin: (top: 0em))

#set text(font: ("libertinus serif", "Noto Serif CJK JP"), size: 16pt)


/// Custom colors - Updated to match iDSC branding
#set-primary-border-color(rgb("#5B9BD5"))           // Blue border
#set-primary-body-color(rgb("#5B9BD5").transparentize(90%))  // Light blue background
// #set-sec
#set-secondary-border-color(rgb("#A0B89E"))         // Sage green border
#set-secondary-body-color(rgb("#A0B89E").transparentize(90%))  // Light sage background
#set-tertiary-border-color(rgb("#4A90C0"))          // Darker blue border
#set-tertiary-body-color(rgb("#4A90C0").transparentize(90%))   // Light darker-blue background
#set-primary-symbol[#sym.suit.diamond.filled]


#title-slide()

#set text(size: 20pt)
== Outline
- Latar Belakang & Masalah
- Skenario 1: Model Baseline (Diskret Linear)
- Skenario 2: Model Baru (Cobb-Douglas)
- Metode Penylesaian
- Skenario 3: Model Hybrid 
- Hasil Eksplorasi 
- Rencana Selanjutnya

= Latar Belakang & Masalah

== Concrete Works Schedule


  #set text(size: 12pt)
  #let base-data = yaml("concrete.yaml")
  #let vanilla-data = remove-deps(base-data)

  #grid(
    columns: (2fr, 1fr),
    gutter: 0pt,
    scale(80%, origin: center + top)[
    #gantt(vanilla-data)
  ], align(horizon)[#v(-3em)#block(
      fill: rgb("#5B9BD5").transparentize(90%),
      stroke: 1.5pt + rgb("#5B9BD5"),
      inset: 0.8em,
      radius: 4pt,
      [
        #set text(size: 16pt)
        Misalkan PT XYZ saat ini sedang melaksanakan proyek pembangunan Gedung ABC. 
        
        Per 10 November, proyek tersebut diproyeksikan akan selesai pada Desember 30
      ]
    )]
  )
  
#pagebreak()

== Concrete Works Schedule


  #set text(size: 12pt)
  #let base-data = yaml("concrete.yaml")
  
  #let late-data = remove-deps(base-data)
  #let late-data = add-deadline(late-data, "2023-12-10")

  #grid(
    columns: (2fr, 1fr),
    gutter: 0pt,
    scale(80%, origin: center + top)[
    #gantt(late-data)
  ], align(horizon)[#v(-3em)#block(
      fill: rgb("#5B9BD5").transparentize(90%),
      stroke: 1.5pt + rgb("#5B9BD5"),
      inset: 0.8em,
      radius: 4pt,
      [
        #set text(size: 16pt)
        Namun, PT GHI telah menetapkan batas waktu penyelesaian (deadline) pada Desember 10. 
        
        Oleh karena itu, PT XYZ perlu mempercepat proses pengerjaan proyek tersebut. 
        
        Terkait hal ini, PT XYZ meminta kami untuk menentukan strategi crashing yang paling optimal.
      ]
    )]
  )


#pagebreak()

== Resource Constraints
#grid(
    columns: (2.1fr, 0.9fr),
    gutter: 10pt,
align(center)[
  #v(0.5em)
  #text(fill: black)[*Labor Crew*]

  #cetz.canvas({
    import cetz.draw: *

    let capacity = 7
    let max-y = 8
    
    let days = (
      ("Nov 15", (("Strip 2nd", 3), ("Form 3rd", 2))),
      ("Nov 16", (("Strip 2nd", 3), ("Form 3rd", 2))),
      ("Nov 17", (("Form 3rd", 2), ("Form 1st", 2), ("Rebar 1st", 3))),
      ("Nov 18", (("Form 3rd", 2), ("Form 1st", 2), ("Rebar 1st", 3))),
      ("Nov 19", (("Form 3rd", 2), ("Form 1st", 2), ("Rebar 1st", 3))),
      ("Nov 20", (("Form 3rd", 2), ("Form 1st", 2), ("Rebar 1st", 3))),
      ("Nov 21", (("Form 3rd", 2), ("Form 1st", 2), ("Rebar 1st", 3))),
      ("Nov 22", (("Pour 3rd", 2), ("Form 1st", 2), ("Rebar 1st", 3))),
      ("Nov 23", (("Pour 3rd", 2), )),
      ("Nov 24", (("Pour 3rd", 2), ("Pour 1st", 2))),
    )

    let colors = (
      "Strip 2nd": rgb("#FFa39e"),
      "Form 3rd": rgb("#91d5ff"),
      "Form 1st": rgb("#b7eb8f"),
      "Rebar 1st": rgb("#ffe58f"),
      "Pour 3rd": rgb("#d3adf7"),
      "Pour 1st": rgb("#ffbb96")
    )

    let width = 16
    let step-x = width / days.len()
    let bar-w = 0.8
    
    // Draw horizontal grid lines and Y-axis labels
    for y in range(0, max-y + 1) {
      if y > 0 { line((0, y), (width, y), stroke: luma(220)) }
      content((-0.5, y), text(size: 10pt, fill: luma(100))[#y])
    }

    // Draw bottom X-axis line
    line((0, 0), (width, 0), stroke: 1pt + black)
    
    // Draw Red Capacity Line
    line((0, capacity), (width + 0.5, capacity), name: "cap")
    content("cap.end", anchor: "west", padding: 5pt, text(size: 10pt, fill: red, weight: "bold")[MAX])

    // Draw the stacked bars using explicit coordinates
    let x = (step-x / 2)
    for (date, blocks) in days {
      let current-y = 0
      
      for (name, val) in blocks {
        let next-y = current-y + val
        
        rect(
          (x - (bar-w / 2), current-y), 
          (x + (bar-w / 2), next-y),
          fill: colors.at(name),
          stroke: white + 0.5pt
        )
        
        // Add number inside the block
        content(
          (x, current-y + (val / 2)),
          text(size: 9pt, weight: "bold")[#val]
        )
        
        current-y = next-y
      }
      
      // Add Date label at the bottom
      content((x, -0.6), text(size: 9pt, weight: "bold")[#date])
      x += step-x
    }
  })

  #v(0.5em)
  
  // Legend built entirely with grid, avoiding the stack variable error
  #grid(
    columns: 6,
    gutter: 10pt,
    .. (
      ("Strip 2nd", rgb("#FFa39e")),
      ("Form 3rd", rgb("#91d5ff")),
      ("Form 1st", rgb("#b7eb8f")),
      ("Rebar 1st", rgb("#ffe58f")),
      ("Pour 3rd", rgb("#d3adf7")),
      ("Pour 1st", rgb("#ffbb96"))
    ).map(pair => {
      let (name, color) = pair
      grid(columns: 2, gutter: 8pt,
        box(width: 14pt, height: 14pt, fill: color, radius: 2pt),
        align(horizon)[#text(size: 10pt)[#name]]
      )
    })
  )
], 
align(horizon)[#block(
      fill: rgb("#5B9BD5").transparentize(90%),
      stroke: 1.5pt + rgb("#5B9BD5"),
      inset: 0.8em,
      radius: 4pt,
      
      [
        #set text(size: 16pt)
        Proyek pembangunan memiliki berbagai batasan maksimum, salah satunya adalah batasan sumber daya. 
        
        Dalam kasus ini, sebagai contoh, alokasi labor crew di lapangan per hari untuk setiap task dengan batasan maksimal 7 pekerja per hari, dapat dilihat pada grafik.
      ]
    )]
)

== Temporal Constraints


  #let dep-data = yaml("concrete.yaml")

  #grid(
    columns: (2fr, 1fr),
    gutter: 0pt,
    scale(80%, origin: center + top)[
    #set text(size: 12pt)
    #gantt(dep-data)
  ], align(horizon)[#v(-2.5em)#block(
      fill: rgb("#5B9BD5").transparentize(90%),
      stroke: 1.5pt + rgb("#5B9BD5"),
      inset: 0.8em,
      radius: 4pt,
      [
        
        #set text(size: 16pt)
        Namun, PT GHI telah menetapkan batas waktu penyelesaian (deadline) pada Desember 10. 
        
        Oleh karena itu, PT XYZ perlu mempercepat proses pengerjaan proyek tersebut. 
        
        Terkait hal ini, PT XYZ meminta kami untuk menentukan strategi crashing yang paling optimal.
      ]
    )]
  )

#set text(size: 16pt)

== Resource Constrained Project Scheduling Problem (RCPSP)

// #set text(size: 20pt)

#align(center + horizon)[
  #set text(size: 25pt)
  #diagram(
    node-stroke: 0.5pt + rgb("#7F7F7F"),
    node-fill: white,
    node-inset: 10pt,
    edge-stroke: 1pt + black,
    mark-scale: 80%,
    spacing: (30pt, 40pt),
    
    node((1, 0), text(fill: rgb("#5B9BD5"))[*RCPSP*]),
    
    node((0, 1), [Resource Constraint]),
    node((1, 1), [Project Objective]),
    node((2, 1), [Temporal Constraint]),
    
    node((0.5, 2), [Time]),
    node((1.5, 2), [Cost]),
    
    node((1, 3), [*TCTP*]),
    
    edge((1, 0), (0, 1), "-|>"),
    edge((1, 0), (1, 1), "-|>"),
    edge((1, 0), (2, 1), "-|>"),
    
    edge((1, 1), (0.5, 2), "-|>"),
    edge((1, 1), (1.5, 2), "-|>"),
    
    edge((0.5, 2), (1, 3), "-|>"),
    edge((1.5, 2), (1, 3), "-|>")
  )
]

#set text(size: 16pt)

// #set text(size: 16pt)

== Skenario

#align(center + horizon)[
  #set text(size: 15pt)
  #v(-2em)
  #diagram(
    node-stroke: 0.5pt + rgb("#7F7F7F"),
    node-fill: white,
    node-inset: 10pt,
    edge-stroke: 1pt + black,
    mark-scale: 80%,
    spacing: (45pt, 40pt),
    // Question Node 1
    node((1, 0), align(center)[
      *Apakah data* \
      *Crashing Cost tersedia?*
    ], corner-radius: 4pt, fill: rgb("#F9F9F9")),
    
    // Skenario 1
    node((0, 1.2), align(center)[
      *Skenario 1: Model Baseline* \
      (Mekanisme: Durasi Crash)
    ], corner-radius: 4pt, name: <sken1>, fill: rgb("#EBF3FA"), stroke: 1pt + rgb("#5B9BD5")),
    
    // Question Node 2
    node((2, 1.2), align(center)[
      *Apakah dilakukan* \
      *Preprocessing?*
    ], corner-radius: 4pt, fill: rgb("#F9F9F9"), name: <estim>),
    
    // Skenario 2
    node((1.2, 2.4), align(center)[
      *Skenario 2: Model Cobb-Douglas* \
      (Overmanning & Overtime)
    ], corner-radius: 4pt, name: <sken2>),
    
    // Preprocessing Node
    node((2.5, 2.4), align(center)[
      *Preprocessing* \
      (Estimasi Crashing Cost)
    ], corner-radius: 4pt, name: <preproc>),
    
    // Skenario 3
    node((2.2, 3.5), align(center)[
      *Skenario 3: Model Hybrid* \
      (Preprocessing + CP-SAT)
    ], corner-radius: 4pt, name: <sken3>, fill: rgb("#F1F8F1"), stroke: 1pt + rgb("#A0B89E")),
    
    // Edges
    edge((1, 0), <sken1>, "-|>", label: [Ya], label-pos: 0.4, label-side: left),
    edge((1, 0), <estim>, "-|>", label: [Tidak], label-pos: 0.4, label-side: right),
    
    edge(<estim>, <sken2>, "-|>", label: [Tidak], label-pos: 0.4, label-side: left),
    edge(<estim>, <preproc>, "-|>", label: [Ya], label-pos: 0.4, label-side: right),
    
    edge(<preproc>, <sken3>, "-|>"),
    
    // Show relation between Skenario 3 and Skenario 1's model (curved downward)
    edge(<sken3>, <sken1>, "--|>", label: text(fill: rgb("#5B9BD5"))[Model & Mekanisme sama seperti Skenario 1], bend: 45deg, stroke: 1pt + rgb("#5B9BD5").transparentize(20%), label-side: right)
  )
]
== Contoh Data yang Dimiliki (1)
Dalam Skenario 1 (Baseline), kita memiliki data:
- *Data Aktivitas*: Durasi normal ($d_i^(max)$), durasi minimum ($d_i^(min)$), dan biaya crashing harian ($C_i$).
- *Data Sumber Daya*: Kapasitas harian ($U_k^(max)$) dan kebutuhan harian ($U_(i,k)$).

#align(center)[
  #set text(size: 13pt)
  #grid(
    columns: (auto, 1fr),
    gutter: 0.8cm,
    align: horizon,
    [
      #table(
        columns: (3.2cm, 2.5cm, 1.8cm, 1.8cm, 2.2cm, 2.3cm, 3.2cm),
        align: (left, center, center, center, center, center, left),
        fill: (col, row) => if row == 0 { luma(240) },
        table.header(
          [*Nama Aktivitas*], [*Precedence*], [*$d_i^(min)$*], [*$d_i^(max)$*], [*Normal Cost*], [*$C_i$ (USD/hari)*], [*Sumber Daya*]
        ),
        [Bids & Contracts], [-], [7 hari], [10 hari], [\$600], [\$60.00], [Gen. Mgmt (1), Proj. Mgmt (1)],
        [Grading & Permits], [Bids], [7 hari], [10 hari], [\$700], [\$70.00], [Gen. Mgmt (1), Survey Crew (1)],
        [Site Work], [Grading], [5 hari], [7 hari], [\$300], [\$30.00], [Labor Crew (3), Contractor (2)],
        table.cell(colspan: 7, align: center)[#text(style: "italic")[...]]
      )
    ],
    [
      #table(
        columns: (3.5cm, 2.5cm),
        align: (left, center),
        fill: (col, row) => if row == 0 { luma(240) },
        table.header(
          [*Resource Name*], [*Availability*]
        ),
        [General Manager],  [1 orang],
        [Project Manager],  [1 orang],
        [Survey Crew],      [1 orang],
        [Labor Crew],       [5 orang],
        [Contractor],       [3 orang],
        table.cell(colspan: 2, align: center)[#text(style: "italic")[...]]
      )
    ],
  )
]

*Contoh:* _Site Work_ dikerjakan setelah _Grading & Permits_ oleh *3* _Labor Crew_ dan *2* _Contractor_ selama *7* hari dengan biaya \$300. Namun dapat dipercepat hingga *5* hari dengan biaya percepatan \$30 per hari.

Total terdapat *5* _Labor Crew_ yang dan *3* _Contractor_ yang tersedia dan dapat dikerahkan untuk menyelesaikan Task tersebut.



== Contoh Data yang Dimiliki (2)

Dalam Skenario 2 & 3, terdapat

- `task_table`: ID, Nama, Durasi Baseline, Outline Level, Predecessors.
- `resource_table`: Tarif reguler ($r_k$) dan kapasitas maksimal harian ($U_k^(max)$).
- `assignment_table`: Total usaha kerja ($W_(i,k)$ dalam jam) dan persentase alokasi harian baseline ($U_(i,k)$).

#align(center)[
  #set text(size: 12pt)
  #grid(
    columns: (1.6fr, 1fr),
    gutter: 1.2em,
    table(
      columns: (auto, 1.2fr, auto, auto, 1.3fr, auto),
      align: (center, left, center, center, left, center),
      fill: (col, row) => if row == 0 { luma(240) },
      table.header([*ID*], [*Aktivitas*], [*Baseline*], [*Pred.*], [*Resource (SDM)*], [*Jam Kerja*]),
      [2], [Receive notice to proceed and sign contract], [3 hari], [-], [G.C. General Management], [24 jam],
      table.cell(rowspan: 2, align: center + horizon)[3],
      table.cell(rowspan: 2, align: left + horizon)[Submit bond and insurance documents],
      table.cell(rowspan: 2, align: center + horizon)[2 hari],
      table.cell(rowspan: 2, align: center + horizon)[2],
      [G.C. Project Management], [16 jam],
      [G.C. General Management], [4 jam],
      table.cell(rowspan: 2, align: center + horizon)[4],
      table.cell(rowspan: 2, align: left + horizon)[Prepare and submit project schedule],
      table.cell(rowspan: 2, align: center + horizon)[2 hari],
      table.cell(rowspan: 2, align: center + horizon)[3],
      [G.C. Project Management], [4 jam],
      [G.C. Scheduler], [16 jam],
      table.cell(colspan: 6, align: center)[#text(style: "italic")[...]]
    ),
    table(
      columns: (auto, 1fr, auto),
      align: (center, left, center),
      fill: (col, row) => if row == 0 { luma(240) },
      table.header([*ID*], [*SDM (Resource)*], [*Tarif*]),
      [1], [G.C. General Management], [\$120.00/jam],
      [2], [G.C. Project Management], [\$95.00/jam],
      [9], [G.C. Labor Crew], [\$30.00/jam],
      table.cell(colspan: 3, align: center)[#text(style: "italic")[...]]
    )
  )
]

*Contoh:* Task _Submit bond and insurance documents_ normalnya membutuhkan *2* hari, dikerjakan oleh _Project Manager_ *8* jam kerja per hari ($8 times 2 = 16$ total jam kerja) dan _General Manager_ *2* jam per hari ($2 times 2 = 4$ total jam kerja). Task ini harus dikerjakan setelah task dengan `ID=2` yaitu _Recieve notice to proceed and sign contract_. 

Tarif _General Manager_ adalah \$120 per jam kerja dan _Project Manager_ adalah \$95 per jam kerja.

= Skenario 1: Model Baseline (Diskret Linear)

== Parameter & Variabel Lengkap

#grid(
  columns: (1fr, 1.2fr),
  gutter: 1.5em,
  align: center + horizon, 
  [

    #align(center)[*Variabel & Himpunan*]
    #v(-0.3em)
    #table(

      columns: (auto, 1fr, auto),
      align: (center, left, center),
      inset: 8.5pt,
      fill: (col, row) => if row == 0 { luma(240) },
      table.header([*Notasi*], [*Deskripsi*], [*Satuan*]),
      [$I$], [Himpunan aktivitas proyek], [-],
      [$K$], [Himpunan jenis sumber daya], [-],
      [$E$], [Himpunan relasi precedence], [-],
      [$I_0, I_1$], [Aktivitas selesai / belum mulai], [-],
      [$I_0^C$], [Aktivitas belum selesai], [-],
      [$s_i$], [Hari mulai aktivitas $i$], [hari],
      [$e_i$], [Hari selesai aktivitas $i$], [hari],
      [$s_(n+1)$], [Hari penyelesaian proyek], [hari],
    )
  ],
  [
    #align(center)[*Parameter Model*]
    #v(-0.3em)
    #table(
      columns: (auto, 1fr, auto),
      align: (center, left, center),
      inset: 8pt,
      fill: (col, row) => if row == 0 { luma(240) },
      table.header([*Notasi*], [*Deskripsi*], [*Satuan*]),
      [$d_i^max$], [Durasi normal aktivitas $i$], [hari],
      [$d_i^min$], [Durasi minimum aktivitas $i$], [hari],
      [$C_i$], [Biaya percepatan aktivitas $i$], [\$/hari],
      [$U_(i,k)$], [Kebutuhan resource $k$ oleh $i$], [pekerja],
      [$U_k^max$], [Kapasitas maksimum resource $k$], [pekerja],
      [$T_0$], [Hari peninjauan status proyek], [hari],
      [$T_max$], [Target tenggat waktu proyek], [hari],
      [$c_"late"$], [Koefisien denda keterlambatan], [\$/hari],
      [$c_"early"$], [Koefisien bonus penyelesaian awal], [\$/hari],
    )
  ]
)


== Asumsi Dasar & Karakteristik

Model baseline merumuskan masalah optimisasi penjadwalan dengan durasi diskrit dan biaya percepatan durasi _crashing cost_ linier menggunakan parameter yang diketahui sejak awal.
#v(2.5em)
#grid( 
  columns: (1fr, 1fr),
  gutter: 1.5em,
  [
    #block(
      width: 100%,
      height: 6.2em,
      fill: rgb("#5B9BD5").transparentize(90%),
      stroke: 1.5pt + rgb("#5B9BD5"),
      inset: 0.8em,
      radius: 4pt,
      [
        *Mekanisme Dasar* \
        _Crashing_ dilakukan secara langsung dengan menambah biaya, tanpa memedulikan _underlying mechanism_ dari proses _crashing_.
      ]
    )
    #v(0.5em)
    #block(
      width: 100%,
      height: 6.2em,
      fill: rgb("#5B9BD5").transparentize(90%),
      stroke: 1.5pt + rgb("#5B9BD5"),
      inset: 0.8em,
      radius: 4pt,
      [
        *Linieritas Biaya Crashing* \
        Pengurangan durasi aktivitas diasumsikan memiliki biaya tambahan konstan per hari.
      ]
    )
  ],
  [
    #block(
      width: 100%,
      height: 6.2em,
      fill: rgb("#4A90C0").transparentize(90%),
      stroke: 1.5pt + rgb("#4A90C0"),
      inset: 0.8em,
      radius: 4pt,
      [
        *Non-Preemptive* \
        Aktivitas yang sedang berjalan tidak dapat diinterupsi.
      ]
    )
    #v(0.5em)
    
    #block(
      width: 100%,
      height: 6.2em,
      fill: rgb("#4A90C0").transparentize(90%),
      stroke: 1.5pt + rgb("#4A90C0"),
      inset: 0.8em,
      radius: 4pt,
      [
        *Ketersediaan _Resource_* \
        Resource _availability_ dari masing-masing resource dianggap konstan.
      ]
    )
  ]
)
#pagebreak()

== Variabel Keputusan

#align(center)[
  #v(1em)
  #set text(size: 16pt)
  #table(
    columns: (6cm, 2.5cm, 9.5cm),
    align: center + horizon,
    fill: (col, row) => if row == 0 { luma(240) },
    table.header([*Variabel Keputusan*], [*Domain*], [*Deskripsi*]),
    [$s_i$], [$ZZ$], [Hari mulai untuk aktivitas $i in I$.],
    [$e_i$], [$ZZ$], [Hari akhir untuk aktivitas $i in I$.],
  )
]

#v(1em)
*Variabel Global Proyek:*

#block(
  fill: luma(250),
  stroke: 0.5pt + luma(200),
  inset: 0.8em,
  radius: 4pt,
  width: 100%,
  [
    #align(center)[$ s_(n+1) in ZZ $]
  ]
)

$s_(n+1)$ adalah *task semu* yang merepresentasikan penyelesaian proyek.

#v(0.75em)
*Batasan Precedence:*
$s_(n+1) >= e_i$ untuk semua aktivitas $i$ sehingga $s_(n+1)$ akan bernilai sama dengan waktu penyelesaian proyek.

#pagebreak()

== Batasan Waktu & Precedence

#grid(
  columns: (1fr, 1.2fr),
  gutter: 1.5em,
  [
    *Batasan Durasi & Precedence:* \
    Durasi pengerjaan aktivitas dibatasi antara durasi minimum setelah crashing dan durasi normalnya.
    #block(fill: luma(250), stroke: 0.5pt + luma(200), inset: 0.5em, radius: 4pt, width: 100%,
      [$ d_i^(min) <= e_i - s_i <= d_i^(max) quad forall i in I $]
    )
    
    #v(0.3em)
    
    Aktivitas penerus hanya boleh dimulai setelah seluruh aktivitas pendahulunya selesai dikerjakan.
    #block(fill: luma(250), stroke: 0.5pt + luma(200), inset: 0.5em, radius: 4pt, width: 100%,
      [$ s_i >= e_j quad forall (i,j) in E $]
    )
    
    #set text(13pt)
    *Keterangan:*
    1. $d_i^min$ menyatakan _minimum crashable duration_
    2. $d_i^max$ menyatakan _normal duration_
    3. $T_0$ menyatakan _current date of the project_
    4. $s_i^((0))$ dan $e_i^((0))$ menyatakan jadwal baseline tanpa crashing
  ],
  [
    *Batasan Dinamis terhadap Hari Peninjauan ($T_0$):*
    #block(fill: luma(250), stroke: 0.5pt + luma(200), inset: 0.5em, radius: 4pt, width: 100%,
      [
        #set text(size: 15pt)
        - *Selesai ($i in I_0$):* \ 
          Jadwal dikunci sesuai realisasi historisnya. \
          $ s_i = s_i^((0)), quad e_i = e_i^((0)) $ 
          #v(1em)
        - *Berjalan ($i in I_0^C inter I_1^C$):* \
          Hari mulai dikunci dan penyelesaian dibatasi setelah $T_0$.\
          $ s_i = s_i^((0)), quad e_i >= T_0 $ 
          #v(1em)
        - *Belum Mulai ($i in I_1$):* \
          Tugas hanya boleh dijadwalkan pada atau setelah $T_0$.
          $ s_i >= T_0 $
      ]
    )
  ]
)

#pagebreak()

== Batasan Kapasitas Sumber Daya

Jumlah kebutuhan harian untuk setiap jenis sumber daya yang sedang aktif digunakan secara bersamaan tidak boleh melebihi kapasitas maksimum yang tersedia.

#block(fill: luma(250), stroke: 0.5pt + luma(200), inset: 0.8em, radius: 4pt, width: 100%,
  [$ sum_(i in I) U_(i,k) dot bb(1)\{s_i <= s_j < e_i\} <= U_k^(max) quad forall k in K, forall j in I $]
)

#v(0.5em)
*Penjelasan:*
- Himpunan $I$ merupakan indeks aktivitas dan $K$ merupakan indeks resource.
- Parameter $U_(i,k)$ menyatakan kebutuhan harian sumber daya $k$ oleh aktivitas $i$, dan $U_k^(max)$ menyatakan kapasitas harian maksimum sumber daya $k$.
- Fungsi indikator $bb(1)\{s_i <= s_j < e_i\}$ bernilai $1$ jika aktivitas $i$ sedang berjalan pada saat aktivitas $j$ dimulai ($s_j$), memastikan total penggunaan pekerja di setiap titik awal aktivitas selalu berada dalam batas kapasitas.

#pagebreak()

== Fungsi Objektif

#align(center)[
  #tidy-tree-graph(
    compact: true, 
    draw-node: ((label,)) => (stroke: none)
  )[
    - #block(
        fill: luma(250),
        stroke: 0.5pt + luma(200),
        inset: 1em,
        radius: 4pt,
        width: 12cm,
        [
          #set text(size: 14pt)
          *A. Multi-Objektif* \
          Optimisasi multiobjektif atas waktu dan biaya:
          $ min (s_(n+1), sum_(i in I_0^C) C_i (d_i^max - (e_i - s_i))) $
        ]
      )
      - #block(
          fill: luma(250),
          stroke: 0.5pt + luma(200),
          inset: 1em,
          radius: 4pt,
          width: 14cm,
          [
            #set text(size: 14pt)
            *1. Cost-Driven (Deadline Terkunci)* \
            Meminimalkan total biaya crash dengan batas deadline:
        
              $ min sum_(i in I_0^C) C_i (d_i^max - (e_i - s_i)) quad "s.t." quad s_(n+1) <= T_max $
          
          ]
        )
      - #block(
          fill: luma(250),
          stroke: 0.5pt + luma(200),
          inset: 1em,
          radius: 4pt,
          width: 14cm,
          [
            #set text(size: 14pt)
            *2. Time-Driven (Anggaran Terkunci)* \
            Meminimalkan durasi proyek dengan batas anggaran $B$:
            $ min s_(n+1) quad "s.t." quad sum_(i in I) C_i (d_i^max - (e_i - s_i)) <= B $
          ]
        )
  ]
]

#block(
  fill: rgb("#5B9BD5").transparentize(90%),
  stroke: 1.5pt + rgb("#5B9BD5"),
  inset: 0.7em,
  radius: 4pt,
  width: 100%,
  [
    #set text(size: 14pt)
    *B. Fungsi Objektif Bonus-Penalty* \
    Dimensi "time" dikonversikan menjadi "cost" melalui mekanisme bonus dan penalty pada fungsi objektif _cost-driven_.
    
    #v(0.5em)
    #align(center)[
      #set text(size: 14pt)
      $ min 
      underbrace(sum_(i in I_0^C) C_i (d_i^max - (e_i - s_i)), "Biaya Crashing Baru") + underbrace(c_"late" max(0, s_(n+1) - T_"max"), "Denda Keterlambatan") - underbrace(c_"early" max(0, T_"max" - s_(n+1)), "Bonus Penyelesaian Awal") $
    ]
  ]
)



#pagebreak()

= Skenario 2: Model Baru (Cobb-Douglas)

== Skenario 2: Parameter & Variabel Lengkap

#grid(
  columns: (1.1fr, 1.3fr),
  gutter: 1.5em,
  align: center + horizon,
  [
    #set text(15pt)
    #align(center)[*Variabel & Himpunan*]
    #v(-0.3em)
    #table(
      columns: (auto, 1fr, auto),
      inset: 5.5pt,
      align: (center, left, center),
      fill: (col, row) => if row == 0 { luma(240) },
      table.header([*Notasi*], [*Deskripsi*], [*Satuan*]),
      [$I, K$], [Himpunan aktivitas & resource], [-],
      [$E_"FS", E_"SS", E_"FF"$], [Relasi precedence FS, SS, FF], [-],
      [$I_0, I_1, I_0^C$], [Status aktivitas proyek], [-],
      [$s_i, e_i$], [Waktu mulai & selesai aktivitas $i$], [hari],
      [$x_(i,k)$], [Pengali overmanning pekerja $k$], [-],
      [$tau_(i,k)$], [Jam lembur harian pekerja $k$], [jam/hari],
      [$d_(i,k)$], [Durasi aktual pekerja $k$ pada $i$], [hari],
      [$z_(i,k)$], [Total biaya pekerja $k$ pada $i$], [\$],
      [$s_(n+1)$], [Hari penyelesaian proyek], [hari],
    )
  ],
  [
    #align(center)[*Parameter Model*]
    #v(-0.3em)
    #table(
      columns: (auto, 1fr, auto),
      align: (center, left, center),
      inset: 8pt,
      fill: (col, row) => if row == 0 { luma(240) },
      table.header([*Notasi*], [*Deskripsi*], [*Satuan*]),
      [$d_(i,k)^((0))$], [Durasi normal pekerja $k$ pada $i$], [hari],
      [$W_(i,k)^((0))$], [Usaha kerja normal pekerja $k$], [hari-orang],
      [$p_(i,k)$], [Progress pengerjaan pekerja $k$], [%],
      [$r_k, r'_k$], [Tarif upah normal & lembur], [\$/jam],
      [$alpha, beta$], [Elastisitas crowding & lembur], [-],
      [$x_(i,k)^max$], [Batas pengali overmanning], [-],
      [$delta_(i j)$], [Waktu lag/lead aktivitas $i$ & $j$], [hari],
      [$T_0, T_max$], [Hari peninjauan & target deadline], [hari],
      [$c_"late", c_"early"$], [Koefisien denda & bonus proyek], [\$/hari],
      [$U_(i,k), U_k^max$], [Kebutuhan & kapasitas resource], [pekerja],
    )
  ]
)


== Motivasi

Sekarang, kita tidak diberikan *crashing cost* secara langsung. Apa yang harus dilakukan? 

#v(0.3em)
*Formulasi Durasi Berdasarkan Data* \
Secara fisik, untuk jenis tenaga kerja $k$ pada tugas $i$, total jam kerja (usaha kerja $W_(i,k)$) adalah hasil perkalian antara hari kerja ($d_(i,k)$), *durasi kerja* harian normal (8 jam), dan *jumlah tenaga kerja* baseline ($U_(i,k)$):
#v(-0.3em)
$ W_(i,k) = d_(i,k) dot 8 dot U_(i,k) quad arrow.r quad d_(i,k) = W_(i,k) / (8 dot U_(i,k)) $ sedangkan biaya _baseline_  adalah 

$ z_(i,k)^(\(0\)) = W_(i,k) r_k. $

*Mekanisme Crashing* \
Karena kedua variabel di atas yang memengaruhi durasi, kita pilih keduanya sebagai mekanisme crashing-nya: kita bisa menambahkan tenaga kerja (*overmanning*, $x_(i,k) >= 1.0$ dengan batas $x_("max") = 2.0$) dan/atau menambahkan jam kerja lembur (*overtime*, $tau_(i,k) >= 0.0$ dengan batas $tau_("max") = 4.0$ jam/hari).

#v(-0.2em)
#pagebreak()

== Latar Belakang _Cobb-Douglas_


#grid(
  columns: (1fr, auto, 1fr),
  gutter: 0.8em,
  align: horizon,
  [
    #block(
      fill: luma(250),
      stroke: 0.5pt + luma(200),
      inset: 0.8em,
      radius: 4pt,
      width: 100%,
      [
        #set text(size: 15pt)
        *Paradoks Biaya Nol (Naive Crashing)* \
        Secara naif, durasi task dapat dihitung dengan $ d'_(i,k) = W_(i,k) / ((8+tau_(i,k)) x_(i,k) U_(i,k)) $Namun,
        #v(0.2em)
        #align(center)[
            $ z_(i,k) = d'_(i,k) dot x_(i,k) U_(i,k) dot (8 + tau_(i,k)) r_k = W_(i,k) r_k = z_(i,k)^((0)). $
        ]
        #v(0.2em)
        Hal ini tidak realistis karena mengabaikan hilangnya efisiensi akibat kepadatan area kerja (*crowding*) dan kelelahan pekerja (*fatigue*).
      ]
    )
  ],
  [
    #text(size: 28pt, fill: rgb("#5B9BD5"))[#sym.arrow.r]
  ],
  [
    #block(
      fill: rgb("#5B9BD5").transparentize(90%),
      stroke: 1.5pt + rgb("#5B9BD5"),
      inset: 0.8em,
      radius: 4pt,
      width: 100%,
      [
        #set text(size: 15pt)
        *_Deminishing Return_ via Fungsi Cobb-Douglas* \
        Teori ekonomi menggunakan fungsi produksi Cobb-Douglas $ Y = A L^alpha K^beta $ untuk memodelkan hubungan output ($Y$) dengan tenaga kerja ($L$) dan modal ($K$). Kita memetakan:
        - Input Tenaga Kerja ($L$) $arrow.r$ *overmanning* 
        #v(1mm)
        - Input Waktu/Modal ($K$) $arrow.r$  *overtime* 
        
        Dengan eksponen elastisitas marjinal $alpha, beta in (0, 1)$ untuk memodelkan *diminishing returns*:
        #v(0.2em)
        #align(center)[
$ d^'_(i,k) = d_(i,k)^((0)) dot (1 / x_(i,k))^alpha dot (8 / (8 + tau_(i,k)))^beta $
        ]
        #v(0.2em)
      
      ]
    )
  ]
)

#pagebreak()

== Penurunan Biaya Crashing

*Formulasi Biaya Harian:* \
Biaya total baru adalah hasil kali dari durasi kerja aktual, jumlah pekerja harian, dan tarif upah harian yang mencakup premi tarif lembur ($r'_k$):
$ 
z_(i,k)(x_(i,k), tau_(i,k)) 
&= d_(i,k) (x_(i,k), tau_(i,k)) dot x_(i,k) U_(i,k) dot (8 r_k + tau_(i,k) r'_k) \ 

&= W_(i,k) / (8 U_(i,k)) dot (1 / x_(i,k))^alpha dot (8 / (8 + tau_(i,k)))^beta dot x_(i,k) U_(i,k) dot (8 r_k + tau_(i,k) r'_k) \

&= W_(i,k) dot x_(i,k)^(-alpha) dot x_(i,k) dot ((8 + tau_(i,k)) / 8)^(-beta) dot (8 + tau_(i,k)) / 8 dot 1 / (8 + tau_(i,k)) dot (8 r_k + tau_(i,k) r'_k) \

&= 
underbrace(W_(i,k) r_k, "baseline") dot 
underbrace(x_(i,k)^(1-alpha), "overman") dot 
underbrace(((8 + tau_(i,k)) / 8)^(1-beta), "overtime") dot 
underbrace((8 + r'_k / r_k tau_(i,k)) / (8 + tau_(i,k)), "extra wage"). 
$

#pagebreak()

== Variabel Keputusan

Solver menentukan waktu mulai, tingkat overmanning, dan jam lembur untuk menghasilkan jadwal proyek dengan total biaya minimum.

#align(center)[
  #set text(size: 14pt)
  #table(
    columns: (6cm, 3cm, 9cm),
    align: (center, center, left),
    fill: (col, row) => if row == 0 { luma(240) },
    table.header([*Variabel Keputusan*], [*Domain*], [*Deskripsi*]),
    [$s_i$], [$RR$], [Hari mulai untuk aktivitas $i in I$.],
    [$x_(i,k)$], [$RR$], [Pengali overmanning pekerja $k$ pada aktivitas $i$ ($1 <= x_(i,k) <= x_(i,k)^max$).],
    [$tau_(i,k)$], [$ZZ$], [Jam lembur harian pekerja $k$ pada aktivitas $i$ ($0 <= tau_(i,k) <= 4$).],
  )
]

*Variabel Global Proyek:*

#block(
  fill: luma(250),
  stroke: 0.5pt + luma(200),
  inset: 0.8em,
  radius: 4pt,
  width: 100%,
  [
    #align(center)[$ s_(n+1) in RR $]
  ]
)

$s_(n+1)$ adalah *task semu* yang merepresentasikan penyelesaian proyek.

#v(0.75em)
*Batasan Precedence:*
$s_(n+1) >= e_i$ untuk semua aktivitas $i$ sehingga $s_(n+1)$ akan bernilai sama dengan waktu penyelesaian proyek.


#pagebreak()

== Batasan Waktu, Precedence & Dinamis

#grid(
  columns: (1.1fr, 1fr),
  gutter: 1em,
  [
    *Batasan Durasi* \
    Di sini, $e_i$ hanya variabel pembantu (bukan variabel keputusan) untuk memudahkan penulisan batasan. 
    #block(fill: luma(250), stroke: 0.5pt + luma(200), inset: 0.4em, radius: 4pt, width: 100%,
      [
        #set text(size: 13pt)
        $ e_i = s_i + max_k d^'_(i,k) $
        
      ]
    )
    #v(0.2em)
    *Batasan Precedence* \ 
    Seperti sebelumnya, perlu ada batasan _precedence_. 
    #block(fill: luma(250), stroke: 0.5pt + luma(200), inset: 0.4em, radius: 4pt, width: 100%,
      [
        #set text(size: 13pt)
        $ s_j >= e_i  quad forall (i,j) in E $
        // Percepatan durasi hanya boleh difokuskan pada aktivitas jalur kritis (*bottleneck*) karena mempercepat aktivitas non-kritis hanya membuang anggaran tanpa mempercepat durasi proyek.
      ]
    )
    #set text(size: 14pt)
    *Keterangan:*
    1. $p_i$ menyatakan proporsi task $i$ yang sudah selesai
    2. $T_0$ menyatakan _current date of the project_
    3. $s_i^((0))$ menyatakan jadwal baseline tanpa crashing
    4. $W_(i,k)^((0))$ menyatakan total jam kerja baseline tanpa crashing
    
  ],
  [
    *Batasan Dinamis*
    #block(fill: luma(250), stroke: 0.5pt + luma(200), inset: 0.4em, radius: 4pt, width: 100%,
      [
        #set text(size: 13pt)
        - *Selesai ($i in I_0$):* #h(2pt)
          Jadwal dan alokasi tugas *dikunci* sepenuhnya.
          $ s_i = s_i^((0)), \ x_(i,k) = 1, \ tau_(i,k) = 0 $
          #v(1em)
        - *Berjalan ($i in I_0^C inter I_1^C$):* #h(2pt)
          Sisa alokasi dioptimasi dari sisa usaha kerja. 
          $ s_i &= s_i^((0)), \ e_i &>= T_0, \ W_(i,k) &= W_(i,k)^((0)) (1-p_(i)) $
          #v(1em)
        - *Belum Mulai ($i in I_1$):* #h(2pt)
          Tugas dimulai pada atau setelah $T_0$.
          $ s_i >= T_0, \ W_(i,k) = W_(i,k)^((0)) $
      ]
    )
  ]
)

#pagebreak()

== Batasan Kapasitas Sumber Daya

Total alokasi pekerja harian untuk suatu jenis sumber daya tidak boleh melebihi kapasitas maksimum yang tersedia sepanjang durasi tugas mereka.

#block(fill: luma(250), stroke: 0.5pt + luma(200), inset: 0.8em, radius: 4pt, width: 100%,
  [$ sum_(i in I) U_(i,k) dot bb(1)\{s_i <= s_j < s_i + d_(i,k)\} <= U_k^(max) quad forall k in K, forall j in I $]
)

#v(0.5em)
*Penjelasan:*
- Batasan ini dievaluasi pada level alokasi pekerja ($s_i + d_(i,k)$) bukan tingkat tugas ($e_i$), yang memungkinkan pekerja berpindah tugas begitu pekerjaan spesifiknya selesai.
- Pengecekan hanya dilakukan pada setiap titik hari mulai aktivitas ($s_j$) untuk menyederhanakan perhitungan beban komputasi.

#pagebreak()

== Alternatif Objektif

#v(-0.25em)

#align(center)[
  #tidy-tree-graph(
    compact: true, 
    draw-node: ((label,)) => (stroke: none)
  )[
    - #block(
        fill: luma(250),
        stroke: 0.5pt + luma(200),
        inset: 1em,
        radius: 4pt,
        width: 12cm,
        [
          #set text(size: 14pt)
          *A. Multi-Objektif* \
          Optimisasi multiobjektif atas waktu dan biaya:
          $ min (s_(n+1), sum_(i in I_0^C) z_(i,k) (x_(i,k), tau_(i,k)) $
        ]
      )
      - #block(
          fill: luma(250),
          stroke: 0.5pt + luma(200),
          inset: 1em,
          radius: 4pt,
          width: 14cm,
          [
            #set text(size: 14pt)
            *1. Cost-Driven (Deadline Terkunci)* \
            Meminimalkan total biaya upah endogen dengan batas $T_max$:
         $ min sum_(i in I_0^C) sum_(k in K) z_(i,k)(x_(i,k), tau_(i,k)) quad "s.t." quad s_(n+1) <= T_max $
          ]
        )
      - #block(
          fill: luma(250),
          stroke: 0.5pt + luma(200),
          inset: 1em,
          radius: 4pt,
          width: 14cm,
          [
            #set text(size: 14pt)
            *2. Time-Driven (Anggaran Terkunci)* \
            Meminimalkan durasi proyek dengan batas anggaran $B$:
            $ min s_(n+1) quad "s.t." quad sum_(i in I) sum_(k in K) z_(i,k)(x_(i,k), tau_(i,k)) <= B $
          ]
        )
  ]
]

#block(
  fill: rgb("#5B9BD5").transparentize(90%),
  stroke: 1.5pt + rgb("#5B9BD5"),
  inset: 0.6em,
  radius: 4pt,
  width: 100%,
  [
    #set text(size: 14.8pt)
    *Fungsi Objektif Bonus-Penalty* \
    Dimensi "time" dikonversikan menjadi "cost" melalui mekanisme bonus dan penalty pada fungsi objektif _cost-driven_.
    
    #align(center)[
      #set text(size: 16pt)
      $ min underbrace(sum_(i in I_0^C) sum_(k in K) z_(i,k)(x_(i,k), tau_(i,k)), "Total Biaya Upah Endogen") + underbrace(c_"late" max(0, s_(n+1) - T_"max"), "Denda Keterlambatan") - underbrace(c_"early" max(0, T_"max" - s_(n+1)), "Bonus Penyelesaian Awal") $
    ]
  ]
)
    
#pagebreak()

= Metode Penyelesaian

== Metode Penyelesaian Skenario 1 & 2

#grid(
  columns: (1fr, 1fr),
  gutter: 1.5em,
  [
    #block(
      fill: rgb("#5B9BD5").transparentize(90%),
      stroke: 1.5pt + rgb("#5B9BD5"),
      inset: 0.8em,
      radius: 4pt,
      width: 100%,
      height: 16em,
      [
        #set text(size: 11.5pt)
        *Skenario 1: Google OR-Tools CP-SAT* \
        Model diselesaikan secara optimal global menggunakan Constraint Programming (CP) solver.
        
        #v(0.3em)
        *Setup Solver:*
        - *Interval Task*: `NewIntervalVar(s_i, d_i, e_i)` menggabungkan mulai, durasi, dan selesai.
        - *Relasi Crashing*: $d_i + c_i == d_i^max$, dengan variabel crash days $c_i in [0, d_i^max - d_i^min]$.
        - *Precedence*: `model.Add(s_j >= e_i)` untuk memaksakan hubungan Finish-to-Start.
        - *Kapasitas*: `model.AddCumulative(intervals, demands, capacity)` untuk batasan resource.
        - *Multi-threading*: `num_search_workers` pada parameter solver.
      ]
    )
  ],
  [
    #block(
      fill: rgb("#A0B89E").transparentize(90%),
      stroke: 1.5pt + rgb("#A0B89E"),
      inset: 0.8em,
      radius: 4pt,
      width: 100%,
      height: 16em,
      [
        #set text(size: 11.5pt)
        *Skenario 2: Genetic Algorithm (pymoo)* \
        Model diselesaikan dengan pendekatan metaheuristik untuk menangani non-linieritas Cobb-Douglas.
        
        #v(0.3em)
        *Setup Algoritma:*
        - *Representasi*: `ElementwiseProblem` dengan pengali overmanning $x_(i,k) in [1, x_(i,k)^max]$ dan jam lembur $tau_(i,k) in [0, 4]$.
        - *Evaluasi Fitnes*: *CPM Forward Pass* di dalam kode Python untuk menghitung makespan ($s_(n+1)$).
        - *Kendala*: Batasan durasi minimum ($d_(i,k)^"min"$) dimodelkan sebagai kendala inequality $G[p] <= 0$.
        - *Operator GA*: Crossover menggunakan *SBX* (probabilitas $0.9$) dan mutasi *PM*.
        - *Kriteria Berhenti*: Kriteria konvergensi toleransi multiobjektif (`RobustTermination`).
      ]
    )
  ]
)

= Hasil Eksplorasi

== Hasil Eksplorasi Model 1 
Digunakan objective _cost driven_ dengan parameter $T_0=20$ dan $T_max=243$, diperoleh hasil berikut. 
#grid(
  columns: (1fr, 1fr),
  gutter: 1.5em,
  [
    #set text(size: 14pt)
    #align(center)[
      *Gantt Chart Model IDSC*
      #image("gantt_idsc.jpeg", height: 50%)
    ]
  ],
  [
    #set text(size: 14pt)
    #align(center)[
      *Gantt Chart Model Kami*
      #image("gantt_crashed.png", height: 50%)
    ]
  ]
)

#v(0.2em)
#align(center)[
  #set text(size: 14pt)
  *Tabel 1: Perbandingan Kuantitatif Hasil Optimasi Penjadwalan*
  #v(0.2em)
  #set text(size: 12pt)
  #table(
    columns: (4cm, 3.5cm, 3cm, 4cm),
    align: center + horizon,
    fill: (col, row) => if row == 0 { luma(240) },
    [*Model*], [*Total Biaya (\$)*], [*Status Solusi*], [*Waktu Eksekusi*],
    [IDSC], [220], [Optimal Global], [\~3 mnt],
    [*Kami*], [*220*], [*Optimal Global*], [*< 1s*]
  )
]

#pagebreak()

== Hasil Eksplorasi Model 2 (Cobb-Douglas)

#set text(size: 13pt)

Digunakan objective _bonus-penalty_ dengan parameter $T_0=156$ dan $T_max=344$, diperoleh hasil berikut (hanya ditampilkan 20 _task_ aktif pertama) dengan waktu eksekusi \~30 menit. 

#align(center)[
  #image("cobb_gantt_20.png", width: 80%)
]

#pagebreak()

#set text(20pt)
= Skenario 3: Model Hybrid 

== Skenario 3 - Model Hybrid
- *Ide Utama*: Menggabungkan kelebihan realisme data Skenario 2 (upah SDM, Cobb-Douglas) dengan kecepatan komputasi Skenario 1 (CP-SAT).
- *Mekanisme*: Melakukan *preprocessing* menggunakan matematika Cobb-Douglas dari Skenario 2 untuk mengestimasi batas durasi dan biaya crashing per hari secara otomatis.
- Parameter hasil preprocessing ($d_i^(min), d_i^(max), C_i$) kemudian dimasukkan langsung ke solver CP-SAT Skenario 1.
- Solver CP-SAT akan menyelesaikan model dalam waktu yang cepat.

== Langkah Preprocessing 

Untuk setiap tugas $i$ dan jenis SDM $k$ dihitung:
1. *Durasi Normal*: $d_i^(max) = max_k ceil(W_(i,k) / (8 U_(i,k)))$ dan *Biaya Baseline*: $Z_i^("base") = sum_k W_(i,k) r_k$
2. *Durasi Minimum* (pada $x_"max" = 2.0$ dan $tau_"max" = 2.0$):
   $ d_i^(min) = max_(k in K_i) ceil(W_(i,k) / (8 U_(i,k)) dot (1 / x_"max")^alpha dot (8 / (8 + tau_"max"))^beta) $
3. *Biaya Crashing Maksimum*: $Z_i^("crash") = sum_k z_(i,k)(x_"max", tau_"max")$
4. *Biaya Crashing Harian (Crash Slope)* $C_i$:
   $ C_i = cases(
     (Z_i^("crash") - Z_i^("base")) / (d_i^(max) - d_i^(min)) & "jika" d_i^(max) > d_i^(min),
     0 & "jika" d_i^(max) = d_i^(min)
   ) $

== Integrasi ke Solver CP-SAT

#set text(20pt)

Setelah preprocessing, kita selesaikan model penjadwalan linier:
$ min sum_(i in I_0^C) C_i (d_i^(max) - (e_i - s_i)) + c_"late" max(0, s_(n+1) - T_"max") - c_"early" max(0, T_"max" - s_(n+1)) $
dengan batasan linier terpusat:
- *Batasan Waktu & Durasi*:
  $ e_i = s_i + d_i $
  $ d_i^(min) <= e_i - s_i <= d_i^(max) $
- *Precedence*: $s_j >= e_i$
- *Kapasitas*: $sum_i U_(i,k) dot bb(1)\{s_i <= s_j < e_i\} <= U_k^(max)$
- *Batasan Dinamis* terhadap $T_0$.

== Perbandingan Karakteristik Model

#set text(size: 20pt)
#align(center)[
  
  #set text(size: 15pt) 
  #table(
    columns: (0.6fr, 1.2fr, 1.1fr, 1.1fr),
    align: center + horizon,
    inset: 0.85em,
    fill: (col, row) => if row == 0 { luma(240) },
    table.header(
      [*Karakteristik*], [*Model Baseline (Skenario 1)*], [*Model Baru (Skenario 2)*], [*Model Hybrid (Skenario 3)*],
    ),
    [*Input Biaya*], [Eksplisit per hari crashing (\$/hari).], [Endogen dari upah SDM (\$/jam).], [Cobb-Douglas preprocessing + linearisasi crash slope.],
    [*Akselerasi*], [Memotong hari durasi secara langsung.], [Menambah orang ($x$) & jam kerja lembur ($tau$).], [Batas $x_"max"$, $tau_"max"$ pada preprocessing.],
    [*Sifat Efisiensi*], [Efisiensi konstan (biaya linier terhadap crashing).], [Efisiensi menurun (*diminishing returns*).], [Efisiensi Cobb-Douglas didekati linier lokal per tugas.],
    [*Tipe Precedence*], [Finish-to-Start (FS) tanpa lag.], [FS, SS, FF dengan lag/lead.], [Finish-to-Start (FS) tanpa lag.],
    [*Metode Solver*], [OR-Tools CP-SAT (Sangat Cepat).], [MILP (Pyomo) & GA (pymoo) (Sangat Lambat).], [OR-Tools CP-SAT setelah preprocessing (Sangat Cepat).]
  )
]


= Kesimpulan

== Kesimpulan


1. *Skenario 1*: Berkinerja cepat tetapi tidak realistis di lapangan karena data biaya crashing per hari jarang dimiliki perusahaan.
2. *Skenario 2*: Memodelkan realitas penambahan tenaga kerja dan lembur secara presisi menggunakan Cobb-Douglas, namun memiliki biaya komputasi yang tinggi (NP-hard).
3. *Skenario 3 (Hybrid)*: Menawarkan *solusi jalan tengah terbaik*. Menggunakan preprocessing Cobb-Douglas dari Skenario 2 untuk menghasilkan parameter biaya dan durasi realistis secara otomatis, kemudian menyelesaikannya dalam waktu kurang dari 10 milidetik menggunakan solver CP-SAT Skenario 1.


= Rencana Selanjutnya

== Langkah Strategis Selanjutnya
#align(center + horizon)[
  #set text(size: 11pt)
  #v(-1em)
  #diagram(
    node-stroke: 1pt + rgb("#7F7F7F"),
    node-fill: white,
    node-inset: 8pt,
    edge-stroke: 1pt + rgb("#7F7F7F"),
    mark-scale: 80%,
    spacing: (60pt, 30pt),
    
    // Model 1 (CP-SAT)
    node((0, 0), align(center)[
      *Model 1: Baseline (CP-SAT)*
    ], corner-radius: 4pt, fill: rgb("#5B9BD5").transparentize(90%), stroke: 1.5pt + rgb("#5B9BD5"), name: <m1>),
    
    node((1.5, 0), align(left)[
      *Implementasi:* \
      - Multiobjektif
      - Bonus-Penalty
    ], corner-radius: 4pt, fill: rgb("#5B9BD5").transparentize(90%), stroke: 1.5pt + rgb("#5B9BD5"), name: <m1_impl>),
    
    // Model 2 (Cobb-Douglas GA)
    node((0, 1.5), align(center)[
      *Model 2: Cobb-Douglas (GA)*
    ], corner-radius: 4pt, fill: rgb("#A0B89E").transparentize(90%), stroke: 1.5pt + rgb("#A0B89E"), name: <m2>),
    
    node((1.5, 1.5), align(left)[
      *Implementasi:* \
      - Multiobjektif
    ], corner-radius: 4pt, fill: rgb("#A0B89E").transparentize(90%), stroke: 1.5pt + rgb("#A0B89E"), name: <m2_impl>),
    
    // Skenario 3 (Hybrid)
    node((0, 3.0), align(center)[
      *Skenario 3: Hybrid*
    ], corner-radius: 4pt, fill: rgb("#4A90C0").transparentize(90%), stroke: 1.5pt + rgb("#4A90C0"), name: <s3>),
    
    node((1.5, 3.0), align(left)[
      *Implementasi:* \
      - Model Hybrid
    ], corner-radius: 4pt, fill: rgb("#4A90C0").transparentize(90%), stroke: 1.5pt + rgb("#4A90C0"), name: <s3_impl>),
    
    // Convergence Target: Sensitivity Analysis
    node((3.3, 1.5), align(center)[
      *Analisis Sensitivitas* \
      (Sensitivity Analysis) \
      #v(0.3em)
      Menguji variasi parameter: \
      $alpha$, $beta$, denda/bonus, \
      $x_"max"$, dan $tau_"max"$
    ], corner-radius: 4pt, fill: luma(250), stroke: 2pt + luma(180), name: <sens>),
    
    // Edges
    edge(<m1>, <m1_impl>, "-|>"),
    edge(<m2>, <m2_impl>, "-|>"),
    edge(<s3>, <s3_impl>, "-|>"),
    
    edge(<m1_impl>, <sens>, "-|>", bend: -15deg),
    edge(<m2_impl>, <sens>, "-|>"),
    edge(<s3_impl>, <sens>, "-|>", bend: 15deg),
  )
]

= Terima Kasih

// #align(center)[
//   #text(size: 32pt, weight: "bold")[Terima Kasih]
// ]