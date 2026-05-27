import os
import numpy as np
import pandas as pd
from pymoo.core.problem import ElementwiseProblem
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

    # Precedence: tambah kolom indeks lokal, lalu reset index agar 0-based
    precedence = precedence.copy()
    precedence["i"] = precedence["task_id"].map(id_to_idx)   # successor
    precedence["j"] = precedence["pred_id"].map(id_to_idx)   # predecessor
    precedence = (precedence
                  .dropna(subset=["i", "j"])
                  .astype({"i": int, "j": int})
                  .reset_index(drop=True))   # ← PENTING: index harus 0-based

    # Resources (assignments)
    resources = resources.copy()
    resources["i"] = resources["task_id"].map(id_to_idx)
    resources = (resources
                 .dropna(subset=["i"])
                 .astype({"i": int})
                 .reset_index(drop=True))

    # Mapping: task_idx → list of row indices di resources
    K_i = {}
    for row_idx, row in resources.iterrows():
        K_i.setdefault(int(row["i"]), []).append(row_idx)

    return tasks, precedence, resources, N, K_i


# ===========================================================================
# Problem Definition
# ===========================================================================

class ResourceBasedScheduling(ElementwiseProblem):
    """
    Variabel Keputusan (array 1D, panjang 2P)
    ------------------------------------------
    x[0:P]   = x_{i,k}   : pengali buruh (crowding factor)
    x[P:2P]  = tau_{i,k} : lembur harian (jam/hari)

    s_i TIDAK dioptimasi — dihitung deterministik via CPM forward pass.
    Karena s_i selalu konsisten dengan precedence, tidak ada kendala inequality.

    Fungsi Objektif
    ---------------
    min Z = sum_{i,k} [ D_{i,k} * x_{i,k} * U_{i,k} * (8*r_k + tau_{i,k}*r'_k) ]
            + c_late  * max(0, T_finish - T_max)
            - c_early * max(0, T_max - T_finish)

    Durasi Crash (Cobb-Douglas)
    ----------------------------
    D_{i,k} = D_base_ik * (1/x_{i,k})^alpha * (8/(8+tau_{i,k}))^beta
    D_i     = max_{k in K_i} D_{i,k}
    """

    def __init__(self, tasks, precedence, resources, N, K_i,
                 alpha=0.5, beta=0.5,
                 x_min=1.0, x_max=None,
                 tau_min=1.0, tau_max=4.0,
                 c_late=10000.0, c_early=1000.0,
                 T_max=344,
                 overtime_mult=1.5,
                 hours_per_day=8, **kwargs):

        self.tasks      = tasks
        self.precedence = precedence
        self.resources  = resources
        self.N          = N
        self.K_i        = K_i
        self.P          = len(resources)

        self.alpha        = alpha
        self.beta         = beta
        self.x_min        = x_min
        self.tau_min      = tau_min
        self.tau_max      = tau_max
        self.c_late       = c_late
        self.c_early      = c_early
        self.T_max        = T_max
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
        self.res_task_idx = resources["i"].values

        # Precompute precedence sebagai array numpy (lebih cepat dari iterrows)
        self.prec_i    = precedence["i"].values.astype(int)    # successor
        self.prec_j    = precedence["j"].values.astype(int)    # predecessor
        self.prec_lag  = precedence["lag"].values.astype(float)
        self.prec_type = precedence["type"].values              # string array

        P = self.P
        xl = np.concatenate([np.full(P, x_min),   np.full(P, tau_min)])
        xu = np.concatenate([np.full(P, x_max),   np.full(P, tau_max)])

        super().__init__(
            n_var=2 * P,
            n_obj=1,
            n_ieq_constr=0,   # ← tidak ada kendala; s_i dijamin via forward pass
            xl=xl,
            xu=xu,
            **kwargs,
        )

    @staticmethod
    def _compute_x_max(alpha, x_min=1.0, threshold=0.5):
        x = x_min
        while x < 50:
            if (1.0 / x) ** alpha - (1.0 / (x + 1)) ** alpha < threshold:
                break
            x += 0.5
        return max(x, x_min + 1.0)

    def crash_duration(self, x_ik, tau_ik, D_base_ik):
        """D_{i,k} = D_base * (1/x)^alpha * (8/(8+tau))^beta"""
        return D_base_ik * (1.0 / x_ik) ** self.alpha * (8.0 / (8.0 + tau_ik)) ** self.beta

    def compute_durations(self, x_vec):
        """Hitung D_ik dan D_i dari vektor x_vec = [x_ik | tau_ik]."""
        P = self.P
        x_ik   = x_vec[0:P]
        tau_ik = x_vec[P:2 * P]
        D_ik = self.crash_duration(x_ik, tau_ik, self.D_base_ik)   # vectorized
        D_i = np.zeros(self.N)
        for i in range(self.N):
            for p in self.K_i.get(i, []):
                D_i[i] = max(D_i[i], D_ik[p])
        return D_ik, D_i

    def forward_pass(self, D_i):
        """
        CPM Forward Pass — hitung s_i yang konsisten dengan semua precedence.

        Algoritma: iterasi Bellman-Ford (konvergen pada DAG).
          Untuk setiap constraint:
            FS : s[i] = max(s[i], s[j] + D[j] + lag)
            FF : s[i] = max(s[i], s[j] + D[j] + lag - D[i])
            SS : s[i] = max(s[i], s[j]           + lag)
        di mana i = successor, j = predecessor.
        """
        s = np.zeros(self.N)

        for _ in range(self.N): 
            s_prev = s.copy()
            for idx in range(len(self.prec_i)):
                i   = self.prec_i[idx]
                j   = self.prec_j[idx]
                lag = self.prec_lag[idx]
                t   = self.prec_type[idx]

                if t == "FS":
                    candidate = s[j] + D_i[j] + lag
                elif t == "FF":
                    candidate = s[j] + D_i[j] + lag - D_i[i]
                elif t == "SS":
                    candidate = s[j] + lag
                else:
                    continue

                if candidate > s[i]:
                    s[i] = candidate

            if np.allclose(s, s_prev, atol=1e-8):
                break                    # konvergen

        return s, s + D_i

    def _evaluate(self, x, out, *args, **kwargs):
        P = self.P

        x_ik   = x[0:P]
        tau_ik = x[P:2 * P]

        # Crash durations (vectorized)
        D_ik = self.crash_duration(x_ik, tau_ik, self.D_base_ik)

        # Durasi per task
        D_i = np.zeros(self.N)
        for i in range(self.N):
            for p in self.K_i.get(i, []):
                D_i[i] = max(D_i[i], D_ik[p])

        # Jadwal via forward pass (selalu feasible)
        s, f = self.forward_pass(D_i)
        T_finish = np.max(f)

        # Biaya tenaga kerja
        labor_cost = np.sum(
            D_ik * x_ik * self.U_ik
            * (self.hours_per_day * self.r_k + tau_ik * self.r_k_ot)
        )

        penalty = self.c_late  * max(0.0, T_finish - self.T_max)
        bonus   = self.c_early * max(0.0, self.T_max - T_finish)

        out["F"] = labor_cost + penalty - bonus
        # out["G"] tidak diperlukan (n_ieq_constr=0)


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

    # ---- 2. Buat instance problem ----
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
        c_late=5000.0,
        c_early=2000.0,
        T_max=344,
        overtime_mult=1.5,
        hours_per_day=8,
    )

    # ---- 3. Info problem ----
    P = problem.P
    print(f"Tasks             : N = {N}")
    print(f"Resource pairs    : P = {P}  (pasangan i,k)")
    print(f"Precedence        : {len(precedence)}")
    print(f"n_var             : {problem.n_var}  = x_ik:{P} + tau_ik:{P}")
    # print(f"n_ieq_constr      : {problem.n_ieq_constr}  (semua precedence otomatis terpenuhi)")
    print(f"x_max             : {problem.x_max:.2f}")

    # ---- 6. GA Solver ----
    print("\n" + "=" * 60)
    print("MENGOPTIMALKAN JADWAL & BIAYA DENGAN GA SOLVER")
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

    # ---- 7. Hasil ----
    print("\n" + "=" * 60)
    print("HASIL OPTIMASI TERBAIK")
    print("=" * 60)

    if res.X is not None:
        x_opt   = res.X
        x_ik_opt   = x_opt[0:P]
        tau_ik_opt = x_opt[P:2 * P]

        D_ik_opt, D_i_opt = problem.compute_durations(x_opt)
        s_opt, f_opt      = problem.forward_pass(D_i_opt)
        makespan          = np.max(f_opt)

        labor_cost_opt = np.sum(
            D_ik_opt * x_ik_opt * problem.U_ik
            * (problem.hours_per_day * problem.r_k + tau_ik_opt * problem.r_k_ot)
        )
        penalty = problem.c_late  * max(0.0, makespan - problem.T_max)
        bonus   = problem.c_early * max(0.0, problem.T_max - makespan)
        total   = labor_cost_opt + penalty - bonus

        print(f"  Biaya Tenaga Kerja   = {labor_cost_opt:>15,.2f} USD")
        print(f"  Total Biaya Proyek   = {total:>15,.2f} USD")
        print(f"  Total Waktu Proyek   = {makespan:>10.2f} hari  (Batas: {problem.T_max} hari)")

        if bonus > 0:
            print(f"  Bonus diterima       = {bonus:>15,.2f} USD")
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