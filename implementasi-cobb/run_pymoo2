"""
Model 2: Resource-Based Scheduling (Cobb-Douglas)
==================================================
Optimasi alokasi sumber daya manusia pada proyek konstruksi
menggunakan framework pymoo + GA.

Fitur utama:
  - current_day : hari ke berapa proyek saat ini berjalan (input pengguna).
                  Task yang sudah selesai sebelum current_day dikunci ke baseline.
                  Crashing hanya diterapkan pada task yang belum selesai.
  - s_i untuk task yang belum selesai dihitung deterministik via CPM forward pass
    dengan lower bound max(current_day, hasil_precedence).
  - Variabel keputusan GA: hanya x_{i,k} dan tau_{i,k} untuk task belum selesai.
    Task yang sudah selesai dikunci ke x=1, tau=0 (tidak di-crash).
  - x_max ditentukan via diminishing returns relatif: berhenti saat marginal
    benefit < 50% dari manfaat pekerja tambahan pertama (threshold = 0.5 * delta_0).
  - tau_min = 0.0 sesuai slide (0 ≤ τ ≤ τ_max).
  - D_min_ratio: durasi crash tidak boleh < D_min_ratio × D_base per pasangan (i,k).
"""

import os
import numpy as np
import pandas as pd
from pymoo.core.problem import ElementwiseProblem
from pymoo.core.repair import Repair
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.optimize import minimize
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM


# ===========================================================================
# Path Helper
# ===========================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def data_path(filename):
    return os.path.join(BASE_DIR, filename)


# ===========================================================================
# Data Loader
# ===========================================================================

def load_data(path_tasks, path_precedence, path_assignments):
    tasks      = pd.read_csv(path_tasks)
    precedence = pd.read_csv(path_precedence)
    resources  = pd.read_csv(path_assignments)

    resources = resources.rename(columns={"D_base": "D_base_ik"})

    N = len(tasks)
    id_to_idx = {tid: idx for idx, tid in enumerate(tasks["task_id"])}

    precedence = precedence.copy()
    precedence["i"] = precedence["task_id"].map(id_to_idx)   # successor
    precedence["j"] = precedence["pred_id"].map(id_to_idx)   # predecessor
    precedence = (precedence
                  .dropna(subset=["i", "j"])
                  .astype({"i": int, "j": int})
                  .reset_index(drop=True))

    resources = resources.copy()
    resources["i"] = resources["task_id"].map(id_to_idx)
    resources = (resources
                 .dropna(subset=["i"])
                 .astype({"i": int})
                 .reset_index(drop=True))

    K_i = {}
    for row_idx, row in resources.iterrows():
        K_i.setdefault(int(row["i"]), []).append(row_idx)

    return tasks, precedence, resources, N, K_i


# ===========================================================================
# Problem Definition
# ===========================================================================

