import numpy as np
import pandas as pd
from pymoo.core.problem import ElementwiseProblem

# ===========================================================================
# Data Loader
# ===========================================================================

def load_data(path_tasks, path_precedence, path_resources):
    """Muat data proyek dari CSV yang sudah dipisah dan dirapikan.

    Parameters
    ----------
    path_tasks : str
        Path ke CSV data task (kolom: task_id, task_name, duration_days).
    path_precedence : str
        Path ke CSV data precedence (kolom: task_id, pred_id, type, lag).
    path_resources : str
        Path ke CSV data resource per task.
        Kolom: task_id, task_name, resource_id, resource_name,
               W_ik, U_ik, D_base_ik, r_k_usd.

    Returns
    -------
    tasks : pd.DataFrame       — data tiap task (N baris)
    precedence : pd.DataFrame  — relasi antar task
    resources : pd.DataFrame   — data resource per (i,k) pair
    N : int                    — jumlah task
    K_i : dict[int, list[int]] — mapping task_idx → list of row indices di resources
    """
    tasks = pd.read_csv(path_tasks)
    precedence = pd.read_csv(path_precedence)
    resources = pd.read_csv(path_resources)

    N = len(tasks)

    # Mapping: task_id asli → indeks lokal 0..N-1
    # Karena pada data asli, task yang dipakai hanyalah task dengan outline 2
    id_to_idx = {tid: idx for idx, tid in enumerate(tasks["task_id"])}

    # Tambahkan kolom indeks lokal
    precedence = precedence.copy()
    precedence["i"] = precedence["task_id"].map(id_to_idx)
    precedence["j"] = precedence["pred_id"].map(id_to_idx)
    precedence = precedence.dropna(subset=["i", "j"]).astype({"i": int, "j": int})

    resources = resources.copy()
    resources["i"] = resources["task_id"].map(id_to_idx)
    resources["D_base_ik"] = resources["D_base"]

    # Mapping: task_idx i → list of row indices di resources dataframe
    # K_0 = [0] -> task 0 memakai 1 resource (baris 0 di resources)
    # K_1 = [1, 2] -> task 1 memakai 2 resource (baris 1 dan 2 di resources)
    K_i = {}
    for row_idx, row in resources.iterrows():
        i = int(row["i"])
        K_i.setdefault(i, []).append(row_idx)

    return tasks, precedence, resources, N, K_i


# ===========================================================================
# Problem Definition
# ===========================================================================

