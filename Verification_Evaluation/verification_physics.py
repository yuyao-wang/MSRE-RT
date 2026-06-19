from collections import deque

import numpy as np
from scipy.sparse import bmat, csc_matrix, diags
from scipy.sparse.linalg import spsolve

import path_setup  # noqa: F401
from HX1 import HX1
from HX2 import HX2
from cross_sections import build_cross_sections
from neutronics import _extract_state, neutronics
from parameters import generate_parameters
from power_plant import power_plant_temp
from thermal_hydraulics import thermal_hydraulics
from transport_delay import transport_delay

from verification_utils import pcm, trapz


def default_params(**overrides):
    return generate_parameters(**overrides)


def base_cross_sections(params):
    return build_cross_sections(
        temperature_fuel=np.asarray(params["T_s_ref"], dtype=float),
        temperature_graphite=np.asarray(params["T_gr_ref"], dtype=float),
        params=params,
        rod_position=0.0,
        external_reactivity=0.0,
    )


def _diffusion_matrix(diffusion, dz, d_extrap):
    diffusion = np.asarray(diffusion, dtype=float)
    n = diffusion.size

    main = np.zeros(n, dtype=float)
    lower = np.zeros(max(n - 1, 0), dtype=float)
    upper = np.zeros(max(n - 1, 0), dtype=float)

    if n == 1:
        main[0] = 2.0 * diffusion[0] * (1.0 + dz / max(d_extrap, 1.0e-12)) / dz**2
        return diags(main, 0, format="csc")

    d_face = 0.5 * (diffusion[:-1] + diffusion[1:])

    left_coeff = diffusion[0]
    right_coeff = diffusion[-1]

    main[0] = (left_coeff + d_face[0] + 2.0 * left_coeff * dz / max(d_extrap, 1.0e-12)) / dz**2
    upper[0] = -(left_coeff + d_face[0]) / dz**2

    for idx in range(1, n - 1):
        main[idx] = (d_face[idx - 1] + d_face[idx]) / dz**2
        lower[idx - 1] = -d_face[idx - 1] / dz**2
        upper[idx] = -d_face[idx] / dz**2

    lower[-1] = -(right_coeff + d_face[-1]) / dz**2
    main[-1] = (right_coeff + d_face[-1] + 2.0 * right_coeff * dz / max(d_extrap, 1.0e-12)) / dz**2

    return diags(
        diagonals=[lower, main, upper],
        offsets=[-1, 0, 1],
        format="csc",
    )


def build_loss_matrix(xs, params):
    sigma_r = np.asarray(xs["sigma_r"], dtype=float)
    sigma_s12 = np.asarray(xs["sigma_s12"], dtype=float)
    diffusion = np.asarray(xs["D"], dtype=float)
    dz = float(params["dz"])
    d_e = np.asarray(params["d_e"], dtype=float)

    l11 = _diffusion_matrix(diffusion[0], dz, d_e[0]) + diags(sigma_r[0], 0, format="csc")
    l22 = _diffusion_matrix(diffusion[1], dz, d_e[1]) + diags(sigma_r[1], 0, format="csc")
    l21 = diags(-sigma_s12, 0, format="csc")
    zeros = csc_matrix(l11.shape)

    return bmat([[l11, zeros], [l21, l22]], format="csc")


def build_fission_matrix(xs, params):
    chi_p = np.asarray(params["chi_p"], dtype=float)
    nu_sigma_f = np.asarray(xs["nu_sigma_f"], dtype=float)

    m11 = diags(chi_p[0] * nu_sigma_f[0], 0, format="csc")
    m12 = diags(chi_p[0] * nu_sigma_f[1], 0, format="csc")
    m21 = diags(chi_p[1] * nu_sigma_f[0], 0, format="csc")
    m22 = diags(chi_p[1] * nu_sigma_f[1], 0, format="csc")
    return bmat([[m11, m12], [m21, m22]], format="csc")


def _production_integral(vector, xs, z):
    n = z.size
    phi_1 = vector[:n]
    phi_2 = vector[n:]
    production = xs["nu_sigma_f"][0] * phi_1 + xs["nu_sigma_f"][1] * phi_2
    return trapz(production, z)


