import numpy as np

from criticality import delayed_source_matrix

def _sanitize_temperature(field, reference):
    if field is None:
        return np.asarray(reference, dtype=float)
    arr = np.asarray(field, dtype=float)
    if arr.shape != np.asarray(reference).shape:
        raise ValueError("Temperature field shape does not match the reference profile.")
    return arr


def rod_absorption_perturbation(params, rod_position=0.0, external_reactivity=0.0):
    rod_shape = np.asarray(params["rod_shape"], dtype=float)
    rod_sigma_a_amplitude = np.asarray(params["rod_sigma_a_amplitude"], dtype=float)
    delta_sigma_a = rod_position * rod_shape * rod_sigma_a_amplitude[:, None]

    if external_reactivity != 0.0 and params.get("external_reactivity_mode", "fission_source") == "absorption":
        mapping = np.asarray(params["external_reactivity_to_absorption"], dtype=float)
        delta_sigma_a += (-external_reactivity) * rod_shape * mapping[:, None]

    return delta_sigma_a


def fission_source_scale(params, external_reactivity=0.0, override=None):
    if override is not None:
        return float(override)

    critical_scale = float(params.get("critical_fission_scale", 1.0))
    if params.get("external_reactivity_mode", "fission_source") != "fission_source":
        return critical_scale

    rho = float(external_reactivity)
    return critical_scale / max(1.0 - rho, 1.0e-12)


def build_cross_sections(
    temperature_fuel,
    temperature_graphite,
    params,
    rod_position=0.0,
    external_reactivity=0.0,
    fission_scale_override=None,
):
    T_s_ref = np.asarray(params["T_s_ref"], dtype=float)
    T_gr_ref = np.asarray(params["T_gr_ref"], dtype=float)

    T_s = _sanitize_temperature(temperature_fuel, T_s_ref)
    T_gr = _sanitize_temperature(temperature_graphite, T_gr_ref)

    delta_T_s = T_s - T_s_ref
    delta_T_gr = T_gr - T_gr_ref
    delta_sigma_a_rod = rod_absorption_perturbation(
        params,
        rod_position=rod_position,
        external_reactivity=external_reactivity,
    )

    D = (
        np.asarray(params["D_ref"], dtype=float)
        + np.asarray(params["a_D_s"], dtype=float) * delta_T_s[None, :]
        + np.asarray(params["a_D_gr"], dtype=float) * delta_T_gr[None, :]
    )
    sigma_a = (
        np.asarray(params["sigma_a_ref"], dtype=float)
        + np.asarray(params["a_sigma_a_s"], dtype=float) * delta_T_s[None, :]
        + np.asarray(params["a_sigma_a_gr"], dtype=float) * delta_T_gr[None, :]
        + delta_sigma_a_rod
    )
    sigma_s12 = (
        np.asarray(params["sigma_s12_ref"], dtype=float)
        + np.asarray(params["a_sigma_s12_s"], dtype=float) * delta_T_s
        + np.asarray(params["a_sigma_s12_gr"], dtype=float) * delta_T_gr
    )
    nu_sigma_f_unscaled = (
        np.asarray(params["nu_sigma_f_ref"], dtype=float)
        + np.asarray(params["a_nu_sigma_f_s"], dtype=float) * delta_T_s[None, :]
        + np.asarray(params["a_nu_sigma_f_gr"], dtype=float) * delta_T_gr[None, :]
    )
    sigma_f_physical = nu_sigma_f_unscaled / np.asarray(params["nu"], dtype=float)[:, None]

    min_diffusion = float(params.get("min_diffusion", 1.0e-5))
    min_cross_section = float(params.get("min_cross_section", 1.0e-6))

    D = np.clip(D, min_diffusion, None)
    sigma_a = np.clip(sigma_a, min_cross_section, None)
    sigma_s12 = np.clip(sigma_s12, 0.0, None)
    nu_sigma_f_unscaled = np.clip(nu_sigma_f_unscaled, min_cross_section, None)

    source_scale = fission_source_scale(
        params,
        external_reactivity=external_reactivity,
        override=fission_scale_override,
    )
    nu_sigma_f = nu_sigma_f_unscaled * source_scale

    sigma_r = sigma_a.copy()
    sigma_r[0] += sigma_s12
    sigma_r += D * np.asarray(params["transverse_buckling_sq"], dtype=float)

    sigma_f = np.clip(sigma_f_physical, min_cross_section, None)

    return {
        "temperature_fuel": T_s,
        "temperature_graphite": T_gr,
        "delta_T_s": delta_T_s,
        "delta_T_gr": delta_T_gr,
        "D": D,
        "sigma_a": sigma_a,
        "sigma_s12": sigma_s12,
        "nu_sigma_f": nu_sigma_f,
        "sigma_f": sigma_f,
        "sigma_r": sigma_r,
        "delta_sigma_a_rod": delta_sigma_a_rod,
        "fission_source_scale": source_scale,
    }


def estimate_global_reactivity(xs, params):
    phi_ref = np.vstack([
        np.asarray(params["phi_1_0"], dtype=float),
        np.asarray(params["phi_2_0"], dtype=float),
    ])
    z = np.asarray(params["z"], dtype=float)

    fission_source = np.sum(xs["nu_sigma_f"] * phi_ref, axis=0)
    delayed_source = delayed_source_matrix(params) @ fission_source
    total_source = (1.0 - float(params["Beta"])) * fission_source + delayed_source

    prompt_reference = np.trapezoid(fission_source, z)
    total_reference = np.trapezoid(total_source, z)
    effective_k = total_reference / max(prompt_reference, 1.0e-12)
    return (effective_k - 1.0) / max(effective_k, 1.0e-12)
