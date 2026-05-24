# Formulasi Preprocessing Model Hybrid (Skenario 3)

## 1. Latar Belakang & Motivasi

Dalam manajemen proyek dengan kendala sumber daya, terdapat trade-off antara kecepatan penyelesaian model (*runtime*) dan realisme data yang digunakan:
1.  **Skenario 1 (Model Baseline - CP-SAT)**: Menggunakan pemrograman batasan (*Constraint Programming*). Kelebihannya adalah kecepatan eksekusi yang sangat tinggi (dalam orde milidetik) dan jaminan optimalitas global. Namun, model ini tidak realistis karena mengasumsikan data biaya pemangkasan harian ($C_i$) dan durasi minimum ($d_i^{\min}$) untuk setiap aktivitas diketahui secara langsung (*exogenous*). Di dunia nyata, perusahaan jarang memiliki data biaya pemotongan per hari yang konstan.
2.  **Skenario 2 (Model Novel - Cobb-Douglas)**: Menggunakan fungsi Cobb-Douglas untuk memodelkan efek penurunan efisiensi marjinal (*diminishing returns*) akibat penambahan pekerja (*overcrowding*) dan jam kerja lembur (*overtime*). Model ini sangat realistis dan menggunakan data yang relevan dengan perusahaan (tarif upah, alokasi jam kerja harian, total usaha kerja). Namun, fungsi durasi dan biaya yang dihasilkan bersifat non-linier dan non-konveks (MINLP). Penyelesaian menggunakan algoritma genetika (metaheuristik) memakan waktu lama (*runtime* tinggi) dan tidak menjamin optimalitas global.

Untuk menjembatani celah tersebut, kami mengusulkan **Model Hybrid (Skenario 3)**. Ide dasarnya adalah menggunakan fungsi produksi Cobb-Douglas (dari Skenario 2) sebagai **tahap preprocessing** untuk menghitung batas durasi minimum ($d_i^{\min}$) dan biaya pemangkasan durasi harian ($C_i$) secara otomatis dari data internal perusahaan. Hasil preprocessing tersebut kemudian dimasukkan ke dalam solver CP-SAT (Skenario 1) yang sangat cepat dan akurat.

---

## 2. Langkah-Langkah Preprocessing Data (Cobb-Douglas)

Diberikan data input yang sama dengan Skenario 2 untuk setiap aktivitas $i \in I$ dan jenis sumber daya (SDM) $k \in K_i$:
*   $W_{i,k}$: Usaha kerja baseline SDM $k$ untuk aktivitas $i$ (dalam jam).
*   $U_{i,k}$: Alokasi harian baseline SDM $k$ untuk aktivitas $i$ (proporsi terhadap 8 jam kerja).
*   $r_k$: Tarif upah reguler SDM $k$ (Rp/jam).
*   $r'_k$: Tarif upah lembur SDM $k$ (Rp/jam), di mana $r'_k = \text{ot\_mult} \cdot r_k$.
*   $\alpha$: Eksponen Cobb-Douglas untuk overcrowding ($0 < \alpha < 1$).
*   $\beta$: Eksponen Cobb-Douglas untuk overtime ($0 < \beta < 1$).

### Langkah 1: Perhitungan Durasi Normal dan Biaya Baseline

1.  **Durasi Normal ($d_i^{\max}$)**:
    Durasi normal aktivitas $i$ dihitung berdasarkan kebutuhan usaha kerja harian maksimum di antara seluruh SDM yang ditugaskan:
    $$ d_i^{\max} = \max_{k \in K_i} \left\lceil \frac{W_{i,k}}{8 \cdot U_{i,k}} \right\rceil $$
    *Catatan: Pembulatan ke atas ($\lceil \cdot \rceil$) digunakan karena durasi pada solver CP-SAT dimodelkan dalam satuan hari diskrit.*

2.  **Biaya Normal/Baseline ($Z_i^{\text{base}}$)**:
    Biaya total aktivitas $i$ jika dikerjakan dalam kondisi normal (tanpa overcrowding dan lembur) adalah akumulasi biaya upah reguler untuk seluruh SDM:
    $$ Z_i^{\text{base}} = \sum_{k \in K_i} W_{i,k} \cdot r_k $$

---

### Langkah 2: Perhitungan Durasi Minimum dan Biaya Maksimal pada Crashing Maksimum

Untuk menghitung seberapa jauh suatu tugas dapat dipercepat dan berapa biaya tambahannya, kita menentukan batas akselerasi maksimum yang diperbolehkan secara praktis:
*   Batas overcrowding maksimum: $x_{i,k} = x_{\max} = 2.0$ (alokasi tenaga kerja dilipatgandakan).
*   Batas overtime harian maksimum: $\tau_{i,k} = \tau_{\max} = 2.0$ jam/hari.

1.  **Durasi Minimum setelah Crashing Maksimal ($d_i^{\min}$)**:
    Menggunakan rumus durasi Cobb-Douglas, durasi minimum aktivitas $i$ ketika dipercepat secara maksimal adalah:
    $$ d_i^{\min} = \max_{k \in K_i} \left\lceil \frac{W_{i,k}}{8 \cdot U_{i,k}} \cdot \left(\frac{1}{x_{\max}}\right)^\alpha \cdot \left(\frac{8}{8 + \tau_{\max}}\right)^\beta \right\rceil $$

