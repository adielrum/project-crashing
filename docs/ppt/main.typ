#import "@preview/touying:0.6.1": *
#import "university.typ" : *
#import "@preview/theorion:0.4.0": *
#import "@preview/cetz:0.5.0"
#import "@preview/gantty:0.5.1": gantt, 
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
  // align: horizon,
  // config-common(handout: true),
  config-common(frozen-counters: (theorem-counter,)),  // freeze theorem counter for animation
  config-info(
    title: [Resource-Constrained TCTPs in Project Crashing],
    subtitle: [Optimisasi Penjadwalan Proyek],
    author: [K13 Pemodelan Matematika],
    date: [2026-05-08],
    institution: [ MA3251 Pemodelan Matematika \
    Institut Teknologi Bandung],
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

== Outline
- Latar Belakang & Masalah
- Skenario 1: Model Baseline (CP-SAT)
- Skenario 2: Model Novel (Cobb-Douglas)
- Penurunan Matematika Cobb-Douglas (Overcrowding & Overtime)
- Skenario 3: Model Hybrid (Preprocessing + CP-SAT)
- Perbandingan & Kesimpulan

= Latar Belakang & Masalah

== Concrete Works Schedule

#{
  set text(size: 12pt)
  let base-data = yaml("concrete.yaml")
  let vanilla-data = remove-deps(base-data)

  scale(80%, origin: center + top)[
    #gantt(vanilla-data)
  ]
}

#pagebreak()

== Concrete Works Schedule

#{
  set text(size: 12pt)
  let base-data = yaml("concrete.yaml")
  
  let late-data = remove-deps(base-data)
  late-data = add-deadline(late-data, "2023-12-10")

  scale(80%, origin: center + top)[
    #gantt(late-data)
  ]
}

#pagebreak()

== Resource Constraints

#lorem(50)

== Temporal Constraints

#{
  set text(size: 12pt)
  let dep-data = yaml("concrete.yaml")

  scale(80%, origin: center + top)[
    #gantt(dep-data)
  ]
}

== Skenario

- Skenario 1: Perusahaan memiliki data crashing cost per hari untuk setiap task. Mekanisme crashing dengan menentukan durasi crash.

- Skenario 2: Perusahaan tidak memiliki data crashing cost per hari untuk setiap task. Mekanisme crashing dengan overmanning dan overtime.

- Skenario 3: Perusahaan tidak memiliki data crashing cost per hari untuk setiap task. Crashing cost diestimasi pada tahap preprocessing data. Mekanisme crashing dengan menentukan durasi crash.

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
        [General Manager],  [1/hari],
        [Project Manager],  [1/hari],
        [Survey Crew],      [1/hari],
        [Labor Crew],       [5/hari],
        [Contractor],       [3/hari],
        table.cell(colspan: 2, align: center)[#text(style: "italic")[...]]
      )
    ],
  )
]

*Contoh:* _Site Work_ dikerjakan setelah _Grading & Permits_ oleh *3* _Labor Crew_ dan *2* _Contractor_ selama *7* hari dengan biaya \$300. Namun dapat dipercepat hingga *5* hari dengan biaya percepatan \$30 per hari.

Total terdapat *5* _Labor Crew_ yang dan *3* _Contractor_ yang tersedia dan dapat dikerahkan untuk menyelesaikan Task tersebut.



== Contoh Data yang Dimiliki (2)

Dalam Skenario 2 & 3, data operasional lebih realistis dan berasal dari MS Project:
- `task_table`: ID, Nama, Durasi Baseline, Outline Level, Predecessors.
- `resource_table`: Tarif reguler ($r_k$) dan kapasitas maksimal harian ($U_k^(max)$).
- `assignment_table`: Total usaha kerja ($W_(i,k)$ dalam jam) dan persentase alokasi harian baseline ($U_(i,k)$).

#align(center)[
  #set text(size: 13pt)
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
      [G.C. Scheduler], [16 jam]
    ),
    table(
      columns: (auto, 1fr, auto),
      align: (center, left, center),
      fill: (col, row) => if row == 0 { luma(240) },
      table.header([*ID*], [*SDM (Resource)*], [*Tarif*]),
      [1], [G.C. General Management], [\$120.00/jam],
      [2], [G.C. Project Management], [\$95.00/jam],
      [9], [G.C. Labor Crew], [\$30.00/jam]
    )
  )
]

