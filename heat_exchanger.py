import numpy as np

from ode_solver import ode_solver


def _upwind_gradient(field, inlet_temperature, dx, signed_velocity):
    gradient = np.empty_like(field)

    if signed_velocity >= 0.0:
        gradient[0] = (field[0] - inlet_temperature) / dx
        gradient[1:] = (field[1:] - field[:-1]) / dx
    else:
        gradient[:-1] = (field[1:] - field[:-1]) / dx
        gradient[-1] = (inlet_temperature - field[-1]) / dx

    return gradient


def solve_heat_exchanger(y_hx, hot_inlet, cold_inlet, config, params, step):
    Nx = int(params["Nx"])
    dx = float(config["dx"])
    err = float(params["err"])

    hot_velocity = float(config["hot_velocity"])
    cold_velocity = float(config["cold_velocity"])
    hot_exchange_coeff = float(config["hot_exchange_coeff"])
    cold_exchange_coeff = float(config["cold_exchange_coeff"])
    hot_initial = np.asarray(config["hot_initial"], dtype=float)
    cold_initial = np.asarray(config["cold_initial"], dtype=float)

    def pde_to_ode_hx(t, y):
        hot = y[:Nx]
        cold = y[Nx:]

        hot_gradient = _upwind_gradient(hot, hot_inlet, dx, hot_velocity)
        cold_gradient = _upwind_gradient(cold, cold_inlet, dx, cold_velocity)
        delta_t = hot - cold

        dhot_dt = -hot_velocity * hot_gradient - hot_exchange_coeff * delta_t + err
        dcold_dt = -cold_velocity * cold_gradient + cold_exchange_coeff * delta_t + err

        return np.concatenate([dhot_dt, dcold_dt])

    if step == 0:
        y0 = np.concatenate([hot_initial, cold_initial])
    else:
        y0 = np.asarray(y_hx[:, -1], dtype=float)

    solution_y_hx = ode_solver(y0, [], pde_to_ode_hx, params)
    return solution_y_hx.y
