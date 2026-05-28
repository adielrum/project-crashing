"""
SOAC - Spiral Optimization Algorithm with Clustering

A Python library for finding numerical solutions to Diophantine equations
using the Spiral Optimization Algorithm with Clustering (SOAC).

Reference:
    Sumarti et al., "A method for finding numerical solutions to Diophantine
    equations using Spiral Optimization Algorithm with Clustering (SOAC)",
    Applied Soft Computing, 2023.

Example usage:
    >>> import numpy as np
    >>> from soac import run_soac
    >>> from soac.problems import F_1
    >>> bounds = (np.array([-50.0, -50.0]), np.array([50.0, 50.0]))
    >>> params = {
    ...     'm_cluster': 350, 'k_cluster': 10, 'gamma': 0.01,
    ...     'epsilon': 1e-7, 'delta': 0.1,
    ...     'm': 30, 'k_max': 10, 'r': 0.95, 'theta': np.pi / 4
    ... }
    >>> roots = run_soac(2, bounds, params, F_1)
    >>> print(f"Found {len(roots)} roots")
"""

from soac.core import run_soac, get_rotation_matrix, generate_sobol_points, Cluster

__all__ = [
    "run_soac",
    "get_rotation_matrix",
    "generate_sobol_points",
    "Cluster",
]
