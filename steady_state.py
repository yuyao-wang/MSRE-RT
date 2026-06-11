import numpy as np
from collections import deque

from HX1 import HX1
from HX2 import HX2
from neutronics import neutronics
from power_plant import power_plant_temp
from thermal_hydraulics import thermal_hydraulics
from transport_delay import transport_delay


def _reference_multiplication_ratio(params, phi_1, phi_2, z):
    phi_ref = np.vstack([phi_1, phi_2])
    production = np.trapz(
        np.sum(np.asarray(params["nu_sigma_f_ref"], dtype=float) * phi_ref, axis=0),
        z,
    )
    absorption = np.trapz(
        np.sum(np.asarray(params["sigma_a_ref"], dtype=float) * phi_ref, axis=0),
        z,
    )
    return production / max(absorption, 1.0e-12)


def _steady_sweep(partner_profile, inlet_temperature, velocity, exchange_coeff, dx):
    partner_profile = np.asarray(partner_profile, dtype=float)
    profile = np.empty_like(partner_profile)
    advection_coeff = abs(float(velocity)) / max(float(dx), 1.0e-12)
    diagonal = advection_coeff + float(exchange_coeff)

    if velocity >= 0.0:
        profile[0] = (
            advection_coeff * float(inlet_temperature)
            + float(exchange_coeff) * partner_profile[0]
        ) / diagonal
        for idx in range(1, profile.size):
            profile[idx] = (
                advection_coeff * profile[idx - 1]
                + float(exchange_coeff) * partner_profile[idx]
            ) / diagonal
    else:
        profile[-1] = (
            advection_coeff * float(inlet_temperature)
            + float(exchange_coeff) * partner_profile[-1]
        ) / diagonal
        for idx in range(profile.size - 2, -1, -1):
            profile[idx] = (
                advection_coeff * profile[idx + 1]
                + float(exchange_coeff) * partner_profile[idx]
            ) / diagonal

    return profile


def solve_heat_exchanger_steady(hot_inlet, cold_inlet, config, num_points, tol=1.0e-8, max_iter=500):
    hot_profile = np.full(int(num_points), float(hot_inlet), dtype=float)
    cold_profile = np.full(int(num_points), float(cold_inlet), dtype=float)

    for iteration in range(max_iter):
        previous_hot = hot_profile.copy()
        previous_cold = cold_profile.copy()

        hot_profile = _steady_sweep(
            partner_profile=previous_cold,
            inlet_temperature=hot_inlet,
            velocity=config["hot_velocity"],
            exchange_coeff=config["hot_exchange_coeff"],
            dx=config["dx"],
        )
        cold_profile = _steady_sweep(
            partner_profile=hot_profile,
            inlet_temperature=cold_inlet,
            velocity=config["cold_velocity"],
            exchange_coeff=config["cold_exchange_coeff"],
            dx=config["dx"],
        )

        residual = max(
            float(np.max(np.abs(hot_profile - previous_hot))),
            float(np.max(np.abs(cold_profile - previous_cold))),
        )
        if residual < tol:
            return hot_profile, cold_profile, iteration + 1, residual

    return hot_profile, cold_profile, max_iter, residual


def _hx1_config(params):
    return {
        "dx": params["L_HX"] / max(params["Nx"] - 1, 1),
        "hot_velocity": -params["V_he_s"],
        "cold_velocity": params["V_he_ss"],
        "hot_exchange_coeff": params["U_hx"] / (params["M_he_s"] * params["c_p_s"]),
        "cold_exchange_coeff": params["U_hx"] / (params["M_he_ss"] * params["c_p_ss"]),
    }


def _hx2_config(params):
    return {
        "dx": params["L_HX2"] / max(params["Nx"] - 1, 1),
        "hot_velocity": -params["V_he2_s"],
        "cold_velocity": params["V_he2_ss"],
        "hot_exchange_coeff": params["U2_hx"] / (params["M_he2_s"] * params["c_p_ss"]),
        "cold_exchange_coeff": params["U2_hx"] / (params["M_he2_ss"] * params["c_p_sss"]),
    }


