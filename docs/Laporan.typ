// Dynamic RCPSP-TCT Project Crashing — Typst source

#set document(
  title: "Dynamic RC-TCTP Project Crashing",
  author: "K13 Pemodelan Matematika",
  date: datetime(year: 2026, month: 5, day: 8),
)

#set page(
  paper: "us-letter",
  margin: (top: 1in, bottom: 1in, left: 1in, right: 1in),
)

#set text(
  font: "New Computer Modern",
  size: 11pt,
  lang: "id",
)

#set par(justify: true, leading: 0.8em, first-line-indent: 0pt)

#set heading(numbering: "1.1")
#show heading: set block(below: 1em)

#let eq(label-name) = block(
  width: 100%,
  below: 0.8em,
  above: 0.8em,
  {
    box(width: 100%, {
      h(1fr)
      [#context { counter("equation").step() }#context { counter("equation").display() }]
    })
  },
)

#align(center)[
  #text(size: 17pt, weight: "bold")[Dynamic RC-WTCTP Project Crashing]

  #v(0.25em)

  #text(size: 12pt)[K13 Pemodelan Matematika]

  #text(size: 12pt)[May 8, 2026]

  #v(1em)
]

= Pendahuluan

Dalam manajemen proyek modern, penyelesaian proyek tepat waktu dengan biaya minimal merupakan salah satu tantangan utama yang dihadapi oleh manajer proyek. Proyek sering kali menghadapi ketidakpastian, keterbatasan kapasitas sumber daya, dan tekanan tenggat waktu (*deadline*). Untuk mengatasi masalah ini, dikembangkan dua konsep optimisasi penting: *Resource-Constrained Project Scheduling Problem* (RCPSP) dan *Time-Cost Trade-off Problem* (TCTP).

RCPSP berfokus pada penjadwalan aktivitas proyek dengan memperhatikan batasan ketergantungan antar-aktivitas (*precedence constraints*) dan keterbatasan kapasitas sumber daya harian yang tersedia. Di sisi lain, TCTP mengasumsikan bahwa durasi pengerjaan suatu aktivitas dapat dipangkas (*project crashing*) dengan cara mengalokasikan sumber daya tambahan, yang konsekuensinya akan meningkatkan biaya proyek. 

Secara umum, terdapat dua skenario *project crashing* yang dibahas dalam laporan ini:
1. *Skenario Baseline*: Menghadapi masalah *crashing* ketika biaya pemotongan durasi harian (*crash cost per day*) dan batas durasi minimum (*minimum duration*) untuk setiap aktivitas telah diketahui secara eksplisit dan bernilai konstan. Model ini dikembangkan menggunakan paradigma pemrograman batasan (*Constraint Programming*) melalui Google OR-Tools CP-SAT.
2. *Skenario Novel*: Menghadapi masalah *crashing* ketika biaya pemotongan durasi dan batas durasi minimum tidak diketahui secara langsung. Sebaliknya, manajer proyek hanya memiliki tuas kontrol berupa alokasi harian sumber daya manusia, yang dapat dipercepat melalui dua mekanisme: penambahan tenaga kerja (*overcrowding*) dan penambahan jam kerja lembur (*overtime*). Hubungan non-linier antara alokasi sumber daya tambahan dengan durasi aktivitas dimodelkan menggunakan fungsi produksi Cobb-Douglas guna menangkap efek penurunan efisiensi marjinal (*diminishing returns*). Model ini diselesaikan menggunakan pemrograman linier integer campuran (MILP) berbasis diskretisasi serta algoritma genetika (metaheuristik).

Laporan ini menyajikan perumusan model matematika lengkap, penjelasan data, asumsi, justifikasi variabel, serta metode penyelesaian untuk kedua skenario di atas secara terstruktur.

#pagebreak()

= Baseline Model (Skenario 1)

Model baseline ini merumuskan suatu masalah optimisasi berupa *Resource-Constrained Time-Cost Trade-off Problem* (RC-TCTP) dinamis pada proyek dengan durasi diskrit dan biaya pemotongan durasi (*crashing cost*) yang linier.

== Deskripsi Data
Model baseline ini dibangun menggunakan tiga berkas data utama yang saling berkaitan:
1. *Data Aktivitas* (`activity_data_v3.json`): Menentukan daftar aktivitas proyek, durasi normal ($d_i^max$), durasi minimum setelah _crashing_ ($d_i^min$), biaya pemangkasan harian ($C_i$), hubungan ketergantungan antar-aktivitas (_precedence_), serta status pengerjaan tugas saat ini. 
2. *Kapasitas Sumber Daya* (`resource_capacity_v3.json`): Menentukan batas kapasitas harian maksimum ($U_k^max$) untuk setiap jenis sumber daya $k$.
3. *Kebutuhan Sumber Daya* (`resource_requirements_v3.json`): Menentukan kebutuhan harian aktivitas $i$ terhadap sumber daya $k$ (yaitu $U_(i, k)$) ketika aktivitas tersebut sedang aktif berjalan.

Contoh format dan sampel data terintegrasi untuk Skenario 1 dapat dilihat pada tabel di bawah ini:

#align(center)[
  #set text(size: 9pt)
  #table(
    columns: (3cm, 2.5cm, 2cm, 2cm, 2.2cm, 4.3cm),
    align: (left, center, center, center, center, left),
    fill: (col, row) => if row == 0 { luma(240) },
    table.header(
      [*Nama Aktivitas*], [*Precedence*], [*$d_i^min$*], [*$d_i^max$*], [*$C_i$ (USD/hari)*], [*Sumber Daya (Kebutuhan)*]
    ),
    [Bids & Contracts], [-], [7 hari], [10 hari], [\$60.00], [General Management (1), Project Management (1)],
    [Grading & Permits], [Bids & Contracts], [7 hari], [10 hari], [\$70.00], [General Management (1), Survey Crew (1), Grading Contractor (2)],
    [Site Work], [Grading & Permits], [5 hari], [7 hari], [\$30.00], [Labor Crew (3), Grading Contractor (2), Survey Crew (1)]
  )
]

