import numpy as np
from collections import deque

from criticality import solve_critical_mode, solve_precursor_groups_steady_state
from cross_sections import build_cross_sections
from HX1 import HX1
from HX2 import HX2
from neutronics import neutronics
from power_plant import power_plant_temp
from point_kinetics import initialize_point_kinetics_state
from precursor_loop import initialize_precursor_loop_state
from thermal_hydraulics import thermal_hydraulics
from transport_delay import transport_delay


def _reference_multiplication_ratio(params, phi_1, phi_2, z):
    phi_ref = np.vstack([phi_1, phi_2])
    production = np.trapezoid(
        np.sum(np.asarray(params["nu_sigma_f_ref"], dtype=float) * phi_ref, axis=0),
        z,
    )
    absorption = np.trapezoid(
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
    ua_hx = params.get("UA_hx", params["U_hx"])
    return {
        "dx": params["L_HX"] / max(params["Nx"] - 1, 1),
        "hot_velocity": -params["V_he_s"],
        "cold_velocity": params["V_he_ss"],
        "hot_exchange_coeff": ua_hx / (params["M_he_s"] * params["c_p_s"]),
        "cold_exchange_coeff": ua_hx / (params["M_he_ss"] * params["c_p_ss"]),
    }


def _hx2_config(params):
    ua_hx2 = params.get("UA2_hx", params["U2_hx"])
    return {
        "dx": params["L_HX2"] / max(params["Nx"] - 1, 1),
        "hot_velocity": -params["V_he2_s"],
        "cold_velocity": params["V_he2_ss"],
        "hot_exchange_coeff": ua_hx2 / (params["M_he2_s"] * params["c_p_ss"]),
        "cold_exchange_coeff": ua_hx2 / (params["M_he2_ss"] * params["c_p_sss"]),
    }


def _solve_steady_neutronics_state(temperature_fuel, temperature_graphite, params):
    raw_xs = build_cross_sections(
        temperature_fuel=temperature_fuel,
        temperature_graphite=temperature_graphite,
        params=params,
        rod_position=0.0,
        external_reactivity=0.0,
        fission_scale_override=1.0,
    )
    raw_mode = solve_critical_mode(raw_xs, params)
    critical_scale = 1.0 / max(raw_mode["k_eff"], 1.0e-12)
    params["critical_fission_scale"] = critical_scale

    xs = build_cross_sections(
        temperature_fuel=temperature_fuel,
        temperature_graphite=temperature_graphite,
        params=params,
        rod_position=0.0,
        external_reactivity=0.0,
    )
    mode = solve_critical_mode(xs, params)
    phi_1 = np.asarray(mode["phi_1"], dtype=float)
    phi_2 = np.asarray(mode["phi_2"], dtype=float)
    fission_source = xs["nu_sigma_f"][0] * phi_1 + xs["nu_sigma_f"][1] * phi_2
    precursor_groups = solve_precursor_groups_steady_state(fission_source, params)
    delayed_source = np.sum(
        np.asarray(params["lambda_i_np"], dtype=float)[:, None] * precursor_groups,
        axis=0,
    )

    z = np.asarray(params["z"], dtype=float)
    q_vol_unscaled = np.sum(xs["sigma_f"] * np.vstack([phi_1, phi_2]), axis=0)
    raw_power = np.trapezoid(np.asarray(params["A_f"], dtype=float) * q_vol_unscaled, z)
    power_scale = float(params["nominal_total_power"]) / max(raw_power, 1.0e-12)
    q_prime = power_scale * np.asarray(params["A_f"], dtype=float) * q_vol_unscaled

    params["power_scale"] = power_scale
    params["phi_1_0"] = phi_1.copy()
    params["phi_2_0"] = phi_2.copy()
    params["phi_0"] = np.concatenate([phi_1, phi_2])
    params["c0_groups"] = precursor_groups.copy()
    params["c0"] = precursor_groups.reshape(-1).copy()
    params["reference_multiplication_ratio"] = float(mode["k_eff"])
    params["precursor_loop_state"] = initialize_precursor_loop_state(
        precursor_groups=params["precursor_groups"],
        seed_outlet=precursor_groups[:, -1],
        outer_dt=params.get("outer_dt", 1.0),
        tau_loop=params.get("precursor_loop_tau", params["tau_l"]),
    )
    params["last_effective_beta"] = float(
        np.trapezoid(delayed_source, z) / max(np.trapezoid(fission_source, z), 1.0e-12)
    )
    initialize_point_kinetics_state(params, params["last_effective_beta"])

    return {
        "xs": xs,
        "phi_1": phi_1,
        "phi_2": phi_2,
        "precursors": precursor_groups,
        "q_prime": q_prime,
        "critical_scale": critical_scale,
        "k_eff": float(mode["k_eff"]),
    }


def _relax_thermal_loops(q_prime, params, spinup_steps):
    N = params["N"]
    Nx = params["Nx"]
    z = np.asarray(params["z"], dtype=float)

    y_th_seed = np.asarray(params.get("y_th_init", []), dtype=float)
    if y_th_seed.size == 2 * N:
        y_th = y_th_seed.reshape(2 * N, 1)
        temperature_fuel = y_th_seed[:N].copy()
        temperature_graphite = y_th_seed[N:].copy()
    else:
        y_th = np.zeros((2 * N, 1))
        temperature_fuel = np.asarray(params["initialS"], dtype=float).copy()
        temperature_graphite = np.asarray(params["initialG"], dtype=float).copy()

    y_hx1_seed = np.asarray(params.get("y_hx1_init", []), dtype=float)
    y_hx2_seed = np.asarray(params.get("y_hx2_init", []), dtype=float)
    y_hx1 = np.zeros((2 * Nx, 1))
    y_hx2 = np.zeros((2 * Nx, 1))
    if y_hx1_seed.size == 2 * Nx:
        y_hx1[:, 0] = y_hx1_seed.reshape(-1)
    else:
        y_hx1[:, 0] = np.concatenate([params["u_init"], params["v_init"]])
    if y_hx2_seed.size == 2 * Nx:
        y_hx2[:, 0] = y_hx2_seed.reshape(-1)
    else:
        y_hx2[:, 0] = np.concatenate([params["u2_init"], params["v2_init"]])

    Tss_HX2_0 = float(params["Tss_in"])
    Ts_HX1_0 = float(params["Ts_in"])
    Tss_HX1_0 = float(params["Tss_in"])
    Tsss_pp_0 = float(params["Tsss_in"])

    buffer_hx_c = deque(params.get("buffer_hx_c_init", []))
    buffer_c_hx = deque(params.get("buffer_c_hx_init", []))
    buffer_r_hx = deque(params.get("buffer_r_hx_init", []))
    buffer_hx_r = deque(params.get("buffer_hx_r_init", []))
    buffer_r_pp = deque(params.get("buffer_r_pp_init", []))
    buffer_pp_r = deque(params.get("buffer_pp_r_init", []))

    Ts_in = float(params["Ts_in"])
    Ts_out = float(params["Ts_out"])
    Tss_in = float(params["Tss_in"])
    Tss_out = float(params["Tss_out"])
    Tsss_in = float(params["Tsss_in"])
    Tsss_out = float(params["Tsss_out"])

    core_power = float(np.trapezoid(q_prime, z))

    for step in range(int(spinup_steps)):
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

        y_th = thermal_hydraulics(y_th[:, -1], q_prime, Ts_core_0, params, step)
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
        y_hx1 = HX1(y_hx1[:, -1], Ts_HX1_L, Tss_HX1_0, params, step)
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
        y_hx2 = HX2(y_hx2[:, -1], Tss_HX2_L, Tsss_HX2_0, params, step)
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
        params["brayton_available_heat_W"] = core_power
        Tsss_pp_0 = float(power_plant_temp(Tsss_pp_L, params, step))

    return {
        "y_th_init": np.asarray(y_th[:, -1], dtype=float).copy(),
        "y_hx1_init": np.asarray(y_hx1[:, -1], dtype=float).copy(),
        "y_hx2_init": np.asarray(y_hx2[:, -1], dtype=float).copy(),
        "buffer_hx_c_init": list(buffer_hx_c),
        "buffer_c_hx_init": list(buffer_c_hx),
        "buffer_r_hx_init": list(buffer_r_hx),
        "buffer_hx_r_init": list(buffer_hx_r),
        "buffer_r_pp_init": list(buffer_r_pp),
        "buffer_pp_r_init": list(buffer_pp_r),
        "initialS": np.asarray(temperature_fuel, dtype=float).copy(),
        "initialG": np.asarray(temperature_graphite, dtype=float).copy(),
        "u_init": np.asarray(Ts_HX1, dtype=float),
        "v_init": np.asarray(Tss_HX1, dtype=float),
        "u2_init": np.asarray(Tss_HX2, dtype=float),
        "v2_init": np.asarray(Tsss_HX2, dtype=float),
        "Ts_in": float(Ts_core_0),
        "Ts_out": float(Ts_HX1_L),
        "Tss_in": float(Tss_HX1_0),
        "Tss_out": float(Tss_HX2_L),
        "Tsss_in": float(Tsss_HX2_0),
        "Tsss_out": float(Tsss_pp_L),
        "core_power": core_power,
    }


def initialize_system_steady_state(params, spinup_steps=180):
    temperature_fuel = np.asarray(params["initialS"], dtype=float).copy()
    temperature_graphite = np.asarray(params["initialG"], dtype=float).copy()

    max_outer_iterations = int(params.get("steady_state_outer_iterations", 8))
    convergence_tol = float(params.get("steady_state_tolerance", 5.0e-4))

    neutronics_state = None
    thermal_state = None

    for _ in range(max_outer_iterations):
        neutronics_state = _solve_steady_neutronics_state(temperature_fuel, temperature_graphite, params)
        thermal_state = _relax_thermal_loops(neutronics_state["q_prime"], params, spinup_steps)

        updated_fuel = np.asarray(thermal_state["initialS"], dtype=float)
        updated_graphite = np.asarray(thermal_state["initialG"], dtype=float)
        residual = max(
            float(np.max(np.abs(updated_fuel - temperature_fuel))),
            float(np.max(np.abs(updated_graphite - temperature_graphite))),
        )

        temperature_fuel = updated_fuel
        temperature_graphite = updated_graphite
        params.update(thermal_state)
        params["T_s_ref"] = temperature_fuel.copy()
        params["T_gr_ref"] = temperature_graphite.copy()

        if residual < convergence_tol:
            break

    z = np.asarray(params["z"], dtype=float)
    phi_1 = neutronics_state["phi_1"]
    phi_2 = neutronics_state["phi_2"]
    c_groups = np.asarray(neutronics_state["precursors"], dtype=float)
    y_n_init = np.concatenate([phi_1, phi_2, c_groups.reshape(-1)])

    params["last_global_rho"] = 0.0
    params["y_n_init"] = y_n_init.copy()

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
        "y_n_init": y_n_init.copy(),
        "history_step_offset": int(spinup_steps),
        "history_time_offset_s": float(spinup_steps) * float(params.get("outer_dt", 1.0)),
        "reference_multiplication_ratio": float(neutronics_state["k_eff"]),
        "steady_state_summary": {
            "spinup_steps": int(spinup_steps),
            "core_inlet_temperature": float(params["Ts_in"]),
            "core_outlet_temperature": float(params["Ts_out"]),
            "secondary_inlet_temperature": float(params["Tss_in"]),
            "secondary_outlet_temperature": float(params["Tss_out"]),
            "tertiary_inlet_temperature": float(params["Tsss_in"]),
            "tertiary_outlet_temperature": float(params["Tsss_out"]),
            "core_power": float(np.trapezoid(neutronics_state["q_prime"], z)),
            "critical_fission_scale": float(neutronics_state["critical_scale"]),
            "effective_beta_flow": float(params.get("last_effective_beta", 0.0)),
            "global_reactivity": 0.0,
            "brayton_net_work": float(params.get("last_power_plant", {}).get("W_net", 0.0)),
            "brayton_efficiency": float(params.get("last_power_plant", {}).get("eta_b", 0.0)),
            "brayton_model": params.get("last_power_plant", {}).get("model", "ideal_gas_surrogate"),
            "history_time_offset_s": float(spinup_steps) * float(params.get("outer_dt", 1.0)),
        },
    }
