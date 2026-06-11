import numpy as np

from ode_solver import ode_solver


def _salt_upwind_gradient(temperature_fuel, inlet_temperature, dz):
    temp_im1 = np.empty_like(temperature_fuel)
    temp_im1[0] = inlet_temperature
    temp_im1[1:] = temperature_fuel[:-1]
    return (temperature_fuel - temp_im1) / dz


def _neumann_second_derivative(field, dz):
    second_derivative = np.empty_like(field)
    if field.size == 1:
        second_derivative[0] = 0.0
        return second_derivative

    second_derivative[1:-1] = (field[2:] - 2.0 * field[1:-1] + field[:-2]) / dz**2
    second_derivative[0] = 2.0 * (field[1] - field[0]) / dz**2
    second_derivative[-1] = 2.0 * (field[-2] - field[-1]) / dz**2
    return second_derivative


def thermal_hydraulics(y_th, q_prime, Ts_core_inlet, params, step):
    N = params["N"]
    dz = params["dz"]

    rho_s = float(params["rho_s"])
    c_p_s = float(params["c_p_s"])
    A_s = float(params["A_s"])
    rho_gr = float(params["rho_gr"])
    c_p_g = float(params["c_p_g"])
    A_gr = float(params["A_gr"])
    u_c = float(params["u_core"])
    eta_s = float(params["eta_s"])
    eta_gr = float(params["eta_gr"])
    heat_exchange = float(params["h_sgr"]) * float(params["P_sgr"])
    graphite_axial_conductivity = float(params["k_gr"]) * A_gr
    use_graphite_axial_conduction = bool(params.get("use_graphite_axial_conduction", True))
    initialS = np.asarray(params["initialS"], dtype=float)
    initialG = np.asarray(params["initialG"], dtype=float)
    err = float(params["err"])

    salt_capacity = rho_s * c_p_s * A_s
    graphite_capacity = rho_gr * c_p_g * A_gr
    q_prime = np.asarray(q_prime, dtype=float)
    inlet_temperature = float(params["bc_s0"] if Ts_core_inlet is None else Ts_core_inlet)

    def pde_to_ode_th(t, y):
        temperature_fuel = y[:N]
        temperature_graphite = y[N:]

        fuel_gradient = _salt_upwind_gradient(temperature_fuel, inlet_temperature, dz)
        fuel_exchange = heat_exchange * (temperature_graphite - temperature_fuel)
        fuel_rhs = -u_c * fuel_gradient + (eta_s * q_prime + fuel_exchange) / salt_capacity + err

        graphite_exchange = -heat_exchange * (temperature_graphite - temperature_fuel)
        graphite_rhs = (eta_gr * q_prime + graphite_exchange) / graphite_capacity + err
        if use_graphite_axial_conduction:
            graphite_rhs += (
                graphite_axial_conductivity / graphite_capacity
            ) * _neumann_second_derivative(temperature_graphite, dz)

        # Enforce the prescribed salt inlet temperature directly.
        fuel_rhs[0] = inlet_temperature - temperature_fuel[0]

        return np.concatenate([fuel_rhs, graphite_rhs])

    y_th_array = np.asarray(y_th, dtype=float)
    if step == 0:
        y0 = np.concatenate([initialS, initialG])
    elif y_th_array.size == 2 * N:
        y0 = y_th_array.reshape(-1)
    else:
        y0 = np.concatenate([initialS, initialG])

    y0[0] = inlet_temperature
    return ode_solver(y0, [], pde_to_ode_th, params)
