"""
Model 2: Resource-Based Scheduling (Cobb-Douglas)
==================================================
Optimasi alokasi sumber daya manusia pada proyek konstruksi
menggunakan framework pymoo + GA.

Fitur utama:
  - current_day : hari ke berapa proyek saat ini berjalan (input pengguna).
                  Task yang sudah selesai sebelum current_day dikunci ke baseline.
                  Crashing hanya diterapkan pada task yang belum selesai.
  - s_i untuk task yang belum dikunci adalah variabel keputusan BEBAS, dibangun
    oleh Serial Schedule Generation Scheme (SSS, Hartmann 1998) berdasarkan
    priority list yang dipilih GA -- lihat ResourceBasedScheduling._serial_schedule.
  - Variabel keputusan GA: x_{i,k}, tau_{i,k}, dan priority_i untuk task belum
    selesai. Task yang sudah selesai dikunci ke x=1, tau=0 (tidak di-crash).
  - x_max ditentukan via diminishing returns relatif: berhenti saat marginal
    benefit < 50% dari manfaat pekerja tambahan pertama (threshold = 0.5 * delta_0).
  - tau_min = 0.0 sesuai slide (0 ≤ τ ≤ τ_max).
  - D_min_ratio: durasi crash tidak boleh < D_min_ratio × D_base per pasangan (i,k).
  - Kapasitas resource (U_max_k, dari data_resources.csv) ditegakkan SECARA
    STRUKTURAL oleh SSS: task ditempatkan pada waktu paling awal yang tidak
    melanggar kapasitas resource manapun yang dipakainya (Eq. 11), bukan lewat
    kendala G atau penalti biaya.
  - completion_fraction (opsional): task yang sedang berjalan pada current_day
    dapat dikunci start-nya ke baseline namun sisa workload-nya tetap
    di-crash, alih-alih hanya dua kategori selesai/belum-selesai.
"""

import os
import json
import argparse
import numpy as np
import pandas as pd
from pymoo.core.problem import ElementwiseProblem
from pymoo.core.callback import Callback
from pymoo.core.termination import Termination
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.termination import get_termination
from pymoo.termination.ftol import MultiObjectiveSpaceTermination, SingleObjectiveSpaceTermination
from pymoo.termination.robust import RobustTermination
import matplotlib.pyplot as plt
from multiprocessing.pool import ThreadPool

# ===========================================================================
# Path Helper
# ===========================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def data_path(filename):
    return os.path.join(BASE_DIR, "../data", filename)


# ===========================================================================
# Data Loader
# ===========================================================================

def load_data(path_tasks, path_precedence, path_assignments, path_resources=None):
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

    # ── Resource capacity U_max_k (Eq. 11 / Eq. 27) ─────────────────────
    # data_resources.csv carries the daily availability of every resource
    # *type* (resource_id). We merge it onto each (task, resource) pair so
    # the scheduling problem can enforce that simultaneous usage of a given
    # resource type never exceeds its availability. Without this file, the
    # model explicitly falls back to infinite capacity (old "unconstrained"
    # behaviour) rather than silently ignoring the constraint.
    if path_resources is None:
        path_resources = data_path("data_resources.csv")
    if os.path.exists(path_resources):
        resource_pool = pd.read_csv(path_resources)
        resources = resources.merge(
            resource_pool[["resource_id", "resource_availability"]],
            on="resource_id", how="left",
        )
        resources = resources.rename(columns={"resource_availability": "U_max_k"})
        if resources["U_max_k"].isna().any():
            missing = sorted(resources.loc[resources["U_max_k"].isna(), "resource_id"].unique().tolist())
            raise ValueError(
                f"resource_id(s) {missing} appear in assignments but have no "
                f"matching entry in {path_resources}; cannot enforce resource "
                f"capacity constraints for them."
            )
        resources["U_max_k"] = resources["U_max_k"].astype(float)
    else:
        resources["U_max_k"] = np.inf

    K_i = {}
    for row_idx, row in resources.iterrows():
        K_i.setdefault(int(row["i"]), []).append(row_idx)

    return tasks, precedence, resources, N, K_i


# ===========================================================================
# Problem Definition
# ===========================================================================

class MyCallback(Callback):

    def __init__(self) -> None:
        super().__init__()
        self.n_evals = []
        self.opt = []

    def notify(self, algorithm):
        self.n_evals.append(algorithm.evaluator.n_eval)
        self.opt.append(algorithm.opt[0].F)


class CombinedTermination(Termination):
    """Terminate when EITHER criterion is met (whichever fires first)."""

    def __init__(self, t1, t2):
        super().__init__()
        self.t1 = t1
        self.t2 = t2

    def _update(self, algorithm):
        return max(self.t1.update(algorithm), self.t2.update(algorithm))


