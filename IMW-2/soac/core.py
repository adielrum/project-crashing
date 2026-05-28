"""
Core implementation of the Spiral Optimization Algorithm with Clustering (SOAC).

Reference:
    Sumarti et al., "A method for finding numerical solutions to Diophantine
    equations using Spiral Optimization Algorithm with Clustering (SOAC)",
    Applied Soft Computing, 2023.
"""

import numpy as np
from scipy.stats import qmc
from scipy.spatial.distance import cdist


def get_rotation_matrix(n: int, theta: float) -> np.ndarray:
    """Compute the composite n-dimensional rotation matrix R^(n)(theta).

    The matrix is the product of all 2D rotation matrices R_{i,j}^(n)(theta)
    for 1 <= i < j <= n, each rotating on the (i,j) coordinate plane.

    Args:
        n: Dimensionality.
        theta: Rotation angle in radians.

    Returns:
        The n x n rotation matrix.
    """
    R = np.eye(n)
    for i in range(n - 1):
        for j in range(i + 1, n):
            R_ij = np.eye(n)
            R_ij[i, i] = np.cos(theta)
            R_ij[i, j] = -np.sin(theta)
            R_ij[j, i] = np.sin(theta)
            R_ij[j, j] = np.cos(theta)
            R = R @ R_ij
    return R


def generate_sobol_points(n: int, m: int, bounds: tuple) -> np.ndarray:
    """Generate m quasi-random points in [lower, upper]^n using a Sobol sequence.

    Args:
        n: Dimensionality.
        m: Number of points to generate.
        bounds: Tuple of (lower_bounds, upper_bounds), each an array of length n.

    Returns:
        Array of shape (m, n) with points in the specified bounds.
    """
    lower_bounds, upper_bounds = bounds
    power = int(np.ceil(np.log2(m)))
    sampler = qmc.Sobol(d=n, scramble=False)
    sample = sampler.random_base2(m=power)[:m]
    scaled = qmc.scale(sample, lower_bounds, upper_bounds)
    return scaled


class Cluster:
    """A cluster with a center point and radius."""

    def __init__(self, center: np.ndarray, radius: float):
        self.center = np.copy(center)
        self.radius = radius