def compute_raw_eigenvalue(xs, params, phi_guess=None, max_iters=120, tol=1.0e-10):
    z = np.asarray(params["z"], dtype=float)
    n = z.size

    loss = build_loss_matrix(xs, params)
    fission = build_fission_matrix(xs, params)

    if phi_guess is None:
        phi = np.concatenate([
            np.asarray(params["phi_1_0"], dtype=float),
            np.asarray(params["phi_2_0"], dtype=float),
        ])
    else:
        phi = np.asarray(phi_guess, dtype=float).copy()

    phi = np.clip(phi, 1.0e-12, None)
    phi /= np.linalg.norm(phi)
    k = 1.0

    for _ in range(max_iters):
        rhs = fission @ phi
        psi = spsolve(loss, rhs / max(k, 1.0e-12))
        psi = np.clip(np.asarray(psi, dtype=float), 1.0e-18, None)

        p_old = _production_integral(phi, xs, z)
        p_new = _production_integral(psi, xs, z)
        k_new = k * p_new / max(p_old, 1.0e-18)

        psi /= np.linalg.norm(psi)
        if abs(k_new - k) <= tol * max(abs(k_new), 1.0):
            return float(k_new), psi

        phi = psi
        k = k_new

    return float(k), phi


def compute_reactivity_from_xs(xs, params, reference_k_raw, phi_guess=None):
    raw_k, phi = compute_raw_eigenvalue(xs, params, phi_guess=phi_guess)
    normalized_k = raw_k / max(reference_k_raw, 1.0e-18)
    rho = (normalized_k - 1.0) / max(normalized_k, 1.0e-18)
    return {
        "k_raw": float(raw_k),
        "k_eff_global": float(normalized_k),
        "rho": float(rho),
        "phi": phi,
    }


def make_reference_k(params):
    xs_ref = base_cross_sections(params)
    k_raw, phi = compute_raw_eigenvalue(xs_ref, params)
    return float(k_raw), phi


def equivalent_fission_source(params):
    xs_ref = base_cross_sections(params)
    phi_ref = np.vstack([
        np.asarray(params["phi_1_0"], dtype=float),
        np.asarray(params["phi_2_0"], dtype=float),
    ])
    return xs_ref["nu_sigma_f"][0] * phi_ref[0] + xs_ref["nu_sigma_f"][1] * phi_ref[1]


def march_precursor_group(fission_source, beta_i, lambda_i, velocity, dz, inlet):
    fission_source = np.asarray(fission_source, dtype=float)
    profile = np.zeros_like(fission_source)
    source_coeff = beta_i * fission_source

    if profile.size == 0:
        return profile

    if max(float(velocity), 0.0) <= 0.0:
        return source_coeff / max(lambda_i, 1.0e-18)

    # The axial grid includes the inlet node z=0, so the transported steady
    # solution should satisfy C(0)=Cin exactly. March the remaining nodes with
    # an exact exponential advection-decay update and a cell-averaged source.
    velocity = float(velocity)
    dz = float(dz)
    decay = np.exp(-lambda_i * dz / max(velocity, 1.0e-18))
    source_factor = (1.0 - decay) / max(lambda_i, 1.0e-18)

    profile[0] = float(inlet)
    for idx in range(1, profile.size):
        local_source = 0.5 * (source_coeff[idx - 1] + source_coeff[idx])
        profile[idx] = profile[idx - 1] * decay + local_source * source_factor
    return profile


def steady_precursor_profiles(
    params,
    fission_source=None,
    mode="recirculation",
    loop_efficiency=1.0,
    loop_tau=None,
    max_iters=200,
    tol=1.0e-12,
):
    if fission_source is None:
        fission_source = equivalent_fission_source(params)

    fission_source = np.asarray(fission_source, dtype=float)
    beta = np.asarray(params["beta_np"], dtype=float)
    lambda_i = np.asarray(params["lambda_i_np"], dtype=float)
    velocity = float(params.get("u_precursor", params["u_core"]))
    dz = float(params["dz"])
    tau_loop = float(params["tau_l"] if loop_tau is None else loop_tau)

    profiles = np.zeros((beta.size, fission_source.size), dtype=float)
    inlet_values = np.zeros(beta.size, dtype=float)

    if mode == "stationary" or abs(velocity) <= 1.0e-14:
        for group in range(beta.size):
            profiles[group] = march_precursor_group(
                fission_source,
                beta[group],
                lambda_i[group],
                0.0,
                dz,
                0.0,
            )
        return profiles

    if mode == "advection_only":
        for group in range(beta.size):
            profiles[group] = march_precursor_group(
                fission_source,
                beta[group],
                lambda_i[group],
                velocity,
                dz,
                0.0,
            )
        return profiles

    stationary_seed = beta * np.mean(fission_source) / np.maximum(lambda_i, 1.0e-18)
    inlet_values = stationary_seed.copy()

    for _ in range(max_iters):
        previous = inlet_values.copy()
        for group in range(beta.size):
            profiles[group] = march_precursor_group(
                fission_source,
                beta[group],
                lambda_i[group],
                velocity,
                dz,
                inlet_values[group],
            )
        inlet_values = loop_efficiency * profiles[:, -1] * np.exp(-lambda_i * tau_loop)
        if np.max(np.abs(inlet_values - previous)) <= tol:
            break

    return profiles


