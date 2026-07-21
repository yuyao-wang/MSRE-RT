import numpy as np
from scipy import linalg


def _diffusion_term(phi, diffusion, dz, d_extrap):
    left_ghost = phi[1] - 2.0 * dz * phi[0] / max(d_extrap, 1.0e-12)
    right_ghost = phi[-2] - 2.0 * dz * phi[-1] / max(d_extrap, 1.0e-12)

    phi_ext = np.concatenate(([left_ghost], phi, [right_ghost]))
    diffusion_ext = np.concatenate(([diffusion[0]], diffusion, [diffusion[-1]]))

    d_face = 0.5 * (diffusion_ext[:-1] + diffusion_ext[1:])
    phi_jump = phi_ext[1:] - phi_ext[:-1]

    return (d_face[1:] * phi_jump[1:] - d_face[:-1] * phi_jump[:-1]) / dz**2


def build_diffusion_matrix(diffusion, dz, d_extrap):
    diffusion = np.asarray(diffusion, dtype=float)
    size = diffusion.size
    matrix = np.zeros((size, size), dtype=float)

    for column in range(size):
        basis = np.zeros(size, dtype=float)
        basis[column] = 1.0
        matrix[:, column] = _diffusion_term(basis, diffusion, float(dz), float(d_extrap))

    return matrix


def solve_precursor_group_steady_state(
    source,
    beta_i,
    lambda_i,
    params,
    max_iter=256,
    tol=1.0e-12,
):
    source = np.asarray(source, dtype=float)
    velocity = abs(float(params.get("u_precursor", params["u_core"])))
    if velocity < 1.0e-12:
        return float(beta_i) * source / max(float(lambda_i), 1.0e-12)

    dz = float(params["dz"])
    loop_tau = float(params.get("precursor_loop_tau", params["tau_l"]))
    loop_efficiency = float(params.get("precursor_loop_efficiency", 1.0))
    loop_decay = loop_efficiency * np.exp(-float(lambda_i) * loop_tau)

    advection_coeff = velocity / max(dz, 1.0e-12)
    denominator = advection_coeff + float(lambda_i)
    inlet = 0.0
    concentration = np.zeros_like(source)

    for _ in range(max_iter):
        concentration[0] = (advection_coeff * inlet + float(beta_i) * source[0]) / denominator
        for idx in range(1, concentration.size):
            concentration[idx] = (
                advection_coeff * concentration[idx - 1]
                + float(beta_i) * source[idx]
            ) / denominator

        updated_inlet = loop_decay * concentration[-1]
        scale = max(1.0, abs(updated_inlet), abs(inlet))
        if abs(updated_inlet - inlet) <= tol * scale:
            inlet = updated_inlet
            break
        inlet = updated_inlet

    concentration[0] = (advection_coeff * inlet + float(beta_i) * source[0]) / denominator
    for idx in range(1, concentration.size):
        concentration[idx] = (
            advection_coeff * concentration[idx - 1]
            + float(beta_i) * source[idx]
        ) / denominator

    return concentration


def solve_precursor_groups_steady_state(source, params):
    beta = np.asarray(params["beta_np"], dtype=float)
    lambda_i = np.asarray(params["lambda_i_np"], dtype=float)
    groups = [
        solve_precursor_group_steady_state(source, beta_value, lambda_value, params)
        for beta_value, lambda_value in zip(beta, lambda_i)
    ]
    return np.asarray(groups, dtype=float)


def _build_delayed_source_matrix(params):
    size = int(params["N"])
    lambda_i = np.asarray(params["lambda_i_np"], dtype=float)
    delayed_matrix = np.zeros((size, size), dtype=float)

    for column in range(size):
        unit_source = np.zeros(size, dtype=float)
        unit_source[column] = 1.0
        precursor_groups = solve_precursor_groups_steady_state(unit_source, params)
        delayed_matrix[:, column] = np.sum(lambda_i[:, None] * precursor_groups, axis=0)

    return delayed_matrix


def delayed_source_matrix(params):
    cached = params.get("_delayed_source_matrix")
    if cached is None:
        cached = _build_delayed_source_matrix(params)
        params["_delayed_source_matrix"] = cached
    return np.asarray(cached, dtype=float)


def build_generalized_criticality_matrices(xs, params):
    size = int(params["N"])
    beta_total = float(params["Beta"])
    chi_p = np.asarray(params["chi_p"], dtype=float)
    chi_d = np.asarray(params["chi_d"], dtype=float)

    diffusion_1 = build_diffusion_matrix(xs["D"][0], params["dz"], params["d_e"][0])
    diffusion_2 = build_diffusion_matrix(xs["D"][1], params["dz"], params["d_e"][1])

    mass_matrix = np.zeros((2 * size, 2 * size), dtype=float)
    mass_matrix[:size, :size] = np.diag(xs["sigma_r"][0]) - diffusion_1
    mass_matrix[size:, size:] = np.diag(xs["sigma_r"][1]) - diffusion_2
    mass_matrix[size:, :size] = -np.diag(xs["sigma_s12"])

    fission_fast = np.diag(xs["nu_sigma_f"][0])
    fission_thermal = np.diag(xs["nu_sigma_f"][1])
    delayed_matrix = delayed_source_matrix(params)
    prompt_factor = max(1.0 - beta_total, 0.0)

    source_matrix = np.zeros((2 * size, 2 * size), dtype=float)
    source_matrix[:size, :size] = (
        chi_p[0] * prompt_factor * fission_fast
        + chi_d[0] * delayed_matrix @ fission_fast
    )
    source_matrix[:size, size:] = (
        chi_p[0] * prompt_factor * fission_thermal
        + chi_d[0] * delayed_matrix @ fission_thermal
    )
    source_matrix[size:, :size] = (
        chi_p[1] * prompt_factor * fission_fast
        + chi_d[1] * delayed_matrix @ fission_fast
    )
    source_matrix[size:, size:] = (
        chi_p[1] * prompt_factor * fission_thermal
        + chi_d[1] * delayed_matrix @ fission_thermal
    )

    return source_matrix, mass_matrix


def solve_critical_mode(xs, params):
    source_matrix, mass_matrix = build_generalized_criticality_matrices(xs, params)
    eigenvalues, eigenvectors = linalg.eig(source_matrix, mass_matrix, check_finite=False)

    real_mask = np.isfinite(eigenvalues) & (np.abs(eigenvalues.imag) <= 1.0e-9)
    positive_mask = real_mask & (eigenvalues.real > 0.0)
    if not np.any(positive_mask):
        raise RuntimeError("Failed to locate a positive generalized criticality eigenvalue.")

    physical_indices = np.where(positive_mask)[0]
    dominant_index = physical_indices[int(np.argmax(eigenvalues.real[positive_mask]))]

    mode = np.asarray(eigenvectors[:, dominant_index].real, dtype=float)
    if np.sum(mode) < 0.0:
        mode *= -1.0
    mode = np.abs(mode)

    size = int(params["N"])
    phi_1 = mode[:size]
    phi_2 = mode[size:]
    normalization = np.trapezoid(phi_1 + phi_2, np.asarray(params["z"], dtype=float))
    mode /= max(normalization, 1.0e-12)

    return {
        "k_eff": float(eigenvalues[dominant_index].real),
        "phi_1": mode[:size],
        "phi_2": mode[size:],
    }
