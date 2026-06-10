import numpy as np

from cross_sections import build_cross_sections, estimate_global_reactivity
from ode_solver import ode_solver
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


def neutronics(y_n, state, step, params):
    N = params["N"]
    dz = params["dz"]
    precursor_groups = params["precursor_groups"]

    beta = np.asarray(params["beta_np"], dtype=float)
    Beta = float(params["Beta"])
    lambda_i = np.asarray(params["lambda_i_np"], dtype=float)
    chi_p = np.asarray(params["chi_p"], dtype=float)
    chi_d = np.asarray(params["chi_d"], dtype=float)
    neutron_velocity = np.asarray(params["neutron_velocity"], dtype=float)
    d_e = np.asarray(params["d_e"], dtype=float)
    u_core = float(params["u_core"])
    outer_dt = float(params.get("outer_dt", 1.0))
    current_time = step * outer_dt
    precursor_inlet = precursor_inlet_from_loop(params, current_time)

    temperature_fuel = state.get("temperature_fuel")
    temperature_graphite = state.get("temperature_graphite")
    rod_position = float(state.get("rod_position", 0.0))
    external_reactivity = float(state.get("external_reactivity", 0.0))

    xs = build_cross_sections(
        temperature_fuel=temperature_fuel,
        temperature_graphite=temperature_graphite,
        params=params,
        rod_position=rod_position,
        external_reactivity=external_reactivity,
    )
    params["last_global_rho"] = estimate_global_reactivity(xs, params)
    params["last_cross_sections"] = xs

    def pde_to_ode_neutronics(t, y):
        phi_1, phi_2, C = _extract_state(y, N, precursor_groups)

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
        precursor_advection = _precursor_advection(C, precursor_inlet, u_core, dz)
        dC_dt = precursor_production - lambda_i[:, None] * C - precursor_advection

        return np.concatenate([dphi_1_dt, dphi_2_dt, dC_dt.reshape(-1)])

    if step == 0 or y_n.size != params["neutronics_state_size"]:
        y0 = _initial_state(params)
    else:
        y0 = np.asarray(y_n, dtype=float)

    solution_y_n = ode_solver(y0, [], pde_to_ode_neutronics, params)
    y_n = solution_y_n.y

    phi_1, phi_2, C = _extract_state(y_n[:, -1], N, precursor_groups)
    record_precursor_outlet(params, current_time + outer_dt, C[:, -1])

    q_vol = params["power_scale"] * np.sum(xs["sigma_f"] * np.vstack([phi_1, phi_2]), axis=0)
    q_prime = np.asarray(params["A_f"], dtype=float) * q_vol

    return y_n, q_prime