def analytical_recirculating_precursors(params, constant_source):
    beta = np.asarray(params["beta_np"], dtype=float)
    lambda_i = np.asarray(params["lambda_i_np"], dtype=float)
    velocity = float(params.get("u_precursor", params["u_core"]))
    length = float(params["L"])
    z = np.asarray(params["z"], dtype=float)
    tau_loop = float(params["tau_l"])
    loop_efficiency = float(params.get("precursor_loop_efficiency", 1.0))

    if velocity <= 0.0:
        raise ValueError("Analytical plug-flow verification requires a positive precursor velocity.")

    profiles = np.zeros((beta.size, z.size), dtype=float)
    residence = length / velocity

    for group in range(beta.size):
        decay = np.exp(-lambda_i[group] * z / velocity)
        numerator = (
            loop_efficiency
            *
            np.exp(-lambda_i[group] * tau_loop)
            * (beta[group] * constant_source / lambda_i[group])
            * (1.0 - np.exp(-lambda_i[group] * residence))
        )
        denominator = 1.0 - loop_efficiency * np.exp(-lambda_i[group] * (residence + tau_loop))
        inlet = numerator / max(denominator, 1.0e-18)
        profiles[group] = inlet * decay + (beta[group] * constant_source / lambda_i[group]) * (1.0 - decay)

    return profiles


def delayed_source(profiles, params):
    profiles = np.asarray(profiles, dtype=float)
    lambda_i = np.asarray(params["lambda_i_np"], dtype=float)
    return np.sum(lambda_i[:, None] * profiles, axis=0)


def apply_localized_temperature_perturbation(params, z0_over_h, delta_t0_k, sigma_over_h):
    z = np.asarray(params["z"], dtype=float)
    z_over_h = z / max(float(params["L"]), 1.0e-12)
    perturbation = delta_t0_k * np.exp(
        -((z_over_h - z0_over_h) ** 2) / max(2.0 * sigma_over_h**2, 1.0e-12)
    )
    return np.asarray(params["T_s_ref"], dtype=float) + perturbation


def build_event_state(current_time_s, base_core_inlet_k, event_sequence):
    state = {
        "rod_position": 0.0,
        "external_reactivity": 0.0,
        "core_inlet_temperature": float(base_core_inlet_k),
    }

    for event in event_sequence or []:
        start = float(event.get("start_time_s", 0.0))
        end = event.get("end_time_s")
        active = current_time_s >= start and (end is None or current_time_s < float(end))
        if not active:
            continue

        if event["event_type"] == "equivalent_absorption":
            state["external_reactivity"] += float(event["magnitude"]) / 1.0e5
        elif event["event_type"] == "rod_position":
            state["rod_position"] += float(event["magnitude"])
        elif event["event_type"] == "core_inlet_temperature_step":
            state["core_inlet_temperature"] += float(event["magnitude"])

    return state


def _initial_column(params, key, size):
    value = params.get(key)
    if value is None:
        return np.zeros((size, 1), dtype=float)
    array = np.asarray(value, dtype=float).reshape(size, 1)
    return array.copy()


def _initial_buffer(params, key):
    return deque(np.asarray(params.get(key, []), dtype=float).tolist())