def run_soac(
    n: int,
    bounds: tuple,
    params: dict,
    F,
    verbose: bool = False,
) -> list:
    """Run the SOAC algorithm to find integer solutions to a system of equations.

    Args:
        n: Number of variables (dimensionality).
        bounds: Tuple of (lower_bounds, upper_bounds), each an array of length n.
        params: Dictionary of algorithm hyperparameters:
            - m_cluster (int): Number of initial points for clustering phase.
            - k_cluster (int): Number of clustering iterations.
            - gamma (float): Fitness threshold for clustering.
            - epsilon (float): Tolerance for solution acceptance (1 - F(x) <= epsilon).
            - delta (float): Distance threshold for merging duplicate roots.
            - m (int): Number of points per cluster in spiral phase.
            - k_max (int): Number of spiral iterations per cluster.
            - r (float): Spiral contraction rate (0 < r < 1).
            - theta (float): Spiral rotation angle in radians.
        F: Fitness function mapping R^n -> [0, 1]. F(x) = 1 iff x is an exact solution.
        verbose: If True, print progress information.

    Returns:
        List of integer solution vectors (each a 1-D numpy array).
    """
    m_cluster = params['m_cluster']
    k_cluster = params['k_cluster']
    gamma = params['gamma']
    epsilon = params['epsilon']
    delta = params['delta']
    m = params['m']
    k_max = params['k_max']
    r = params['r']
    theta = params['theta']

    Rn = get_rotation_matrix(n, theta)
    Sn = r * Rn
    lower_bounds, upper_bounds = bounds

    # 1. Generate initial points using Sobol sequence
    x = generate_sobol_points(n, m_cluster, bounds)

    # Radius of first cluster
    rho_1 = 0.5 * np.min(np.abs(upper_bounds - lower_bounds))

    # Find initial center
    q_initial = np.round(x)
    q_initial = np.clip(q_initial, lower_bounds, upper_bounds)
    fit_initial = np.array([F(qi) for qi in q_initial])
    best_idx = np.argmax(fit_initial)
    x_star = np.copy(q_initial[best_idx])

    clusters = [Cluster(x_star, rho_1)]

    # Clustering Function CF(y)
    def CF(y):
        new_centers = []
        centers = np.array([c.center for c in clusters])
        dists = np.sum((y - centers) ** 2, axis=1)
        closest_idx = np.argmin(dists)
        C = clusters[closest_idx]

        xt = 0.5 * (y + C.center)

        y_round = np.clip(np.round(y), lower_bounds, upper_bounds)
        center_round = np.clip(np.round(C.center), lower_bounds, upper_bounds)
        xt_round = np.clip(np.round(xt), lower_bounds, upper_bounds)

        fy = F(y_round)
        fc = F(center_round)
        fxt = F(xt_round)

        if fxt < fy and fxt < fc:
            new_radius = np.linalg.norm(y - xt)
            clusters.append(Cluster(y, new_radius))
            new_centers.append(y)
        elif fxt > fy and fxt > fc:
            new_radius = np.linalg.norm(y - xt)
            clusters.append(Cluster(y, new_radius))
            new_centers.append(y)
            new_centers.extend(CF(xt))
        elif fy > fc:
            C.center = np.copy(y)
            C.radius = np.linalg.norm(y - xt)
            new_centers.append(y)

        return new_centers

    # Run clustering iterations
    for k in range(k_cluster):
        q = np.clip(np.round(x), lower_bounds, upper_bounds)
        fit = np.array([F(qi) for qi in q])

        valid_indices = np.where(fit > gamma)[0]
        if len(valid_indices) > 0:
            centers = np.array([c.center for c in clusters])
            dists_valid = cdist(x[valid_indices], centers, metric='sqeuclidean')
            min_dists = np.min(dists_valid, axis=1)

            for idx_in_valid, i in enumerate(valid_indices):
                if min_dists[idx_in_valid] > 1e-12:
                    new_c = CF(x[i])
                    for nc in new_c:
                        dists_to_new = np.sum((x[valid_indices] - nc) ** 2, axis=1)
                        min_dists = np.minimum(min_dists, dists_to_new)

        # Vectorized spiral transformation towards closest cluster centers
        centers = np.array([c.center for c in clusters])
        dists_p = cdist(x, centers, metric='sqeuclidean')
        closest_idx = np.argmin(dists_p, axis=1)
        x_p = centers[closest_idx]

        x = (x - x_p) @ Sn.T + x_p

    # Get rounded unique centers
    final_clusters = []
    for c in clusters:
        c_center_round = np.clip(np.round(c.center), lower_bounds, upper_bounds)
        dup = False
        for fc in final_clusters:
            if np.all(fc.center == c_center_round):
                dup = True
                break
        if not dup:
            final_clusters.append(Cluster(c_center_round, c.radius))

    # --- SPIRAL OPTIMIZATION PHASE ---
    candidates = []
    for c in final_clusters:
        cl_lower = np.maximum(lower_bounds, c.center - c.radius)
        cl_upper = np.minimum(upper_bounds, c.center + c.radius)

        if np.any(cl_upper > cl_lower):
            points = generate_sobol_points(n, m, (cl_lower, cl_upper))
            for k in range(k_max):
                q_pts = np.round(points)
                q_pts = np.clip(q_pts, cl_lower, cl_upper)
                fit_pts = np.array([F(qp) for qp in q_pts])
                b_idx = np.argmax(fit_pts)
                x_star_c = points[b_idx]

                points = (points - x_star_c) @ Sn.T + x_star_c

            q_final = np.round(x_star_c)
            q_final = np.clip(q_final, lower_bounds, upper_bounds)
            candidates.append(q_final)
        else:
            candidates.append(c.center)

    # --- SELECTION PHASE ---
    valid_candidates = []
    for cand in candidates:
        if (1.0 - F(cand)) <= epsilon:
            if not any(np.all(cand == vc) for vc in valid_candidates):
                valid_candidates.append(cand)

    keep = [True] * len(valid_candidates)
    for i in range(len(valid_candidates)):
        if not keep[i]:
            continue
        for j in range(i + 1, len(valid_candidates)):
            if not keep[j]:
                continue
            if np.linalg.norm(valid_candidates[i] - valid_candidates[j]) <= delta:
                if F(valid_candidates[i]) >= F(valid_candidates[j]):
                    keep[j] = False
                else:
                    keep[i] = False
                    break

    roots = [valid_candidates[i] for i in range(len(valid_candidates)) if keep[i]]
    return roots
