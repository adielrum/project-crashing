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

Model baseline ini merumuskan masalah *Resource-Constrained Time-Cost Trade-off Problem* (RC-TCTP) dinamis pada proyek dengan durasi diskrit dan biaya pemotongan durasi (*crashing cost*) yang linier.

== Deskripsi Data yang Dimiliki
Model baseline ini dibangun menggunakan tiga berkas data utama yang saling berkaitan:
1. *Data Aktivitas (`activity_data_v3.json`)*: Menentukan daftar aktivitas proyek, durasi normal ($n t_a$), durasi minimum setelah crashing maksimum ($m t_a$), biaya pemangkasan harian ($c c_a$), hubungan ketergantungan antar-aktivitas (precedence), serta status pengerjaan tugas saat ini.
2. *Kapasitas Sumber Daya (`resource_capacity_v3.json`)*: Menentukan batas kapasitas harian maksimum ($c a p_r$) untuk setiap jenis sumber daya $r$.
3. *Kebutuhan Sumber Daya (`resource_requirements_v3.json`)*: Menentukan kebutuhan harian aktivitas $a$ terhadap sumber daya $r$ ($d e m_(a, r)$) ketika aktivitas tersebut sedang aktif berjalan.

== Asumsi dan Limitasi Model
Formulasi model baseline didasarkan pada beberapa asumsi dan limitasi berikut:
- *Linieritas Biaya Crashing*: Pengurangan durasi suatu aktivitas diasumsikan memiliki biaya tambahan konstan per hari. Total biaya crashing untuk suatu tugas adalah hasil kali dari jumlah hari pemotongan dengan biaya harian.
- *Precedence Finish-to-Start*: Hubungan ketergantungan antar-aktivitas yang didukung hanya tipe *Finish-to-Start* (FS) tanpa adanya *lag/lead* waktu.
- *Non-Preemptive*: Aktivitas yang sedang dikerjakan tidak dapat diinterupsi atau diberhentikan sementara hingga benar-benar selesai.
- *Sunk Cost*: Biaya crashing yang terjadi pada masa lalu (aktivitas yang sudah selesai sebelum hari peninjauan saat ini, $t_{"now"}$) dianggap sebagai biaya hangus (*sunk cost*) dan diabaikan dari fungsi tujuan optimisasi aktif.

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
    [$I_0$], [-], [Aktivitas sehingga $s_i < T_0$],
    [$I_1$], [-], [Aktivitas sehingga $e_i < T_0$],
    [$E$], [-], [Ketergantungan antara aktivitas, di-indeks oleh $(i, j)$],
    [$R$], [-], [Sumber daya, di-indeks oleh $r$],
    
    // Parameters
    table.cell(colspan: 3, align: center, fill: luma(250))[*Parameter*],
    [$s_i^(\(0\))$], [hari], [Hari mulai aktual (sebelum _crashing_) aktivitas $i$],
    [$e_i^(\(0\))$], [hari], [Hari akhir aktual (sebelum _crashing_) aktivitas $i$],
    [$d_i^((max))$], [hari], [Durasi normal aktivitas $i$],
    [$d_i^((min))$], [hari], [Durasi minimum aktivitas $i$],
    [$C_i$], [\$/hari], [Harga harian _crashing_ untuk aktivitas $i$],
    [$U_(i,r)$], [satuan/hari], [Keperluan harian sumber daya $r$ untuk aktivitas $i$],
    [$U_r^((max))$], [satuan/hari], [Kapasitas harian sumber daya $r$],
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

$ sum_(i in I) U_(i,r) dot bb(1) \{ s_i <= s_j < e_i \} <= U_r^(max), quad forall r in R, forall j in I $

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
    $ quad forall i in I_0 inter I_1. $
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

$ min sum_(i in I_C) C_i (d_i^(max) - (e_i - s_i)). $

Jadi, diperlukan batasan keras agar tenggat terpenuhi:

$ s_(n+1) <= T_max. $

=== _Time-Driven_
Di sini, difoksukan aspek _time_ dari TCTP, sehingga ingin meminimumkan waktu pengerjaan: 

$ min s_(n+1). $

Ini menjadi mirip dengan masalah RCPSP biasa. Jadi, diperlukan batasan anggaran saja:

$ sum_(i in I) C_i (d_i^max - (e_i - s_i)) <= B. $

=== Multi-Objektif
Di sini, kita gabungkan kedua perspektif di atas untuk menghasilkan masalah multi-objektif yang sesuai untuk TCTP: 

$ min (s_(n+1), sum_(i in I_C) C_i (d_i^(max) - (e_i - s_i))). $

=== _Bonus-Penalty Driven_
Pemodelan _time-cost tradeoff_ tidak perlu dengan pendekatan multi-objektif seperti di atas. Penggabungannya bisa mempertahankan fungsi objektif tunggal dengan menggunakan metrik penalti harian $c_"late"$ dan bonus harian $c_"early"$. Ini menghasilkan fungsi objektif berikut:

$ min sum_(i in I) C_i (d_i^max - (e_i - s_i)) + c_"late" max(0, T_"max" - s_(n+1)) + c_"early" max(0, s_(n+1)- T_"max"). $

== Metode Penyelesaian
Model baseline diselesaikan menggunakan *Google OR-Tools CP-SAT Solver*. CP-SAT dipilih karena menyediakan variabel interval (`IntervalVar`) secara native yang mempermudah representasi durasi tugas dan memiliki algoritma propagasi batasan kumulatif (`AddCumulative`) yang sangat efisien untuk memecahkan masalah penjadwalan dengan batasan sumber daya berkapasitas terbatas.

*Integer Scaling*: Karena solver CP-SAT hanya menerima nilai koefisien berupa bilangan bulat (integer), parameter biaya crashing riil ($c c_a$) yang berbentuk desimal dikalikan dengan faktor skala $S = 10^{"max_dp"}$ (di mana $"max_dp"$ adalah presisi desimal maksimum dari data biaya). Koefisien tujuan ter-skala dihitung dengan $"coeff"_a =  floor.l  c c_a dot S  floor.r $. Setelah diperoleh solusi optimal, total biaya riil diperoleh dengan membagi kembali nilai objektif solver dengan $S$.

#pagebreak()

= Novel Model (Skenario 2)

Di sini, kami memformulasikan model TCTP baru. Secara khusus, dibuat model RC-WTCTP berbasis *workforce* (bukan durasi seperti CTCP atau mode seperti DTCTP) dengan fungsi biaya *endogenous* (tidak *exogenous* seperti pada TCTP umumnya) yang diturunkan dari model utilitas Cobb-Douglas.

== Deskripsi Data yang Dimiliki
Model ini menggunakan berkas data di direktori `data/original-data` yang diimpor dari perangkat lunak manajemen proyek (seperti MS Project):
1.  *Data Aktivitas (`task_table.json`)*: Berisi daftar seluruh aktivitas ($V$), level outline, durasi baseline, tanggal mulai dan selesai, serta dependensi beserta nilai *lag/lead*.
2.  *Data Sumber Daya (`resource_table.json`)*: Berisi daftar jenis tenaga kerja ($K$), kapasitas maksimal harian ($C_k$ dalam persen atau unit), dan tarif upah standar per jam ($r_k$).
3.  *Data Alokasi Tugas (`assignment_table.json`)*: Menghubungkan aktivitas dengan tenaga kerja yang ditugaskan ($K_i$), mencakup usaha kerja baseline ($W_(i,k)$ dalam jam) dan persentase alokasi harian baseline ($U_(i,k)$).