== Asumsi dan Limitasi Model
Formulasi model baseline didasarkan pada beberapa asumsi dan limitasi berikut:
- *Linieritas Biaya Crashing*: Pengurangan durasi suatu aktivitas diasumsikan memiliki biaya tambahan konstan per hari. Total biaya crashing untuk suatu tugas adalah hasil kali dari jumlah hari pemotongan dengan biaya harian.
- *Precedence Finish-to-Start*: Hubungan ketergantungan antar-aktivitas yang didukung hanya tipe *Finish-to-Start* (FS) tanpa adanya *lag/lead* waktu.
- *Non-Preemptive*: Aktivitas yang sedang dikerjakan tidak dapat diinterupsi atau diberhentikan sementara hingga benar-benar selesai.
- *Sunk Cost*: Biaya crashing yang terjadi pada masa lalu (sudah selesai) dianggap sebagai biaya hangus (*sunk cost*) dan diabaikan dari fungsi tujuan optimisasi aktif.

== Notasi
#align(center)[
  #table(
    columns: (auto, auto, auto),
    align: (center, center, left),
    fill: (col, row) => if row == 0 { luma(240) },
    table.header(
      [*Variabel*], [*Satuan*], [*Deskripsi*],
    ),
    
    // Sets
    table.cell(colspan: 3, align: center, fill: luma(250))[*Himpunan*],
    [$I$], [-], [Aktivitas, di-indeks oleh $i$],
    [$I_0$], [-], [Aktivitas sehingga $e_i <= T_0$ (sudah selesai)],
    [$I_1$], [-], [Aktivitas sehingga $s_i >= T_0$ (belum mulai)],
    [$E$], [-], [Ketergantungan antara aktivitas, di-indeks oleh $(i, j)$],
    [$K$], [-], [Sumber daya, di-indeks oleh $k$],
    
    // Parameters
    table.cell(colspan: 3, align: center, fill: luma(250))[*Parameter*],
    [$s_i^(\(0\))$], [hari], [Hari mulai aktual (sebelum _crashing_) aktivitas $i$],
    [$e_i^(\(0\))$], [hari], [Hari akhir aktual (sebelum _crashing_) aktivitas $i$],
    [$d_i^((max))$], [hari], [Durasi normal aktivitas $i$],
    [$d_i^((min))$], [hari], [Durasi minimum aktivitas $i$],
    [$C_i$], [Rp/hari], [Harga harian untuk _crash_ aktivitas $i$],
    [$U_(i,k)$], [Rp/hari], [Keperluan harian sumber daya $k$ untuk aktivitas $i$],
    [$U_k^((max))$], [Rp/hari], [Kapasitas harian sumber daya $k$],
    [$T_("max")$], [hari], [Hari tenggat projek (_deadline_)],
    [$T_0$], [hari], [Hari mulai _crashing_ projek],
    [$B$], [hari], [Anggaran total untuk _crashing_],
    
    // Decision Variables
    table.cell(colspan: 3, align: center, fill: luma(250))[*Variabel Keputusan*],
    [$s_i$], [hari], [Hari mulai aktivitas $i$],
    [$e_i$], [hari], [Hari akhir aktivitas $i$],
  )
]

== Formulasi Batasan (Constraints)

=== Batasan Durasi
Pertama, perhatikan bahwa $d_i := e_i - s_i$ menyatakan jumlah hari yang di-_crash_. Karena _crashing_ adalah tindakan terbatas (tidak mungkin membuat aktivitas selesai secara instan), diperlukan batasan untuk $d_i$, yakni:

$ d_i^(min) <= e_i - s_i <= d_i^(max) & quad forall i in I. $

Jadi, durasi pengerjaan suatu aktivitas harus lebih dari _minimum task duration_ dan setidaknya selama _normal task duration_. 

=== Batasan Ketergantungan 

Dalam manajemen, projek dapat digambarkan sebagai jaringan projek $(I,E)$ dengan $I$ adalah semua aktivitas dan $E$ adalah ketergantungan (_dependencies_) antara aktivitas. Terdapat empat jenis ketergantungan: _finish-to-start_ (FS), _finish-to-finish_ (FF), _start-to-start_ (SS), dan _start-to-finish_ (SF). Berdasarkan data kami peroleh, kami fokuskan diri hanya pada jenis ketergantungan _finish-to-start_ (FS) yang paling sederhana. Ini menghasilkan batasan

$ s_i &>= e_j & quad forall (i,j) in E. $

Maka, sebuah aktivitas hanya bisa dimulai setelah semua aktivitas pendahulunya (berdasarkan jaringan projek yang diberikan) selesai. 

=== Batasan Sumber Daya 

Dalam masalah _resource-constrained_ (di _project-scheduling_ atau _time-cost tradeoff_), suatu sumber daya tidak bisa digunakan semena-mena. Pada tiap waktu pelaksanaan, jumlah suatu sumber daya tertentu yang digunakan tidak boleh melebihi kapasitas yang tersedia:

$ sum_(i in I) U_(i,k) dot bb(1) \{ s_i <= s_j < e_i \} <= U_k^(max), quad forall k in K, forall j in I $

Secara matematis, pengecekan cukup dilakukan di setiap awal aktivitas (tidak perlu setiap satuan waktu) untuk menghemat komputasi. _Di OR-Tools, implementasi mudah hanya dengan variabel interval CP-SAT dan fungsi pembantu `AddCumulative`._ 