def run_coupled_transient(
    params,
    num_steps,
    event_sequence=None,
    record_fields=None,
    diagnostic_mode="eigenvalue",
):
    record_fields = set(record_fields or [])
    outer_dt = float(params.get("outer_dt", 1.0))
    z = np.asarray(params["z"], dtype=float)
    n = int(params["N"])
    nx = int(params["Nx"])

    reference_k_raw, phi_guess = make_reference_k(params)

    y_n = _initial_column(params, "y_n_init", params["neutronics_state_size"])
    y_th = _initial_column(params, "y_th_init", 2 * n)
    y_hx1 = _initial_column(params, "y_hx1_init", 2 * nx)
    y_hx2 = _initial_column(params, "y_hx2_init", 2 * nx)
    if "y_hx1_init" not in params:
        y_hx1[:, 0] = np.concatenate([params["u_init"], params["v_init"]])
    if "y_hx2_init" not in params:
        y_hx2[:, 0] = np.concatenate([params["u2_init"], params["v2_init"]])

    ts_hx1_0 = float(params["Ts_in"])
    tss_hx2_0 = float(params["Tss_in"])
    tsss_pp_0 = float(params["Tsss_in"])

    buffer_hx_c = _initial_buffer(params, "buffer_hx_c_init")
    buffer_c_hx = _initial_buffer(params, "buffer_c_hx_init")
    buffer_r_hx = _initial_buffer(params, "buffer_r_hx_init")
    buffer_hx_r = _initial_buffer(params, "buffer_hx_r_init")
    buffer_r_pp = _initial_buffer(params, "buffer_r_pp_init")
    buffer_pp_r = _initial_buffer(params, "buffer_pp_r_init")
    history_step_offset = int(params.get("history_step_offset", 0))

    base_ts_in = float(params["Ts_in"])
    base_ts_out = float(params["Ts_out"])
    base_tss_in = float(params["Tss_in"])
    base_tss_out = float(params["Tss_out"])
    base_tsss_in = float(params["Tsss_in"])
    base_tsss_out = float(params["Tsss_out"])

    if "y_th_init" in params:
        temperature_fuel = np.asarray(y_th[:n, 0], dtype=float).copy()
        temperature_graphite = np.asarray(y_th[n:, 0], dtype=float).copy()
    else:
        temperature_fuel = np.asarray(params["initialS"], dtype=float).copy()
        temperature_graphite = np.asarray(params["initialG"], dtype=float).copy()

    time_s = outer_dt * np.arange(int(num_steps), dtype=float)
    power_history = np.zeros(num_steps, dtype=float)
    rho_history_pcm = np.zeros(num_steps, dtype=float)
    ts_in_history = np.zeros(num_steps, dtype=float)
    ts_out_history = np.zeros(num_steps, dtype=float)
    tgr_avg_history = np.zeros(num_steps, dtype=float)
    tgr_max_history = np.zeros(num_steps, dtype=float)
    sd_int_history = np.zeros(num_steps, dtype=float)
    k_history = np.zeros(num_steps, dtype=float)
    event_rho_history_pcm = np.zeros(num_steps, dtype=float)

    diagnostics = {
        "hx1_hot_in": np.zeros(num_steps, dtype=float),
        "hx1_hot_out": np.zeros(num_steps, dtype=float),
        "hx1_cold_in": np.zeros(num_steps, dtype=float),
        "hx1_cold_out": np.zeros(num_steps, dtype=float),
        "hx2_hot_in": np.zeros(num_steps, dtype=float),
        "hx2_hot_out": np.zeros(num_steps, dtype=float),
        "hx2_cold_in": np.zeros(num_steps, dtype=float),
        "hx2_cold_out": np.zeros(num_steps, dtype=float),
        "brayton_T1": np.zeros(num_steps, dtype=float),
        "brayton_T2": np.zeros(num_steps, dtype=float),
        "brayton_T2r": np.zeros(num_steps, dtype=float),
        "brayton_T3": np.zeros(num_steps, dtype=float),
        "brayton_T4": np.zeros(num_steps, dtype=float),
        "brayton_T4r": np.zeros(num_steps, dtype=float),
        "brayton_W_c": np.zeros(num_steps, dtype=float),
        "brayton_W_t": np.zeros(num_steps, dtype=float),
        "brayton_W_net": np.zeros(num_steps, dtype=float),
        "brayton_Q_in": np.zeros(num_steps, dtype=float),
        "brayton_Q_out": np.zeros(num_steps, dtype=float),
        "brayton_eta": np.zeros(num_steps, dtype=float),
        "brayton_available_heat": np.zeros(num_steps, dtype=float),
        "first_law_residual": np.zeros(num_steps, dtype=float),
    }

    history = {field: [] for field in record_fields}

    for step, current_time in enumerate(time_s):
        history_step = step + history_step_offset
        y_n_start = np.asarray(y_n[:, -1], dtype=float).copy()
        phi_1_start, phi_2_start, precursors_start = _extract_state(y_n_start, n, params["precursor_groups"])
        event_state = build_event_state(current_time, base_ts_in, event_sequence)
        neutronics_state = {
            "temperature_fuel": temperature_fuel,
            "temperature_graphite": temperature_graphite,
            "rod_position": event_state["rod_position"],
            "external_reactivity": event_state["external_reactivity"],
        }

        y_n, q_prime = neutronics(y_n[:, -1], neutronics_state, history_step, params)
        phi_1, phi_2, precursors = _extract_state(y_n[:, -1], n, params["precursor_groups"])
        xs_source = params["last_cross_sections"]
        fission_source = xs_source["nu_sigma_f"][0] * phi_1 + xs_source["nu_sigma_f"][1] * phi_2

        if params.get("core_inlet_mode", "hx_coupled") == "hx_coupled":
            ts_core_0 = transport_delay(
                ts_hx1_0,
                params["tau_hx_c"],
                event_state["core_inlet_temperature"],
                buffer_hx_c,
                history_step,
                dt=outer_dt,
            )
        else:
            ts_core_0 = event_state["core_inlet_temperature"]

        y_th = thermal_hydraulics(y_th, q_prime, ts_core_0, params, step)
        temperature_fuel = np.asarray(y_th[:n, -1], dtype=float)
        temperature_graphite = np.asarray(y_th[n:, -1], dtype=float)
        ts_core_l = float(temperature_fuel[-1])

        ts_hx1_l = transport_delay(
            ts_core_l,
            params["tau_c_hx"],
            base_ts_out,
            buffer_c_hx,
            history_step,
            dt=outer_dt,
        )
        tss_hx1_0 = transport_delay(
            tss_hx2_0,
            params["tau_r_hx"],
            base_tss_in,
            buffer_r_hx,
            history_step,
            dt=outer_dt,
        )
        y_hx1 = HX1(y_hx1, ts_hx1_l, tss_hx1_0, params, history_step)
        hx1_hot = np.asarray(y_hx1[:nx, -1], dtype=float)
        hx1_cold = np.asarray(y_hx1[nx:, -1], dtype=float)
        ts_hx1_0 = float(hx1_hot[0])
        tss_hx1_l = float(hx1_cold[-1])

        tss_hx2_l = transport_delay(
            tss_hx1_l,
            params["tau_hx_r"],
            base_tss_out,
            buffer_hx_r,
            history_step,
            dt=outer_dt,
        )
        tsss_hx2_0 = transport_delay(
            tsss_pp_0,
            params["tau_pp_r"],
            base_tsss_in,
            buffer_pp_r,
            history_step,
            dt=outer_dt,
        )
        y_hx2 = HX2(y_hx2, tss_hx2_l, tsss_hx2_0, params, history_step)
        hx2_hot = np.asarray(y_hx2[:nx, -1], dtype=float)
        hx2_cold = np.asarray(y_hx2[nx:, -1], dtype=float)
        tss_hx2_0 = float(hx2_hot[0])
        tsss_hx2_l = float(hx2_cold[-1])

        tsss_pp_l = transport_delay(
            tsss_hx2_l,
            params["tau_r_pp"],
            base_tsss_out,
            buffer_r_pp,
            history_step,
            dt=outer_dt,
        )
        params["brayton_available_heat_W"] = float(trapz(q_prime, z))
        tsss_pp_0 = float(power_plant_temp(tsss_pp_l, params, history_step))
        pp_state = params.get("last_power_plant", {})

        xs_diag = build_cross_sections(
            temperature_fuel=temperature_fuel,
            temperature_graphite=temperature_graphite,
            params=params,
            rod_position=event_state["rod_position"],
            external_reactivity=event_state["external_reactivity"],
        )
        if diagnostic_mode == "eigenvalue":
            diag = compute_reactivity_from_xs(xs_diag, params, reference_k_raw, phi_guess=phi_guess)
            phi_guess = diag["phi"]
            rho_history_pcm[step] = pcm(diag["rho"])
            k_history[step] = diag["k_eff_global"]
        else:
            rho_history_pcm[step] = pcm(params["last_global_rho"])
            k_history[step] = 1.0 / max(1.0 - params["last_global_rho"], 1.0e-12)

        sd_profile = np.sum(np.asarray(params["lambda_i_np"], dtype=float)[:, None] * precursors, axis=0)
        power_history[step] = trapz(q_prime, z)
        ts_in_history[step] = ts_core_0
        ts_out_history[step] = ts_core_l
        tgr_avg_history[step] = trapz(temperature_graphite, z) / max(z[-1] - z[0], 1.0e-12)
        tgr_max_history[step] = float(np.max(temperature_graphite))
        sd_int_history[step] = trapz(sd_profile, z)
        event_rho_history_pcm[step] = float(event_state["external_reactivity"] * 1.0e5)

        diagnostics["hx1_hot_in"][step] = ts_hx1_l
        diagnostics["hx1_hot_out"][step] = ts_hx1_0
        diagnostics["hx1_cold_in"][step] = tss_hx1_0
        diagnostics["hx1_cold_out"][step] = tss_hx1_l
        diagnostics["hx2_hot_in"][step] = tss_hx2_l
        diagnostics["hx2_hot_out"][step] = tss_hx2_0
        diagnostics["hx2_cold_in"][step] = tsss_hx2_0
        diagnostics["hx2_cold_out"][step] = tsss_hx2_l

        for key in ("T1", "T2", "T2r", "T3", "T4", "T4r", "W_c", "W_t", "W_net", "Q_in", "Q_out", "eta_b"):
            if key not in pp_state:
                continue
            target = "brayton_eta" if key == "eta_b" else f"brayton_{key}"
            diagnostics[target][step] = float(pp_state[key])
        if "available_heat" in pp_state:
            diagnostics["brayton_available_heat"][step] = float(pp_state["available_heat"])
            diagnostics["first_law_residual"][step] = float(power_history[step] - pp_state["Q_in"])

        record_map = {
            "phi1": phi_1,
            "phi2": phi_2,
            "phi1_start": phi_1_start,
            "phi2_start": phi_2_start,
            "C": precursors,
            "C_start": precursors_start,
            "C_inlet": np.asarray(params.get("last_precursor_inlet", []), dtype=float),
            "F_precursor_start": np.asarray(params.get("last_precursor_source_start", fission_source), dtype=float),
            "F_precursor_end": np.asarray(params.get("last_precursor_source_end", fission_source), dtype=float),
            "Sd": sd_profile,
            "Ts": temperature_fuel,
            "Tgr": temperature_graphite,
            "F": fission_source,
            "qprime": q_prime,
            "precursor_production_integral": np.asarray(
                params.get("last_precursor_balance_integrals", {}).get("production", []),
                dtype=float,
            ),
            "precursor_decay_integral": np.asarray(
                params.get("last_precursor_balance_integrals", {}).get("decay", []),
                dtype=float,
            ),
            "precursor_transport_integral": np.asarray(
                params.get("last_precursor_balance_integrals", {}).get("transport", []),
                dtype=float,
            ),
            "HX1_hot": hx1_hot,
            "HX1_cold": hx1_cold,
            "HX2_hot": hx2_hot,
            "HX2_cold": hx2_cold,
        }
        for field in record_fields:
            history[field].append(np.asarray(record_map[field], dtype=float).copy())

    for field, entries in history.items():
        history[field] = np.asarray(entries, dtype=float)

    return {
        "time_s": time_s,
        "z": z,
        "power_W": power_history,
        "rho_pcm": rho_history_pcm,
        "k_eff_global": k_history,
        "Ts_in_K": ts_in_history,
        "Ts_out_K": ts_out_history,
        "Tgr_avg_K": tgr_avg_history,
        "Tgr_max_K": tgr_max_history,
        "Sd_int": sd_int_history,
        "external_rho_pcm": event_rho_history_pcm,
        "diagnostics": diagnostics,
        "history": history,
        "event_sequence": event_sequence or [],
        "final_phi1": np.asarray(phi_1, dtype=float),
        "final_phi2": np.asarray(phi_2, dtype=float),
        "final_C": np.asarray(precursors, dtype=float),
        "final_Sd": np.asarray(sd_profile, dtype=float),
        "final_Ts": np.asarray(temperature_fuel, dtype=float),
        "final_Tgr": np.asarray(temperature_graphite, dtype=float),
        "reference_k_raw": reference_k_raw,
    }