def initialize_system_steady_state(params, spinup_steps=180):
    N = params["N"]
    Nx = params["Nx"]
    precursor_groups = params["precursor_groups"]

    y_n = np.zeros((params["neutronics_state_size"], 1))
    y_th = np.zeros((2 * N, 1))
    y_hx1 = np.zeros((2 * Nx, 1))
    y_hx2 = np.zeros((2 * Nx, 1))
    y_hx1[:, 0] = np.concatenate([params["u_init"], params["v_init"]])
    y_hx2[:, 0] = np.concatenate([params["u2_init"], params["v2_init"]])

    temperature_fuel = np.asarray(params["initialS"], dtype=float).copy()
    temperature_graphite = np.asarray(params["initialG"], dtype=float).copy()
    q_prime = np.zeros(N)

    Tss_HX2_0 = float(params["Tss_in"])
    Ts_HX1_0 = float(params["Ts_in"])
    Tss_HX1_0 = float(params["Tss_in"])
    Tsss_pp_0 = float(params["Tsss_in"])

    buffer_hx_c = deque()
    buffer_c_hx = deque()
    buffer_r_hx = deque()
    buffer_hx_r = deque()
    buffer_r_pp = deque()
    buffer_pp_r = deque()

    Ts_in = float(params["Ts_in"])
    Ts_out = float(params["Ts_out"])
    Tss_in = float(params["Tss_in"])
    Tss_out = float(params["Tss_out"])
    Tsss_in = float(params["Tsss_in"])
    Tsss_out = float(params["Tsss_out"])

    for step in range(int(spinup_steps)):
        state = {
            "temperature_fuel": temperature_fuel,
            "temperature_graphite": temperature_graphite,
            "rod_position": 0.0,
            "external_reactivity": 0.0,
        }
        y_n, q_prime = neutronics(y_n[:, -1], state, step, params)

        if params.get("core_inlet_mode", "prescribed") == "hx_coupled":
            Ts_core_0 = transport_delay(
                Ts_HX1_0,
                params["tau_hx_c"],
                Ts_in,
                buffer_hx_c,
                step,
                dt=params.get("outer_dt", 1.0),
            )
        else:
            Ts_core_0 = Ts_in

        y_th = thermal_hydraulics(y_th, q_prime, Ts_core_0, params, step)
        temperature_fuel = y_th[:N, -1].T
        temperature_graphite = y_th[N:, -1].T
        Ts_core_L = float(temperature_fuel[-1])

        Ts_HX1_L = transport_delay(
            Ts_core_L,
            params["tau_c_hx"],
            Ts_out,
            buffer_c_hx,
            step,
            dt=params.get("outer_dt", 1.0),
        )
        Tss_HX1_0 = transport_delay(
            Tss_HX2_0,
            params["tau_r_hx"],
            Tss_in,
            buffer_r_hx,
            step,
            dt=params.get("outer_dt", 1.0),
        )
        y_hx1 = HX1(y_hx1, Ts_HX1_L, Tss_HX1_0, params, step)
        Ts_HX1 = y_hx1[:Nx, -1]
        Tss_HX1 = y_hx1[Nx:, -1]
        Ts_HX1_0 = float(Ts_HX1[0])
        Tss_HX1_L = float(Tss_HX1[-1])

        Tss_HX2_L = transport_delay(
            Tss_HX1_L,
            params["tau_hx_r"],
            Tss_out,
            buffer_hx_r,
            step,
            dt=params.get("outer_dt", 1.0),
        )
        Tsss_HX2_0 = transport_delay(
            Tsss_pp_0,
            params["tau_pp_r"],
            Tsss_in,
            buffer_pp_r,
            step,
            dt=params.get("outer_dt", 1.0),
        )
        y_hx2 = HX2(y_hx2, Tss_HX2_L, Tsss_HX2_0, params, step)
        Tss_HX2 = y_hx2[:Nx, -1]
        Tsss_HX2 = y_hx2[Nx:, -1]
        Tss_HX2_0 = float(Tss_HX2[0])
        Tsss_HX2_L = float(Tsss_HX2[-1])

        Tsss_pp_L = transport_delay(
            Tsss_HX2_L,
            params["tau_r_pp"],
            Tsss_out,
            buffer_r_pp,
            step,
            dt=params.get("outer_dt", 1.0),
        )
        Tsss_pp_0 = float(power_plant_temp(Tsss_pp_L, params, step))

    z = np.asarray(params["z"], dtype=float)
    final_neutronics_state = np.asarray(y_n[:, -1], dtype=float).copy()
    final_thermal_state = np.asarray(y_th[:, -1], dtype=float).copy()
    final_hx1_state = np.asarray(y_hx1[:, -1], dtype=float).copy()
    final_hx2_state = np.asarray(y_hx2[:, -1], dtype=float).copy()

    phi_1 = final_neutronics_state[:N]
    phi_2 = final_neutronics_state[N:2 * N]
    c_groups = final_neutronics_state[2 * N:].reshape(precursor_groups, N)
    reference_ratio = _reference_multiplication_ratio(params, phi_1, phi_2, z)

    return {
        "phi_1_0": phi_1.copy(),
        "phi_2_0": phi_2.copy(),
        "phi_0": np.concatenate([phi_1, phi_2]),
        "c0_groups": c_groups.copy(),
        "c0": c_groups.reshape(-1).copy(),
        "T_s_ref": np.asarray(temperature_fuel, dtype=float).copy(),
        "T_gr_ref": np.asarray(temperature_graphite, dtype=float).copy(),
        "initialS": np.asarray(temperature_fuel, dtype=float).copy(),
        "initialG": np.asarray(temperature_graphite, dtype=float).copy(),
        "u_init": np.asarray(Ts_HX1, dtype=float),
        "v_init": np.asarray(Tss_HX1, dtype=float),
        "u2_init": np.asarray(Tss_HX2, dtype=float),
        "v2_init": np.asarray(Tsss_HX2, dtype=float),
        "y_n_init": final_neutronics_state,
        "y_th_init": final_thermal_state,
        "y_hx1_init": final_hx1_state,
        "y_hx2_init": final_hx2_state,
        "buffer_hx_c_init": list(buffer_hx_c),
        "buffer_c_hx_init": list(buffer_c_hx),
        "buffer_r_hx_init": list(buffer_r_hx),
        "buffer_hx_r_init": list(buffer_hx_r),
        "buffer_r_pp_init": list(buffer_r_pp),
        "buffer_pp_r_init": list(buffer_pp_r),
        "history_step_offset": int(spinup_steps),
        "history_time_offset_s": float(spinup_steps) * float(params.get("outer_dt", 1.0)),
        "Ts_in": float(Ts_core_0),
        "Ts_out": float(Ts_HX1_L),
        "Tss_in": float(Tss_HX1_0),
        "Tss_out": float(Tss_HX2_L),
        "Tsss_in": float(Tsss_HX2_0),
        "Tsss_out": float(Tsss_pp_L),
        "reference_multiplication_ratio": float(reference_ratio),
        "steady_state_summary": {
            "spinup_steps": int(spinup_steps),
            "core_inlet_temperature": float(Ts_core_0),
            "core_outlet_temperature": float(Ts_core_L),
            "secondary_inlet_temperature": float(Tss_HX1_0),
            "secondary_outlet_temperature": float(Tss_HX2_L),
            "tertiary_inlet_temperature": float(Tsss_HX2_0),
            "tertiary_outlet_temperature": float(Tsss_pp_L),
            "core_power": float(np.trapz(q_prime, z)),
            "global_reactivity": float(params.get("last_global_rho", 0.0)),
            "brayton_net_work": float(params.get("last_power_plant", {}).get("W_net", 0.0)),
            "brayton_efficiency": float(params.get("last_power_plant", {}).get("eta_b", 0.0)),
            "history_time_offset_s": float(spinup_steps) * float(params.get("outer_dt", 1.0)),
        },
    }