=== Batasan Dinamis 

Berikutnya, khususnya untuk _project crashing_ (bukan TCTP secara umum), diperlukan batasan untuk aktivitas-aktivitas yang akan di-_crash_. Untuk aktivitas yang belum dilaksanakan:

$ s_i >= T_0, quad forall i in I_1. $

Untuk aktivitas yang sedang dilaksanakan:

#align(center)[
  #grid(
    columns: 2,
    align: (center, horizon), 
    $ s_i &= s_i^(\(0\)), \
      e_i &>= T_0, $,
    $ quad forall i in I_0^C inter I_1^C. $
  )
]

Untuk aktivitas yang sudah selesai: 

#align(center)[
  #grid(
    columns: 2,
    align: (center, horizon), 
    $ s_i &= s_i^(\(0\)), \
      e_i &= e_i^(\(0\)), $,
    $ quad forall i in I_0. $
  )
]

== Formulasi Objektif

=== _Cost-Driven_
Di sini, difokuskan aspek _cost_ dari TCTP, sehingga ingin meminimumkan biaya total:

$ min sum_(i in I_0^C) C_i (d_i^(max) - (e_i - s_i)). $

Jadi, diperlukan batasan keras agar tenggat terpenuhi:

$ s_(n+1) <= T_max. $

=== _Time-Driven_
Di sini, difoksukan aspek _time_ dari TCTP, sehingga ingin meminimumkan waktu pengerjaan: 

$ min s_(n+1). $

Ini menjadi mirip dengan masalah RCPSP biasa. Jadi, diperlukan batasan anggaran saja:

$ sum_(i in I) C_i (d_i^max - (e_i - s_i)) <= B. $

=== Multi-Objektif
Di sini, kita gabungkan kedua perspektif di atas untuk menghasilkan masalah multi-objektif yang sesuai untuk TCTP: 

$ min (s_(n+1), sum_(i in I_0^C) C_i (d_i^(max) - (e_i - s_i))). $

=== _Bonus-Penalty Driven_
Pemodelan _time-cost tradeoff_ tidak perlu dengan pendekatan multi-objektif seperti di atas. Penggabungannya bisa mempertahankan fungsi objektif tunggal dengan menggunakan metrik penalti harian $c_"late"$ dan bonus harian $c_"early"$. Ini menghasilkan fungsi objektif berikut:

$ min sum_(i in I_0^C) C_i (d_i^max - (e_i - s_i)) + c_"late" max(0, s_(n+1) - T_"max") - c_"early" max(0, T_"max" - s_(n+1)). $

== Metode Penyelesaian
Model baseline diselesaikan menggunakan *Google OR-Tools CP-SAT Solver*. CP-SAT dipilih karena menyediakan variabel interval (`IntervalVar`) secara native yang mempermudah representasi durasi tugas dan memiliki algoritma propagasi batasan kumulatif (`AddCumulative`) yang sangat efisien untuk memecahkan masalah penjadwalan dengan batasan sumber daya berkapasitas terbatas.

*Integer Scaling*: Karena solver CP-SAT hanya menerima nilai koefisien berupa bilangan bulat (integer), parameter biaya crashing riil ($c c_a$) yang berbentuk desimal dikalikan dengan faktor skala $S = 10^{"max_dp"}$ (di mana $"max_dp"$ adalah presisi desimal maksimum dari data biaya). Koefisien tujuan ter-skala dihitung dengan $"coeff"_a =  floor.l  c c_a dot S  floor.r $. Setelah diperoleh solusi optimal, total biaya riil diperoleh dengan membagi kembali nilai objektif solver dengan $S$.

#pagebreak()

= Novel Model (Skenario 2)

Di sini, kami memformulasikan model TCTP baru. Secara khusus, dibuat model RC-WTCTP berbasis *workforce* (bukan durasi seperti CTCP atau mode seperti DTCTP) dengan fungsi biaya *endogenous* (tidak *exogenous* seperti pada TCTP umumnya) yang diturunkan dari model utilitas Cobb-Douglas.

== Deskripsi Data
Model ini menggunakan berkas data sebagai berikut: 
1.  *Data Aktivitas* (`task_table.json`): Berisi daftar seluruh aktivitas ($I$), level outline, durasi baseline, tanggal mulai dan selesai, serta dependensi (_precedence_) dengan nilai *lag/lead*-nya.
2.  *Data Sumber Daya* (`resource_table.json`): Berisi daftar jenis tenaga kerja ($K$), kapasitas maksimal harian ($U_k^max$ dalam persen), dan tarif upah standar per jam ($r_k$). 
3.  *Data Alokasi Tugas* (`assignment_table.json`): Menghubungkan aktivitas dengan tenaga kerja yang ditugaskan ($K_i$), mencakup usaha kerja baseline ($W_(i,k)$ dalam jam) dan persentase alokasi harian baseline ($U_(i,k)$).

Contoh format dan sampel data terintegrasi untuk Skenario 2 ditunjukkan pada tabel-tabel di bawah ini:

#align(center)[
  #grid(
    columns: 1,
    gutter: 1.2em,
    [
      #set text(size: 8.5pt)
      #table(
        columns: (1cm, 6.2cm, 2.5cm, 2.2cm, 2.6cm),
        align: (center, left, center, center, center),
        fill: (col, row) => if row == 0 { luma(240) },
        table.header(
          [*ID*], [*Nama Aktivitas (`task_table`)*], [*Durasi Baseline*], [*Outline Level*], [*Predecessors*]
        ),
        [2], [Receive notice to proceed and sign contract], [3 hari], [2], [-],
        [3], [Submit bond and insurance documents], [2 hari], [2], [2FS],
        [4], [Prepare and submit project schedule], [4 hari], [2], [3FS]
      )
    ],
    [
      #set text(size: 8.5pt)
      #table(
        columns: (1cm, 5.5cm, 3.5cm, 4.5cm),
        align: (center, left, center, center),
        fill: (col, row) => if row == 0 { luma(240) },
        table.header(
          [*ID*], [*Nama Sumber Daya (`resource_table`)*], [*Max Units (Kapasitas)*], [*Standard Rate (Tarif)*]
        ),
        [1], [G.C. General Management], [100% (1 orang)], [\$120.00/jam],
        [2], [G.C. Project Management], [100% (1 orang)], [\$95.00/jam],
        [6], [G.C. Labor Crew], [300% (3 orang)], [\$35.00/jam]
      )
    ],
    [
      #set text(size: 8.5pt)
      #table(
        columns: (5.2cm, 5.2cm, 2.3cm, 2.3cm),
        align: (left, left, center, center),
        fill: (col, row) => if row == 0 { luma(240) },
        table.header(
          [*Nama Aktivitas (`assignment_table`)*], [*Nama Sumber Daya*], [*Work (Usaha)*], [*Units (Alokasi)*]
        ),
        [Submit bond and insurance documents], [G.C. Project Management], [16 jam], [100%],
        [Submit bond and insurance documents], [G.C. General Management], [4 jam], [25%],
        [Prepare and submit project schedule], [G.C. Scheduler], [16 jam], [100%]
      )
    ]
  )
]

== Asumsi dan Limitasi Model
Formulasi model Cobb-Douglas didasarkan pada beberapa asumsi realistis berikut:
- *Diminishing Returns*: Menambah jumlah pekerja pada suatu aktivitas (*overcrowding*) atau memperpanjang jam kerja (*overtime*) akan mempercepat pengerjaan aktivitas, namun dengan efisiensi marjinal yang menurun. Hal ini dimodelkan dengan eksponen elastisitas $alpha, beta in (0, 1)$ pada fungsi Cobb-Douglas.
- *Koordinasi dan Kelelahan*: Overcrowding menyebabkan hilangnya efisiensi karena peningkatan beban koordinasi antar-pekerja. Overtime menurunkan produktivitas pekerja karena kelelahan (*fatigue*).
- *Tarif Lembur Lebih Tinggi*: Jam kerja lembur ($tau$) dikenakan tarif upah yang lebih tinggi daripada jam reguler (dikali multiplier upah lembur $r'_k = "ot_mult" dot r_k$).
- *Non-Preemptive*: Pengerjaan tugas bersifat kontinu dari hari mulai hingga selesai (non-preemptive).

== Notasi
#align(center)[
  #table(
    columns: (auto, auto, auto),
    align: (center, center, left),
    fill: (col, row) => if row == 0 { luma(240) },
    table.header(
      [*Variabel*], [*Satuan*], [*Deskripsi*],
    ),
    
    // Sets
    table.cell(colspan: 3, align: center, fill: luma(250))[*Himpunan*],
    [$I$], [-], [Himpunan semua aktivitas],
    [$I_0$], [-], [Aktivitas sehingga $e_i <= T_0$ (sudah selesai)],
    [$I_1$], [-], [Aktivitas sehingga $s_i >= T_0$ (belum mulai)],
    [$E_"FS", E_"SS", E_"FF"$], [-], [Relasi ketergantungan _finish-to-start_, _start-to-start_, dan _finish-to-finish_],
    [$K$], [-], [Sumber daya, di-indeks oleh $k$],
    
    // Parameters
    table.cell(colspan: 3, align: center, fill: luma(250))[*Parameter*],
    [$W_(i,k)$], [jam], [Usaha kerja baseline SDM $k$ untuk aktivitas $i$],
    [$U_(i,k)$], [-], [Alokasi harian baseline SDM $k$ untuk aktivitas $i$ (proporsi dari 8 jam)],
    [$C_k$], [unit], [Kapasitas SDM $k$ yang tersedia per hari],
    [$r_k$], [Rp/jam], [Tarif reguler SDM $k$],
    [$r'_k$], [Rp/jam], [Tarif lembur SDM $k$, dengan $r'_k >= r_k$],
    [$alpha$], [-], [Eksponen Cobb–Douglas untuk overcrowding ($0 < alpha < 1$)],
    [$beta$], [-], [Eksponen Cobb–Douglas untuk overtime ($0 < beta < 1$)],
    [$c_"late"$], [Rp/hari], [Penalti keterlambatan],
    [$c_"early"$], [Rp/hari], [Bonus penyelesaian awal],
    [$c_"ind"$], [Rp/hari], [Biaya overhead proyek tidak langsung harian],
    [$delta_(i j)$], [hari], [Lag/lead antara aktivitas $i$ dan $j$],
    [$T_0$], [hari], [Hari saat ini peninjauan proyek],
    
    // Decision Variables
    table.cell(colspan: 3, align: center, fill: luma(250))[*Variabel Keputusan*],
    [$x_(i,k)$], [-], [Pengali overcrowding SDM $k$ untuk aktivitas $i  in  V_2$],
    [$tau_(i,k)$], [jam/hari], [Lama overtime harian SDM $k$ untuk aktivitas $i  in  V_2$],
    [$s_i$], [hari], [Hari mulai aktivitas $i$],
  )
]

== Formulasi Model

=== Motivasi
Berdasarkan data penjadwalan _baseline_, durasi normal aktivitas $i$ dapat dihitung dari kebutuhan kerja per tugas sebagai

$ d_i^(\(0\)) = max_(k in K_i) W_(i,k) / (8 U_(i,k)), $

sedangkan biaya _baseline_ untuk tenaga kerja $k$ pada tugas $i$ adalah 

