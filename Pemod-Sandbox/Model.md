# Perumusan Model

**Timothy Niels Ruslim (10123053)**

---

## 1 Model

### 1.1 Variabel dan Parameter

| Notasi | Definisi |
|--------|----------|
| $V$ | Himpunan aktivitas, termasuk awal (0) dan akhir (n) semu. |
| $V_2 \subseteq V$ | Himpunan aktivitas *outline level 2* — satu-satunya yang dapat di-*crash*. Aktivitas level 0 dan 1 hanya rangkuman dan tidak memiliki variabel keputusan crashing. |
| $K_i$ | Himpunan SDM yang ditugaskan ke aktivitas $i$. |
| $E_{\text{FS}}, E_{\text{SS}}, E_{\text{FF}}$ | Himpunan pasangan aktivitas dengan relasi Finish-to-Start, Start-to-Start, dan Finish-to-Finish. |
| $\mathcal{T}$ | Himpunan hari dalam horizon proyek, $\mathcal{T} = \{1, 2, \dots, T^{\text{horizon}}\}$. |

*Tabel 1: Himpunan.*

| Notasi | Satuan | Definisi |
|--------|--------|----------|
| $W_{i,k}$ | Jam | Usaha kerja baseline SDM $k$ untuk aktivitas $i$. |
| $W^{\text{sisa}}_{i,k}$ | Jam | Sisa usaha kerja SDM $k$ untuk aktivitas $i$ pada hari $t_0$ (untuk aktivitas yang sedang berjalan). |
| $U_{i,k}$ | - | Alokasi harian baseline SDM $k$ untuk aktivitas $i$ (proporsi dari 8 jam). |
| $C_k$ | Orang | Kapasitas SDM $k$ yang tersedia per hari. |
| $x_{\min,k}, x_{\max,k}$ | - | Batas bawah dan atas pengali overcrowding untuk SDM $k$. |
| $\tau_{\max,k}$ | Jam | Batas maksimum lembur per hari untuk SDM $k$ (umumnya 4). |
| $r_k$ | Rp / Jam | Tarif reguler SDM $k$. |
| $r'_k$ | Rp / Jam | Tarif lembur SDM $k$, dengan $r'_k \geq r_k$. |
| $\alpha \in (0,1)$ | - | Eksponen Cobb–Douglas untuk overcrowding (semakin kecil, semakin cepat *diminishing returns*). |
| $\beta \in (0,1)$ | - | Eksponen Cobb–Douglas untuk overtime. |
| $T_{\max}$ | Hari | Target waktu penyelesaian proyek. |
| $c_{\text{late}}$ | Rp / Hari | Penalti keterlambatan. |
| $c_{\text{early}}$ | Rp / Hari | Bonus penyelesaian awal, dengan $c_{\text{late}} > c_{\text{early}} \geq 0$. |
| $\delta_{ij}$ | Hari | Lag/lead antara aktivitas $i$ dan $j$. |
| $t_0$ | Hari | Hari saat ini (input pengguna). |
| $\overline{V}$ | - | Aktivitas yang sudah selesai pada $t_0$ (locked: $x_{i,k}=1$, $\tau_{i,k}=0$). |
| $V^{\text{aktif}}$ | - | Aktivitas yang sedang berjalan pada $t_0$ ($s_i \leq t_0 \leq f_i$ pada baseline). |

*Tabel 2: Parameter Model.*

| Notasi | Satuan | Domain | Definisi |
|--------|--------|--------|----------|
| $x_{i,k}$ | - | $[x_{\min,k}, x_{\max,k}]$ | Pengali overcrowding SDM $k$ untuk aktivitas $i \in V_2$. |
| $\tau_{i,k}$ | Jam / Hari | $[0, \tau_{\max,k}]$ | Lama overtime harian SDM $k$ untuk aktivitas $i \in V_2$. |
| $s_i, f_i$ | Hari | $\geq 0$ | Mulai dan akhir aktivitas $i$. |
| $I_{\text{late}}, I_{\text{early}}$ | Hari | $\geq 0$ | Hari proyek selesai setelah / sebelum $T_{\max}$. |
| $y_{i,t}$ | - | $\{0,1\}$ | Indikator: aktivitas $i$ aktif pada hari $t \in \mathcal{T}$. |

*Tabel 3: Variabel Keputusan.* Untuk $i \in \overline{V}$, semua variabel di-fix ke nilai realisasinya. Untuk $i \in V \setminus V_2$, variabel $x, \tau$ tidak ada.

### 1.2 Fungsi Objektif

Biaya SDM $k$ pada aktivitas $i \in V_2$ ketika diterapkan crashing adalah