== Asumsi dan Limitasi Model
Formulasi model Cobb-Douglas didasarkan pada beberapa asumsi realistis berikut:
- *Diminishing Returns*: Menambah jumlah pekerja pada suatu aktivitas (*overcrowding*) atau memperpanjang jam kerja (*overtime*) akan mempercepat pengerjaan aktivitas, namun dengan efisiensi marjinal yang menurun. Hal ini dimodelkan dengan eksponen elastisitas $alpha, beta in (0, 1)$ pada fungsi Cobb-Douglas.
- *Koordinasi dan Kelelahan*: Overcrowding menyebabkan hilangnya efisiensi karena peningkatan beban koordinasi antar-pekerja. Overtime menurunkan produktivitas pekerja karena kelelahan (*fatigue*).
- *Tarif Lembur Lebih Tinggi*: Jam kerja lembur ($ tau $) dikenakan tarif upah yang lebih tinggi daripada jam reguler (dikali multiplier upah lembur $r'_k = "ot_mult" dot r_k$).
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
    [$V$], [-], [Himpunan semua aktivitas, termasuk awal (0) dan akhir (n) semu],
    [$V_2$], [-], [Himpunan aktivitas *outline level 2* (aktivitas riil yang dapat di-crash)],
    [$K_i$], [-], [Himpunan SDM yang ditugaskan ke aktivitas $i$],
    [$E_{"FS"}, E_{"SS"}, E_{"FF"}$], [-], [Himpunan relasi ketergantungan Finish-to-Start, Start-to-Start, dan Finish-to-Finish],
    [$cal(T)$], [-], [Himpunan hari dalam horizon proyek, $cal(T) = \{1, 2,  dot s, H\}$],
    
    // Parameters
    table.cell(colspan: 3, align: center, fill: luma(250))[*Parameter*],
    [$W_(i,k)$], [jam], [Usaha kerja baseline SDM $k$ untuk aktivitas $i$],
    [$U_(i,k)$], [-], [Alokasi harian baseline SDM $k$ untuk aktivitas $i$ (proporsi dari 8 jam)],
    [$C_k$], [unit], [Kapasitas SDM $k$ yang tersedia per hari],
    [$r_k$], [Rp/jam], [Tarif reguler SDM $k$],
    [$r'_k$], [Rp/jam], [Tarif lembur SDM $k$, dengan $r'_k >= r_k$],
    [$alpha$], [-], [Eksponen Cobb–Douglas untuk overcrowding ($0 < alpha < 1$)],
    [$beta$], [-], [Eksponen Cobb–Douglas untuk overtime ($0 < beta < 1$)],
    [$T_d$], [hari], [Target waktu penyelesaian proyek (contractual deadline)],
    [$c_{"late"}$], [Rp/hari], [Penalti keterlambatan],
    [$c_{"early"}$], [Rp/hari], [Bonus penyelesaian awal],
    [$c_{"ind"}$], [Rp/hari], [Biaya overhead proyek tidak langsung harian],
    [$delta_(i j)$], [hari], [Lag/lead antara aktivitas $i$ dan $j$],
    [$t_0$], [hari], [Hari saat ini peninjauan proyek],
    
    // Decision Variables
    table.cell(colspan: 3, align: center, fill: luma(250))[*Variabel Keputusan*],
    [$x_(i,k)$], [-], [Pengali overcrowding SDM $k$ untuk aktivitas $i  in  V_2$],
    [$tau_(i,k)$], [jam/hari], [Lama overtime harian SDM $k$ untuk aktivitas $i  in  V_2$],
    [$s_i, f_i$], [hari], [Hari mulai dan selesai aktivitas $i$],
    [$d_i$], [hari], [Durasi aktual aktivitas $i$ ($d_i = f_i - s_i$)],
    [$L, E$], [hari], [Hari proyek selesai setelah / sebelum $T_d$ (lateness/earliness)],
    [$y_(i,t)$], [-], [Variabel biner: bernilai 1 jika aktivitas $i$ aktif pada hari $t$],
    [$z_(i,t)$], [-], [Variabel biner: bernilai 1 jika aktivitas $i$ dimulai pada hari $t$],
  )
]

