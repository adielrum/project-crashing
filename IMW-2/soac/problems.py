"""
Benchmark Diophantine equation problems from the SOAC paper.

Each fitness function maps R^n -> [0, 1] where F(x) = 1 iff x is an exact
integer solution to the corresponding equation(s).
"""

import numpy as np


def F_1(x):
    """Problem 1: 15x + 11y = 12."""
    val = 15 * x[0] + 11 * x[1] - 12
    return 1.0 / (1.0 + abs(val))


def F_2a(x):
    """Problem 2a: sum_{i=1}^9 x_i^2 = 720."""
    val = np.sum(x**2) - 720
    return 1.0 / (1.0 + abs(val))


def F_2b(x):
    """Problem 2b: sum_{i=1}^{10} x_i^2 = 956."""
    val = np.sum(x**2) - 956
    return 1.0 / (1.0 + abs(val))


def F_3a(x):
    """Problem 3a: x1^3 + x2^3 = 1008."""
    val = x[0]**3 + x[1]**3 - 1008
    return 1.0 / (1.0 + abs(val))


def F_3b(x):
    """Problem 3b: x1^9 + x2^9 = 1000019683."""
    val = x[0]**9 + x[1]**9 - 1000019683
    return 1.0 / (1.0 + abs(val))


def F_4(x, n=3, k=3):
    """Problem 4: Markoff-Hurwitz equations.

    x1^2 + x2^2 + ... + xn^2 = k * x1 * x2 * ... * xn
    """
    val = np.sum(x**2) - k * np.prod(x)
    return 1.0 / (1.0 + abs(val))


def F_5a(x):
    """Problem 5a: x^2 + 7 = y^n, n >= 3.

    Variables: (x, n), where y = round((x^2 + 7)^(1/n)).
    """
    x_val = int(round(x[0]))
    n_val = int(round(x[1]))
    n_val = max(3, min(100, n_val))
    base = x_val**2 + 7
    y_val = int(round(base ** (1.0 / n_val)))
    val = base - y_val**n_val
    return 1.0 / (1.0 + abs(val))


def F_5b(x):
    """Problem 5b: x^2 + 11^b = y^3.

    Variables: (x, y, b).
    """
    x_val = int(round(x[0]))
    y_val = int(round(x[1]))
    b_val = int(round(x[2]))
    b_val = max(0, min(100, b_val))
    val = x_val**2 + (11**b_val) - y_val**3
    return 1.0 / (1.0 + abs(val))


def F_6a(x):
    """Problem 6a: x^2 + 2^a * 11^b = y^3.

    Variables: (x, y, a, b).
    """
    x_val = int(round(x[0]))
    y_val = int(round(x[1]))
    a_val = int(round(x[2]))
    b_val = int(round(x[3]))
    a_val = max(0, min(30, a_val))
    b_val = max(0, min(30, b_val))
    val = x_val**2 + (2**a_val) * (11**b_val) - y_val**3
    return 1.0 / (1.0 + abs(val))


def F_6b(x):
    """Problem 6b: x^2 + 2^a * 11^b = y^4.

    Variables: (x, y, a, b).
    """
    x_val = int(round(x[0]))
    y_val = int(round(x[1]))
    a_val = int(round(x[2]))
    b_val = int(round(x[3]))
    a_val = max(0, min(30, a_val))
    b_val = max(0, min(30, b_val))
    val = x_val**2 + (2**a_val) * (11**b_val) - y_val**4
    return 1.0 / (1.0 + abs(val))


def F_7(x):
    """Problem 7: 2^k + 3*x^2 = y^3.

    Variables: (x, y, k).
    """
    x_val = int(round(x[0]))
    y_val = int(round(x[1]))
    k_val = int(round(x[2]))
    k_val = max(0, min(100, k_val))
    val = (2**k_val) + 3 * x_val**2 - y_val**3
    return 1.0 / (1.0 + abs(val))


def F_8(x):
    """Problem 8: 5^x1 + 5^x2 = 3^x3 + 7^x4.

    Variables: (x1, x2, x3, x4).
    """
    x1 = int(round(x[0]))
    x2 = int(round(x[1]))
    x3 = int(round(x[2]))
    x4 = int(round(x[3]))
    val = 5.0**x1 + 5.0**x2 - (3.0**x3 + 7.0**x4)
    return 1.0 / (1.0 + abs(val))


def F_9a(x):
    """Problem 9a: Pell equation system for p = 2.

    x^2 - 24y^2 = 1, y^2 - 2z^2 = 1.
    Variables: (x, y, z).
    """
    x_val = int(round(x[0]))
    y_val = int(round(x[1]))
    z_val = int(round(x[2]))
    f1 = x_val**2 - 24 * y_val**2 - 1
    f2 = y_val**2 - 2 * z_val**2 - 1
    return 1.0 / (1.0 + abs(f1) + abs(f2))