$$
z'_{i,k}
= W_{i,k} \cdot x_{i,k}^{1-\alpha}
\cdot \left(\frac{8}{8 + \tau_{i,k}}\right)^{\beta}
\cdot \left(r_k + \frac{\tau_{i,k}}{8} r'_k\right).
$$

Pada baseline ($x_{i,k}=1$, $\tau_{i,k}=0$) menghasilkan $z'_{i,k} = W_{i,k} r_k$, konsisten dengan biaya baseline. Penurunan rumus diberikan di Bagian 2.2.

Fungsi objektif total:

$$
\min \quad \sum_{i \in V_2} \sum_{k \in K_i} z'_{i,k}
\;+\; \sum_{i \in V \setminus V_2} \sum_{k \in K_i} W_{i,k} r_k
\;+\; c_{\text{late}} I_{\text{late}} - c_{\text{early}} I_{\text{early}}.
$$

Suku kedua adalah konstanta (tidak ber-variabel keputusan) sehingga dapat diabaikan saat optimisasi, tapi tetap dilaporkan dalam total biaya.

### 1.3 Batasan

**Durasi (Cobb–Douglas, per resource).** Untuk setiap $i \in V_2$ dan $k \in K_i$:

$$
f_i - s_i \;\geq\; \frac{W_{i,k}}{8\, U_{i,k}}
\cdot \frac{1}{x_{i,k}^{\alpha}}
\cdot \left(\frac{8}{8 + \tau_{i,k}}\right)^{\beta}.
$$

Untuk $i \in V \setminus V_2$, durasi mengikuti baseline: $f_i - s_i \geq d_i^{\text{baseline}}$.

**Sisa pekerjaan untuk aktivitas yang sedang berjalan.** Untuk $i \in V^{\text{aktif}}$, ganti $W_{i,k} \to W^{\text{sisa}}_{i,k}$ dan paksa $s_i = t_0$.

**Anchoring waktu sekarang.** Untuk $i \notin \overline{V}$:

$$
s_i \;\geq\; t_0.
$$

**Precedence.**

$$
\begin{aligned}
s_j &\geq f_i + \delta_{ij} && \forall (i,j) \in E_{\text{FS}}, \\
s_j &\geq s_i + \delta_{ij} && \forall (i,j) \in E_{\text{SS}}, \\
f_j &\geq f_i + \delta_{ij} && \forall (i,j) \in E_{\text{FF}}.
\end{aligned}
$$

**Aktivasi harian (time-indexed).** Untuk setiap $i \in V$ dan $t \in \mathcal{T}$, $y_{i,t} = 1$ iff $s_i \leq t \leq f_i$. Linerisasi big-M:

$$
\begin{aligned}
s_i &\leq t \cdot y_{i,t} + T^{\text{horizon}}(1 - y_{i,t}), \\
f_i &\geq t \cdot y_{i,t}.
\end{aligned}
$$

**Kapasitas resource per hari.** Untuk setiap $k$ dan $t \in \mathcal{T}$:

$$
\sum_{i \in V_2 : k \in K_i} x_{i,k}\, U_{i,k}\, y_{i,t}
\;+\; \sum_{i \in V \setminus V_2 : k \in K_i} U_{i,k}\, y_{i,t}
\;\leq\; C_k.
$$

Suku $x_{i,k}\, y_{i,t}$ adalah produk variabel kontinu × biner — di-linearkan dengan McCormick atau dihilangkan via diskretisasi $x$ (lihat Bagian 3).

**Deadline.**

$$
f_n - T_{\max} = I_{\text{late}} - I_{\text{early}}.
$$

**Domain variabel.**

$$
\begin{aligned}
x_{\min,k} &\leq x_{i,k} \leq x_{\max,k} && \forall i \in V_2,\ k \in K_i, \\
0 &\leq \tau_{i,k} \leq \tau_{\max,k} && \forall i \in V_2,\ k \in K_i, \\
s_i, f_i &\geq 0, \quad y_{i,t} \in \{0,1\}, \quad I_{\text{late}}, I_{\text{early}} \geq 0.
\end{aligned}
$$

---

## 2 Motivasi

### 2.1 Time–Cost Trade-off Problem

Di literatur, terdapat tiga pendekatan utama:

1. **Kontinu (CTCTP):** durasi crashing kontinu, biaya linier [3].
2. **Diskrit (DTCTP):** pilih dari daftar mode crashing biner [1].
3. **Berbasis Resource (RCTCTP):** sumber daya sebagai variabel utama, durasi turun darinya [2].

Saya memilih **RCTCTP** karena paling fleksibel, dan literatur sudah menunjukkan algoritma yang efisien [5].

### 2.2 Biaya Pembangunan dan Cobb–Douglas

Dari baseline, durasi aktivitas $i$ adalah

$$
d_i = \max_{k \in K_i} \frac{W_{i,k}}{8\, U_{i,k}},
$$

dan biaya per SDM $z_{i,k} = W_{i,k} r_k$. Untuk memodelkan crashing melalui dua mekanisme — **overcrowding** (pengali $x_{i,k}$ orang) dan **overtime** ($\tau_{i,k}$ jam lembur) — implementasi naif

$$
d'_i = \max_{k \in K_i} \frac{W_{i,k}}{(8 + \tau_{i,k})\, x_{i,k}\, U_{i,k}}
$$

mengakibatkan $z'_{i,k} = W_{i,k} r_k = z_{i,k}$, yakni crashing gratis. Tidak realistis: overcrowding memunculkan koordinasi tambahan dan overtime menurunkan produktivitas per jam. Untuk memodelkan *diminishing returns*, digunakan **fungsi produksi Cobb–Douglas** [4]:

$$
d'_i = \max_{k \in K_i} \frac{W_{i,k}}{A_{i,k}\, (x_{i,k} U_{i,k})^{\alpha}\, (8 + \tau_{i,k})^{\beta}},
\qquad 0 < \alpha, \beta < 1.
$$

Dengan kalibrasi $A_{i,k} = U_{i,k}^{1-\alpha}\, 8^{1-\beta}$ agar $d'_i = d_i$ saat $x=1, \tau=0$:

$$
d'_i = \max_{k \in K_i}
\underbrace{\frac{W_{i,k}}{8\, U_{i,k}}}_{d_i}
\cdot \underbrace{\frac{1}{x_{i,k}^{\alpha}}}_{\text{overcrowding}}
\cdot \underbrace{\left(\frac{8}{8 + \tau_{i,k}}\right)^{\beta}}_{\text{overtime}}.
$$

> **Catatan revisi:** Pada draf sebelumnya rumus akhir tertulis $\frac{8}{(8+\tau)^\beta}$. Setelah substitusi $A = U^{1-\alpha} 8^{1-\beta}$, bentuk yang benar adalah $\left(\frac{8}{8+\tau}\right)^{\beta}$.

Sekarang biaya **memisahkan tarif reguler dan lembur**. Pekerja-hari $= d'_i \cdot x_{i,k} U_{i,k}$, dan biaya per pekerja-hari $= 8 r_k + \tau_{i,k} r'_k$ (8 jam reguler + $\tau$ jam lembur). Maka

$$
z'_{i,k}
= d'_i \cdot x_{i,k} U_{i,k} \cdot (8 r_k + \tau_{i,k} r'_k)
= W_{i,k} \cdot x_{i,k}^{1-\alpha} \left(\frac{8}{8+\tau_{i,k}}\right)^{\beta} \left(r_k + \frac{\tau_{i,k}}{8} r'_k\right).
$$

Verifikasi baseline: $x=1, \tau=0 \Rightarrow z'_{i,k} = W_{i,k} r_k$. ✓

> **Catatan revisi:** Pada draf sebelumnya, biaya tidak membedakan $r_k$ vs $r'_k$, sehingga setelah penyederhanaan algebra seluruh jam (termasuk reguler) terhitung pada tarif lembur. Versi di atas memperbaiki ini dengan memisahkan komponen reguler ($8 r_k$) dan lembur ($\tau r'_k$) sebelum dikalikan jumlah pekerja-hari.

