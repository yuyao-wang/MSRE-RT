import numpy as np
from scipy.linalg import expm


def advance_point_kinetics_state(
    amplitude,
    precursors,
    beta_effective,
    lambda_i,
    rho,
    dt,
    prompt_generation_time,
):
    lambda_i = np.asarray(lambda_i, dtype=float)
    beta_effective = np.asarray(beta_effective, dtype=float)
    precursors = np.asarray(precursors, dtype=float)

    system_size = 1 + beta_effective.size
    operator = np.zeros((system_size, system_size), dtype=float)
    operator[0, 0] = (float(rho) - float(np.sum(beta_effective))) / max(float(prompt_generation_time), 1.0e-12)
    operator[0, 1:] = lambda_i
    operator[1:, 0] = beta_effective / max(float(prompt_generation_time), 1.0e-12)
    operator[1:, 1:] = -np.diag(lambda_i)

    state = np.concatenate(([float(amplitude)], precursors))
    state = expm(operator * float(dt)) @ state
    state = np.clip(state, 0.0, None)
    return {
        "amplitude": float(state[0]),
        "precursors": np.asarray(state[1:], dtype=float),
    }


def initialize_point_kinetics_state(params, effective_beta_total):
    lambda_i = np.asarray(params["lambda_i_np"], dtype=float)
    beta = np.asarray(params["beta_np"], dtype=float)
    beta_total = float(params["Beta"])
    beta_scale = float(effective_beta_total) / max(beta_total, 1.0e-12)
    beta_effective = beta * beta_scale
    prompt_generation_time = float(params.get("prompt_generation_time_s", 2.0e-4))

    precursor_amplitudes = beta_effective / max(prompt_generation_time, 1.0e-12) / np.maximum(lambda_i, 1.0e-12)
    params["kinetics_amplitude"] = 1.0
    params["kinetics_precursors"] = precursor_amplitudes.copy()
    params["kinetics_beta_effective"] = beta_effective.copy()


def advance_point_kinetics(params, rho, dt):
    if not params.get("point_kinetics_enabled", True):
        return {
            "amplitude": float(params.get("kinetics_amplitude", 1.0)),
            "precursors": np.asarray(params.get("kinetics_precursors", []), dtype=float),
        }

    lambda_i = np.asarray(params["lambda_i_np"], dtype=float)
    beta_effective = np.asarray(params["kinetics_beta_effective"], dtype=float)
    beta_total = float(np.sum(beta_effective))
    prompt_generation_time = float(params.get("prompt_generation_time_s", 2.0e-4))

    amplitude = float(params.get("kinetics_amplitude", 1.0))
    precursors = np.asarray(params.get("kinetics_precursors", np.zeros_like(lambda_i)), dtype=float)

    state = advance_point_kinetics_state(
        amplitude=amplitude,
        precursors=precursors,
        beta_effective=beta_effective,
        lambda_i=lambda_i,
        rho=rho,
        dt=dt,
        prompt_generation_time=prompt_generation_time,
    )

    params["kinetics_amplitude"] = float(state["amplitude"])
    params["kinetics_precursors"] = np.asarray(state["precursors"], dtype=float)
    return {
        "amplitude": float(state["amplitude"]),
        "precursors": np.asarray(state["precursors"], dtype=float),
    }
