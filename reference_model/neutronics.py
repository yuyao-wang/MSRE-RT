import numpy as np

from cross_sections import build_cross_sections, estimate_global_reactivity
from ode_solver import ode_solver
from point_kinetics import advance_point_kinetics_state
from precursor_loop import precursor_inlet_from_loop, record_precursor_outlet


def _diffusion_term(phi, diffusion, dz, d_extrap):
    left_ghost = phi[1] - 2.0 * dz * phi[0] / max(d_extrap, 1.0e-12)
    right_ghost = phi[-2] - 2.0 * dz * phi[-1] / max(d_extrap, 1.0e-12)

    phi_ext = np.concatenate(([left_ghost], phi, [right_ghost]))
    diffusion_ext = np.concatenate(([diffusion[0]], diffusion, [diffusion[-1]]))

    d_face = 0.5 * (diffusion_ext[:-1] + diffusion_ext[1:])
    phi_jump = phi_ext[1:] - phi_ext[:-1]

    return (d_face[1:] * phi_jump[1:] - d_face[:-1] * phi_jump[:-1]) / dz**2


def _precursor_advection(C, inlet, velocity, dz):
    C_im1 = np.empty_like(C)
    C_im1[:, 0] = inlet
    C_im1[:, 1:] = C[:, :-1]
    return velocity * (C - C_im1) / dz


def _initial_state(params):
    return np.concatenate([
        np.asarray(params["phi_1_0"], dtype=float),
        np.asarray(params["phi_2_0"], dtype=float),
        np.asarray(params["c0"], dtype=float),
    ])


def _extract_state(y, N, precursor_groups):
    phi_1 = y[:N]
    phi_2 = y[N:2 * N]
    C = y[2 * N:].reshape(precursor_groups, N)
    return phi_1, phi_2, C


def _group_inventory_beta(F, C, lambda_i, z):
    fission_integral = float(np.trapezoid(F, z))
    inventories = np.asarray([np.trapezoid(group, z) for group in C], dtype=float)
    beta_groups = lambda_i * inventories / max(fission_integral, 1.0e-12)
    return beta_groups, inventories, fission_integral


def _global_temperature_feedback_rho(temperature_fuel, temperature_graphite, params):
    z = np.asarray(params["z"], dtype=float)
    length = max(float(z[-1] - z[0]), 1.0e-12)

    fuel_reference = np.asarray(params.get("feedback_reference_fuel", params["T_s_ref"]), dtype=float)
    graphite_reference = np.asarray(params.get("feedback_reference_graphite", params["T_gr_ref"]), dtype=float)

    fuel_delta = np.asarray(temperature_fuel, dtype=float) - fuel_reference
    graphite_delta = np.asarray(temperature_graphite, dtype=float) - graphite_reference

    fuel_avg_delta = float(np.trapezoid(fuel_delta, z) / length)
    graphite_avg_delta = float(np.trapezoid(graphite_delta, z) / length)

    if params.get("feedback_reactivity_mode", "linear_coefficients") == "global_estimate":
        reference_xs = build_cross_sections(
            temperature_fuel=fuel_reference,
            temperature_graphite=graphite_reference,
            params=params,
            rod_position=0.0,
            external_reactivity=0.0,
        )
        current_xs = build_cross_sections(
            temperature_fuel=temperature_fuel,
            temperature_graphite=temperature_graphite,
            params=params,
            rod_position=0.0,
            external_reactivity=0.0,
        )
        rho_feedback = estimate_global_reactivity(current_xs, params) - estimate_global_reactivity(reference_xs, params)
        rho_feedback_pcm = rho_feedback * 1.0e5
    else:
        alpha_fuel_pcm_per_k = float(params.get("fuel_feedback_coeff_pcm_per_K", 0.0))
        alpha_graphite_pcm_per_k = float(params.get("graphite_feedback_coeff_pcm_per_K", 0.0))
        rho_feedback_pcm = alpha_fuel_pcm_per_k * fuel_avg_delta + alpha_graphite_pcm_per_k * graphite_avg_delta

    params["last_feedback_rho_pcm"] = rho_feedback_pcm
    params["last_feedback_fuel_delta_K"] = fuel_avg_delta
    params["last_feedback_graphite_delta_K"] = graphite_avg_delta
    return rho_feedback_pcm * 1.0e-5


