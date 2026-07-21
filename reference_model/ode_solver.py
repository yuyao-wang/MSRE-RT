import numpy as np


def ode_solver(ic, bc, vector_to_be_solved, params, prefix=None):
    del bc  # Boundary conditions are handled inside each RHS function.

    def _get(name, default):
        if prefix is not None:
            keyed = f"{prefix}_{name}"
            if keyed in params:
                return params[keyed]
        return params.get(name, default)

    def rk4_step(fun, t, y, h):
        k1 = fun(t, y)
        k2 = fun(t + 0.5 * h, y + 0.5 * h * k1)
        k3 = fun(t + 0.5 * h, y + 0.5 * h * k2)
        k4 = fun(t + h, y + h * k3)
        return y + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

    y = np.asarray(ic, dtype=float).copy()
    n = y.size

    t0 = 0.0
    tf = float(_get('ode_horizon', 1.0))
    if tf <= t0:
        return y[:, None]

    # Adaptive controls with conservative defaults for stability.
    rtol = float(_get('ode_rtol', 1e-4))
    atol = float(_get('ode_atol', 1e-6))
    h_min = float(_get('ode_h_min', 1e-5))
    h_max = float(_get('ode_h_max', 0.25))
    h = float(_get('ode_initial_h', min(0.05, tf)))
    h = min(max(h, h_min), h_max, tf)

    max_steps = int(_get('ode_max_steps', 100000))
    safety = 0.9

    t = t0
    steps = 0

    while t < tf and steps < max_steps:
        if t + h > tf:
            h = tf - t

        y_full = rk4_step(vector_to_be_solved, t, y, h)
        y_half = rk4_step(vector_to_be_solved, t, y, 0.5 * h)
        y_half = rk4_step(vector_to_be_solved, t + 0.5 * h, y_half, 0.5 * h)

        if not (np.isfinite(y_full).all() and np.isfinite(y_half).all()):
            h *= 0.5
            if h < h_min:
                raise RuntimeError("Adaptive RK4 failed: non-finite state at minimum step.")
            continue

        scale = atol + rtol * np.maximum(np.abs(y_half), np.abs(y_full))
        err_vec = (y_half - y_full) / scale
        err_norm = np.linalg.norm(err_vec) / np.sqrt(max(1, n))

        if err_norm <= 1.0:
            y = y_half
            t += h
            steps += 1

            if err_norm == 0.0:
                growth = 2.0
            else:
                growth = min(2.0, max(1.1, safety * err_norm ** (-0.2)))
            h = min(h_max, max(h_min, h * growth))
        else:
            shrink = max(0.2, safety * err_norm ** (-0.25))
            h = max(h_min, h * shrink)
            if h <= h_min and err_norm > 1.0:
                raise RuntimeError("Adaptive RK4 failed: required step below ode_h_min.")

    if steps >= max_steps and t < tf:
        raise RuntimeError("Adaptive RK4 failed: exceeded ode_max_steps before reaching tf.")

    # Keep 2D shape contract used by calling modules (n, 1).
    return y[:, None]