class ResourceBasedScheduling(ElementwiseProblem):
    """
    Variabel Keputusan (n_var = 2P + N)
    -------------------------------------
    x[0:P]      = x_{i,k}     : crowding factor (pengali buruh)
    x[P:2P]     = tau_{i,k}   : lembur harian (jam/hari)
    x[2P:2P+N]  = priority_i  : activity-list priority per task, ∈ [0,1]

    Untuk task yang sudah selesai sebelum current_day:
      x_{i,k} dan tau_{i,k} dikunci ke 1 dan 0 di dalam _evaluate,
      sehingga D_ik = D_base_ik (tidak di-crash).

    Jadwal (s_i) dibangun oleh Serial Schedule Generation Scheme (SSS,
    Hartmann 1998 -- lihat §2.1.2/2.2.2 di paper) di _serial_schedule():
    priority_i menentukan urutan penjadwalan di antara task yang "ready"
    (semua predecessor-nya sudah terjadwal); tiap task ditempatkan pada
    waktu paling awal yang menghormati precedence (Eq. 9) DAN kapasitas
    resource (Eq. 11) terhadap task-task yang sudah ditempatkan sebelumnya.
    Dengan ini s_i benar-benar variabel keputusan bebas -- GA bisa
    menggeser start suatu task untuk menghindari bentrok resource, alih-alih
    s_i dihitung murni deterministik dari precedence saja.

    Kendala (n_ieq_constr = P [+1 jika deadline/budget])
    --------------------------------------------------------------------------
    G[p] = D_min_ik[p] - D_ik[p] ≤ 0   untuk setiap pasangan (i,k)
    → Hanya aktif untuk task yang belum selesai.

    Kapasitas resource (Eq. 11/27) TIDAK lagi berupa kendala G terpisah --
    ia sudah "built-in" pada cara SSS membangun s_i, sehingga setiap
    individu GA yang dievaluasi otomatis resource-feasible (kecuali ada
    pasangan (i,k) yang kebutuhan minimalnya sendirian sudah melebihi
    U_max_k, kasus data yang di-warn saat __init__).

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
                 alpha=0.7, beta=0.7,
                 x_min=1.0, x_max=None,
                 tau_min=0.0,
                 tau_max=4.0,
                 D_min_ratio=0.5,
                 c_late=5000.0, c_early=2000.0,
                 T_max=344,
                 current_day=0,        # ← input pengguna: hari mulai crashing
                 overtime_mult=1.5,
                 hours_per_day=8,
                 mode="bonus_penalty",
                 budget_limit=None,
                 completion_fraction=None,
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
        self.mode          = mode
        self.budget_limit  = budget_limit

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

        # ── Task sebagian selesai (partial completion, Eq. 14/30) ───────────
        # completion_fraction: dict opsional {task_id: p_i in (0,1)} untuk
        # task yang sedang berjalan pada current_day. Start-nya dikunci ke
        # baseline (pekerjaan sudah dimulai, tidak bisa digeser), tetapi sisa
        # workload-nya (fraksi 1 - p_i) tetap bisa di-crash seperti task yang
        # belum dimulai. Tanpa argumen ini perilaku model persis seperti
        # sebelumnya (hanya ada kategori selesai / belum selesai).
        completion_fraction = completion_fraction or {}
        self.completion_fraction = dict(completion_fraction)
        task_id_to_idx = {tid: idx for idx, tid in enumerate(tasks["task_id"])}

        self.partial_tasks = set()
        partial_frac_by_idx = {}
        if completion_fraction:
            for tid, p_i in completion_fraction.items():
                if not (0.0 < p_i < 1.0):
                    raise ValueError(
                        f"completion_fraction untuk task_id={tid} harus di (0,1), didapat {p_i}"
                    )
                idx = task_id_to_idx.get(tid)
                if idx is None:
                    raise ValueError(f"completion_fraction mereferensikan task_id={tid} yang tidak dikenal")
                if idx in self.completed_tasks:
                    continue  # sudah selesai penuh menurut baseline; abaikan
                self.partial_tasks.add(idx)
                partial_frac_by_idx[idx] = p_i
        elif current_day > 0:
            for i in range(N):
                if s_bl[i] < current_day < f_bl[i] and D_base_i[i] > 1e-9:
                    self.partial_tasks.add(i)
                    elapsed = current_day - s_bl[i]
                    partial_frac_by_idx[i] = elapsed / D_base_i[i]
        self.partial_completion = partial_frac_by_idx

        self.partial_pairs = set(
            p for p in range(self.P)
            if int(resources.loc[p, "i"]) in self.partial_tasks
        )

        # Task-task yang start-nya terkunci ke baseline: selesai ATAU sebagian selesai
        self.locked_start_tasks = self.completed_tasks | self.partial_tasks
        self.sorted_locked_start_tasks = sorted(self.locked_start_tasks, key=lambda t: (self.s_baseline[t], t))

        # Baseline efektif untuk crashing: task sebagian selesai hanya boleh
        # di-crash atas SISA workload-nya, W_{i,k} = W^(0)_{i,k} (1 - p_i)
        # (Eq. 14), yang secara linear mengecilkan durasi efektif d^(0)_{i,k}.
        self.D_base_ik_active = self.D_base_ik.copy()
        for p in self.partial_pairs:
            i_task = int(resources.loc[p, "i"])
            self.D_base_ik_active[p] = self.D_base_ik[p] * (1.0 - partial_frac_by_idx[i_task])
        self.D_min_ik = D_min_ratio * self.D_base_ik_active

        # ── Bounds variabel keputusan ───────────────────────────────────────
        # Semua P pasangan tetap masuk sebagai variabel agar indeks konsisten,
        # tetapi pasangan task-selesai diberi bounds xl=xu=nilai_baseline
        # sehingga GA tidak mengubahnya.
        P = self.P
        xl_x   = np.full(P, x_min)
        xu_x   = np.full(P, x_max)
        xl_tau = np.full(P, tau_min)
        xu_tau = np.full(P, tau_max)

        # ── Kapasitas resource (Eq. 11 / 27) ─────────────────────────────────
        # Dipakai oleh SSS (_serial_schedule) untuk mencari slot waktu paling
        # awal yang tidak melanggar kapasitas -- bukan lagi kendala G atau
        # penalti biaya, karena s_i sekarang benar-benar variabel bebas yang
        # bisa "digeser" SSS untuk menghindari bentrok resource.
        self.resource_id_of_pair = resources["resource_id"].values.astype(int)
        self.capacity_by_resource = {}
        for rid in np.unique(self.resource_id_of_pair):
            rows = resources.loc[resources["resource_id"] == rid, "U_max_k"]
            self.capacity_by_resource[int(rid)] = float(rows.iloc[0])

        # Kapasitas resource membatasi x_ik juga: bila x_ik * U_ik saja sudah
        # melebihi U_max_k, tidak ada penjadwalan (penggeseran s_i) yang bisa
        # menolong -- jadi batasi x_ik supaya SATU pasangan sendirian tidak
        # pernah melebihi kapasitas resource-nya.
        for p in range(P):
            rid = int(self.resource_id_of_pair[p])
            cap = self.capacity_by_resource.get(rid, np.inf)
            if np.isfinite(cap) and self.U_ik[p] > 1e-9:
                max_feasible_x = cap / self.U_ik[p]
                if max_feasible_x < xu_x[p]:
                    xu_x[p] = max(max_feasible_x, xl_x[p])

        # Task yang sudah selesai KUNCI agar tidak diubah GA
        for p in self.completed_pairs:
            xl_x[p]   = xu_x[p]   = 1.0   # x_ik dikunci ke 1 (tidak di-crash)
            xl_tau[p] = xu_tau[p] = 0.0   # tau_ik dikunci ke 0 (tidak lembur)

        # Priority list (Eq. bebas, Hartmann 1998 / §2.1.2 & 2.2.2 di paper):
        # N variabel tambahan yang menentukan urutan penjadwalan pada Serial
        # Schedule Generation Scheme (SSS) di bawah. Berbeda dari x_ik/tau_ik,
        # priority TIDAK mempunyai arti fisik -- hanya dipakai untuk memilih
        # task mana yang dijadwalkan lebih dulu di antara task-task yang
        # "ready" (semua predecessor-nya sudah terjadwal) pada suatu iterasi.
        xl_prio = np.zeros(N)
        xu_prio = np.ones(N)

        # ── Struktur graf precedence untuk SSS ───────────────────────────────
        # pred_edges[i]  = daftar (j, lag, type) dengan i sebagai successor
        # successors[j]  = daftar i dengan j sebagai predecessor
        # in_degree[i]   = banyak edge precedence yang menunjuk ke i
        self.pred_edges = {i: [] for i in range(N)}
        self.successors = {j: [] for j in range(N)}
        self.in_degree  = np.zeros(N, dtype=int)
        for idx in range(len(self.prec_i)):
            i, j = int(self.prec_i[idx]), int(self.prec_j[idx])
            lag, ptype = float(self.prec_lag[idx]), self.prec_type[idx]
            self.pred_edges[i].append((j, lag, ptype))
            self.successors[j].append(i)
            self.in_degree[i] += 1

        # Diagnostic murni: satu-satunya kasus yang TIDAK bisa diselesaikan
        # SSS (menggeser start tidak menolong) adalah bila kebutuhan minimum
        # SATU pasangan (i,k) sendirian (x=x_min) sudah melebihi kapasitas
        # resource-nya. Ini adalah masalah data, bukan penjadwalan.
        for p in range(self.P):
            rid = int(self.resource_id_of_pair[p])
            cap = self.capacity_by_resource.get(rid, np.inf)
            if np.isfinite(cap) and self.U_ik[p] * x_min > cap + 1e-9:
                print(f"[ResourceBasedScheduling] WARNING: pasangan (task_idx={self.res_task_idx[p]}, "
                      f"resource_id={rid}) butuh U_ik*x_min={self.U_ik[p]*x_min:.3f} sendirian, "
                      f"melebihi U_max_k={cap:.3f}. Tidak ada penjadwalan yang bisa memenuhi ini "
                      f"-- periksa data_resources.csv / data_assignments.csv.")

        n_obj = 2 if self.mode == "multiobjective" else 1
        n_constr = P
        if self.mode == "cost_with_deadline":
            n_constr += 1
        elif self.mode == "time_with_budget":
            n_constr += 1
            
        super().__init__(
            n_var=2 * P + N,
            n_obj=n_obj,
            n_ieq_constr=n_constr,   # D_min per pasangan (i,k) + possible deadline/budget constr
            xl=np.concatenate([xl_x, xl_tau, xl_prio]),
            xu=np.concatenate([xu_x, xu_tau, xu_prio]),
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
        """D_{i,k} = D_base_ik · (1/x)^α · (8/(8+τ))^β  [vectorized]

        Default D_base is D_base_ik_active, i.e. the baseline duration
        already reduced for partially-completed tasks (Eq. 14); this makes
        crashing act only on the *remaining* workload for such tasks.
        """
        if D_base is None:
            D_base = self.D_base_ik_active
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

    def _find_feasible_start(self, i, lb, D_ik, x_ik, resource_intervals):
        """
        Cari waktu mulai paling awal ≥ lb untuk task i yang tidak melanggar
        kapasitas resource manapun yang dipakainya, terhadap interval-interval
        yang SUDAH ditempatkan di resource_intervals. Standar "insertion"
        step dari serial SGS: coba lb, dan bila bentrok, loncat ke waktu
        selesainya interval yang bentrok, ulangi.
        """
        pairs = self.K_i.get(i, [])
        if not pairs:
            return lb

        # Defensive guard: if a pair's own demand ALREADY exceeds its
        # resource's capacity regardless of any other scheduled task (should
        # be structurally impossible given the x_ik upper bound derived from
        # capacity in __init__, but we don't want a bounds edge-case to ever
        # turn into a runaway search below), just skip enforcing that pair's
        # capacity rather than loop toward a meaningless huge start time.
        unenforceable = set()
        for p in pairs:
            rid = int(self.resource_id_of_pair[p])
            cap = self.capacity_by_resource.get(rid, np.inf)
            if np.isfinite(cap) and x_ik[p] * self.U_ik[p] > cap + 1e-6:
                unenforceable.add(p)
                print(f"[ResourceBasedScheduling] WARNING: task_idx={i} pair={p} "
                      f"demand={x_ik[p]*self.U_ik[p]:.3f} alone exceeds U_max_k={cap:.3f} "
                      f"for resource_id={rid}; ignoring capacity for this pair.")

        s_candidate = lb
        max_iter = len(pairs) * 200 + 200  # generous, dijamin berhenti (lihat komentar di bawah)
        for _ in range(max_iter):
            next_jump = None
            feasible = True
            for p in pairs:
                if p in unenforceable:
                    continue
                rid = int(self.resource_id_of_pair[p])
                cap = self.capacity_by_resource.get(rid, np.inf)
                if not np.isfinite(cap):
                    continue
                dur = D_ik[p]
                demand = x_ik[p] * self.U_ik[p]
                end_candidate = s_candidate + dur
                intervals = resource_intervals.get(rid, [])
                overlapping = [
                    (ivs, ive, ivd) for ivs, ive, ivd in intervals
                    if s_candidate < ive and ivs < end_candidate
                ]
                if not overlapping:
                    if demand - cap > 1e-6:
                        feasible = False
                        if next_jump is None or end_candidate < next_jump:
                            next_jump = end_candidate
                    continue

                instants = [s_candidate]
                for ivs, ive, ivd in overlapping:
                    if s_candidate < ivs < end_candidate:
                        instants.append(ivs)
                for t in instants:
                    usage = demand
                    for ivs, ive, ivd in overlapping:
                        if ivs <= t < ive:
                            usage += ivd
                    if usage - cap > 1e-6:
                        feasible = False
                        min_end = end_candidate
                        has_overlap = False
                        for ivs, ive, ivd in overlapping:
                            if ivs <= t < ive:
                                has_overlap = True
                                if ive < min_end:
                                    min_end = ive
                        candidate_jump = min_end if has_overlap else end_candidate
                        if next_jump is None or candidate_jump < next_jump:
                            next_jump = candidate_jump
                        break
            if feasible:
                return s_candidate
            s_candidate = next_jump if next_jump is not None else s_candidate + 1.0

        return s_candidate  # fallback, praktis tidak pernah tercapai

    def _serial_schedule(self, D_i, D_ik, x_ik, priority):
        """
        Serial Schedule Generation Scheme (SSS, Hartmann 1998; lihat §2.1.2
        dan §2.2.2 paper). GA memilih `priority` (Eq. bebas per task); SSS
        membangun jadwal dengan menjadwalkan task satu per satu -- dipilih
        dari himpunan task yang "ready" (semua predecessor sudah terjadwal)
        berdasarkan priority tertinggi -- pada waktu paling awal yang
        menghormati precedence (Eq. 9) DAN kapasitas resource (Eq. 11)
        terhadap task-task yang sudah ditempatkan.

        Task yang selesai/sebagian selesai (locked_start_tasks) ditempatkan
        lebih dulu pada s_baseline-nya (fakta historis, tidak bisa berubah),
        diurutkan berdasarkan s_baseline agar konsisten secara precedence.
        """
        N = self.N
        s = np.empty(N)
        f = np.empty(N)
        scheduled = np.zeros(N, dtype=bool)
        remaining_indeg = self.in_degree.copy()
        resource_intervals = {rid: [] for rid in self.capacity_by_resource.keys()}

        def _place(i, s_i):
            s[i] = s_i
            if i in self.partial_tasks:
                elapsed = self.current_day - self.s_baseline[i]
                f[i] = s_i + elapsed + D_i[i]
            else:
                f[i] = s_i + D_i[i]
            scheduled[i] = True
            for p in self.K_i.get(i, []):
                rid = int(self.resource_id_of_pair[p])
                if i in self.partial_tasks:
                    start_r = float(self.current_day)
                else:
                    start_r = s_i
                resource_intervals.setdefault(rid, []).append(
                    (start_r, start_r + D_ik[p], x_ik[p] * self.U_ik[p])
                )
            for succ in self.successors[i]:
                remaining_indeg[succ] -= 1

        # Fase 1: task yang start-nya terkunci (selesai/sebagian selesai),
        # ditempatkan dulu pada s_baseline, dalam urutan waktu historisnya.
        for i in self.sorted_locked_start_tasks:
            _place(i, self.s_baseline[i])

        # Fase 2: SSS berbasis priority untuk task yang belum dikunci.
        ready_list = [i for i in range(N) if not scheduled[i] and remaining_indeg[i] == 0]
        while ready_list:
            best_idx = 0
            best_p = priority[ready_list[0]]
            for idx in range(1, len(ready_list)):
                p = priority[ready_list[idx]]
                if p > best_p:
                    best_p = p
                    best_idx = idx
            i = ready_list.pop(best_idx)

            lb = float(self.current_day)
            for (j, lag, ptype) in self.pred_edges[i]:
                if ptype == "FS":   cand = f[j] + lag
                elif ptype == "FF": cand = f[j] + lag - D_i[i]
                elif ptype == "SS": cand = s[j] + lag
                else: continue
                if cand > lb:
                    lb = cand

            s_i = self._find_feasible_start(i, lb, D_ik, x_ik, resource_intervals)
            _place(i, s_i)

            for succ in self.successors[i]:
                if remaining_indeg[succ] == 0 and not scheduled[succ]:
                    ready_list.append(succ)

        return s, f

    def _evaluate(self, x, out, *args, **kwargs):
        P, N = self.P, self.N

        x_ik     = x[0:P].copy()
        tau_ik   = x[P:2 * P].copy()
        priority = x[2 * P:2 * P + N]

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

        s, f = self._serial_schedule(D_i, D_ik, x_ik, priority)
        T_finish = float(np.max(f))

        labor_cost = float(np.sum(
            D_ik * x_ik * self.U_ik
            * (self.hours_per_day * self.r_k + tau_ik * self.r_k_ot)
        ))

        penalty = self.c_late  * max(0.0, T_finish - self.T_max)
        bonus   = self.c_early * max(0.0, self.T_max - T_finish)

        if self.mode == "bonus_penalty":
            out["F"] = labor_cost + penalty - bonus
        elif self.mode == "cost_with_deadline":
            out["F"] = labor_cost
        elif self.mode == "time_with_budget":
            out["F"] = T_finish
        elif self.mode == "multiobjective":
            out["F"] = [T_finish, labor_cost]

        # Kendala D_min: aktif hanya untuk task belum selesai. Kapasitas
        # resource (Eq. 11) TIDAK lagi berupa kendala G -- sudah ditegakkan
        # secara struktural oleh _serial_schedule di atas.
        G = self.D_min_ik - D_ik
        for p in self.completed_pairs:
            G[p] = 0.0   # task selesai selalu feasible, tidak dihitung

        if self.mode == "cost_with_deadline":
            G = np.append(G, T_finish - self.T_max)
        elif self.mode == "time_with_budget":
            G = np.append(G, labor_cost - self.budget_limit)
            
        out["G"] = G

    def extract_solution(self, x_vec):
        return extract_solution(self, x_vec)


def extract_solution(problem, x_vec):
    """
    Extract and post-process a solution vector from the optimizer.

    Returns a dict with keys: x_ik, tau_ik, D_ik, D_i, s, f,
    makespan, labor_cost, penalty, bonus, total_cost.
    """
    P, N = problem.P, problem.N
    x_ik = x_vec[0:P].copy()
    tau_ik = x_vec[P:2 * P].copy()
    priority = x_vec[2 * P:2 * P + N]

    for p in problem.completed_pairs:
        x_ik[p] = 1.0
        tau_ik[p] = 0.0

    D_ik, D_i = problem.compute_durations(x_vec)
    for i in problem.completed_tasks:
        D_i[i] = problem.D_base_i[i]

    s, f = problem._serial_schedule(D_i, D_ik, x_ik, priority)
    for i in range(N):
        D_i[i] = f[i] - s[i]
    for p in range(P):
        i_task = int(problem.res_task_idx[p])
        if i_task in problem.partial_tasks:
            elapsed = problem.current_day - problem.s_baseline[i_task]
            D_ik[p] = D_ik[p] + elapsed
            
    makespan = float(np.max(f))

    labor_cost = float(np.sum(
        D_ik * x_ik * problem.U_ik
        * (problem.hours_per_day * problem.r_k + tau_ik * problem.r_k_ot)
    ))

    penalty = problem.c_late * max(0.0, makespan - problem.T_max)
    bonus = problem.c_early * max(0.0, problem.T_max - makespan)
    total_cost = labor_cost + penalty - bonus

    return {
        "x_ik": x_ik,
        "tau_ik": tau_ik,
        "D_ik": D_ik,
        "D_i": D_i,
        "s": s,
        "f": f,
        "makespan": makespan,
        "labor_cost": labor_cost,
        "penalty": penalty,
        "bonus": bonus,
        "total_cost": total_cost,
    }


def generate_gantt_comparison_plot(tasks, s_bl, f_bl, s_opt, f_opt, current_day, output_path):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    import os

    N = len(tasks)
    baseline_order = sorted(range(N), key=lambda i: (s_bl[i], f_bl[i], i))
    optimized_order = sorted(range(N), key=lambda i: (s_opt[i], f_opt[i], i))

    def get_color(i, end_day):
        if end_day <= current_day:
            return "#95a5a6"  # Gray for completed tasks
        
        baseline_idx = baseline_order.index(i)
        optimized_idx = optimized_order.index(i)
        order_changed = baseline_idx != optimized_idx
        
        crashed = (f_opt[i] - s_opt[i]) < (f_bl[i] - s_bl[i] - 1e-5)
        
        if order_changed and crashed:
            return "#e67e22"  # Orange (crashed & order changed)
        elif order_changed and not crashed:
            return "#2ecc71"  # Green (order changed)
        elif not order_changed and crashed:
            return "#e74c3c"  # Red (crashed)
        else:
            return "#3498db"  # Blue (normal)
    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(12, max(12, 0.7 * N)))

    # Plot baseline
    for idx, i in enumerate(baseline_order):
        name = tasks.iloc[i]["task_name"]
        start = s_bl[i]
        duration = f_bl[i] - s_bl[i]
        end = f_bl[i]
        color = "#95a5a6" if end <= current_day else "#3498db"
        ax1.barh(idx, duration, left=start, height=0.6, color=color, edgecolor="black", linewidth=0.5)
        if duration > 2:
            ax1.text(start + duration / 2, idx, f"{duration:.1f}", va="center", ha="center", color="white", fontsize=8, weight="bold")
        else:
            ax1.text(start + duration + 0.5, idx, f"{duration:.1f}", va="center", ha="left", color="black", fontsize=8)

    ax1.set_title("Original Schedule (Baseline)", fontsize=14, pad=15)
    ax1.set_xlabel("Project Day", fontsize=12)
    ax1.set_yticks(range(N))
    ax1.set_yticklabels([tasks.iloc[i]["task_name"] for i in baseline_order], fontsize=8)
    ax1.invert_yaxis()
    ax1.grid(axis="x", linestyle="--", alpha=0.5)
    ax1.axvline(x=current_day, color="#2c3e50", linestyle="--", linewidth=1.5)

    # Plot optimized
    for idx, i in enumerate(optimized_order):
        name = tasks.iloc[i]["task_name"]
        start = s_opt[i]
        duration = f_opt[i] - s_opt[i]
        end = f_opt[i]
        color = get_color(i, end)
        ax2.barh(idx, duration, left=start, height=0.6, color=color, edgecolor="black", linewidth=0.5)
        if duration > 2:
            ax2.text(start + duration / 2, idx, f"{duration:.1f}", va="center", ha="center", color="white", fontsize=8, weight="bold")
        else:
            ax2.text(start + duration + 0.5, idx, f"{duration:.1f}", va="center", ha="left", color="black", fontsize=8)

    ax2.set_title("Crashed/Optimized Cobb-Douglas Schedule", fontsize=14, pad=15)
    ax2.set_xlabel("Project Day", fontsize=12)
    ax2.set_yticks(range(N))
    ax2.set_yticklabels([tasks.iloc[i]["task_name"] for i in optimized_order], fontsize=8)
    ax2.invert_yaxis()
    ax2.grid(axis="x", linestyle="--", alpha=0.5)
    ax2.axvline(x=current_day, color="#2c3e50", linestyle="--", linewidth=1.5)
    
    opt_end_date = np.max(f_opt)
    ax2.axvline(x=opt_end_date, color="red", linestyle="--", linewidth=1.5)

    legend_elements = [
        Patch(facecolor="#95a5a6", edgecolor="black", label="Completed (Finished <= Current Day)"),
        Patch(facecolor="#3498db", edgecolor="black", label="Normal (No Crash, Order Unchanged)"),
        Patch(facecolor="#e74c3c", edgecolor="black", label="Crashed (Order Unchanged)"),
        Patch(facecolor="#2ecc71", edgecolor="black", label="Normal (No Crash, Order Changed)"),
        Patch(facecolor="#e67e22", edgecolor="black", label="Crashed & Order Changed"),
        Line2D([0], [0], color="#2c3e50", linestyle="--", linewidth=1.5, label=f"Current Day (Day {current_day})"),
        Line2D([0], [0], color="red", linestyle="--", linewidth=1.5, label=f"Project End Date (Day {opt_end_date:.1f})"),
    ]
    fig.legend(handles=legend_elements, loc="lower center", bbox_to_anchor=(0.5, -0.05), ncol=4, fontsize=9)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved Gantt chart comparison plot to: {output_path}")


def generate_interactive_gantt_html(
    tasks, resources, s_bl, f_bl, s_opt, f_opt, x_ik_opt, tau_ik_opt, D_ik_opt, D_i_opt,
    current_day, T_max, output_path
):
    import plotly.graph_objects as go
    from collections import defaultdict
    import os

    N = len(tasks)
    P = len(resources)
    
    # Map task index to its assignments' optimized x and tau
    task_crashes = defaultdict(list)
    for p in range(P):
        tid = int(resources.loc[p, "i"])
        tname = tasks.iloc[tid]["task_name"]
        x_val = float(x_ik_opt[p])
        tau_val = float(tau_ik_opt[p])
        res_name = resources.loc[p, "resource_name"] if "resource_name" in resources else f"Resource_{resources.loc[p, 'resource_id']}"
        
        if x_val > 1.0 + 1e-5 or tau_val > 0.0 + 1e-5:
            # Calculate duration saved for this resource
            d_base = float(resources.loc[p, "D_base_ik"])
            d_crashed = float(D_ik_opt[p])
            saved = d_base - d_crashed
            
            task_crashes[tid].append({
                "resource": res_name,
                "x": round(x_val, 2),
                "tau": round(tau_val, 1),
                "saved": round(saved, 2)
            })

    # Sort tasks by baseline start time
    baseline_order = sorted(range(N), key=lambda i: (s_bl[i], f_bl[i], i))
    task_labels = [f"{tasks.iloc[i]['task_id']}: {tasks.iloc[i]['task_name']}" for i in baseline_order]

    fig = go.Figure()
    legend_shown = set()

    for i in baseline_order:
        tname = tasks.iloc[i]["task_name"]
        label = f"{tasks.iloc[i]['task_id']}: {tname}"
        sv, fv = s_opt[i], f_opt[i]
        
        is_done = fv <= current_day
        is_crashed = len(task_crashes[i]) > 0
        
        if is_done:
            group, color = "Completed", "#95a5a6"
        elif is_crashed:
            group, color = "Crashed", "#ef4444"
        else:
            group, color = "Active (normal)", "#3b82f6"

        info = [
            f"<b>{label}</b>",
            f"Day {sv:.1f} &rarr; Day {fv:.1f} (Duration: {fv-sv:.2f}d)"
        ]
        
        if is_crashed:
            info.append("<br><b>Cobb-Douglas Crashing:</b>")
            for entry in task_crashes[i]:
                info.append(
                    f"&nbsp;&nbsp;{entry['resource']}: x={entry['x']}, &tau;={entry['tau']}h (saved {entry['saved']:.1f}d)"
                )
        
        text = "<br>".join(info)

        # Plotly Scatter lines for Gantt bars
        fig.add_trace(go.Scatter(
            x=[sv, fv], y=[label, label],
            mode='lines',
            line=dict(color=color, width=14),
            name=group,
            legendgroup=group,
            showlegend=(group not in legend_shown),
            hovertemplate=text + "<extra></extra>"
        ))
        legend_shown.add(group)

    # Vertical lines for current day and target deadline
    fig.add_shape(type="line", x0=current_day, x1=current_day, y0=0, y1=1, yref="paper",
                  line=dict(color="black", width=2, dash="dash"))
    fig.add_shape(type="line", x0=T_max, x1=T_max, y0=0, y1=1, yref="paper",
                  line=dict(color="blue", width=2, dash="dot"))
    
    fig.add_annotation(x=current_day, y=1.02, yref="paper", showarrow=False,
                       text=f"Current Day {current_day}", font=dict(color="black"))
    fig.add_annotation(x=T_max, y=-0.05, yref="paper", showarrow=False,
                       text=f"Target Deadline Day {T_max}", font=dict(color="blue"))

    fig.update_layout(
        title=f"Crashed Cobb-Douglas Gantt Chart (Current Day: {current_day}, Makespan: {np.max(f_opt):.2f}d)",
        xaxis_title="Project Day",
        yaxis_title="Task",
        height=max(600, 18 * N),
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=300, r=40, t=80, b=60),
    )
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=8),
                     categoryorder="array", categoryarray=task_labels)

    html = fig.to_html(include_plotlyjs='cdn', full_html=True)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as fh:
        fh.write(html)
    print(f"Saved interactive HTML Gantt chart to: {output_path}")


def save_solution_json(
    tasks, resources, precedence, problem,
    x_opt, x_ik_opt, tau_ik_opt, D_ik_opt, D_i_opt, s_opt, f_opt,
    current_day, T_max, makespan, labor_cost, total_project_cost,
    output_path
):
    import json
    import os
    
    crash_plan = {}
    P = len(resources)
    N = len(tasks)
    
    for p in range(P):
        tid = int(resources.loc[p, "i"])
        tname = tasks.iloc[tid]["task_name"]
        x_val = float(x_ik_opt[p])
        tau_val = float(tau_ik_opt[p])
        
        if x_val > 1.0 + 1e-5 or tau_val > 0.0 + 1e-5:
            r_k = float(problem.r_k[p])
            U_ik = float(problem.U_ik[p])
            W_ik = float(problem.W_ik[p])
            
            c_chosen = float(D_ik_opt[p] * x_val * U_ik * (problem.hours_per_day * r_k + tau_val * problem.r_k_ot[p]))
            c_base = float(problem.D_base_ik[p] * 1.0 * U_ik * (problem.hours_per_day * r_k + 0.0 * problem.r_k_ot[p]))
            cost_delta = c_chosen - c_base
            
            d_base = float(problem.D_base_ik[p])
            d_crashed = float(D_ik_opt[p])
            saved = d_base - d_crashed
            
            res_name = resources.loc[p, "resource_name"] if "resource_name" in resources else f"Resource_{resources.loc[p, 'resource_id']}"
            crash_plan.setdefault(tname, []).append({
                "resource": res_name,
                "x": round(x_val, 4),
                "tau": round(tau_val, 4),
                "cost_delta": round(cost_delta, 2),
                "duration_saved": round(saved, 2),
            })
            
    schedule = []
    for i in range(N):
        task_id = int(tasks.iloc[i]["task_id"])
        task_name = tasks.iloc[i]["task_name"]
        
        status = "completed" if f_opt[i] <= current_day else ("in_progress" if s_opt[i] <= current_day < f_opt[i] else "not_started")
        
        assignments = []
        for p in problem.K_i.get(i, []):
            res_name = resources.loc[p, "resource_name"] if "resource_name" in resources else f"Resource_{resources.loc[p, 'resource_id']}"
            assignments.append({
                "resource_name": res_name,
                "baseline_duration": float(problem.D_base_ik[p]),
                "optimized_duration": float(D_ik_opt[p]),
                "x": float(x_ik_opt[p]),
                "tau": float(tau_ik_opt[p]),
            })
            
        schedule.append({
            "task_id": task_id,
            "task_name": task_name,
            "baseline_start": float(problem.s_baseline[i]),
            "baseline_finish": float(problem.f_baseline[i]),
            "baseline_duration": float(problem.D_base_i[i]),
            "optimized_start": float(s_opt[i]),
            "optimized_finish": float(f_opt[i]),
            "optimized_duration": float(D_i_opt[i]),
            "status": status,
            "assignments": assignments
        })
        
    result_data = {
        "success": True,
        "solver": "pymoo_GA",
        "current_day": current_day,
        "target_day": T_max,
        "baseline_makespan": float(np.max(problem.f_baseline)),
        "makespan": float(makespan),
        "makespan_reduction": float(np.max(problem.f_baseline) - makespan),
        "labor_cost": float(labor_cost),
        "total_project_cost": float(total_project_cost),
        "crash_plan": crash_plan,
        "schedule": schedule
    }
    
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(result_data, fh, indent=2)
    print(f"Wrote solution JSON to: {output_path}")


# ===========================================================================
# Unified Solver API
# ===========================================================================

def extract_solution(problem, x_vec):
    """
    Extract and post-process a solution vector from the optimizer.

    Returns a dict with keys: x_ik, tau_ik, D_ik, D_i, s, f,
    makespan, labor_cost, penalty, bonus, total_cost.
    """
    P, N = problem.P, problem.N
    x_ik = x_vec[0:P].copy()
    tau_ik = x_vec[P:2 * P].copy()
    priority = x_vec[2 * P:2 * P + N]

    for p in problem.completed_pairs:
        x_ik[p] = 1.0
        tau_ik[p] = 0.0

    D_ik, D_i = problem.compute_durations(x_vec)
    for i in problem.completed_tasks:
        D_i[i] = problem.D_base_i[i]

    s, f = problem._serial_schedule(D_i, D_ik, x_ik, priority)
    makespan = float(np.max(f))

    labor_cost = float(np.sum(
        D_ik * x_ik * problem.U_ik
        * (problem.hours_per_day * problem.r_k + tau_ik * problem.r_k_ot)
    ))

    penalty = problem.c_late * max(0.0, makespan - problem.T_max)
    bonus = problem.c_early * max(0.0, problem.T_max - makespan)
    total_cost = labor_cost + penalty - bonus

    return {
        "x_ik": x_ik,
        "tau_ik": tau_ik,
        "D_ik": D_ik,
        "D_i": D_i,
        "s": s,
        "f": f,
        "makespan": makespan,
        "labor_cost": labor_cost,
        "penalty": penalty,
        "bonus": bonus,
        "total_cost": total_cost,
    }


def build_termination(tol=0.005, period=20, max_gen=10000, is_moo=True):
    """
    Build a robust termination criterion:
      - Convergence: change/eps < tol for `period` consecutive iterations
      - Safety cap: max_gen generations
    Whichever triggers first stops the optimization.
    """
    t_max_gen = get_termination("n_gen", max_gen)
    eff_tol = max(tol, 1e-5)
    if not is_moo:
        t_convergence = RobustTermination(
            SingleObjectiveSpaceTermination(tol=eff_tol, n_skip=1), period=period
        )
        return CombinedTermination(t_convergence, t_max_gen)
        
    t_convergence = RobustTermination(
        MultiObjectiveSpaceTermination(tol=eff_tol, n_skip=1), period=period
    )
    return CombinedTermination(t_convergence, t_max_gen)


def solve(problem, pop_size=200, seed=42, verbose=True,
          max_gen=10000, tol=0.005, period=20, callback=None):
    """
    Unified solver for ResourceBasedScheduling problems.

    Automatically selects GA (single-objective) or NSGA2 (multiobjective)
    based on problem.mode.

    Termination: convergence eps < tol for `period` iterations,
                 OR max_gen generations (whichever fires first).

    Returns:
      - Single-objective: dict from extract_solution() with extra keys
        'pymoo_result' and 'callback', or None if infeasible.
      - Multiobjective: pymoo Result object (with .F, .X, .callback).
    """
    is_moo = problem.mode == "multiobjective"

    if is_moo:
        algorithm = NSGA2(
            pop_size=pop_size,
            crossover=SBX(prob=0.9, eta=15),
            mutation=PM(eta=20),
            eliminate_duplicates=True,
        )
    else:
        algorithm = GA(
            pop_size=pop_size,
            crossover=SBX(prob=0.9, eta=15),
            mutation=PM(eta=20),
            eliminate_duplicates=True,
        )

    termination = build_termination(tol=tol, period=period, max_gen=max_gen, is_moo=is_moo)

    if callback is None:
        callback = MyCallback()
        
    n_threads = int(os.environ.get("PYMOO_THREADS", 4))
    pool = ThreadPool(processes=n_threads) if n_threads > 1 else None
    starmap_arg = pool.starmap if pool is not None else None

    res = minimize(
        problem, algorithm, termination,
        seed=seed, callback=callback, verbose=verbose, starmap=starmap_arg,
    )

    if is_moo:
        res.callback = callback
        return res

    if res.X is None:
        return None

    solution = extract_solution(problem, res.X)
    solution["pymoo_result"] = res
    solution["callback"] = callback
    return solution


def parse_args():
    import argparse
    parser = argparse.ArgumentParser(
        description="Solve dynamic project crashing under Cobb-Douglas with pymoo GA"
    )
    parser.add_argument(
        "--path-tasks",
        default=data_path("data_tasks.csv"),
        help="Path to tasks CSV"
    )
    parser.add_argument(
        "--path-precedence",
        default=data_path("data_precedence.csv"),
        help="Path to precedence CSV"
    )
    parser.add_argument(
        "--path-assignments",
        default=data_path("data_assignments.csv"),
        help="Path to assignments CSV"
    )
    parser.add_argument(
        "--current-day",
        type=int,
        default=0,
        help="Current execution day"
    )
    parser.add_argument(
        "--output-json",
        default=os.path.join(BASE_DIR, "../outputs/resource-based/cobb_solution.json"),
        help="Path to output solution JSON"
    )
    parser.add_argument(
        "--output-gantt",
        default=os.path.join(BASE_DIR, "../outputs/resource-based/cobb_gantt.png"),
        help="Path to output Gantt chart PNG"
    )
    parser.add_argument(
        "--output-gantt-html",
        default=os.path.join(BASE_DIR, "../outputs/resource-based/cobb_gantt.html"),
        help="Path to output interactive Gantt chart HTML"
    )
    parser.add_argument(
        "--pop-size",
        type=int,
        default=500,
        help="Population size for GA"
    )
    parser.add_argument(
        "--n-gen",
        type=int,
        default=1000,
        help="Number of generations for GA"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # ---- 1. Muat data ----
    tasks, precedence, resources, N, K_i = load_data(
        path_tasks=args.path_tasks,
        path_precedence=args.path_precedence,
        path_assignments=args.path_assignments,
    )

    CURRENT_DAY = args.current_day

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
    print(f"n_var             : {problem.n_var}  = x_ik:{P} + tau_ik:{P} + priority:{N}")
    print(f"n_ieq_constr      : {problem.n_ieq_constr}  (D_min per pasangan i,k)")
    print(f"x_max             : {problem.x_max:.2f}")

    # ---- 5. Solve ----
    print(f"\nCRASHING DARI HARI KE-{CURRENT_DAY} HINGGA T_MAX={problem.T_max}")

    solution = solve(problem, pop_size=args.pop_size, seed=42, verbose=True)

    if solution is None:
        print("GA tidak menemukan solusi. Coba naikkan pop_size atau n_gen.")
    else:
        # Convergence plot
        cb = solution["callback"]
        if cb.n_evals:
            plt.title("Convergence")
            plt.plot(cb.n_evals, cb.opt, "--")
            plt.yscale("log")
            plt.xlabel("Number of Evaluations")
            plt.ylabel("Best Objective Value")
            conv_path = os.path.join(os.path.dirname(args.output_json), "cobb_convergence.png")
            os.makedirs(os.path.dirname(conv_path) or ".", exist_ok=True)
            plt.savefig(conv_path, dpi=150, bbox_inches="tight")
            plt.close()

        # ---- 6. Hasil ----
        makespan = solution["makespan"]
        labor_cost = solution["labor_cost"]
        total = solution["total_cost"]

        print(f"\n{'='*60}")
        print("HASIL OPTIMASI TERBAIK")
        print(f"{'='*60}")
        print(f"  Biaya Tenaga Kerja   = {labor_cost:>15,.2f} USD")
        print(f"  Total Biaya Proyek   = {total:>15,.2f} USD")
        print(f"  Baseline makespan    = {np.max(problem.f_baseline):>10.1f} hari")
        print(f"  Optimized makespan   = {makespan:>10.2f} hari  "
              f"(Batas: {problem.T_max} hari)")
        reduction = np.max(problem.f_baseline) - makespan
        print(f"  Reduksi durasi       = {reduction:>10.1f} hari  "
              f"({reduction / np.max(problem.f_baseline) * 100:.1f}%)")

        save_solution_json(
            tasks=tasks, resources=resources, precedence=precedence, problem=problem,
            x_opt=solution["pymoo_result"].X,
            x_ik_opt=solution["x_ik"], tau_ik_opt=solution["tau_ik"],
            D_ik_opt=solution["D_ik"], D_i_opt=solution["D_i"],
            s_opt=solution["s"], f_opt=solution["f"],
            current_day=CURRENT_DAY, T_max=problem.T_max,
            makespan=makespan, labor_cost=labor_cost, total_project_cost=total,
            output_path=args.output_json,
        )

        try:
            generate_gantt_comparison_plot(
                tasks=tasks, s_bl=problem.s_baseline, f_bl=problem.f_baseline,
                s_opt=solution["s"], f_opt=solution["f"],
                current_day=CURRENT_DAY, output_path=args.output_gantt,
            )
        except Exception as e:
            print(f"[warning] Static Gantt chart failed: {e}")

        try:
            generate_interactive_gantt_html(
                tasks=tasks, resources=resources,
                s_bl=problem.s_baseline, f_bl=problem.f_baseline,
                s_opt=solution["s"], f_opt=solution["f"],
                x_ik_opt=solution["x_ik"], tau_ik_opt=solution["tau_ik"],
                D_ik_opt=solution["D_ik"], D_i_opt=solution["D_i"],
                current_day=CURRENT_DAY, T_max=problem.T_max,
                output_path=args.output_gantt_html,
            )
        except Exception as e:
            print(f"[warning] Interactive Gantt chart failed: {e}")