$ z_(i,k)^(\(0\)) = W_(i,k) r_k. $

Dari rumus di atas, terlihat bahwa kita bisa mensimulasikan _crashing_ dengan mengubah nilai durasi kerja harian $8$ dan usaha kerja $U_(i,k)$. Jadi, kita bisa mememperkenalkan suatu variabel pengali *tenaga kerja* $x_(i,k)$ dan variabel aditif *jam lembur* $tau_(i,k)$. Jika kita mengimplementasikan variabel _crashing_ ini secara naif dengan langsung menggabungkannya di rumus durasi aktivitas $i$ untuk SDM $k$, akan diperoleh

$ d_(i,k)^' = W_(i,k) / ((8 + tau_(i,k))(x_(i,k) U_(i,k))). $

Namun, perhatikan bahwa  rumusan naif ini mengakibatkan total biaya sumber daya tidak berbeda dari _baseline_:

$ z_(i,k) = d_(i,k)^' dot x_(i,k) U_(i,k) dot (8 + tau_(i,k)) dot r_(i,k) = W_(i,k) r_(i,k) = z_(i,k)^(\(0\)). $

=== Cobb-Douglas

Di dunia sempurna, ini mungkin benar: menggandakan jumlah pekerja akan memaruhkan durasi kerja, sehingga biaya total akan sama. Tetapi secara realistis, ini tentu tidak masuk akal, sebab terdapat _inefficiency_ yang mengakibatkan Untuk mengatasi ini, diperkenalkan *fungsi produksi Cobb-Douglas* untuk memodelkan fenomena _diminishing returns_, yang berbunyi: 

$ Y(L,K) = A L^alpha K^beta $

dengan $Y$ adalah output produksi total, $L$ adalah input tenaga kerja (_labor_), dan $K$ adalah input modal (_capital_). Lalu, $A$ adalah faktor produktivitas total, $alpha in (0,1)$ menyatakan elastisitas tenaga kerja, dan $beta in (0,1)$ menyatakan elastisitas modal. Di kasus _project crashing_, kita punya bahwa jumlah sumber daya $x_(i,k) U_(i,k)$ mewakili tenaga kerja $L$ dan durasi total kerja $8 + tau_(i,k)$ mewakili modal $K$. Jadi, kita bisa menggantikan rumus durasi aktivitas $i$ untuk SDM $k$ setelah _crashing_ menjadi 

$ d_(i,k) (x_(i,k), tau_(i,k)) = W_(i,k) / (A_(i,k) (x_(i,k) U_(i,k))^alpha (8 + tau_(i,k))^beta). $

Sekarang, dengan memilih konstanta $A_(i,k) = U_(i,k)^(1-alpha) 8^(1-beta)$ sehingga durasi baru bernilai sama dengan _baseline_ ketika $x_(i,k)=1$ and $tau_(i,k)=0$, maka durasi yang sudah di-_crash_ dapat disederhanakan menjadi

$ 
d_(i,k) (x_(i,k), tau_(i,k)) = 
underbrace(W_(i,k) / (8 U_(i,k)), "baseline") dot
underbrace((1 / x_(i,k))^alpha, "overwork") dot 
underbrace((8 / (8 + tau_(i,k)))^beta, "overtime").
$

sehingga durasi aktivitas $i$ saja menjadi

$ d_i = max_(k in K_i) d_(i,k) (x_(i,k), tau_(i,k)) $

Dengan ini, ingat kembali bahwa durasi pengerjaan, usaha harian, dan biaya harian sudah berubah. 

1. Durasi "efektif" pengerjaan aktivitas $i$ oleh SDM $k$ berubah menjadi $d_(i,k)^* (x_(i,k), tau_(i,k))$. 
2. Total usaha SDM $k$ pada aktivitas $i$ adalah $x_(i,k) U_(i,k)$. 
3. Biaya harian mencakup upah reguler (8 jam dengan tarif $r_k$) dan upah lembur ($tau_(i,k)$ jam dengan tarif lembur $r'_k$), sehingga gaji totalnya adalah $8 r_k + tau_(i,k) r'_k$. 

Dengan mengalikan ketiga suku tersebut, diperoleh total biaya $z_(i,k)(x_(i,k), tau_(i,k))$ baru untuk SDM $k$ pada aktivitas $i$ adalah

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

Persamaan biaya ini secara elegan memodelkan *diminishing returns*: karena $1-alpha, 1 - beta < 1$, peningkatan _overcrowding_ ($x_(i,k) > 1$) maupun _overtime_ ($tau_(i,k) > 0$) akan menghasilkan total biaya yang lebih tinggi daripada _baseline_, menyelesaikan masalah yang kita miliki sebelumnya.

=== Estimasi Parameter

$alpha$ : digitalcommons.unl.edu/cgi/viewcontent.cgi?article=1012&context=constructiondiss 

$beta$ : www.long-intl.com/articles/loss-of-labor-productivity/

=== Contoh
Perhatikan ilustrasi tugas di bawah ini:

#align(center)[
  #image("img/Contoh Crashing 1.png", width: 90%)
]

Secara normal, pengerjaan tugas ini membutuhkan *Roofing Contractor Management* untuk bekerja 8 jam per hari selama 10 hari (total 80 jam kerja _baseline_).
1. *Mekanisme Overtime*: Jika pekerja diminta untuk lembur $tau = 1$ jam per hari (total 9 jam kerja per hari), dengan efek kelelahan $beta = 0.3$, durasi efektifnya menjadi $d = 10 dot (8/9)^0.3 approx 9.6$ hari. Upah jam lembur dihitung dengan tarif $r'_k$ lebih tinggi.
2. *Mekanisme Overcrowding*: Jika kita menambah satu pekerja lagi ($x = 2.0$) dengan efek koordinasi $alpha = 0.6$, durasi baru menjadi $d' = 10 dot 1/(2^0.6) approx 6.6$ hari. Jumlah hari-pekerja meningkat menjadi $6.6 dot 2 = 13.2$ hari-orang, yang berarti biaya labor total naik sebesar $2^(1-0.6) = 2^0.4 approx 1.32$ kali biaya baseline.