class ResourceBasedScheduling(ElementwiseProblem):
    """Resource-Based Project Scheduling Problem.

    Minimasi total biaya proyek (biaya tenaga kerja + penalti - bonus)
    dengan mengoptimalkan waktu mulai tiap task, pengali buruh, dan lembur
    per task-resource pair.

    Variabel Keputusan (array 1D, panjang N + 2P)
    ----------------------------------------------
    x[0:N]       = s_i       : waktu mulai task i (hari)
    x[N:N+P]     = x_{i,k}   : pengali buruh untuk task i, resource k
    x[N+P:N+2P]  = tau_{i,k} : lembur harian untuk task i, resource k (jam/hari)

    Dimana:
    - N = jumlah task
    - P = jumlah pasangan (i,k) yang ada (sparse, hanya yang dialokasikan)
    - Setiap task i punya K_i resource: x_{i,k} dan tau_{i,k} untuk k in K_i

    Fungsi Objektif
    ---------------
    min Z = sum_{i in V} sum_{k in K_i}
              [ D_{i,k}(x_{i,k}, tau_{i,k}) * x_{i,k} * U_{i,k} * (8*r_k + tau_{i,k}*r'_k) ]
            + c_late * max(0, T_finish - T_max)
            - c_early * max(0, T_max - T_finish)

    Durasi Crash (Cobb-Douglas, per (i,k))
    ---------------------------------------
    D_{i,k} = (W_{i,k} / (8 * U_{i,k})) * (1/x_{i,k})^alpha * (8/(8+tau_{i,k}))^beta

    Durasi Task (untuk scheduling)
    ------------------------------
    D_i = max_{k in K_i} D_{i,k}

    Kendala (inequality, g <= 0)
    ----------------------------
    FS: s_j + D_j + lag - s_i <= 0
    FF: s_j + D_j + lag - s_i - D_i <= 0
    SS: s_j + lag - s_i <= 0
    """

    def __init__(self, tasks, precedence, resources, N, K_i,
                 alpha=0.5, beta=0.5,
                 x_min=1.0, x_max=None,
                 tau_min=1.0, tau_max=4.0,
                 c_late=150.0, c_early=100.0,
                 T_max=344,
                 overtime_mult=1.5,
                 hours_per_day=8, **kwargs):

        # Simpan data
        self.tasks = tasks
        self.precedence = precedence
        self.resources = resources
        self.N = N
        self.K_i = K_i
        self.P = len(resources)  # jumlah pasangan (i,k)

        # Simpan parameter
        self.alpha = alpha
        self.beta = beta
        self.x_min = x_min
        self.tau_min = tau_min
        self.tau_max = tau_max
        self.c_late = c_late
        self.c_early = c_early
        self.T_max = T_max
        self.overtime_mult = overtime_mult
        self.hours_per_day = hours_per_day

        # Hitung x_max otomatis dari alpha
        if x_max is None:
            x_max = self._compute_x_max(alpha, x_min)
        self.x_max = x_max

        # --- Data per pasangan (i,k) ---
        # Konversi tarif: USD/jam
        self.r_k = resources["r_k_usd"].values / 1e6
        self.r_k_ot = self.r_k * overtime_mult

        self.W_ik = resources["W_ik"].values             # usaha kerja (jam)
        self.U_ik = resources["U_ik"].values             # alokasi baseline
        self.D_base_ik = resources["D_base"].values      # durasi baseline (hari)
        self.res_task_idx = resources["i"].values         # task index untuk setiap (i,k)

        # --- Bangun batas bawah dan atas ---
        P = self.P
        xl = np.concatenate([
            np.zeros(N),                          # s_i >= 0
            np.full(P, x_min),                    # x_{i,k} >= x_min
            np.full(P, tau_min),                  # tau_{i,k} >= tau_min
        ])
        xu = np.concatenate([
            np.full(N, 2.0 * T_max),             # s_i <= 2*T_max
            np.full(P, x_max),                    # x_{i,k} <= x_max
            np.full(P, tau_max),                  # tau_{i,k} <= tau_max
        ])

        super().__init__(
            n_var=N + 2 * P,
            n_obj=1,
            n_ieq_constr=len(precedence),
            xl=xl,
            xu=xu,
            **kwargs,
        )

    @staticmethod
    def _compute_x_max(alpha, x_min=1.0, threshold=0.01):
        """Hitung x_max berdasarkan efek diminishing returns dari crowding."""
        x = x_min
        while x < 50:
            delta = (1.0 / x) ** alpha - (1.0 / (x + 1)) ** alpha
            if delta < threshold:
                break
            x += 0.5
        return max(x, x_min + 1.0)

    def crash_duration(self, x_ik, tau_ik, D_base_ik):
        """D_{i,k} = D_base * (1/x_{i,k})^alpha * (8/(8+tau_{i,k}))^beta"""
        crowd = (1.0 / x_ik) ** self.alpha
        fatigue = (8.0 / (8.0 + tau_ik)) ** self.beta
        return D_base_ik * crowd * fatigue

    def _evaluate(self, x, out, *args, **kwargs):
        """Evaluasi fungsi objektif dan kendala untuk satu solusi."""
        N, P = self.N, self.P

        # ---- Ekstrak variabel ----
        s = x[0:N]                        # s_i
        x_ik = x[N:N + P]                 # x_{i,k}
        tau_ik = x[N + P:N + 2 * P]       # tau_{i,k}

        # ---- Durasi crash per (i,k) ----
        D_ik = np.array([
            self.crash_duration(x_ik[p], tau_ik[p], self.D_base_ik[p])
            for p in range(P)
        ])

        # ---- Durasi per task: D_i = max_{k in K_i} D_{i,k} ----
        D_i = np.zeros(N)
        for i in range(N):
            for p in self.K_i.get(i, []):
                D_i[i] = max(D_i[i], D_ik[p])

        # ---- Fungsi Objektif ----
        # Biaya tenaga kerja: sum_{i,k} D_{i,k} * x_{i,k} * U_{i,k} * (8*r_k + tau_{i,k}*r'_k)
        labor_cost = np.sum(
            D_ik * x_ik * self.U_ik
            * (self.hours_per_day * self.r_k + tau_ik * self.r_k_ot)
        )

        # Penalti & bonus
        T_finish = np.max(s + D_i)
        penalty = self.c_late * max(0.0, T_finish - self.T_max)
        bonus = self.c_early * max(0.0, self.T_max - T_finish)

        out["F"] = labor_cost + penalty - bonus

        # ---- Kendala Precedence (g <= 0) ----
        G = np.zeros(len(self.precedence))

        for k, row in self.precedence.iterrows():
            i, j = int(row["i"]), int(row["j"])
            lag = row["lag"]

            if row["type"] == "FS":
                G[k] = s[j] + D_i[j] + lag - s[i]
            elif row["type"] == "FF":
                G[k] = s[j] + D_i[j] + lag - s[i] - D_i[i]
            elif row["type"] == "SS":
                G[k] = s[j] + lag - s[i]

        out["G"] = G