def F_9b(x):
    """Problem 9b: Pell equation system for p = 11.

    x^2 - 24y^2 = 1, y^2 - 11z^2 = 1.
    Variables: (x, y, z).
    """
    x_val = int(round(x[0]))
    y_val = int(round(x[1]))
    z_val = int(round(x[2]))
    f1 = x_val**2 - 24 * y_val**2 - 1
    f2 = y_val**2 - 11 * z_val**2 - 1
    return 1.0 / (1.0 + abs(f1) + abs(f2))


def F_10(x):
    """Problem 10: Linear equation system of 7 equations.

    Variables: (x1, ..., x7).
    """
    x_val = np.round(x).astype(int)
    f1 = x_val[0] - 1
    f2 = 3*x_val[0] + x_val[1] - 6
    f3 = 4*x_val[0] + 3*x_val[1] + x_val[2] + x_val[4] - 15
    f4 = 3*x_val[0] + 4*x_val[1] + 3*x_val[2] + x_val[3] + x_val[4] + x_val[5] - 20
    f5 = 3*x_val[1] + 4*x_val[2] + 3*x_val[3] + x_val[4] + x_val[5] + x_val[6] - 15
    f6 = 3*x_val[2] + 4*x_val[3] + x_val[5] + x_val[6] - 6
    f7 = 3*x_val[3] + x_val[6] - 1
    val = abs(f1) + abs(f2) + abs(f3) + abs(f4) + abs(f5) + abs(f6) + abs(f7)
    return 1.0 / (1.0 + val)


def F_11(x):
    """Problem 11: Nonlinear equation system of 6 equations.

    Variables: (x1, ..., x6).
    """
    x_val = np.round(x).astype(int)
    f1 = 5*x_val[0] + 10*x_val[1] - 5*x_val[2] + x_val[4]**3 + 8*x_val[5] - 1772
    f2 = 3*x_val[0] + 18*x_val[2] - 5*x_val[4] + 17*x_val[5] - 153
    f3 = 6*x_val[0] + x_val[2] - 99*x_val[1] + (15*x_val[5])**2 - 1772
    f4 = -x_val[0] + 5*x_val[1] + 8*x_val[2] - 6*x_val[3] + 15*x_val[4] + 10*x_val[5] - 277
    f5 = (x_val[0] + x_val[1])**2 - 7*x_val[2] + 5*x_val[3] + 12*x_val[4] - 8*x_val[5] - 150
    f6 = x_val[1] + 5*x_val[2] - 3*x_val[4] - x_val[5] - 4
    val = abs(f1) + abs(f2) + abs(f3) + abs(f4) + abs(f5) + abs(f6)
    return 1.0 / (1.0 + val)


def F_12(x):
    """Problem 12: Nonlinear equation system of 9 equations.

    Variables: (x1, ..., x10).
    """
    x_val = np.round(x).astype(int)
    f1 = x_val[0]**2 - 2*(x_val[1] + x_val[3])**3 + x_val[4] - 3*x_val[5] - x_val[6] + 4*x_val[8] + 15*x_val[9] + 24
    f2 = 2*x_val[0] + (x_val[1] + 3*x_val[3])**3 + (5*x_val[6])**2 - 6*x_val[7] + x_val[8] - 9*x_val[9] - 31
    f3 = 3*x_val[0] - (2*x_val[1])**2 + 10*x_val[2] - 9*x_val[3] + 3*x_val[4] + x_val[5] - 2*x_val[6] - 8*x_val[7] + 12*x_val[8] - 5*x_val[9] + 25
    f4 = 5*x_val[0] + 2*x_val[1] - 8*x_val[3] - 3*x_val[4] + 4*x_val[5] + x_val[6] - x_val[8] - 23
    f5 = x_val[0] - x_val[2] + 2*x_val[4] - x_val[6] - x_val[8] + 3
    f6 = x_val[1] + (2*x_val[3])**2 - 6*x_val[5] - x_val[7] + 2*x_val[9] - 8
    f7 = 3*x_val[0] + 2*x_val[1] - 5*x_val[2] - x_val[3]**4 - 2*x_val[4] + x_val[5] + 4*x_val[6] - 10*x_val[7] + 8*x_val[8] + 9
    f8 = x_val[0] - 3*x_val[1] + 4*x_val[3] + x_val[5] - 6*x_val[6] + x_val[7] - 2*x_val[8] + 16
    f9 = (2*x_val[0] + x_val[1])**2 + 3*x_val[2] - 10*x_val[4] - (x_val[5] + 3*x_val[6])**3 - x_val[7] - 6*x_val[8] - 27
    val = abs(f1) + abs(f2) + abs(f3) + abs(f4) + abs(f5) + abs(f6) + abs(f7) + abs(f8) + abs(f9)
    return 1.0 / (1.0 + val)