== Formulasi Batasan 


Pertama, berdasarkan hasil yang diperoleh di Bagian 3.4, diiulang definisi durasi efektif oleh SDM $k$ pada aktivitas $i$ adalah

$ d_(i,k) (x_(i,k), tau_(i,k)) := W_(i,k) / (8 U_(i,k)) dot (1 / x_(i,k))^alpha dot (8 / (8 + tau_(i,k)))^beta, $

sedangkan biaya efektif untuk aktivitas $i$ dan SDM $k$ adalah

$ 
z_(i,k) (x_(i,k), tau_(i,k)) =
W_(i,k) r_k dot 
x_(i,k)^(1-alpha) dot 
((8 + tau_(i,k)) / 8)^(1-beta) dot 
(8 + r'_k / r_k tau_(i,k)) / (8 + tau_(i,k)). 
$

Serupa, didefinisikan hari akhir suatu aktivitas $i$ sebagai: 

$ e_i := s_i + max_(k in K) d_(i,k)(x_(i,k),tau_(i,k)). $

Ketiga variabel di atas ini *bukan* variabel keputusan, melainkan hanya variabel pembantu untuk kami formulasikan model di bagian-bagian berikut dengan lebih mudah. Cukup mensubstitusikan dua ekspresi di atas setiap ada munculnya $d_(i,k)$, $z_(i,k)$, atau $e_i$ di seluruh rumusan berikutnya untuk menghilangkan mereka. 

=== Batasan Ketergantungan 
Di sini, model akan diperumum untuk mendukung tiga jenis ketergantungan: _finish-to-start_ (FS), _finish-to-finish_ (FF), dan _start-to-start_ (SS). Ini menghasilkan batasan berikut:

$ 
  s_j >= e_i + delta_(i j), quad forall (i,j) in E_"FS", \
  s_j >= s_i + delta_(i j), quad forall (i,j) in E_"SS", \
  e_j >= e_i + delta_(i j), quad forall (i,j) in E_"FF". 
$

Serupa, ketergantungan _start-to-finish_ bisa ditambahkan jika perlu pada data. 

=== Batasan Sumber Daya

Seperti di Bagian 2, sifat _resource-constrained_ dari RC-TCTP diberikan oleh batasan sumber daya. Untuk model ini, diformulasikan batasannya sebagai berikut:

$ sum_(i in I) U_(i,k) dot bb(1) \{ s_i <= s_j < s_i + d_(i,k) \} <= U_k^(max), quad forall k in K, forall j in I $

Sekali lagi, pengecekan cukup dilakukan di setiap awal aktivitas (tidak perlu setiap satuan waktu) untuk menghemat komputasi. Tetapi selebihnya, perhatikan bahwa di sini batas atas adalah $s_i + d_(i,k)$, bukan $e_i$. Perbedaan ini berarti bahwa keputusan alokasi sumber daya bukan dilakukan pada level aktivitas, melainkan pada level sumber daya-nya sendiri. Jadi, suatu sumber daya bisa memutuskan untuk berpindah ke aktivitas lain jika sudah selesai dengan tugas mereka di aktivitas sekarang. 

=== Batasan Dinamis 

Terakhir, diperlukan batasan untuk aktivitas-aktivitas yang akan atau tidak akan di-_crash_. Untuk aktivitas yang belum dilaksanakan:

$ s_i >= T_0, quad forall i in I_1, $

dan perhitungan waktu kerja total menggunakan yang orisinal: 

$ W_(i,k) = W_(i,k)^(\(0\)), quad forall i in I_1. $

Untuk aktivitas yang sedang dilaksanakan, kita menghitung suatu rasio $p_(i,k)$ yaitu bagian dari durasi _baseline_ yang sudah dikerjakan. Dengan itu, kita definisikan waktu kerja total efektifnya adalah

$ W_(i,k) = W_(i,k)^(\(0\))(1 - p_(i,k)), quad forall i in I_0^C inter I_1^C. $

Selain itu, diperlukan seperti biasa

$ s_i &= s_i^(\(0\)), quad forall i in I_0^C inter I_1^C. $

Untuk aktivitas yang sudah selesai: 

#align(center)[
  #grid(
    columns: 2,
    align: (center, horizon), 
    $ s_i &= s_i^(\(0\)), \
      x_(i,k) &= 1, \
      tau_(i,k) &= 0, $,
    $ quad forall i in I_0, $
  )
]

dan perhitungan waktu kerja total menggunakan yang orisinal: 

$ W_(i,k) = W_(i,k)^(\(0\)), quad forall i in I_0. $

== Formulasi Objektif 

=== _Cost-Driven_
Di sini, difokuskan aspek _cost_ dari TCTP, sehingga ingin meminimumkan biaya total:

$ min sum_(i in I_0^C) sum_(k in K) z_(i,k)(x_(i,k), tau_(i,k)). $

Jadi, diperlukan batasan keras agar tenggat terpenuhi:

$ s_(n+1) <= T_max. $

=== _Time-Driven_
Di sini, difoksukan aspek _time_ dari TCTP, sehingga ingin meminimumkan waktu pengerjaan: 

$ min s_(n+1). $

Ini menjadi mirip dengan masalah RCPSP biasa. Jadi, diperlukan batasan anggaran saja:

$ sum_(i in I) sum_(k in K) z_(i,k)(x_(i,k), tau_(i,k)) <= B. $