2.  **Biaya Total pada Crashing Maksimal ($Z_i^{\text{crash}}$)**:
    Biaya total aktivitas $i$ ketika dijalankan pada kapasitas akselerasi maksimal ($x_{\max}, \tau_{\max}$) dihitung menggunakan fungsi biaya Cobb-Douglas:
    $$ Z_i^{\text{crash}} = \sum_{k \in K_i} z_{i,k}(x_{\max}, \tau_{\max}) $$
    Di mana biaya per assignment $z_{i,k}$ didefinisikan secara endogen sebagai:
    $$ z_{i,k}(x_{\max}, \tau_{\max}) = W_{i,k} \cdot r_k \cdot x_{\max}^{1-\alpha} \cdot \left(\frac{8 + \tau_{\max}}{8}\right)^{1-\beta} \cdot \left( \frac{8 + \frac{r'_k}{r_k} \tau_{\max}}{8 + \tau_{\max}} \right) $$

---

### Langkah 3: Perhitungan Crash Slope (Biaya Pemotongan Durasi Harian, $C_i$)

Setelah durasi normal, durasi minimum, biaya baseline, dan biaya crashing maksimum dihitung, kita memproyeksikan hubungan non-linier tersebut ke dalam pendekatan linier lokal (*linear approximation*).

Biaya pemotongan durasi per hari (*crash slope*) untuk setiap aktivitas $i$ dihitung sebagai rasio antara kenaikan biaya total dengan jumlah hari yang berhasil dipotong:

$$ C_i = \begin{cases} \frac{Z_i^{\text{crash}} - Z_i^{\text{base}}}{d_i^{\max} - d_i^{\min}}, & \text{jika } d_i^{\max} > d_i^{\min} \\ 0, & \text{jika } d_i^{\max} = d_i^{\min} \end{cases} $$

---

## 3. Integrasi ke Model Optimisasi CP-SAT (Skenario 3)

Nilai $d_i^{\max}$, $d_i^{\min}$, dan $C_i$ yang diperoleh dari tahap preprocessing di atas kemudian dimasukkan langsung sebagai parameter masukan untuk model CP-SAT.

### Formulasi Model CP-SAT Hybrid

**Himpunan & Indeks:**
*   $I$: Himpunan seluruh aktivitas, di-indeks oleh $i$.
*   $I_0^C$: Himpunan aktivitas aktif dan belum mulai (yang dapat di-crash).
*   $E$: Himpunan relasi ketergantungan *Finish-to-Start* $(i, j)$ di mana aktivitas $i$ adalah pendahulu dari $j$.
*   $K$: Himpunan jenis sumber daya (SDM), di-indeks oleh $k$.

**Variabel Keputusan:**
*   $s_i \in [0, T_{\max}]$: Hari mulai aktivitas $i$.
*   $e_i \in [0, T_{\max}]$: Hari selesai aktivitas $i$.
*   $d_i \in [d_i^{\min}, d_i^{\max}]$: Durasi efektif aktivitas $i$.

**Fungsi Objektif (Cost-Driven):**
Tujuan utama model ini adalah meminimalkan total biaya tambahan akibat pemotongan durasi (*crashing cost*) ditambah penalti keterlambatan atau dikurangi bonus penyelesaian awal proyek:

$$ \min \quad \sum_{i \in I_0^C} C_i \cdot (d_i^{\max} - d_i) + c_{\text{late}} \cdot I_{\text{late}} - c_{\text{early}} \cdot I_{\text{early}} $$

Di mana $I_{\text{late}} = \max(0, e_n - T_{\max})$ dan $I_{\text{early}} = \max(0, T_{\max} - e_n)$, dengan $e_n$ menyatakan hari selesai aktivitas akhir proyek.

**Batasan (Constraints):**

1.  **Konsistensi Waktu**:
    $$ e_i = s_i + d_i, \quad \forall i \in I $$

2.  **Batasan Durasi**:
    $$ d_i^{\min} \le d_i \le d_i^{\max}, \quad \forall i \in I $$

3.  **Ketergantungan Precedence (Finish-to-Start)**:
    $$ s_j \ge e_i, \quad \forall (i, j) \in E $$

4.  **Kapasitas Sumber Daya Kumulatif**:
    Untuk setiap jenis sumber daya $k \in K$, jumlah alokasi harian dari seluruh aktivitas yang aktif secara bersamaan tidak boleh melebihi kapasitas maksimum $U_k^{\max}$:
    $$ \text{Cumulative}(\text{intervals} = \{[s_i, d_i, e_i] \mid k \in K_i\}, \text{demands} = \{U_{i,k} \mid k \in K_i\}, \text{capacity} = U_k^{\max}) $$

5.  **Batasan Penjadwalan Dinamis**:
    Sama halnya dengan Skenario 1, untuk aktivitas yang sudah selesai sebelum $T_0$, variabel $s_i, e_i, d_i$ dikunci ke nilai realisasinya. Untuk aktivitas yang sedang berjalan pada $T_0$, waktu mulai dikunci ($s_i = s_i^{(0)}$) dan sisa durasi minimum disesuaikan dengan progress pekerjaan. Untuk aktivitas masa depan, $s_i \ge T_0$.