def neutronics(y_n, state, step, params):
    N = params["N"]
    dz = params["dz"]
    precursor_groups = params["precursor_groups"]
    z = np.asarray(params["z"], dtype=float)

    beta = np.asarray(params["beta_np"], dtype=float)
    Beta = float(params["Beta"])
    lambda_i = np.asarray(params["lambda_i_np"], dtype=float)
    chi_p = np.asarray(params["chi_p"], dtype=float)
    chi_d = np.asarray(params["chi_d"], dtype=float)
    neutron_velocity = np.asarray(params["neutron_velocity"], dtype=float)
    d_e = np.asarray(params["d_e"], dtype=float)
    u_precursor = float(params.get("u_precursor", params["u_core"]))
    outer_dt = float(params.get("outer_dt", 1.0))
    current_time = float(params.get("history_time_offset_s", 0.0)) + step * outer_dt
    precursor_inlet = precursor_inlet_from_loop(params, current_time)
    params["last_precursor_inlet"] = np.asarray(precursor_inlet, dtype=float).copy()
    params["last_precursor_inlet_time_s"] = current_time
    main_state_size = int(params["neutronics_state_size"])
    precursor_balance_audit_enabled = bool(params.get("precursor_balance_audit_enabled", False))

    temperature_fuel = state.get("temperature_fuel")
    temperature_graphite = state.get("temperature_graphite")
    rod_position = float(state.get("rod_position", 0.0))
    external_reactivity = float(state.get("external_reactivity", 0.0))
    point_kinetics_enabled = bool(params.get("point_kinetics_enabled", True))
    xs_reactivity = 0.0 if point_kinetics_enabled else external_reactivity

    xs = build_cross_sections(
        temperature_fuel=temperature_fuel,
        temperature_graphite=temperature_graphite,
        params=params,
        rod_position=rod_position,
        external_reactivity=xs_reactivity,
    )
    params["last_global_rho"] = external_reactivity
    params["last_cross_sections"] = xs

    y_n_array = np.asarray(y_n, dtype=float)
    if y_n_array.size == params["neutronics_state_size"]:
        y0 = y_n_array.reshape(-1)
    else:
        y0 = _initial_state(params)

    phi_1_old, phi_2_old, C_old = _extract_state(y0, N, precursor_groups)
    F_old = xs["nu_sigma_f"][0] * phi_1_old + xs["nu_sigma_f"][1] * phi_2_old
    params["last_precursor_source_start"] = np.asarray(F_old, dtype=float).copy()
    beta_effective_groups, precursor_inventories_old, fission_integral_old = _group_inventory_beta(
        F_old,
        C_old,
        lambda_i,
        z,
    )
    prompt_generation_time = float(params.get("prompt_generation_time_s", 2.0e-4))
    precursor_amplitudes_old = precursor_inventories_old / max(
        prompt_generation_time * fission_integral_old,
        1.0e-12,
    )
    if point_kinetics_enabled and abs(external_reactivity) < 1.0e-14:
        params["feedback_reference_fuel"] = np.asarray(temperature_fuel, dtype=float).copy()
        params["feedback_reference_graphite"] = np.asarray(temperature_graphite, dtype=float).copy()
    rho_feedback = _global_temperature_feedback_rho(temperature_fuel, temperature_graphite, params)

    def pde_to_ode_neutronics(t, y):
        y_main = y[:main_state_size] if precursor_balance_audit_enabled else y
        phi_1, phi_2, C = _extract_state(y_main, N, precursor_groups)

        F = xs["nu_sigma_f"][0] * phi_1 + xs["nu_sigma_f"][1] * phi_2
        delayed_source = np.sum(lambda_i[:, None] * C, axis=0)

        diffusion_1 = _diffusion_term(phi_1, xs["D"][0], dz, d_e[0])
        diffusion_2 = _diffusion_term(phi_2, xs["D"][1], dz, d_e[1])

        rhs_1 = (
            diffusion_1
            - xs["sigma_r"][0] * phi_1
            + chi_p[0] * (1.0 - Beta) * F
            + chi_d[0] * delayed_source
        )
        rhs_2 = (
            diffusion_2
            - xs["sigma_r"][1] * phi_2
            + xs["sigma_s12"] * phi_1
            + chi_p[1] * (1.0 - Beta) * F
            + chi_d[1] * delayed_source
        )

        dphi_1_dt = neutron_velocity[0] * rhs_1
        dphi_2_dt = neutron_velocity[1] * rhs_2

        precursor_production = beta[:, None] * F
        precursor_advection = _precursor_advection(C, precursor_inlet, u_precursor, dz)
        dC_dt = precursor_production - lambda_i[:, None] * C - precursor_advection

        main_rhs = np.concatenate([dphi_1_dt, dphi_2_dt, dC_dt.reshape(-1)])
        if not precursor_balance_audit_enabled:
            return main_rhs

        node_weight = dz
        production_rates = node_weight * np.sum(precursor_production, axis=1)
        decay_rates = node_weight * np.sum(lambda_i[:, None] * C, axis=1)
        transport_rates = u_precursor * (C[:, -1] - precursor_inlet)
        return np.concatenate([main_rhs, production_rates, decay_rates, transport_rates])

    if precursor_balance_audit_enabled:
        audit_initial = np.zeros(3 * precursor_groups, dtype=float)
        ode_initial = np.concatenate([y0, audit_initial])
    else:
        ode_initial = y0

    y_n = ode_solver(ode_initial, [], pde_to_ode_neutronics, params, prefix="neutronics")
    if precursor_balance_audit_enabled:
        audit_values = y_n[main_state_size:, -1]
        params["last_precursor_balance_integrals"] = {
            "production": audit_values[:precursor_groups].copy(),
            "decay": audit_values[precursor_groups:2 * precursor_groups].copy(),
            "transport": audit_values[2 * precursor_groups:].copy(),
        }
        y_n = y_n[:main_state_size, :]
    else:
        params["last_precursor_balance_integrals"] = {
            "production": np.full(precursor_groups, np.nan, dtype=float),
            "decay": np.full(precursor_groups, np.nan, dtype=float),
            "transport": np.full(precursor_groups, np.nan, dtype=float),
        }

    if point_kinetics_enabled:
        phi_1_prov, phi_2_prov, C_prov = _extract_state(y_n[:, -1], N, precursor_groups)
        params["last_precursor_source_end"] = (
            xs["nu_sigma_f"][0] * phi_1_prov + xs["nu_sigma_f"][1] * phi_2_prov
        ).copy()
        total_state = advance_point_kinetics_state(
            amplitude=1.0,
            precursors=precursor_amplitudes_old,
            beta_effective=beta_effective_groups,
            lambda_i=lambda_i,
            rho=rho_feedback + external_reactivity,
            dt=outer_dt,
            prompt_generation_time=prompt_generation_time,
        )
        correction_mode = params.get("point_kinetics_correction_mode", "absolute")
        if correction_mode == "relative":
            feedback_state = advance_point_kinetics_state(
                amplitude=1.0,
                precursors=precursor_amplitudes_old,
                beta_effective=beta_effective_groups,
                lambda_i=lambda_i,
                rho=rho_feedback,
                dt=outer_dt,
                prompt_generation_time=prompt_generation_time,
            )
            phi_scale = float(total_state["amplitude"]) / max(float(feedback_state["amplitude"]), 1.0e-12)
        else:
            fission_integral_prov = float(
                np.trapezoid(xs["nu_sigma_f"][0] * phi_1_prov + xs["nu_sigma_f"][1] * phi_2_prov, z)
            )
            phi_scale = float(total_state["amplitude"]) / max(
                fission_integral_prov / max(fission_integral_old, 1.0e-12),
                1.0e-12,
            )
        phi_1 = phi_scale * phi_1_prov
        phi_2 = phi_scale * phi_2_prov
        C = C_prov
        y_n = np.concatenate([phi_1, phi_2, C.reshape(-1)])[:, None]
        params["last_prompt_jump_factor"] = phi_scale
    else:
        phi_1, phi_2, C = _extract_state(y_n[:, -1], N, precursor_groups)
        params["last_precursor_source_end"] = (
            xs["nu_sigma_f"][0] * phi_1 + xs["nu_sigma_f"][1] * phi_2
        ).copy()
        params["last_prompt_jump_factor"] = 1.0

    record_precursor_outlet(params, current_time + outer_dt, C[:, -1])

    q_vol = params["power_scale"] * np.sum(xs["sigma_f"] * np.vstack([phi_1, phi_2]), axis=0)
    q_prime = np.asarray(params["A_f"], dtype=float) * q_vol

    F = xs["nu_sigma_f"][0] * phi_1 + xs["nu_sigma_f"][1] * phi_2
    delayed_source = np.sum(lambda_i[:, None] * C, axis=0)
    params["last_effective_beta"] = float(
        np.trapezoid(delayed_source, params["z"]) / max(np.trapezoid(F, params["z"]), 1.0e-12)
    )
    params["last_effective_beta_groups"] = (
        lambda_i * np.asarray([np.trapezoid(group, z) for group in C], dtype=float)
        / max(np.trapezoid(F, z), 1.0e-12)
    )
    params["last_neutron_amplitude"] = float(
        np.trapezoid(F, z) / max(fission_integral_old, 1.0e-12)
    )

    return y_n, q_prime