=== Multi-Objektif
Di sini, kita gabungkan kedua perspektif di atas untuk menghasilkan masalah multi-objektif yang sesuai untuk TCTP: 

$ min (s_(n+1), sum_(i in I_0^C) sum_(k in K) z_(i,k)(x_(i,k), tau_(i,k))). $

=== _Bonus-Penalty Driven_
Pemodelan _time-cost tradeoff_ tidak perlu dengan pendekatan multi-objektif seperti di atas. Penggabungannya bisa mempertahankan fungsi objektif tunggal dengan menggunakan metrik penalti harian $c_"late"$ dan bonus harian $c_"early"$. Ini menghasilkan fungsi objektif berikut:

$ min sum_(i in I_0^C) sum_(k in K) z_(i,k)(x_(i,k), tau_(i,k)) + c_"late" max(0, s_(n+1) - T_"max") - c_"early" max(0, T_"max" - s_(n+1)). $


== Metode Penyelesaian Skenario 2

Model Cobb-Douglas asli merupakan model *MINLP (Mixed-Integer Non-Linear Programming)* yang non-konveks karena persamaan durasi dan biaya mengandung eksponen pecahan. Untuk menyelesaikan model ini secara efisien dan andal, digunakan dua pendekatan:

=== MILP berbasis Diskretisasi Grid
Metode ini mendiskretkan ruang pencarian kontinu pengali overcrowding $x_(i,k)$ dan overtime harian $tau_(i,k)$ menjadi beberapa titik grid tertentu:
-   $x_g in \{1.0, 1.25, 1.5, 1.75, 2.0\}$
-   $tau_g in \{0.0, 1.0, 2.0, 3.0, 4.0\}$

Definisikan variabel keputusan biner baru $xi_(i,k)^(m,n) in \{0, 1\}$ yang bernilai 1 jika SDM $k$ pada tugas $i$ memilih titik grid overcrowding ke-$m$ dan overtime ke-$n$.
Dengan diskretisasi ini, nilai durasi $d_{i,m,n}$ dan biaya harian labor $"cost"_(i,m,n)$ untuk masing-masing kombinasi grid dihitung terlebih dahulu sebelum optimisasi (*precomputed*). Seluruh konstrain durasi dan biaya menjadi fungsi linier terhadap variabel biner $xi_(i,k)^(m,n)$:
$ d_i = sum_(m) sum_(n) xi_(i,k)^(m,n) dot d_{i,m,n}. $
Model ini kemudian dimodelkan menggunakan *Pyomo* dan diselesaikan menggunakan solver MILP komersial/open-source seperti *CBC* atau *HiGHS* hingga mencapai jaminan solusi optimal global dalam hitungan detik.

=== Pendekatan Metaheuristik (Genetic Algorithm)
Sebagai alternatif pembanding untuk ruang pencarian kontinu tanpa diskretisasi, diimplementasikan algoritma genetika (GA) menggunakan pustaka *`pymoo`* di Python:
-   *Representasi Kromosom*: Variabel keputusan $(x, tau)$ dikodekan langsung sebagai vektor bilangan real.
-   *Fungsi Penalti*: Karena GA sulit menangani batasan secara langsung, kendala precedence dan kapasitas sumber daya ditambahkan sebagai penalti kuadratis ke dalam fungsi objektif jika terjadi pelanggaran (*precedence violation penalty*).
-   *Operator Genetika*: Menggunakan operator seleksi turnamen, persilangan SBX (_Simulated Binary Crossover_), dan mutasi PM (_Polynomial Mutation_).

Meskipun metode GA dapat menangani fungsi Cobb-Douglas asli tanpa diskretisasi, ia tidak memberikan jaminan optimalitas global dan membutuhkan waktu komputasi yang lebih lama untuk konvergensi dibandingkan dengan pendekatan MILP diskret.

#pagebreak()
= Hybrid Model (Skenario 3)

== Deskripsi Data
Model Hybrid menggunakan struktur data yang sama dengan Skenario 2, yakni data aktivitas (`task_table.json`), data sumber daya (`resource_table.json`), dan alokasi tugas (`assignment_table.json`). Pengguna tidak perlu menyediakan estimasi biaya pemotongan harian ($C_i$) secara langsung, karena parameter tersebut akan dihitung secara endogen dari data internal organisasi.

== Asumsi dan Limitasi Model
Formulasi model hybrid didasarkan pada beberapa asumsi berikut:
- *Linearisasi Lokal*: Hubungan non-linier antara alokasi sumber daya dengan durasi proyek didekati secara linier melalui perhitungan *crash slope* lokal antara kondisi baseline dengan kondisi akselerasi maksimal.
- *Batas Kendali Maksimal*: Ditentukan batas overcrowding maksimum ($x_"max" = 2.0$) dan batas overtime harian maksimum ($tau_"max" = 2.0$ jam/hari) sebagai kondisi batas percepatan proyek yang realistis.
- *Sunk Cost*: Biaya masa lalu diabaikan dalam optimisasi dinamis.

== Langkah Preprocessing Data
Untuk menjembatani realisme data Skenario 2 dengan kecepatan komputasi Skenario 1, dilakukan preprocessing menggunakan fungsi Cobb-Douglas untuk setiap aktivitas $i$ dan jenis SDM $k in K_i$:

1. *Durasi Normal ($d_i^((max))$)*:
   $ d_i^((max)) = max_(k in K_i) ceil.l W_(i,k) / (8 U_(i,k)) ceil.r $

2. *Biaya Normal ($Z_i^("base")$)*:
   $ Z_i^("base") = sum_(k in K_i) W_(i,k) dot r_k $