*Contoh:* Task _Submit bond and insurance documents_ normalnya membutuhkan *2* hari, dikerjakan oleh _Project Manager_ 8 jam kerja per hari dan _General Manager_ 2 jam per hari. Task ini harus dikerjakan setelah task dengan `ID=2` yaitu _Recieve notice to proceed and sign contract_. Tarif _General Manager_ adalah \$120 per jam dan _Project Manager_ adalah \$95 per jam./.

= Skenario 1: Model Baseline (CP-SAT)

== Skenario 1 - Model Baseline

- *Kelebihan*: Menyelesaikan penjadwalan dengan sangat cepat (milidetik) dengan jaminan solusi optimal global menggunakan *Google OR-Tools CP-SAT*.
- *Kekurangan*: Asumsi data tidak realistis. Biaya pemotongan durasi harian ($C_i$) diasumsikan konstan dan diketahui secara langsung. Perusahaan jarang memiliki data crashing harian seperti ini.

*Fungsi Objektif (Bonus-Penalty)*:
$ min sum_(i in I_0^C) C_i (d_i^(max) - (e_i - s_i)) + c_"late" max(0, s_(n+1) - T_"max") - c_"early" max(0, T_"max" - s_(n+1)) $
*Batasan Utama*:
- Durasi: $d_i^(min) <= e_i - s_i <= d_i^(max)$
- Precedence: $s_j >= e_i$
- Kapasitas Sumber Daya: $sum_(i in I) U_(i,k) dot bb(1) \{ s_i <= s_j < e_i \} <= U_k^max$

#pagebreak()



= Skenario 2: Model Novel (Cobb-Douglas)

== Skenario 2 - Model Novel

- *Latar Belakang*: Di lapangan, manajer proyek hanya memiliki tuas kontrol berupa:
  1. *Overcrowding* ($x_(i,k) >= 1.0$): Menambah tenaga kerja.
  2. *Overtime* ($tau_(i,k) >= 0.0$ jam/hari): Menambah jam kerja lembur.
- Penambahan pekerja menimbulkan inefisiensi beban koordinasi, sedangkan lembur menimbulkan kelelahan (*labor fatigue*).
- Hubungan non-linier ini dimodelkan dengan *Fungsi Produksi Cobb-Douglas* untuk menangkap efek penurunan efisiensi marjinal (*diminishing returns*).

== Penurunan Durasi Cobb-Douglas

Fungsi produksi Cobb-Douglas standar: $Y(L,K) = A L^alpha K^beta$.
Dalam konteks crashing, kita kalibrasi durasi efektif untuk SDM $k$ pada tugas $i$ sebagai:
$ d_(i,k) (x_(i,k), tau_(i,k)) = d_(i,k)^((0)) dot (1 / x_(i,k))^alpha dot (8 / (8 + tau_(i,k)))^beta $
Di mana:
- $d_(i,k)^((0)) = W_(i,k) / (8 U_(i,k))$ menyatakan durasi baseline.
- $x_(i,k)$ adalah pengali overcrowding.
- $tau_(i,k)$ adalah jam lembur (0 hingga 4 jam/hari).
- $alpha, beta in (0, 1)$ adalah eksponen inefisiensi overcrowding dan fatigue overtime.

== Penurunan Biaya Endogen