# ===========================================================================
# Main: Inisialisasi Problem
# ===========================================================================

if __name__ == "__main__":

    # ---- 1. Muat data ----
    tasks, precedence, resources, N, K_i = load_data(
        path_tasks="data_tasks.csv",
        path_precedence="data_precedence.csv",
        path_resources="data_assignments.csv",
    )

    # ---- 2. Buat instance problem ----
    problem = ResourceBasedScheduling(
        tasks=tasks,
        precedence=precedence,
        resources=resources,
        N=N,
        K_i=K_i,

        # Faktor produktivitas
        alpha=0.5,           # crowding
        beta=0.5,            # fatigue

        # Batasan variabel keputusan
        x_min=1.0,           # undermanning limit
        tau_min=1.0,         # jam/hari
        tau_max=4.0,         # jam/hari

        # Penalti & bonus (M Rp/hari)
        c_late=150.0,
        c_early=100.0,

        # Deadline
        T_max=344,           # hari kerja

        # Konversi mata uang
        exchange_rate=15000.0,   # Rp/USD
        overtime_mult=1.5,       # pengali gaji lembur
    )

    # ---- 3. Info problem ----
    P = len(resources)
    print(f"Tasks       : N = {N}")
    print(f"Resources   : P = {P}  (pasangan i,k)")
    print(f"Precedence  : {len(precedence)}")
    print(f"n_var       : {problem.n_var}  = s:{N} + x:{{i,k}}:{P} + tau:{{i,k}}:{P}")
    print(f"n_obj       : {problem.n_obj}")
    print(f"n_ieq_constr: {problem.n_ieq_constr}")
    print(f"x_max       : {problem.x_max}")

    # ---- 4. Verifikasi ----
    np.random.seed(42)
    x_test = problem.xl + (problem.xu - problem.xl) * np.random.rand(problem.n_var)
    F, G = problem.evaluate(x_test)

    print(f"\nVerifikasi evaluasi:")
    print(f"  F (biaya total)     = {F[0]:.4f} M Rp")
    print(f"  Kendala terpenuhi   = {np.sum(G <= 0)} / {len(G)}")
    print(f"  Kendala dilanggar   = {np.sum(G > 0)} / {len(G)}")

    # ---- 5. Contoh data (i,k) ----
    print(f"\n--- Contoh x_{{i,k}} dan tau_{{i,k}} (5 baris pertama) ---")
    for _, r in resources.head(5).iterrows():
        i = int(r["i"])
        r_mrp = r["r_k_usd"] * 15000 / 1e6
        print(f"  Task[{i:2d}] × Res[{r['resource_name'][:25]:25s}] | "
              f"W={r['W_ik']:6.1f}h U={r['U_ik']:.0%} "
              f"D_base={r['D_base_ik']:5.1f}d r_k={r_mrp:.4f} M Rp/h")