3. *Durasi Minimum ($d_i^((min))$)*:
   $ d_i^((min)) = max_(k in K_i) ceil.l W_(i,k) / (8 U_(i,k)) dot (1 / x_"max")^alpha dot (8 / (8 + tau_"max"))^beta ceil.r $

4. *Biaya Crashing Maksimum ($Z_i^("crash")$)*:
   $ Z_i^("crash") = sum_(k in K_i) z_(i,k)(x_"max", tau_"max") $
   dengan:
   $ z_(i,k)(x_"max", tau_"max") = W_(i,k) r_k dot x_"max"^(1-alpha) dot ((8 + tau_"max") / 8)^(1-beta) dot (8 + r'_k / r_k tau_"max") / (8 + tau_"max") $

5. *Crash Slope ($C_i$)*:
   $ C_i = cases(
     (Z_i^("crash") - Z_i^("base")) / (d_i^((max)) - d_i^((min))) & "jika" d_i^((max)) > d_i^((min)),
     0 & "jika" d_i^((max)) = d_i^((min))
   ) $

== Integrasi ke CP-SAT Solver
Nilai $d_i^((max))$, $d_i^((min))$, dan $C_i$ yang dihitung pada tahap preprocessing digunakan langsung sebagai parameter input untuk model penjadwalan CP-SAT. Model ini meminimalkan biaya crashing total:

$ min sum_(i in I_0^C) C_i (d_i^((max)) - (e_i - s_i)) + c_"late" max(0, s_(n+1) - T_"max") - c_"early" max(0, T_"max" - s_(n+1)) $

dengan batasan-batasan sebagai berikut:

- *Batasan Waktu*:
  $ e_i = s_i + d_i, quad forall i in I $

- *Batasan Durasi*:
  $ d_i^((min)) <= e_i - s_i <= d_i^((max)), quad forall i in I $

- *Batasan Precedence*:
  $ s_i >= e_j, quad forall (i,j) in E $

- *Batasan Kapasitas Sumber Daya*:
  $ sum_(i in I) U_(i,k) dot bb(1) \{ s_i <= s_j < e_i \} <= U_k^((max)), quad forall k in K, forall j in I $

- *Batasan Dinamis*:
  Untuk aktivitas yang belum dilaksanakan:
  $ s_i >= T_0, quad forall i in I_1. $
  Untuk aktivitas yang sedang dilaksanakan:
  #align(center)[
    #grid(
      columns: 2,
      align: (center, horizon), 
      $ s_i &= s_i^(\(0\)), \
        e_i &>= T_0, $,
      $ quad forall i in I_0^C inter I_1^C. $
    )
  ]
  Untuk aktivitas yang sudah selesai: 
  #align(center)[
    #grid(
      columns: 2,
      align: (center, horizon), 
      $ s_i &= s_i^(\(0\)), \
        e_i &= e_i^(\(0\)), $,
      $ quad forall i in I_0. $
    )
  ]

Karena seluruh konstrain dan fungsi tujuan di atas bersifat linier, model ini dapat diselesaikan oleh CP-SAT secara optimal global dalam hitungan milidetik.

#pagebreak()

= Kesimpulan dan Perbandingan Model

#align(center)[
  #table(
    columns: (3cm, 4.2cm, 4.2cm, 4.2cm),
    align: (center, left, left, left),
    fill: (col, row) => if row == 0 { luma(240) },
    table.header(
      [*Karakteristik*], [*Model Baseline (Skenario 1)*], [*Model Novel (Skenario 2)*], [*Model Hybrid (Skenario 3)*],
    ),
    [*Input Biaya*], [Eksplisit diketahui per hari crashing per tugas (\$/hari).], [Ditentukan secara endogen dari tarif reguler/lembur SDM (\$/jam).], [Dihitung secara endogen melalui preprocessing Cobb-Douglas, lalu di-linearisasi per tugas.],
    [*Tuas Akselerasi*], [Langsung memotong hari durasi tugas.], [Menambah pekerja (*overcrowding*) & menambah jam kerja lembur (*overtime*).], [Menggunakan batas $x_"max"$ dan $tau_"max"$ pada preprocessing untuk memotong durasi.],
    [*Sifat Efisiensi*], [Efisiensi konstan (biaya linier terhadap waktu pemangkasan).], [Efisiensi menurun (*diminishing returns*) akibat koordinasi & kelelahan.], [Efisiensi non-linier didekati dengan linearisasi lokal (*crash slope*) per tugas.],
    [*Tipe Precedence*], [Finish-to-Start (FS) sederhana tanpa lag.], [Finish-to-Start (FS), Start-to-Start (SS), Finish-to-Finish (FF) dengan lag.], [Finish-to-Start (FS) sederhana tanpa lag.],
    [*Metode Solver*], [Constraint Programming (OR-Tools CP-SAT).], [MILP (Pyomo + CBC) via Diskretisasi Grid & Metaheuristik (pymoo GA).], [Constraint Programming (OR-Tools CP-SAT) setelah preprocessing.],
  )
]

Secara ringkas, jika manajer proyek memiliki estimasi biaya crashing langsung dan mengabaikan efek kelelahan kerja, *Model Baseline* adalah pilihan tercepat. Untuk alokasi proyek taktis yang memperhatikan kelelahan pekerja secara dinamis dan memiliki hubungan precedence kompleks, *Model Novel Cobb-Douglas* memberikan presisi yang tinggi. Namun, jika manajer proyek menginginkan solusi yang realistis berbasis data perusahaan tetapi membutuhkan kecepatan komputasi yang sangat tinggi (milidetik) dengan jaminan solusi optimal global, *Model Hybrid* menawarkan solusi jalan tengah terbaik dengan memadukan keunggulan preprocessing Cobb-Douglas dan efisiensi solver CP-SAT.