### 2.3 Resource Capacity

Aktivitas paralel yang berbagi SDM yang sama tidak boleh melampaui kapasitasnya. Tanpa constraint kapasitas, solver bebas men-stack semua aktivitas pada tanggal yang sama dengan $x = x_{\max}$ — secara fisik mustahil. Karena itu, diperkenalkan variabel biner *aktivasi harian* $y_{i,t}$ yang menjadi 1 jika aktivitas $i$ sedang berjalan pada hari $t$, lalu menjumlahkan beban harian per resource. Tanpa constraint ini, pendekatan tidak lagi pantas disebut *resource-constrained*.

### 2.4 Status Saat Ini

Pengguna menginput $t_0$ (hari saat ini). Untuk aktivitas yang **sudah selesai** ($i \in \overline{V}$), seluruh variabelnya di-fix ke nilai realisasinya — tidak ada gunanya men-crash masa lalu. Untuk aktivitas yang **sedang berjalan** ($i \in V^{\text{aktif}}$), $s_i = t_0$ dan $W_{i,k}$ diganti dengan sisa pekerjaan $W^{\text{sisa}}_{i,k} = W_{i,k}(1 - p_{i,k})$ dengan $p_{i,k}$ persen penyelesaian dari data assignment. Aktivitas yang **belum mulai** dipaksa $s_i \geq t_0$.