class ResourceBasedScheduling(ElementwiseProblem):
    """
    Variabel Keputusan (n_var = 2P)
    ---------------------------------
    x[0:P]   = x_{i,k}   : crowding factor (pengali buruh)
    x[P:2P]  = tau_{i,k} : lembur harian (jam/hari)

    Untuk task yang sudah selesai sebelum current_day:
      x_{i,k} dan tau_{i,k} dikunci ke 1 dan 0 di dalam _evaluate,
      sehingga D_ik = D_base_ik (tidak di-crash).

    Jadwal (s_i) selalu dihitung deterministik via CPM forward pass:
      s_i = max(current_day, hasil_precedence)  ← untuk task belum selesai
      s_i = s_baseline[i]                       ← untuk task sudah selesai

    Kendala (n_ieq_constr = P)
    ---------------------------
    G[p] = D_min_ik[p] - D_ik[p] ≤ 0   untuk setiap pasangan (i,k)
    → Hanya aktif untuk task yang belum selesai.

    Fungsi Objektif
    ---------------
    min Z = Σ_{i,k} D_{i,k} · x_{i,k} · U_{i,k} · (8·r_k + τ_{i,k}·r'_k)
            + c_late  · max(0, T_finish − T_max)
            − c_early · max(0, T_max − T_finish)

    Durasi Crash (Cobb-Douglas) — sesuai slide:
    D_{i,k} = D_base_ik · (1/x_{i,k})^α · (8/(8+τ_{i,k}))^β
    D_i     = max_{k ∈ K_i} D_{i,k}
    """

    def __init__(self, tasks, precedence, resources, N, K_i,
                 alpha=0.5, beta=0.5,
                 x_min=1.0, x_max=None,
                 tau_min=0.0,
                 tau_max=4.0,
                 D_min_ratio=0.5,
                 c_late=10000.0, c_early=1000.0,
                 T_max=344,
                 current_day=0,        # ← input pengguna: hari mulai crashing
                 overtime_mult=1.5,
                 hours_per_day=8,
                 **kwargs):

        self.tasks         = tasks
        self.precedence    = precedence
        self.resources     = resources
        self.N             = N
        self.K_i           = K_i
        self.P             = len(resources)

        self.alpha         = alpha
        self.beta          = beta
        self.x_min         = x_min
        self.tau_min       = tau_min
        self.tau_max       = tau_max
        self.D_min_ratio   = D_min_ratio
        self.c_late        = c_late
        self.c_early       = c_early
        self.T_max         = T_max
        self.current_day   = current_day
        self.overtime_mult = overtime_mult
        self.hours_per_day = hours_per_day

        if x_max is None:
            x_max = self._compute_x_max(alpha, x_min)
        self.x_max = x_max

        # Data per pasangan (i,k)
        self.r_k          = resources["r_k_usd"].values
        self.r_k_ot       = self.r_k * overtime_mult
        self.W_ik         = resources["W_ik"].values
        self.U_ik         = resources["U_ik"].values
        self.D_base_ik    = resources["D_base_ik"].values
        self.D_min_ik     = D_min_ratio * self.D_base_ik
        self.res_task_idx = resources["i"].values

        # Precompute precedence sebagai numpy array
        self.prec_i    = precedence["i"].values.astype(int)
        self.prec_j    = precedence["j"].values.astype(int)
        self.prec_lag  = precedence["lag"].values.astype(float)
        self.prec_type = precedence["type"].values

        # ── Hitung baseline schedule (x=1, tau=0) ──────────────────────────
        # Digunakan untuk: (1) identifikasi task selesai, (2) kunci s_i task selesai
        D_base_i = np.zeros(N)
        for i in range(N):
            for p in K_i.get(i, []):
                D_base_i[i] = max(D_base_i[i], self.D_base_ik[p])
        s_bl, f_bl = self._forward_pass_raw(D_base_i, lower_bound=None)
        self.s_baseline = s_bl
        self.f_baseline = f_bl
        self.D_base_i   = D_base_i

        # ── Identifikasi task selesai sebelum current_day ──────────────────
        # Task selesai: f_baseline <= current_day  DAN  memiliki durasi > 0
        self.completed_tasks = set(
            i for i in range(N)
            if f_bl[i] <= current_day and D_base_i[i] > 1e-9
        )
        # Pasangan (i,k) yang task-nya sudah selesai
        self.completed_pairs = set(
            p for p in range(self.P)
            if int(resources.loc[p, "i"]) in self.completed_tasks
        )

        # ── Bounds variabel keputusan ───────────────────────────────────────
        # Semua P pasangan tetap masuk sebagai variabel agar indeks konsisten,
        # tetapi pasangan task-selesai diberi bounds xl=xu=nilai_baseline
        # sehingga GA tidak mengubahnya.
        P = self.P
        xl_x   = np.full(P, x_min)
        xu_x   = np.full(P, x_max)
        xl_tau = np.full(P, tau_min)
        xu_tau = np.full(P, tau_max)

        for p in self.completed_pairs:
            xl_x[p]   = xu_x[p]   = 1.0   # x_ik dikunci ke 1 (tidak di-crash)
            xl_tau[p] = xu_tau[p] = 0.0   # tau_ik dikunci ke 0 (tidak lembur)

        super().__init__(
            n_var=2 * P,
            n_obj=1,
            n_ieq_constr=P,   # D_min per pasangan (i,k)
            xl=np.concatenate([xl_x, xl_tau]),
            xu=np.concatenate([xu_x, xu_tau]),
            **kwargs,
        )

    @staticmethod
    def _compute_x_max(alpha, x_min=1.0):
        """
        x_max = titik di mana marginal benefit penambahan pekerja
        turun di bawah 50% dari manfaat pekerja tambahan pertama.

        threshold = 0.5 × delta(x=1)
                  = 0.5 × [(1/1)^alpha − (1/2)^alpha]

        Dengan alpha=0.5: threshold ≈ 0.146 → x_max = 2.0
        Alasan: saat x=2→3, manfaat hanya ~44% dari pekerja ke-1,
        artinya diminishing returns sudah signifikan secara praktis.
        """
        delta_first = (1.0 / x_min) ** alpha - (1.0 / (x_min + 1)) ** alpha
        threshold   = 0.5 * delta_first

        x = x_min
        while x < 50:
            delta = (1.0 / x) ** alpha - (1.0 / (x + 1)) ** alpha
            if delta < threshold:
                break
            x += 0.5
        return max(x, x_min + 1.0)

    def crash_duration(self, x_ik, tau_ik, D_base=None):
        """D_{i,k} = D_base_ik · (1/x)^α · (8/(8+τ))^β  [vectorized]"""
        if D_base is None:
            D_base = self.D_base_ik
        return D_base * (1.0 / x_ik) ** self.alpha * (8.0 / (8.0 + tau_ik)) ** self.beta

    def compute_durations(self, x_vec):
        """Hitung D_ik dan D_i dari vektor x_vec = [x_ik | tau_ik]."""
        N, P = self.N, self.P
        x_ik   = x_vec[0:P]
        tau_ik = x_vec[P:2 * P]
        D_ik   = self.crash_duration(x_ik, tau_ik)
        D_i    = np.zeros(N)
        for i in range(N):
            for p in self.K_i.get(i, []):
                D_i[i] = max(D_i[i], D_ik[p])
        return D_ik, D_i

    def _forward_pass_raw(self, D_i, lower_bound=None):
        """
        CPM Forward Pass murni (tanpa pertimbangan current_day).
        Digunakan saat inisialisasi untuk menghitung baseline schedule.
        """
        s = np.zeros(self.N)
        for _ in range(self.N):
            s_prev = s.copy()
            for idx in range(len(self.prec_i)):
                i, j  = self.prec_i[idx], self.prec_j[idx]
                lag, t = self.prec_lag[idx], self.prec_type[idx]
                if t == "FS":   cand = s[j] + D_i[j] + lag
                elif t == "FF": cand = s[j] + D_i[j] + lag - D_i[i]
                elif t == "SS": cand = s[j] + lag
                else: continue
                if cand > s[i]: s[i] = cand
            if lower_bound is not None:
                s = np.maximum(s, lower_bound)
            if np.allclose(s, s_prev, atol=1e-8):
                break
        return s, s + D_i

    def forward_pass(self, D_i):
        """
        CPM Forward Pass dengan mempertimbangkan current_day.

        Aturan:
          - Task sudah selesai : s_i = s_baseline[i]  (dikunci, tidak berubah)
          - Task belum selesai : s_i = max(current_day, hasil_precedence)
            → Task tidak bisa dimulai sebelum hari crashing dimulai.
        """
        s = np.zeros(self.N)

        # Inisialisasi: task selesai dikunci ke s_baseline
        for i in self.completed_tasks:
            s[i] = self.s_baseline[i]

        for _ in range(self.N):
            s_prev = s.copy()
            for idx in range(len(self.prec_i)):
                i, j  = self.prec_i[idx], self.prec_j[idx]
                lag, t = self.prec_lag[idx], self.prec_type[idx]
                if t == "FS":   cand = s[j] + D_i[j] + lag
                elif t == "FF": cand = s[j] + D_i[j] + lag - D_i[i]
                elif t == "SS": cand = s[j] + lag
                else: continue
                if cand > s[i]: s[i] = cand

            # Terapkan lower bound current_day hanya untuk task yang belum selesai
            for i in range(self.N):
                if i not in self.completed_tasks:
                    s[i] = max(s[i], self.current_day)

            # Kembalikan task selesai ke s_baseline (tidak boleh bergeser)
            for i in self.completed_tasks:
                s[i] = self.s_baseline[i]

            if np.allclose(s, s_prev, atol=1e-8):
                break

        return s, s + D_i

    def _evaluate(self, x, out, *args, **kwargs):
        P = self.P

        x_ik   = x[0:P].copy()
        tau_ik = x[P:2 * P].copy()

        # Task selesai: kunci ke baseline (tidak di-crash)
        # Bounds sudah mengunci ini, tapi copy eksplisit untuk keamanan
        for p in self.completed_pairs:
            x_ik[p]   = 1.0
            tau_ik[p] = 0.0

        D_ik = self.crash_duration(x_ik, tau_ik)

        D_i = np.zeros(self.N)
        for i in range(self.N):
            for p in self.K_i.get(i, []):
                D_i[i] = max(D_i[i], D_ik[p])

        # Task selesai: pastikan D_i tetap = D_base_i
        for i in self.completed_tasks:
            D_i[i] = self.D_base_i[i]

        s, f = self.forward_pass(D_i)
        T_finish = float(np.max(f))

        labor_cost = float(np.sum(
            D_ik * x_ik * self.U_ik
            * (self.hours_per_day * self.r_k + tau_ik * self.r_k_ot)
        ))

        penalty = self.c_late  * max(0.0, T_finish - self.T_max)
        bonus   = self.c_early * max(0.0, self.T_max - T_finish)

        out["F"] = labor_cost + penalty - bonus

        # Kendala D_min: aktif hanya untuk task belum selesai
        G = self.D_min_ik - D_ik
        for p in self.completed_pairs:
            G[p] = 0.0   # task selesai selalu feasible, tidak dihitung
        out["G"] = G