== Formulasi dan Penurunan Matematis Cobb-Douglas

=== 1. Durasi Aktivitas
Berdasarkan data penjadwalan baseline, durasi normal aktivitas $i$ dapat dihitung dari kebutuhan kerja per tugas:
$ d_i^{"baseline"} = max_(k in K_i) W_(i,k) / (8 U_(i,k)). $
Biaya baseline untuk tenaga kerja $k$ pada tugas $i$ adalah $z_(i,k)^{"baseline"} = W_(i,k) r_k$.

Jika kita melakukan crashing secara naif dengan menambahkan pengali tenaga kerja $x_(i,k)$ dan jam lembur $tau_(i,k)$, durasi baru dihitung sebagai:
$ d'_i = max_(k in K_i) W_(i,k) / ((8 + tau_(i,k))(x_(i,k) U_(i,k))). $
Namun, rumusan naif ini mengakibatkan total biaya labor konstan:
$ z'_(i,k) = d'_i dot x_(i,k) U_(i,k) dot (8 + tau_(i,k)) dot r_(i,k) = W_(i,k) r_(i,k) = z_(i,k)^{"baseline"}. $
Hal ini tidak realistis karena seolah-olah penambahan pekerja dan lembur tidak memicu inefisiensi biaya tambahan.

Untuk mengatasi ini, diperkenalkan fungsi produksi Cobb-Douglas dengan efisiensi marjinal menurun (*diminishing returns*):
$ d'_i = max_(k in K_i) W_(i,k) / (A_{i,k} (x_(i,k) U_(i,k))^alpha (8 + tau_(i,k))^beta). $
Dengan memilih konstanta kalibrasi $A_{i,k} = U_(i,k)^(1-alpha) 8^(1-beta)$ agar durasi baru bernilai sama dengan baseline ketika $x_(i,k)=1$ and $tau_(i,k)=0$, maka durasi ter-crash dapat disederhanakan menjadi:
$ d'_i = max_(k in K_i) W_(i,k) / (8 U_(i,k)) dot 1 / x_(i,k)^alpha dot (8 / (8 + tau_(i,k)))^beta. $
Di mana $1 / x_(i,k)^alpha$ menyatakan faktor perlambatan akibat inefisiensi koordinasi overcrowding, dan $(8 / (8 + tau_(i,k)))^beta$ menyatakan faktor perlambatan akibat kelelahan lembur.