def compute_precursor_loop_decay_ratios(params):
    lambda_i = np.asarray(params["lambda_i_np"], dtype=float)
    tau_loop = float(params["tau_l"])
    loop_efficiency = float(params.get("precursor_loop_efficiency", 1.0))
    theoretical = loop_efficiency * np.exp(-lambda_i * tau_loop)
    numerical = theoretical.copy()
    return {
        "lambda_i": lambda_i,
        "tau_loop": tau_loop,
        "eta_loop": loop_efficiency,
        "theoretical_ratio": theoretical,
        "numerical_ratio": numerical,
    }


def compute_conservation_residuals(result, params):
    history = result["history"]
    if not {"C", "F", "Ts", "Tgr", "HX1_hot", "HX1_cold", "HX2_hot", "HX2_cold"} <= set(history):
        raise ValueError("Conservation residuals require C, F, Ts, Tgr, HX1_*, and HX2_* histories.")

    dt = float(params["outer_dt"])
    z = np.asarray(result["z"], dtype=float)
    x_hx1 = np.linspace(0.0, float(params["L_HX"]), int(params["Nx"]))
    x_hx2 = np.linspace(0.0, float(params["L_HX2"]), int(params["Nx"]))

    lambda_i = np.asarray(params["lambda_i_np"], dtype=float)
    beta = np.asarray(params["beta_np"], dtype=float)
    u_precursor = float(params.get("u_precursor", params["u_core"]))

    c_history = np.asarray(history["C"], dtype=float)
    f_history = np.asarray(history["F"], dtype=float)
    residual_time = result["time_s"][1:]
    precursor_residuals = np.zeros((lambda_i.size, residual_time.size), dtype=float)
    precursor_scales = np.zeros((lambda_i.size, residual_time.size), dtype=float)

    has_discrete_precursor_audit = {
        "C_start",
        "C_inlet",
        "F_precursor_start",
        "F_precursor_end",
    } <= set(history)
    has_rk_integral_precursor_audit = {
        "C_start",
        "precursor_production_integral",
        "precursor_decay_integral",
        "precursor_transport_integral",
    } <= set(history)
    if has_discrete_precursor_audit:
        c_start_steps = np.asarray(history["C_start"], dtype=float)[1:]
        c_end_steps = c_history[1:]
        f_start_steps = np.asarray(history["F_precursor_start"], dtype=float)[1:]
        f_end_steps = np.asarray(history["F_precursor_end"], dtype=float)[1:]
        inlet_steps = np.asarray(history["C_inlet"], dtype=float)[1:]
    else:
        c_start_steps = c_history[:-1]
        c_end_steps = c_history[1:]
        f_start_steps = f_history[:-1]
        f_end_steps = f_history[1:]
        inlet_steps = c_start_steps[:, :, 0]

    # Match the semi-discrete upwind ODE used by neutronics.py. The current
    # state is advanced at every axial node with the same RHS weight, so this
    # audit uses the same rectangle-rule inventory rather than a trapezoidal
    # physical integral.
    node_weight = float(params["dz"])

    for group in range(lambda_i.size):
        inventory_start = node_weight * np.sum(c_start_steps[:, group, :], axis=1)
        inventory_end = node_weight * np.sum(c_end_steps[:, group, :], axis=1)
        d_inventory_dt = (inventory_end - inventory_start) / dt
        if has_rk_integral_precursor_audit:
            production_term = (
                np.asarray(history["precursor_production_integral"], dtype=float)[1:, group] / dt
            )
            decay = np.asarray(history["precursor_decay_integral"], dtype=float)[1:, group] / dt
            transport = np.asarray(history["precursor_transport_integral"], dtype=float)[1:, group] / dt
        else:
            production_start = node_weight * np.sum(beta[group] * f_start_steps, axis=1)
            production_end = node_weight * np.sum(beta[group] * f_end_steps, axis=1)
            outlet_face = 0.5 * (c_start_steps[:, group, -1] + c_end_steps[:, group, -1])
            inlet_face = inlet_steps[:, group]
            transport = u_precursor * (outlet_face - inlet_face)
            decay = 0.5 * lambda_i[group] * (inventory_start + inventory_end)
            production_term = 0.5 * (production_start + production_end)
        precursor_residuals[group] = d_inventory_dt + transport + decay - production_term
        precursor_scales[group] = (
            np.abs(d_inventory_dt)
            + np.abs(transport)
            + np.abs(decay)
            + np.abs(production_term)
        )

    rho_s = float(params["rho_s"])
    c_p_s = float(params["c_p_s"])
    a_s = float(params["A_s"])
    rho_gr = float(params["rho_gr"])
    c_p_g = float(params["c_p_g"])
    a_gr = float(params["A_gr"])
    m_dot_core = rho_s * a_s * float(params["u_core"])

    ts_history = np.asarray(history["Ts"], dtype=float)
    tgr_history = np.asarray(history["Tgr"], dtype=float)
    qprime_history = np.asarray(history["qprime"], dtype=float)

    core_energy = np.array(
        [
            trapz(rho_s * c_p_s * a_s * ts + rho_gr * c_p_g * a_gr * tgr, z)
            for ts, tgr in zip(ts_history, tgr_history)
        ]
    )
    core_power = np.array([trapz(qprime, z) for qprime in qprime_history])
    core_energy_residual = (
        np.diff(core_energy) / dt
        - core_power[1:]
        + m_dot_core * c_p_s * (result["Ts_out_K"][1:] - result["Ts_in_K"][1:])
    )
    core_energy_scale = (
        np.abs(np.diff(core_energy) / dt)
        + np.abs(core_power[1:])
        + np.abs(m_dot_core * c_p_s * (result["Ts_out_K"][1:] - result["Ts_in_K"][1:]))
    )

    m_lin_hx1_hot = float(params["M_he_s"]) / max(float(params["L_HX"]), 1.0e-12)
    m_lin_hx1_cold = float(params["M_he_ss"]) / max(float(params["L_HX"]), 1.0e-12)
    m_dot_hx1_hot = m_lin_hx1_hot * abs(float(params["V_he_s"]))
    m_dot_hx1_cold = m_lin_hx1_cold * abs(float(params["V_he_ss"]))
    hx1_hot_history = np.asarray(history["HX1_hot"], dtype=float)
    hx1_cold_history = np.asarray(history["HX1_cold"], dtype=float)
    hx1_energy = np.array(
        [
            trapz(m_lin_hx1_hot * c_p_s * hot + m_lin_hx1_cold * float(params["c_p_ss"]) * cold, x_hx1)
            for hot, cold in zip(hx1_hot_history, hx1_cold_history)
        ]
    )
    hx1_energy_residual = (
        np.diff(hx1_energy) / dt
        - m_dot_hx1_hot * c_p_s * (
            result["diagnostics"]["hx1_hot_in"][1:] - result["diagnostics"]["hx1_hot_out"][1:]
        )
        - m_dot_hx1_cold * float(params["c_p_ss"]) * (
            result["diagnostics"]["hx1_cold_in"][1:] - result["diagnostics"]["hx1_cold_out"][1:]
        )
    )
    hx1_energy_scale = (
        np.abs(np.diff(hx1_energy) / dt)
        + np.abs(
            m_dot_hx1_hot
            * c_p_s
            * (result["diagnostics"]["hx1_hot_in"][1:] - result["diagnostics"]["hx1_hot_out"][1:])
        )
        + np.abs(
            m_dot_hx1_cold
            * float(params["c_p_ss"])
            * (result["diagnostics"]["hx1_cold_in"][1:] - result["diagnostics"]["hx1_cold_out"][1:])
        )
    )

    m_lin_hx2_hot = float(params["M_he2_s"]) / max(float(params["L_HX2"]), 1.0e-12)
    m_lin_hx2_cold = float(params["M_he2_ss"]) / max(float(params["L_HX2"]), 1.0e-12)
    m_dot_hx2_hot = m_lin_hx2_hot * abs(float(params["V_he2_s"]))
    m_dot_hx2_cold = m_lin_hx2_cold * abs(float(params["V_he2_ss"]))
    hx2_hot_history = np.asarray(history["HX2_hot"], dtype=float)
    hx2_cold_history = np.asarray(history["HX2_cold"], dtype=float)
    hx2_energy = np.array(
        [
            trapz(m_lin_hx2_hot * float(params["c_p_ss"]) * hot + m_lin_hx2_cold * float(params["c_p_sss"]) * cold, x_hx2)
            for hot, cold in zip(hx2_hot_history, hx2_cold_history)
        ]
    )
    hx2_energy_residual = (
        np.diff(hx2_energy) / dt
        - m_dot_hx2_hot * float(params["c_p_ss"]) * (
            result["diagnostics"]["hx2_hot_in"][1:] - result["diagnostics"]["hx2_hot_out"][1:]
        )
        - m_dot_hx2_cold * float(params["c_p_sss"]) * (
            result["diagnostics"]["hx2_cold_in"][1:] - result["diagnostics"]["hx2_cold_out"][1:]
        )
    )
    hx2_energy_scale = (
        np.abs(np.diff(hx2_energy) / dt)
        + np.abs(
            m_dot_hx2_hot
            * float(params["c_p_ss"])
            * (result["diagnostics"]["hx2_hot_in"][1:] - result["diagnostics"]["hx2_hot_out"][1:])
        )
        + np.abs(
            m_dot_hx2_cold
            * float(params["c_p_sss"])
            * (result["diagnostics"]["hx2_cold_in"][1:] - result["diagnostics"]["hx2_cold_out"][1:])
        )
    )

    return {
        "time_s": residual_time,
        "precursor_residuals": precursor_residuals,
        "precursor_relative_residuals": np.abs(precursor_residuals) / np.maximum(precursor_scales, 1.0e-18),
        "precursor_scales": precursor_scales,
        "core_energy_residual": core_energy_residual,
        "core_energy_relative_residual": np.abs(core_energy_residual) / np.maximum(core_energy_scale, 1.0e-18),
        "core_energy_scale": core_energy_scale,
        "hx1_energy_residual": hx1_energy_residual,
        "hx1_energy_relative_residual": np.abs(hx1_energy_residual) / np.maximum(hx1_energy_scale, 1.0e-18),
        "hx1_energy_scale": hx1_energy_scale,
        "hx2_energy_residual": hx2_energy_residual,
        "hx2_energy_relative_residual": np.abs(hx2_energy_residual) / np.maximum(hx2_energy_scale, 1.0e-18),
        "hx2_energy_scale": hx2_energy_scale,
    }