### 2.5 Biaya Batas Waktu

Bonus dan penalti ditulis linier:

$$
z_c = c_{\text{late}} I_{\text{late}} - c_{\text{early}} I_{\text{early}},
\qquad \Delta := f_n - T_{\max} = I_{\text{late}} - I_{\text{early}}.
$$

Optimal selalu memilih $I_{\text{late}} = 0$ atau $I_{\text{early}} = 0$ (tidak keduanya positif), syarat $c_{\text{late}} > c_{\text{early}}$. Sketsa: andai $I_{\text{late}}, I_{\text{early}} > 0$ dengan nilai $a, b$, pengurangan keduanya sebanyak $\min(a,b)$ tetap memenuhi constraint dan menurunkan objektif sebesar $(c_{\text{late}} - c_{\text{early}}) \min(a,b) > 0$ — kontradiksi optimalitas.

---

## 3 Catatan Tractability dan Strategi Pemecahan

### 3.1 Sifat Matematis

Model di atas **bukan MILP** maupun convex NLP karena:

- **Konstrain durasi** $f_i - s_i \geq C_{i,k}\, x_{i,k}^{-\alpha} \left(\frac{8}{8+\tau_{i,k}}\right)^{-\beta}$ memiliki ruas kanan konveks (untuk $\alpha, \beta > 0$), sehingga daerah feasible **non-konveks**.
- **Fungsi objektif** mengandung $x^{1-\alpha} (8+\tau)^{-\beta}$ dengan eksponen $\in (0,1)$, yakni **konkaf**. Minimisasi fungsi konkaf umumnya NP-hard.
- **Kapasitas resource** mengandung produk $x_{i,k} \cdot y_{i,t}$ (kontinu × biner) — bilinear.

### 3.2 Strategi 1: Diskretisasi → MILP (Direkomendasikan)

Diskretkan $x_{i,k}$ ke grid $\{x^{(1)}, \dots, x^{(M)}\}$ dan $\tau_{i,k}$ ke grid $\{0, 1, 2, 3, 4\}$. Definisikan biner $\xi_{i,k}^{(m,n)} = 1$ jika SDM $k$ pada aktivitas $i$ memilih mode $(m,n)$, dengan $\sum_{m,n} \xi_{i,k}^{(m,n)} = 1$. Biaya, durasi, dan kapasitas menjadi **linier** dalam $\xi$. Bilinearitas $x \cdot y$ hilang karena $\xi \cdot y$ dapat di-linearkan dengan teknik standar (biner × biner). Hasilnya MILP eksak terhadap grid.

Implementasi: **Pyomo + HiGHS / CBC**, atau **PuLP**. Sesuai pendekatan multi-mode RCTCTP di [5]. Selain itu, $x_{i,k}$ memang lebih natural diskret karena jumlah orang nyata diskret — grid yang disarankan: $x \in \{1.0, 1.25, 1.5, 1.75, 2.0\}$ bergantung $x_{\max,k}$.

### 3.3 Strategi 2: Metaheuristik (Pembanding)

NSGA-II / GA via **pymoo**, mengikuti [2]. Variabel keputusan $(x, \tau)$ dikodekan langsung sebagai vektor real, schedule diturunkan dari forward-pass + repair untuk konflik kapasitas. Cocok untuk multi-objektif (waktu vs biaya) tanpa skalarisasi via $c_{\text{late}}, c_{\text{early}}$.

---

## Referensi

[1] Athanasios P. Chassiakos and Serafim P. Sakellaropoulos. Time-cost optimization of construction projects with generalized activity constraints. *Journal of Construction Engineering and Management*, 131(10):1115–1126, 2005.

[2] Yixiong Feng, Xiaohua Lin, and Jianrong Tan. Resource constrained time-cost trade-off problem and its genetic algorithm solution. *Applied Mathematics & Information Sciences*, 7(2):639–643, 2013.

[3] D. R. Fulkerson. A network flow computation for project cost curves. *Management Science*, 7(2):167–178, 1961.

[4] Wikipedia contributors. Cobb–Douglas production function. https://en.wikipedia.org/wiki/Cobb%E2%80%93Douglas_production_function, 2026. Accessed: 2026-03-05.

[5] Gizem Çakır, Kemal Subulan, Seyda Topaloglu Yildiz, Alper Hamzaday, and Ceren Asilkefeli. A comparative study of modeling and solution approaches for the multi-mode resource-constrained discrete time-cost trade-off problem: Case study of an ERP implementation project. *Computers & Industrial Engineering*, 169:108201, 2022.