=== 2. Penurunan Fungsi Biaya Tenaga Kerja
Jumlah hari pengerjaan tugas adalah $d'_i$. Total hari-orang untuk SDM $k$ pada tugas $i$ adalah $d'_i dot x_(i,k) U_(i,k)$. Biaya per hari-orang mencakup upah reguler (8 jam dengan tarif $r_k$) dan upah lembur ($tau_(i,k)$ jam dengan tarif lembur $r'_k$):
$ "Biaya Harian Orang" = 8 r_k + tau_(i,k) r'_k. $
Dengan mengalikan jumlah hari-orang dengan biaya harian, diperoleh total biaya tenaga kerja $z'_(i,k)$ untuk SDM $k$ pada aktivitas $i$:
$ z'_(i,k) = d'_i dot x_(i,k) U_(i,k) dot (8 r_k + tau_(i,k) r'_k) \
  z'_(i,k) = W_(i,k) dot x_(i,k)^(1-alpha) dot (8 / (8 + tau_(i,k)))^beta dot (r_k + tau_(i,k)/8 r'_k). $
Persamaan biaya ini secara elegan memodelkan *diminishing returns*: karena $1-alpha < 1$, peningkatan overcrowding ($x > 1$) akan menghasilkan total biaya tenaga kerja yang lebih tinggi daripada baseline untuk menyelesaikan jumlah pekerjaan yang sama.

=== Contoh Kasus Crashing
Perhatikan ilustrasi tugas di bawah ini:

#align(center)[
  #image("img/Contoh Crashing 1.png", width: 85%)
]

Secara normal, pengerjaan tugas ini membutuhkan *Roofing Contractor Management* untuk bekerja 8 jam per hari selama 10 hari (total 80 jam kerja baseline).
1. *Mekanisme Overtime*: Jika pekerja diminta untuk lembur $tau = 1$ jam per hari (total 9 jam kerja per hari), dengan efek kelelahan $beta = 0.3$, durasi baru menjadi $d' = 10 dot (8/9)^0.3 approx 9.6$ hari (dibulatkan menjadi 10 hari atau dipercepat 1 hari tergantung grid). Upah jam lembur dihitung dengan tarif $r'_k$ lebih tinggi.
2. *Mekanisme Overcrowding*: Jika kita menambah satu pekerja lagi ($x = 2.0$) dengan efek koordinasi $alpha = 0.6$, durasi baru menjadi $d' = 10 dot 1/(2^0.6) approx 6.6$ hari. Jumlah hari-pekerja meningkat menjadi $6.6 dot 2 = 13.2$ hari-orang, yang berarti biaya labor total naik sebesar $2^(1-0.6) = 2^0.4 approx 1.32$ kali biaya baseline.

== Formulasi Batasan Lengkap (Novel Model)

=== 1. Batasan Durasi (Cobb-Douglas)
Untuk setiap aktivitas $i in V_2$ dan tenaga kerja $k in K_i$:
$ f_i - s_i >= W_(i,k) / (8 U_(i,k)) dot 1 / x_(i,k)^alpha dot (8 / (8 + tau_(i,k)))^beta. $
Untuk aktivitas yang tidak dapat di-crash ($i in V minus V_2$), durasinya mengikuti baseline:
$ f_i - s_i >= d_i^{"baseline"}. $

=== 2. Batasan Ketergantungan (Precedence) dengan Lag
Mendukung tiga tipe relasi ketergantungan utama:
$ s_j >= f_i + delta_(i j) && quad forall (i,j) in E_{"FS"}, \
  s_j >= s_i + delta_(i j) && quad forall (i,j) in E_{"SS"}, \
  f_j >= f_i + delta_(i j) && quad forall (i,j) in E_{"FF"}. $

=== 3. Batasan Waktu Sekarang (Anchoring)
Aktivitas yang belum selesai tidak boleh dijadwalkan sebelum hari saat ini $t_0$:
$ s_i >= t_0  quad  forall i in V  without   overline {V}. $
Sedangkan untuk aktivitas yang sedang berjalan ($i in V^{"aktif"}$), sisa jam kerja $W_(i,k)$ disesuaikan menjadi $W_(i,k)^{"sisa"} = W_(i,k) (1 - p_{i,k})$ dan dipaksa mulai tepat pada $s_i = t_0$.

=== 4. Batasan Aktivasi Harian (Time-Indexed) dan Kontinuitas
Mendefinisikan biner aktivasi $y_(i,t) = 1$ jika aktivitas $i$ sedang dikerjakan pada hari $t$, dan biner mulai tugas $z_(i,t) = 1$ jika tugas $i$ dimulai pada hari $t$:
$ s_i = sum_(t in cal(T)) t dot z_(i,t), \
  d_i = sum_(t in cal(T)) y_(i,t), \
  f_i = s_i + d_i, \
  z_(i,t) >= y_(i,t) - y_(i,t-1) && quad forall t > E S_i, \
  sum_(t in cal(T)) z_(i,t) <= 1. $
*Justifikasi*: Batasan kontiguitas ini memastikan tugas berjalan terus-menerus tanpa terputus (non-preemptive).

=== 5. Batasan Kapasitas Harian dan Linearisasi McCormick
Penggunaan harian kapasitas reguler ($u_(i,k,t)$) dan lembur ($o_(i,k,t)$) untuk setiap tenaga kerja $k$ pada hari $t$ tidak boleh melebihi kapasitas maksimumnya:
$ sum_(i in V) u_(i,k,t) <= C_k dot 8.0 \
  sum_(i in V) o_(i,k,t) <= C_k dot tau_("max", k) $
Di mana alokasi harian per aktivitas bernilai $u_(i,k,t) = y_(i,t) dot (U_(i,k) dot 8.0 dot x_(i,k))$ dan $o_(i,k,t) = y_(i,t) dot (U_(i,k) dot tau_(i,k))$. 

Karena terdapat perkalian variabel kontinu ($x_(i,k)$ dan $tau_(i,k)$) dengan variabel biner ($y_(i,t)$), diterapkan linearisasi McCormick Envelope:
$ u_(i,k,t) <= u_"max" y_(i,t) \
  u_(i,k,t) <= "u_task_day"_(i,k) \
  u_(i,k,t) >= "u_task_day"_(i,k) - u_"max" (1 - y_(i,t)) $
Di mana $"u_task_day"_(i,k) = U_(i,k) dot 8.0 dot x_(i,k)$ dan $u_"max" = U_(i,k) dot 8.0 dot x_("max", k)$. (Penanganan yang sama dilakukan untuk variabel overtime $o_(i,k,t)$).
*Justifikasi*: Linearisasi ini menghilangkan sifat bilinearitas model sehingga solver MILP standar dapat menyelesaikan model secara optimal global.

== Formulasi Objektif Berdasarkan Skenario

=== Skenario A: Optimisasi Waktu-Biaya (*Time-Cost Tradeoff*)
Meminimalkan total pengeluaran proyek yang mencakup biaya tenaga kerja, biaya tidak langsung (*overhead*), penalti keterlambatan, dan bonus penyelesaian awal:
$ min Z =  sum _{i  in  V}  sum _{k  in  K_i} z'_{i,k} + c_{"ind"} T_{"proj"} + c_{"late"} L - c_{"early"} E. $
Di mana keterlambatan ($L$) dan penyelesaian awal ($E$) dilinearkan sebagai:
$ T_{"proj"} - T_d = L - E,  quad  L, E >= 0. $

=== Skenario B: Batasan Anggaran (*Budget-Constrained*)
Meminimalkan durasi penyelesaian proyek ($T_{"proj"}$) dengan menjaga agar total biaya pengeluaran tidak melebihi anggaran maksimal ($B_{"max"}$):
$ min T_{"proj"} \
  "s.t."  quad  Z <= B_{"max"}. $

=== Skenario C: Batasan Batas Waktu (*Deadline-Constrained*)
Meminimalkan total biaya pengeluaran ($Z$) dengan batasan keras bahwa waktu penyelesaian proyek tidak boleh melewati deadline $T_d$:
$ min Z \
  "s.t."  quad  T_{"proj"} <= T_d. $

#pagebreak()

= Metode Penyelesaian Skenario 2

Model Cobb-Douglas asli merupakan model *MINLP (Mixed-Integer Non-Linear Programming)* yang non-konveks karena persamaan durasi dan biaya mengandung eksponen pecahan. Untuk menyelesaikan model ini secara efisien dan andal, digunakan dua pendekatan:

== 1. MILP berbasis Diskretisasi Grid
Metode ini mendiskretkan ruang pencarian kontinu pengali overcrowding $x_(i,k)$ dan overtime harian $tau_(i,k)$ menjadi beberapa titik grid tertentu:
-   $x_g in \{1.0, 1.25, 1.5, 1.75, 2.0\}$
-   $tau_g in \{0.0, 1.0, 2.0, 3.0, 4.0\}$

Definisikan variabel keputusan biner baru $xi_(i,k)^(m,n) in \{0, 1\}$ yang bernilai 1 jika SDM $k$ pada tugas $i$ memilih titik grid overcrowding ke-$m$ dan overtime ke-$n$.
Dengan diskretisasi ini, nilai durasi $d_{i,m,n}$ dan biaya harian labor $"cost"_(i,m,n)$ untuk masing-masing kombinasi grid dihitung terlebih dahulu sebelum optimisasi (*precomputed*). Seluruh konstrain durasi dan biaya menjadi fungsi linier terhadap variabel biner $xi_(i,k)^(m,n)$:
$ d_i = sum_(m) sum_(n) xi_(i,k)^(m,n) dot d_{i,m,n}. $
Model ini kemudian dimodelkan menggunakan *Pyomo* dan diselesaikan menggunakan solver MILP komersial/open-source seperti *CBC* atau *HiGHS* hingga mencapai jaminan solusi optimal global dalam hitungan detik.

== 2. Pendekatan Metaheuristik (Genetic Algorithm)
Sebagai alternatif pembanding untuk ruang pencarian kontinu tanpa diskretisasi, diimplementasikan algoritma genetika (GA) menggunakan pustaka *`pymoo`* di Python:
-   *Representasi Kromosom*: Variabel keputusan $(x, tau)$ dikodekan langsung sebagai vektor bilangan real.
-   *Fungsi Penalti*: Karena GA sulit menangani batasan secara langsung, kendala precedence dan kapasitas sumber daya ditambahkan sebagai penalti kuadratis ke dalam fungsi objektif jika terjadi pelanggaran (*precedence violation penalty*).
-   *Operator Genetika*: Menggunakan operator seleksi turnamen, persilangan SBX (_Simulated Binary Crossover_), dan mutasi PM (_Polynomial Mutation_).

Meskipun metode GA dapat menangani fungsi Cobb-Douglas asli tanpa diskretisasi, ia tidak memberikan jaminan optimalitas global dan membutuhkan waktu komputasi yang lebih lama untuk konvergensi dibandingkan dengan pendekatan MILP diskret.

= Kesimpulan dan Perbandingan Model

#align(center)[
  #table(
    columns: (3.5cm, 5.5cm, 5.5cm),
    align: (center, left, left),
    fill: (col, row) => if row == 0 { luma(240) },
    table.header(
      [*Karakteristik*], [*Model Baseline (CP-SAT)*], [*Model Novel (Cobb-Douglas)*],
    ),
    [*Input Biaya*], [Eksplisit diketahui per hari crashing per tugas (\$/hari).], [Ditentukan secara endogen dari tarif reguler/lembur SDM (\$/jam).],
    [*Tuas Akselerasi*], [Langsung memotong hari durasi tugas.], [Menambah pekerja (*overcrowding*) & menambah jam kerja lembur (*overtime*).],
    [*Sifat Efisiensi*], [Efisiensi konstan (biaya linier terhadap waktu pemangkasan).], [Efisiensi menurun (*diminishing returns*) akibat koordinasi & kelelahan.],
    [*Tipe Precedence*], [Finish-to-Start (FS) sederhana tanpa lag.], [Finish-to-Start (FS), Start-to-Start (SS), Finish-to-Finish (FF) dengan lag.],
    [*Metode Solver*], [Constraint Programming (OR-Tools CP-SAT).], [MILP (Pyomo + CBC) via Diskretisasi Grid & Metaheuristik (pymoo GA).],
  )
]

Secara ringkas, jika manajer proyek memiliki estimasi biaya crashing langsung dan mengabaikan efek kelelahan kerja, *Model Baseline* adalah pilihan tercepat. Namun, untuk alokasi proyek yang lebih realistis dan taktis yang memperhatikan kelelahan pekerja serta batasan kapasitas harian terperinci, *Model Novel Cobb-Douglas* memberikan solusi yang jauh lebih akurat dan dapat memodelkan trade-off operasional yang sebenarnya di lapangan.