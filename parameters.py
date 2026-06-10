import numpy as np
from scipy.sparse import csc_matrix

from precursor_loop import initialize_precursor_loop_state
from steady_state import initialize_system_steady_state


def _fundamental_shape(z, dz, length):
    phase = (z + 0.5 * dz) / (length + dz)
    shape = np.sin(np.pi * phase)
    return np.clip(shape, 1.0e-3, None)


def _group_profile(values, axial_shape):
    base = np.asarray(values, dtype=float)[:, None]
    return base * axial_shape[None, :]


def generate_parameters(
    dt=0.1,
    L=172.0,
    N=80,
    A=4094.0,
    nominal_total_power=1.0e5,
    v_core=0.2,
    inlet_mode="recirculate",
    core_inlet_mode="hx_coupled",
    neutron_velocity=(0.55, 0.18),
    beta=(0.000228, 0.000788, 0.000664, 0.000736, 0.000136, 0.000088),
    lambda_i=(0.0126, 0.0337, 0.139, 0.325, 1.13, 2.5),
    c_p_s=2090.0,
    c_p_g=1757.0,
    Vc=0.2,
    Ms=1448.0,
    Mg=3687.0,
    gamma=0.30,
    U_sg=15000.0,
    U_gs=15000.0,
    bc_s0=908.0,
    bc_sL=936.0,
    bc_g0=918.0,
    bc_gL=946.0,
    err=0.0,
    L_HX=2.0,
    V_he_s=75.7e-3 / 23.6,
    V_he_ss=53.6e-3 / 23.6,
    U_hx=500.0,
    M_he_s=342.0,
    M_he_ss=117.0,
    c_p_ss=2416.0,
    h_s=0.1,
    k_s=0.5,
    h_ss=0.1,
    k_ss=0.5,
    T_ambient=780.0,
    u_L=940.0,
    u_H=908.0,
    v_L=802.0,
    v_H=902.0,
    L_HX2=2.0,
    V_he2_s=53.6e-3 / 23.6,
    V_he2_ss=33.6e-3 / 23.6,
    U2_hx=500.0,
    M_he2_s=117.0,
    M_he2_ss=100.0,
    c_p_sss=2416.0,
    brayton_gamma=1.28,
    brayton_eta_c=0.89,
    brayton_eta_t=0.91,
    brayton_pi_c=1.20,
    brayton_pi_t=1.20,
    brayton_recuperator_efficiency=0.95,
    brayton_cooler_outlet_temp=620.0,
    brayton_min_heater_approach=12.0,
    brayton_mdot=100.0,
    u2_L=802.0,
    u2_H=902.0,
    v2_L=792.0,
    v2_H=830.0,
    tau_l=16.73,
    tau_c=8.46,
    tau_hx_c=4.0,
    tau_c_hx=4.0,
    tau_hx_r=5.0,
    tau_r_hx=8.0,
    tau_r_pp=6.0,
    tau_pp_r=6.0,
    precursor_loop_efficiency=0.92,
    outer_dt=1.0,
    scale=1.0,
    use_steady_state_initialization=True,
    steady_state_steps=180,
):
    z = np.linspace(0.0, L, N)
    dz = L / (N - 1)
    Nx = N
    dx = L / (Nx - 1)

    beta = np.asarray(beta, dtype=float)
    lambda_i = np.asarray(lambda_i, dtype=float)
    beta_total = float(beta.sum())
    neutron_velocity = np.asarray(neutron_velocity, dtype=float)

    initialS = bc_s0 + (bc_sL - bc_s0) * (0.2 + 0.8 * z / L)
    initialG = bc_g0 + (bc_gL - bc_g0) * (0.15 + 0.85 * z / L)
    T_s_ref = initialS.copy()
    T_gr_ref = initialG.copy()

    mode_shape = _fundamental_shape(z, dz, L)
    axial_slow_taper = 1.0 + 0.04 * np.cos(np.pi * z / L)
    axial_fast_taper = 1.0 + 0.02 * np.sin(2.0 * np.pi * z / L)

    nu = np.asarray([2.45, 2.45], dtype=float)
    chi_p = np.asarray([1.0, 0.0], dtype=float)
    chi_d = np.asarray([1.0, 0.0], dtype=float)
    d_e = np.asarray([2.0 * dz, 2.0 * dz], dtype=float)

    D_ref = np.vstack([
        1.35 * axial_fast_taper,
        0.45 * axial_slow_taper,
    ])
    sigma_s12_ref = 0.0120 * axial_slow_taper
    sigma_a_ref = np.vstack([
        0.0027 * axial_fast_taper,
        0.0054 * axial_slow_taper,
    ])
    sigma_f_ref = np.vstack([
        6.0e-4 * axial_fast_taper,
        2.45e-3 * axial_slow_taper,
    ])
    nu_sigma_f_ref = nu[:, None] * sigma_f_ref
    transverse_buckling_sq = np.zeros((2, N), dtype=float)

    a_sigma_a_s = _group_profile([2.6e-6, 4.1e-6], np.ones(N))
    a_sigma_a_gr = _group_profile([1.8e-6, 2.6e-6], np.ones(N))
    a_sigma_s12_s = -5.5e-7 * np.ones(N)
    a_sigma_s12_gr = -3.5e-7 * np.ones(N)
    a_nu_sigma_f_s = _group_profile([-2.4e-6, -4.3e-6], np.ones(N))
    a_nu_sigma_f_gr = _group_profile([-1.7e-6, -2.9e-6], np.ones(N))
    a_D_s = _group_profile([2.0e-5, 1.2e-5], np.ones(N))
    a_D_gr = _group_profile([1.2e-5, 8.0e-6], np.ones(N))

    rod_shape = np.vstack([
        np.exp(-((z - 0.55 * L) ** 2) / (2.0 * (0.17 * L) ** 2)),
        np.exp(-((z - 0.55 * L) ** 2) / (2.0 * (0.16 * L) ** 2)),
    ])
    rod_shape /= rod_shape.max(axis=1, keepdims=True)
    rod_sigma_a_amplitude = np.asarray([3.0e-4, 9.0e-4], dtype=float)
    external_reactivity_to_absorption = np.asarray([4.0e-4, 1.2e-3], dtype=float)

    phi_1_0 = 0.45 * mode_shape
    phi_2_0 = 1.00 * mode_shape
    phi_0 = np.concatenate([phi_1_0, phi_2_0])
    phi_ref = np.vstack([phi_1_0, phi_2_0])

    F0 = np.sum(nu_sigma_f_ref * phi_ref, axis=0)
    precursor_reduction = 1.0 / (1.0 + (v_core * tau_l / max(L, 1.0)))
    c0_groups = beta[:, None] * F0[None, :] / lambda_i[:, None]
    c0_groups *= precursor_reduction
    c0 = c0_groups.reshape(-1)

    A_f = A * np.ones(N)
    sigma_f_total_ref = np.sum(sigma_f_ref * phi_ref, axis=0)
    raw_power = np.trapz(A_f * sigma_f_total_ref, z)
    power_scale = nominal_total_power / max(raw_power, 1.0e-12)

    reference_production = np.trapz(np.sum(nu_sigma_f_ref * phi_ref, axis=0), z)
    reference_absorption = np.trapz(np.sum(sigma_a_ref * phi_ref, axis=0), z)
    reference_multiplication_ratio = reference_production / max(reference_absorption, 1.0e-12)

    precursor_loop_state = initialize_precursor_loop_state(
        precursor_groups=beta.size,
        seed_outlet=c0_groups[:, -1],
        outer_dt=outer_dt,
        tau_loop=tau_l,
    )

    A_s = 1.0
    A_gr = 1.0
    rho_s = Ms / (A_s * L)
    rho_gr = Mg / (A_gr * L)
    P_sgr = 1.0
    h_sgr = U_sg / (P_sgr * L)
    k_gr = 35.0
    use_graphite_axial_conduction = True

    u_init = np.linspace(bc_s0, bc_sL, N)
    v_init = np.linspace(v_L, v_H, N)
    u2_init = np.linspace(u2_L, u2_H, N)
    v2_init = np.linspace(v2_L, v2_H, N)

    AT = np.diag(-2.0 * np.ones(N)) + np.diag(np.ones(N - 1), 1) + np.diag(np.ones(N - 1), -1)
    AT[0, 0] = AT[-1, -1] = 1.0
    AT[0, 1] = AT[-1, -2] = 0.0
    AT_sparse = csc_matrix(AT) / dz**2

    A_HX = np.diag(-2.0 * np.ones(Nx)) + np.diag(np.ones(Nx - 1), 1) + np.diag(np.ones(Nx - 1), -1)
    A_HX[0, 0] = A_HX[-1, -1] = -1.0
    A_HX[0, 1] = A_HX[-1, -2] = 0.0
    A_HX_sparse = csc_matrix(A_HX) / dx**2

    A_HX2 = np.diag(-2.0 * np.ones(Nx)) + np.diag(np.ones(Nx - 1), 1) + np.diag(np.ones(Nx - 1), -1)
    A_HX2[0, 0] = A_HX2[-1, -1] = -1.0
    A_HX2[0, 1] = A_HX2[-1, -2] = 0.0
    A_HX2_sparse = csc_matrix(A_HX2) / dx**2

    params = {
        "dt": dt,
        "L": L,
        "N": N,
        "Nx": Nx,
        "dz": dz,
        "dx": dx,
        "z": z,
        "A": A,
        "A_f": A_f,
        "v_core": v_core,
        "u_core": v_core,
        "inlet_mode": inlet_mode,
        "core_inlet_mode": core_inlet_mode,
        "neutron_velocity": neutron_velocity,
        "energy_groups": 2,
        "precursor_groups": beta.size,
        "neutronics_state_size": (2 + beta.size) * N,
        "beta": beta.tolist(),
        "beta_np": beta,
        "Beta": beta_total,
        "lambda_i": lambda_i.tolist(),
        "lambda_i_np": lambda_i,
        "nu": nu,
        "chi_p": chi_p,
        "chi_d": chi_d,
        "d_e": d_e,
        "D_ref": D_ref,
        "sigma_a_ref": sigma_a_ref,
        "sigma_s12_ref": sigma_s12_ref,
        "sigma_f_ref": sigma_f_ref,
        "nu_sigma_f_ref": nu_sigma_f_ref,
        "transverse_buckling_sq": transverse_buckling_sq,
        "a_sigma_a_s": a_sigma_a_s,
        "a_sigma_a_gr": a_sigma_a_gr,
        "a_sigma_s12_s": a_sigma_s12_s,
        "a_sigma_s12_gr": a_sigma_s12_gr,
        "a_nu_sigma_f_s": a_nu_sigma_f_s,
        "a_nu_sigma_f_gr": a_nu_sigma_f_gr,
        "a_D_s": a_D_s,
        "a_D_gr": a_D_gr,
        "rod_shape": rod_shape,
        "rod_sigma_a_amplitude": rod_sigma_a_amplitude,
        "external_reactivity_to_absorption": external_reactivity_to_absorption,
        "T_s_ref": T_s_ref,
        "T_gr_ref": T_gr_ref,
        "phi_1_0": phi_1_0,
        "phi_2_0": phi_2_0,
        "phi_0": phi_0,
        "c0_groups": c0_groups,
        "c0": c0,
        "sigma_a": sigma_a_ref.mean(axis=0),
        "nu_sigma_f": np.sum(nu_sigma_f_ref, axis=0),
        "sigma_f": np.sum(sigma_f_ref, axis=0),
        "nominal_total_power": nominal_total_power,
        "power_scale": power_scale,
        "reference_multiplication_ratio": reference_multiplication_ratio,
        "precursor_loop_efficiency": precursor_loop_efficiency,
        "precursor_loop_state": precursor_loop_state,
        "precursor_loop_tau": tau_l,
        "outer_dt": outer_dt,
        "c_p_s": c_p_s,
        "c_p_g": c_p_g,
        "rho_s": rho_s,
        "rho_gr": rho_gr,
        "A_s": A_s,
        "A_gr": A_gr,
        "P_sgr": P_sgr,
        "h_sgr": h_sgr,
        "k_gr": k_gr,
        "use_graphite_axial_conduction": use_graphite_axial_conduction,
        "Vc": Vc,
        "Ms": Ms,
        "Mg": Mg,
        "gamma": gamma,
        "eta_s": gamma,
        "eta_gr": 1.0 - gamma,
        "U_sg": U_sg,
        "U_gs": U_gs,
        "bc_s0": bc_s0,
        "bc_sL": bc_sL,
        "bc_g0": bc_g0,
        "bc_gL": bc_gL,
        "initialS": initialS,
        "initialG": initialG,
        "err": err,
        "L_HX": L_HX,
        "V_he_s": V_he_s,
        "V_he_ss": V_he_ss,
        "U_hx": U_hx,
        "M_he_s": M_he_s,
        "M_he_ss": M_he_ss,
        "c_p_ss": c_p_ss,
        "h_s": h_s,
        "k_s": k_s,
        "h_ss": h_ss,
        "k_ss": k_ss,
        "T_ambient": T_ambient,
        "u_L": u_L,
        "u_H": u_H,
        "v_L": v_L,
        "v_H": v_H,
        "u_init": u_init,
        "v_init": v_init,
        "L_HX2": L_HX2,
        "V_he2_s": V_he2_s,
        "V_he2_ss": V_he2_ss,
        "U2_hx": U2_hx,
        "M_he2_s": M_he2_s,
        "M_he2_ss": M_he2_ss,
        "c_p_sss": c_p_sss,
        "brayton_gamma": brayton_gamma,
        "brayton_eta_c": brayton_eta_c,
        "brayton_eta_t": brayton_eta_t,
        "brayton_pi_c": brayton_pi_c,
        "brayton_pi_t": brayton_pi_t,
        "brayton_recuperator_efficiency": brayton_recuperator_efficiency,
        "brayton_cooler_outlet_temp": brayton_cooler_outlet_temp,
        "brayton_min_heater_approach": brayton_min_heater_approach,
        "brayton_mdot": brayton_mdot,
        "u2_L": u2_L,
        "u2_H": u2_H,
        "v2_L": v2_L,
        "v2_H": v2_H,
        "u2_init": u2_init,
        "v2_init": v2_init,
        "tau_l": tau_l,
        "tau_c": tau_c,
        "tau_hx_c": tau_hx_c,
        "tau_c_hx": tau_c_hx,
        "tau_hx_r": tau_hx_r,
        "tau_r_hx": tau_r_hx,
        "tau_r_pp": tau_r_pp,
        "tau_pp_r": tau_pp_r,
        "Ts_in": bc_s0,
        "Ts_out": bc_sL,
        "Tss_in": v_L,
        "Tss_out": v_H,
        "Tsss_in": v2_L,
        "Tsss_out": v2_H,
        "scale": scale,
        "AT_sparse": AT_sparse,
        "A_HX_sparse": A_HX_sparse,
        "A_HX2_sparse": A_HX2_sparse,
        "min_diffusion": 1.0e-5,
        "min_cross_section": 1.0e-6,
        "last_global_rho": 0.0,
    }

    if use_steady_state_initialization:
        params.update(initialize_system_steady_state(params, spinup_steps=steady_state_steps))

    return params
