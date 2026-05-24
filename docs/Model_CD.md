# Perumusan Model Novel Cobb-Douglas (Skenario 2)

**Timothy Niels Ruslim (10123053)**

---

## 1. Variabel dan Parameter

### 1.1 Himpunan (Sets)
| Notasi | Deskripsi |
|--------|-----------|
| $I$ | Himpunan semua aktivitas proyek. |
| $I_0$ | Himpunan aktivitas yang sudah selesai sebelum hari peninjauan ($e_i \leq T_0$). |
| $I_1$ | Himpunan aktivitas yang belum mulai pada hari peninjauan ($s_i \geq T_0$). |
| $E_{\text{FS}}, E_{\text{SS}}, E_{\text{FF}}$ | Himpunan pasangan aktivitas $(i,j)$ dengan relasi *Finish-to-Start*, *Start-to-Start*, dan *Finish-to-Finish*. |
| $K$ | Himpunan jenis sumber daya (SDM), di-indeks oleh $k$. |

### 1.2 Parameter
| Notasi | Satuan | Deskripsi |
|--------|--------|-----------|
| $W_{i,k}$ | jam | Usaha kerja baseline SDM $k$ untuk aktivitas $i$. |
| $U_{i,k}$ | - | Alokasi harian baseline SDM $k$ untuk aktivitas $i$ (proporsi dari 8 jam). |
| $U_k^{\max}$ (atau $C_k$) | - | Kapasitas maksimal SDM $k$ yang tersedia per hari. |
| $r_k$ | Rp/jam | Tarif reguler SDM $k$. |
| $r'_k$ | Rp/jam | Tarif lembur SDM $k$, dengan $r'_k \geq r_k$. |
| $\alpha \in (0,1)$ | - | Eksponen Cobb–Douglas untuk overcrowding. |
| $\beta \in (0,1)$ | - | Eksponen Cobb–Douglas untuk overtime. |
| $c_{\text{late}}$ | Rp/hari | Penalti keterlambatan penyelesaian proyek. |
| $c_{\text{early}}$ | Rp/hari | Bonus penyelesaian proyek lebih awal. |
| $c_{\text{ind}}$ | Rp/hari | Biaya overhead proyek tidak langsung harian. |
| $\delta_{ij}$ | hari | Lag/lead antara aktivitas $i$ dan $j$. |
| $T_0$ | hari | Hari saat ini peninjauan/evaluasi proyek. |
| $T_{\max}$ | hari | Hari tenggat proyek (*deadline*). |

### 1.3 Variabel Keputusan (Decision Variables)
| Notasi | Domain | Deskripsi |
|--------|--------|-----------|
| $x_{i,k}$ | $[1.0, x_{\max,k}]$ | Pengali overcrowding SDM $k$ untuk aktivitas $i \notin I_0$. |
| $\tau_{i,k}$ | $[0, \tau_{\max,k}]$ | Lama overtime harian SDM $k$ untuk aktivitas $i \notin I_0$ (jam/hari). |
| $s_i$ | $\geq 0$ | Hari mulai aktivitas $i$. |

### 1.4 Variabel Pembantu (Helper Variables - Disubstitusikan ke Model)
*   **Durasi Efektif ($d_{i,k}$)**: Durasi pengerjaan aktivitas $i$ oleh SDM $k$ setelah dipercepat:
    $$ d_{i,k}(x_{i,k}, \tau_{i,k}) := \frac{W_{i,k}}{8 \cdot U_{i,k}} \cdot \left(\frac{1}{x_{i,k}}\right)^\alpha \cdot \left(\frac{8}{8 + \tau_{i,k}}\right)^\beta $$
*   **Biaya Efektif ($z_{i,k}$)**: Total biaya SDM $k$ pada aktivitas $i$ setelah crashing:
    $$ z_{i,k}(x_{i,k}, \tau_{i,k}) := W_{i,k} \cdot r_k \cdot x_{i,k}^{1-\alpha} \cdot \left(\frac{8 + \tau_{i,k}}{8}\right)^{1-\beta} \cdot \left( \frac{8 + \frac{r'_k}{r_k} \tau_{i,k}}{8 + \tau_{i,k}} \right) $$
*   **Hari Selesai ($e_i$)**: Hari selesai aktivitas $i$, yang ditentukan oleh SDM paling lambat selesai:
    $$ e_i := s_i + \max_{k \in K} d_{i,k}(x_{i,k}, \tau_{i,k}) $$

---

## 2. Formulasi Model Matematika

### 2.1 Fungsi Objektif (Bonus-Penalty Driven)
Tujuan model adalah meminimalkan total biaya tenaga kerja (yang mencakup upah reguler dan upah lembur tambahan akibat crashing) ditambah penalti keterlambatan, atau dikurangi bonus penyelesaian awal terhadap tenggat proyek ($T_{\max}$):

$$ \min \quad \sum_{i \in I_0^C} \sum_{k \in K} z_{i,k}(x_{i,k}, \tau_{i,k}) + c_{\text{late}} \max(0, s_{n+1} - T_{\max}) + c_{\text{early}} \max(0, T_{\max} - s_{n+1}) $$

*Catatan: $s_{n+1}$ menyatakan hari mulai aktivitas akhir proyek (dummy end), yang secara efektif merepresentasikan hari selesai proyek secara keseluruhan.*

### 2.2 Batasan (Constraints)

1.  **Ketergantungan Precedence**:
    Mendukung tiga jenis hubungan ketergantungan antar-aktivitas dengan lag/lead $\delta_{ij}$:
    $$ s_j \geq e_i + \delta_{ij}, \quad \forall (i,j) \in E_{\text{FS}} $$
    $$ s_j \geq s_i + \delta_{ij}, \quad \forall (i,j) \in E_{\text{SS}} $$
    $$ e_j \geq e_i + \delta_{ij}, \quad \forall (i,j) \in E_{\text{FF}} $$

2.  **Kapasitas Sumber Daya (Start-Day-Indexed)**:
    Pada setiap awal aktivitas $j \in I$, jumlah kebutuhan harian untuk setiap sumber daya $k \in K$ dari seluruh aktivitas $i \in I$ yang aktif secara bersamaan tidak boleh melebihi kapasitas harian maksimum $U_k^{\max}$:
    $$ \sum_{i \in I} U_{i,k} \cdot \mathbb{1}\{s_i \leq s_j < s_i + d_{i,k}\} \leq U_k^{\max}, \quad \forall k \in K, \forall j \in I $$

3.  **Batasan Dinamis**:
    *   **Aktivitas Selesai ($i \in I_0$)**: Dikunci sesuai jadwal aktualnya.
        $$ s_i = s_i^{(0)} $$
        $$ x_{i,k} = 1.0, \quad \tau_{i,k} = 0.0 $$
        $$ e_i = e_i^{(0)} $$
        $$ W_{i,k} = W_{i,k}^{(0)} $$
    *   **Aktivitas Sedang Berjalan ($i \in I_0^C \cap I_1^C$)**: Mulai dikunci pada hari mulai aktual, namun durasi sisa dihitung berdasarkan sisa pekerjaan.
        $$ s_i = s_i^{(0)} $$
        $$ e_i \geq T_0 $$
        $$ W_{i,k} = W_{i,k}^{(0)}(1 - p_{i,k}) $$
    *   **Aktivitas Belum Mulai ($i \in I_1$)**: Waktu mulai dijadwalkan setelah hari evaluasi.
        $$ s_i \geq T_0 $$
        $$ W_{i,k} = W_{i,k}^{(0)} $$