# ===========================================================================
# Main
# ===========================================================================

if __name__ == "__main__":

    # ---- 1. Muat data ----
    tasks, precedence, resources, N, K_i = load_data(
        path_tasks=data_path("data_tasks.csv"),
        path_precedence=data_path("data_precedence.csv"),
        path_assignments=data_path("data_assignments.csv"),
    )

    # ---- 2. Parameter utama ----
    # current_day : hari ke berapa proyek saat ini berjalan.
    #               Crashing hanya diterapkan untuk task yang belum selesai
    #               pada hari ini. Ubah nilai ini sesuai kondisi aktual proyek.
    CURRENT_DAY = 156

    # ---- 3. Buat instance problem ----
    problem = ResourceBasedScheduling(
        tasks=tasks,
        precedence=precedence,
        resources=resources,
        N=N,
        K_i=K_i,
        alpha=0.7,
        beta=0.7,
        x_min=1.0,
        tau_min=0.0,
        tau_max=4.0,
        D_min_ratio=0.5,
        c_late=5000.0,
        c_early=2000.0,
        T_max=344,
        current_day=CURRENT_DAY,
        overtime_mult=1.5,
        hours_per_day=8,
    )

    # ---- 4. Info problem ----
    P = problem.P
    n_done    = len(problem.completed_tasks)
    n_remain  = N - n_done
    p_done    = len(problem.completed_pairs)
    p_remain  = P - p_done

    print(f"Tasks             : N = {N}")
    print(f"  Sudah selesai   : {n_done}  task  (sebelum hari ke-{CURRENT_DAY})")
    print(f"  Belum selesai   : {n_remain} task  (akan di-crash)")
    print(f"Resource pairs    : P = {P}")
    print(f"  Pasangan selesai: {p_done}  (dikunci, tidak dioptimasi)")
    print(f"  Pasangan aktif  : {p_remain} (dioptimasi GA)")
    print(f"Precedence        : {len(precedence)}")
    print(f"n_var             : {problem.n_var}  = x_ik:{P} + tau_ik:{P}")
    print(f"n_ieq_constr      : {problem.n_ieq_constr}  (D_min per pasangan i,k)")
    print(f"x_max             : {problem.x_max:.2f}")
    # print(f"Baseline makespan : {np.max(problem.f_baseline):.1f} hari")

    # ---- 5. GA Solver ----
    print("\n" + "=" * 60)
    print(f"CRASHING DARI HARI KE-{CURRENT_DAY} HINGGA T_MAX={problem.T_max}")
    print("=" * 60)

    algorithm = GA(
        pop_size=100,
        crossover=SBX(prob=0.9, eta=15),
        mutation=PM(eta=20),
        eliminate_duplicates=True,
    )

    res = minimize(
        problem,
        algorithm,
        termination=("n_gen", 250),
        seed=42,
        verbose=True,
    )

    # ---- 6. Hasil ----
    print("\n" + "=" * 60)
    print("HASIL OPTIMASI TERBAIK")
    print("=" * 60)

    if res.X is not None:
        x_opt      = res.X
        x_ik_opt   = x_opt[0:P].copy()
        tau_ik_opt = x_opt[P:2 * P].copy()

        for p in problem.completed_pairs:
            x_ik_opt[p]   = 1.0
            tau_ik_opt[p] = 0.0

        D_ik_opt, D_i_opt = problem.compute_durations(x_opt)
        for i in problem.completed_tasks:
            D_i_opt[i] = problem.D_base_i[i]

        s_opt, f_opt = problem.forward_pass(D_i_opt)
        makespan     = float(np.max(f_opt))

        labor_cost = float(np.sum(
            D_ik_opt * x_ik_opt * problem.U_ik
            * (problem.hours_per_day * problem.r_k + tau_ik_opt * problem.r_k_ot)
        ))
        penalty = problem.c_late  * max(0.0, makespan - problem.T_max)
        bonus   = problem.c_early * max(0.0, problem.T_max - makespan)
        total   = labor_cost + penalty - bonus

        print(f"  Biaya Tenaga Kerja   = {labor_cost:>15,.2f} USD")
        print(f"  Total Biaya Proyek   = {total:>15,.2f} USD")
        print(f"  Baseline makespan    = {np.max(problem.f_baseline):>10.1f} hari")
        print(f"  Optimized makespan   = {makespan:>10.2f} hari  "
              f"(Batas: {problem.T_max} hari)")
        print(f"  Reduksi durasi       = "
              f"{np.max(problem.f_baseline)-makespan:>10.1f} hari  "
              f"({(np.max(problem.f_baseline)-makespan)/np.max(problem.f_baseline)*100:.1f}%)")

        if bonus > 0:
            print(f"  Bonus diterima       = {bonus:>15,.2f} USD  (selesai lebih awal)")
        elif penalty > 0:
            print(f"  Denda keterlambatan  = {penalty:>15,.2f} USD")
        else:
            print(f"  Tepat waktu — tidak ada penalti maupun bonus.")

        # Ringkasan jadwal
        print(f"\n--- Ringkasan Jadwal (10 task pertama) ---")
        print(f"  {'#':>3}  {'Nama Task':<46}  {'Start':>6}  {'Finish':>6}  {'Durasi':>7}")
        print(f"  {'-'*3}  {'-'*46}  {'-'*6}  {'-'*6}  {'-'*7}")
        for i in range(min(10, N)):
            nama = tasks.iloc[i]["task_name"][:46]
            print(f"  {i:>3}  {nama:<46}  {s_opt[i]:>6.1f}  {f_opt[i]:>6.1f}  {D_i_opt[i]:>7.2f}")
        if N > 10:
            print(f"  ... dan {N - 10} task lainnya")

    else:
        print("GA tidak menemukan solusi. Coba naikkan pop_size atau n_gen.")