Dengan memisahkan upah reguler (8 jam pada tarif $r_k$) dan upah lembur ($tau_(i,k)$ jam pada tarif $r'_k = "ot_mult" dot r_k$), total biaya dihitung dari jumlah pekerja-hari dikalikan upah harian:
$ z_(i,k) (x_(i,k), tau_(i,k)) = d_(i,k) dot x_(i,k) U_(i,k) dot (8 r_k + tau_(i,k) r'_k) $
Substitusikan $d_(i,k)$ untuk mengeliminasi durasi:
$ z_(i,k) (x_(i,k), tau_(i,k)) = W_(i,k) r_k dot x_(i,k)^(1-alpha) dot ((8 + tau_(i,k)) / 8)^(1-beta) dot (8 + r'_k / r_k tau_(i,k)) / (8 + tau_(i,k)) $
*Justifikasi*: Karena $1-alpha, 1-beta < 1$, biaya marjinal per hari pengerjaan akan meningkat seiring kita memotong durasi tugas, sehingga pemotongan durasi tidak lagi "gratis".

== Metode Penyelesaian Skenario 2

- *Sifat Matematis*: Model ini merupakan *MINLP (Mixed-Integer Non-Linear Programming)* yang non-konveks dan NP-hard.
- *Pendekatan*:
  1. *MILP dengan Diskretisasi Grid*: Mendiskretkan pengali $x in {1.0, 1.25, ..., 2.0}$ dan $tau in {0, 1, 2, 3, 4}$ jam. Durasi dan biaya di-precompute untuk setiap titik grid biner $xi_(i,k)^(m,n)$.
  2. *Metaheuristik (Genetic Algorithm)*: Optimisasi kontinu berbasis pymoo.
- *Limitasi*: Ruang pencarian yang besar menyebabkan *runtime* penyelesaian yang tinggi (beberapa menit) dan dapat memicu ketidakakuratan (terjebak lokal optimum) pada proyek besar.

= Skenario 3: Model Hybrid (Jalan Tengah)

== Skenario 3 - Model Hybrid

- *Ide Utama*: Menggabungkan kelebihan realisme data Skenario 2 (upah SDM, Cobb-Douglas) dengan kecepatan komputasi Skenario 1 (CP-SAT).
- *Mekanisme*: Melakukan *preprocessing* menggunakan matematika Cobb-Douglas dari Skenario 2 untuk mengestimasi batas durasi dan biaya crashing per hari secara otomatis.
- Parameter hasil preprocessing ($d_i^(min), d_i^(max), C_i$) kemudian dimasukkan langsung ke solver CP-SAT Skenario 1.
- Solver CP-SAT akan menyelesaikan model dalam waktu kurang dari 10 milidetik secara optimal global.

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

Setelah preprocessing, kita selesaikan model penjadwalan linier:
$ min sum_(i in I_0^C) C_i (d_i^(max) - (e_i - s_i)) + c_"late" max(0, s_(n+1) - T_"max") - c_"early" max(0, T_"max" - s_(n+1)) $
dengan batasan linier terpusat:
- *Batasan Waktu & Durasi*:
  $ e_i = s_i + d_i $
  $ d_i^(min) <= e_i - s_i <= d_i^(max) $
- *Precedence*: $s_j >= e_i$
- *Kapasitas*: $sum_i U_(i,k) dot bb(1)\{s_i <= s_j < e_i\} <= U_k^(max)$
- *Batasan Dinamis* terhadap $T_0$.

= Perbandingan & Eksplorasi Awal

== Perbandingan Karakteristik Model

#align(center)[
  #set text(size: 11pt)
  #table(
    columns: (3cm, 4.2cm, 4.2cm, 4.2cm),
    align: (center, left, left, left),
    fill: (col, row) => if row == 0 { luma(240) },
    table.header(
      [*Karakteristik*], [*Model Baseline (Skenario 1)*], [*Model Novel (Skenario 2)*], [*Model Hybrid (Skenario 3)*],
    ),
    [*Input Biaya*], [Eksplisit per hari crashing (\$/hari).], [Endogen dari upah SDM (\$/jam).], [Cobb-Douglas preprocessing + linearisasi crash slope.],
    [*Akselerasi*], [Memotong hari durasi secara langsung.], [Menambah orang ($x$) & jam kerja lembur ($tau$).], [Batas $x_"max"$, $tau_"max"$ pada preprocessing.],
    [*Sifat Efisiensi*], [Efisiensi konstan (biaya linier terhadap crashing).], [Efisiensi menurun (*diminishing returns*).], [Efisiensi Cobb-Douglas didekati linier lokal per tugas.],
    [*Tipe Precedence*], [Finish-to-Start (FS) tanpa lag.], [FS, SS, FF dengan lag/lead.], [Finish-to-Start (FS) tanpa lag.],
    [*Metode Solver*], [OR-Tools CP-SAT (Sangat Cepat).], [MILP (Pyomo) & GA (pymoo) (Sangat Lambat).], [OR-Tools CP-SAT setelah preprocessing (Sangat Cepat).]
  )
]

== Hasil Eksplorasi Awal

- gantt chart side by side model 1
- gantt chart side by side model 2
- gantt chart side by side model 3

= Kesimpulan

== Kesimpulan

1. *Skenario 1*: Berkinerja cepat tetapi tidak realistis di lapangan karena data biaya crashing per hari jarang dimiliki perusahaan.
2. *Skenario 2*: Memodelkan realitas penambahan tenaga kerja dan lembur secara presisi menggunakan Cobb-Douglas, namun memiliki biaya komputasi yang tinggi (NP-hard).
3. *Skenario 3 (Hybrid)*: Menawarkan *solusi jalan tengah terbaik*. Menggunakan preprocessing Cobb-Douglas dari Skenario 2 untuk menghasilkan parameter biaya dan durasi realistis secara otomatis, kemudian menyelesaikannya dalam waktu kurang dari 10 milidetik menggunakan solver CP-SAT Skenario 1.

= Terima Kasih

// #align(center)[
//   #text(size: 32pt, weight: "bold")[Terima Kasih]
// ]