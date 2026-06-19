#!/usr/bin/env python3
import argparse
import ctypes
import json
import math
import os
from pathlib import Path
from typing import Iterable, Sequence


K_MAX_N = 200
K_PRECURSOR_GROUPS = 6
K_ENERGY_GROUPS = 2
K_MAX_LOOP_HISTORY = 64


REGION_INFO = {
    "core_control": {"base": 0x44A00000},
    "bop_control": {"base": 0x44A10000},
    "core_state": {"base": 0x40000000, "byte_capacity": 64 * 1024},
    "core_params": {"base": 0x40020000, "byte_capacity": 128 * 1024},
    "core_boundary": {"base": 0x40040000, "byte_capacity": 4 * 1024},
    "bop_state": {"base": 0x40050000, "byte_capacity": 32 * 1024},
    "bop_params": {"base": 0x40060000, "byte_capacity": 128 * 1024},
    "bop_boundary": {"base": 0x40080000, "byte_capacity": 4 * 1024},
}

INLET_MODE_ENUM = {
    "recirculate": 0,
    "fresh": 1,
    "copy": 2,
}

CORE_INLET_MODE_ENUM = {
    "prescribed": 0,
    "hx_coupled": 1,
}

EXTERNAL_REACTIVITY_MODE_ENUM = {
    "fission_source": 0,
    "absorption": 1,
}


CORE_REG_OFFSETS = {
    "state": 0x10,
    "params": 0x1C,
    "Ts_core_inlet": 0x28,
    "rod_position": 0x34,
    "external_reactivity": 0x40,
    "boundary_out": 0x4C,
}


BOP_REG_OFFSETS = {
    "state": 0x10,
    "params": 0x1C,
    "Ts_HX1_L": 0x28,
    "Tss_HX1_0": 0x34,
    "Tss_HX2_L": 0x40,
    "Tsss_HX2_0": 0x4C,
    "boundary_out": 0x58,
}


def double_array(length: int):
    return ctypes.c_double * length


def double_matrix(rows: int, cols: int):
    return (ctypes.c_double * cols) * rows


class PrecursorHistory(ctypes.Structure):
    _fields_ = [
        ("outlet_history", double_matrix(K_PRECURSOR_GROUPS, K_MAX_LOOP_HISTORY)),
        ("last_outlet", double_array(K_PRECURSOR_GROUPS)),
        ("write_index", ctypes.c_int),
        ("valid_count", ctypes.c_int),
    ]


class CoreStepState(ctypes.Structure):
    _fields_ = [
        ("phi1", double_array(K_MAX_N)),
        ("phi2", double_array(K_MAX_N)),
        ("C", double_matrix(K_PRECURSOR_GROUPS, K_MAX_N)),
        ("kinetics_amplitude", ctypes.c_double),
        ("kinetics_precursors", double_array(K_PRECURSOR_GROUPS)),
        ("kinetics_beta_effective", double_array(K_PRECURSOR_GROUPS)),
        ("fuel", double_array(K_MAX_N)),
        ("graphite", double_array(K_MAX_N)),
        ("precursor_history", PrecursorHistory),
    ]


class BopStepState(ctypes.Structure):
    _fields_ = [
        ("hx1_hot", double_array(K_MAX_N)),
        ("hx1_cold", double_array(K_MAX_N)),
        ("hx2_hot", double_array(K_MAX_N)),
        ("hx2_cold", double_array(K_MAX_N)),
    ]


class CoreStepBoundary(ctypes.Structure):
    _fields_ = [
        ("rho", ctypes.c_double),
        ("power", ctypes.c_double),
        ("phi_mid", ctypes.c_double),
        ("fuel_mid", ctypes.c_double),
        ("graphite_mid", ctypes.c_double),
        ("Ts_core_inlet", ctypes.c_double),
        ("Ts_core_outlet", ctypes.c_double),
    ]


class BopStepBoundary(ctypes.Structure):
    _fields_ = [
        ("Ts_HX1_0", ctypes.c_double),
        ("Tss_HX1_L", ctypes.c_double),
        ("Tss_HX2_0", ctypes.c_double),
        ("Tsss_HX2_L", ctypes.c_double),
        ("Tsss_pp_0", ctypes.c_double),
    ]


class KernelParams(ctypes.Structure):
    _fields_ = [
        ("N", ctypes.c_int),
        ("Nx", ctypes.c_int),
        ("hardware_substeps", ctypes.c_int),
        ("inlet_mode", ctypes.c_int),
        ("core_inlet_mode", ctypes.c_int),
        ("use_graphite_axial_conduction", ctypes.c_int),
        ("point_kinetics_enabled", ctypes.c_int),
        ("external_reactivity_mode", ctypes.c_int),
        ("precursor_delay_older", ctypes.c_int),
        ("precursor_delay_newer", ctypes.c_int),
        ("precursor_interp_newer", ctypes.c_double),
        ("dz", ctypes.c_double),
        ("outer_dt", ctypes.c_double),
        ("u_core", ctypes.c_double),
        ("u_precursor", ctypes.c_double),
        ("power_scale", ctypes.c_double),
        ("Beta", ctypes.c_double),
        ("critical_fission_scale", ctypes.c_double),
        ("prompt_generation_time_s", ctypes.c_double),
        ("external_reactivity", ctypes.c_double),
        ("brayton_available_heat_W", ctypes.c_double),
        ("beta", double_array(K_PRECURSOR_GROUPS)),
        ("lambda_i", double_array(K_PRECURSOR_GROUPS)),
        ("kinetics_beta_effective", double_array(K_PRECURSOR_GROUPS)),
        ("neutron_velocity", double_array(K_ENERGY_GROUPS)),
        ("nu", double_array(K_ENERGY_GROUPS)),
        ("chi_p", double_array(K_ENERGY_GROUPS)),
        ("chi_d", double_array(K_ENERGY_GROUPS)),
        ("d_e", double_array(K_ENERGY_GROUPS)),
        ("D_ref", double_matrix(K_ENERGY_GROUPS, K_MAX_N)),
        ("sigma_a_ref", double_matrix(K_ENERGY_GROUPS, K_MAX_N)),
        ("sigma_s12_ref", double_array(K_MAX_N)),
        ("nu_sigma_f_ref", double_matrix(K_ENERGY_GROUPS, K_MAX_N)),
        ("transverse_buckling_sq", double_matrix(K_ENERGY_GROUPS, K_MAX_N)),
        ("a_sigma_a_s", double_matrix(K_ENERGY_GROUPS, K_MAX_N)),
        ("a_sigma_a_gr", double_matrix(K_ENERGY_GROUPS, K_MAX_N)),
        ("a_sigma_s12_s", double_array(K_MAX_N)),
        ("a_sigma_s12_gr", double_array(K_MAX_N)),
        ("a_nu_sigma_f_s", double_matrix(K_ENERGY_GROUPS, K_MAX_N)),
        ("a_nu_sigma_f_gr", double_matrix(K_ENERGY_GROUPS, K_MAX_N)),
        ("a_D_s", double_matrix(K_ENERGY_GROUPS, K_MAX_N)),
        ("a_D_gr", double_matrix(K_ENERGY_GROUPS, K_MAX_N)),
        ("rod_shape", double_matrix(K_ENERGY_GROUPS, K_MAX_N)),
        ("rod_sigma_a_amplitude", double_array(K_ENERGY_GROUPS)),
        ("external_reactivity_to_absorption", double_array(K_ENERGY_GROUPS)),
        ("T_s_ref", double_array(K_MAX_N)),
        ("T_gr_ref", double_array(K_MAX_N)),
        ("phi1_ref", double_array(K_MAX_N)),
        ("phi2_ref", double_array(K_MAX_N)),
        ("A_f", double_array(K_MAX_N)),
        ("z", double_array(K_MAX_N)),
        ("min_diffusion", ctypes.c_double),
        ("min_cross_section", ctypes.c_double),
        ("reference_multiplication_ratio", ctypes.c_double),
        ("precursor_loop_efficiency", ctypes.c_double),
        ("precursor_loop_tau", ctypes.c_double),
        ("rho_s", ctypes.c_double),
        ("c_p_s", ctypes.c_double),
        ("A_s", ctypes.c_double),
        ("rho_gr", ctypes.c_double),
        ("c_p_g", ctypes.c_double),
        ("A_gr", ctypes.c_double),
        ("h_sgr", ctypes.c_double),
        ("P_sgr", ctypes.c_double),
        ("k_gr", ctypes.c_double),
        ("eta_s", ctypes.c_double),
        ("eta_gr", ctypes.c_double),
        ("err", ctypes.c_double),
        ("bc_s0", ctypes.c_double),
        ("hx1_dx", ctypes.c_double),
        ("hx1_hot_velocity", ctypes.c_double),
        ("hx1_cold_velocity", ctypes.c_double),
        ("hx1_hot_exchange_coeff", ctypes.c_double),
        ("hx1_cold_exchange_coeff", ctypes.c_double),
        ("hx2_dx", ctypes.c_double),
        ("hx2_hot_velocity", ctypes.c_double),
        ("hx2_cold_velocity", ctypes.c_double),
        ("hx2_hot_exchange_coeff", ctypes.c_double),
        ("hx2_cold_exchange_coeff", ctypes.c_double),
        ("Ts_in", ctypes.c_double),
        ("Ts_out", ctypes.c_double),
        ("Tss_in", ctypes.c_double),
        ("Tss_out", ctypes.c_double),
        ("Tsss_in", ctypes.c_double),
        ("Tsss_out", ctypes.c_double),
        ("brayton_gamma", ctypes.c_double),
        ("brayton_eta_c", ctypes.c_double),
        ("brayton_eta_t", ctypes.c_double),
        ("brayton_pi_c", ctypes.c_double),
        ("brayton_pi_t", ctypes.c_double),
        ("brayton_compressor_temp_scale", ctypes.c_double),
        ("brayton_turbine_temp_scale", ctypes.c_double),
        ("brayton_recuperator_efficiency", ctypes.c_double),
        ("brayton_cooler_outlet_temp", ctypes.c_double),
        ("brayton_min_heater_approach", ctypes.c_double),
        ("brayton_mdot", ctypes.c_double),
        ("c_p_sss", ctypes.c_double),
    ]


BOUNDARY_TYPES = {
    "core": CoreStepBoundary,
    "bop": BopStepBoundary,
}


def set_vector(dst, values: Sequence[float]) -> None:
    for idx, value in enumerate(values):
        dst[idx] = value


def set_matrix(dst, row_values: Iterable[Sequence[float]]) -> None:
    for row_idx, values in enumerate(row_values):
        set_vector(dst[row_idx], values)


def struct_bytes(obj: ctypes.Structure) -> bytes:
    return ctypes.string_at(ctypes.addressof(obj), ctypes.sizeof(obj))


def bytes_to_hex32_words(blob: bytes) -> list[str]:
    pad = (-len(blob)) % 4
    if pad:
        blob += b"\x00" * pad
    words = []
    for idx in range(0, len(blob), 4):
        value = int.from_bytes(blob[idx : idx + 4], byteorder="little", signed=False)
        words.append(f"{value:08X}")
    return words


def hex32_words_to_bytes(words: Sequence[str]) -> bytes:
    blob = bytearray()
    for word in words:
        blob.extend(int(word, 16).to_bytes(4, byteorder="little", signed=False))
    return bytes(blob)


def write_hex32_file(path: Path, blob: bytes) -> int:
    words = bytes_to_hex32_words(blob)
    path.write_text("\n".join(words) + ("\n" if words else ""), encoding="ascii")
    return len(words)


def read_hex32_file(path: Path) -> bytes:
    words = [line.strip() for line in path.read_text(encoding="ascii").splitlines() if line.strip()]
    return hex32_words_to_bytes(words)


def tcl_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def tcl_hex32_words_for_u64(value: int) -> list[str]:
    masked = value & ((1 << 64) - 1)
    return [f"{masked & 0xFFFFFFFF:08X}", f"{(masked >> 32) & 0xFFFFFFFF:08X}"]


def tcl_hex32_words_for_f64(value: float) -> list[str]:
    packed = ctypes.c_uint64.from_buffer_copy(ctypes.c_double(value)).value
    return tcl_hex32_words_for_u64(packed)


def make_control_entry(offset: int, words: Sequence[str]) -> str:
    words_str = " ".join(words)
    return f"{{0x{offset:02X} {{{words_str}}}}}"


def create_default_core_state() -> CoreStepState:
    state = CoreStepState()
    phi1 = [1.0 + 1e-3 * idx for idx in range(K_MAX_N)]
    phi2 = [0.2 + 5e-4 * idx for idx in range(K_MAX_N)]
    fuel = [900.0 + 0.15 * idx for idx in range(K_MAX_N)]
    graphite = [890.0 + 0.10 * idx for idx in range(K_MAX_N)]
    set_vector(state.phi1, phi1)
    set_vector(state.phi2, phi2)
    state.kinetics_amplitude = 1.0
    set_vector(state.kinetics_precursors, [1e-3 * (group + 1) for group in range(K_PRECURSOR_GROUPS)])
    set_vector(state.kinetics_beta_effective, [2.2e-4, 1.0e-3, 1.1e-3, 1.2e-3, 1.3e-3, 1.68e-3])
    set_vector(state.fuel, fuel)
    set_vector(state.graphite, graphite)
    for group in range(K_PRECURSOR_GROUPS):
        set_vector(state.C[group], [1e-4 * (group + 1) for _ in range(K_MAX_N)])
        for hist_idx in range(K_MAX_LOOP_HISTORY):
            state.precursor_history.outlet_history[group][hist_idx] = 1e-4 * (group + 1)
        state.precursor_history.last_outlet[group] = 1e-4 * (group + 1)
    state.precursor_history.write_index = 0
    state.precursor_history.valid_count = K_MAX_LOOP_HISTORY
    return state


def create_default_bop_state() -> BopStepState:
    state = BopStepState()
    set_vector(state.hx1_hot, [920.0 - 0.20 * idx for idx in range(K_MAX_N)])
    set_vector(state.hx1_cold, [650.0 + 0.12 * idx for idx in range(K_MAX_N)])
    set_vector(state.hx2_hot, [640.0 - 0.18 * idx for idx in range(K_MAX_N)])
    set_vector(state.hx2_cold, [500.0 + 0.10 * idx for idx in range(K_MAX_N)])
    return state


def create_default_kernel_params() -> KernelParams:
    params = KernelParams()
    params.N = K_MAX_N
    params.Nx = K_MAX_N
    params.hardware_substeps = 1
    params.inlet_mode = 0
    params.core_inlet_mode = 0
    params.use_graphite_axial_conduction = 1
    params.point_kinetics_enabled = 1
    params.external_reactivity_mode = EXTERNAL_REACTIVITY_MODE_ENUM["fission_source"]
    params.precursor_delay_older = 0
    params.precursor_delay_newer = 1
    params.precursor_interp_newer = 0.0
    params.dz = 0.02
    params.outer_dt = 0.01
    params.u_core = 1.0
    params.u_precursor = 1.0
    params.power_scale = 1.0
    params.Beta = 6.5e-3
    params.critical_fission_scale = 1.0
    params.prompt_generation_time_s = 2.0e-4
    params.external_reactivity = 0.0
    params.brayton_available_heat_W = 1.0e6
    set_vector(params.beta, [2.2e-4, 1.0e-3, 1.1e-3, 1.2e-3, 1.3e-3, 1.68e-3])
    set_vector(params.lambda_i, [0.0124, 0.0305, 0.111, 0.301, 1.14, 3.01])
    set_vector(params.kinetics_beta_effective, [2.2e-4, 1.0e-3, 1.1e-3, 1.2e-3, 1.3e-3, 1.68e-3])
    set_vector(params.neutron_velocity, [2.2e5, 3.0e5])
    set_vector(params.nu, [2.45, 2.45])
    set_vector(params.chi_p, [1.0, 0.0])
    set_vector(params.chi_d, [1.0, 0.0])
    set_vector(params.d_e, [1.0, 1.0])

    z = [params.dz * idx for idx in range(K_MAX_N)]
    shape = [1.0 + 1e-3 * idx for idx in range(K_MAX_N)]
    set_vector(params.sigma_s12_ref, [0.015 for _ in range(K_MAX_N)])
    set_vector(params.a_sigma_s12_s, [0.0 for _ in range(K_MAX_N)])
    set_vector(params.a_sigma_s12_gr, [0.0 for _ in range(K_MAX_N)])
    set_vector(params.T_s_ref, [900.0 for _ in range(K_MAX_N)])
    set_vector(params.T_gr_ref, [890.0 for _ in range(K_MAX_N)])
    set_vector(params.phi1_ref, shape)
    set_vector(params.phi2_ref, [0.2 + 5e-4 * idx for idx in range(K_MAX_N)])
    set_vector(params.A_f, [1.0 for _ in range(K_MAX_N)])
    set_vector(params.z, z)
    set_vector(params.rod_sigma_a_amplitude, [0.0, 0.0])
    set_vector(params.external_reactivity_to_absorption, [0.0, 0.0])

    energy_ref = [
        [0.9 for _ in range(K_MAX_N)],
        [0.6 for _ in range(K_MAX_N)],
    ]
    energy_sigma = [
        [0.03 for _ in range(K_MAX_N)],
        [0.08 for _ in range(K_MAX_N)],
    ]
    energy_fission = [
        [0.045 for _ in range(K_MAX_N)],
        [0.002 for _ in range(K_MAX_N)],
    ]
    zero_energy = [
        [0.0 for _ in range(K_MAX_N)],
        [0.0 for _ in range(K_MAX_N)],
    ]
    set_matrix(params.D_ref, energy_ref)
    set_matrix(params.sigma_a_ref, energy_sigma)
    set_matrix(params.nu_sigma_f_ref, energy_fission)
    set_matrix(params.transverse_buckling_sq, zero_energy)
    set_matrix(params.a_sigma_a_s, zero_energy)
    set_matrix(params.a_sigma_a_gr, zero_energy)
    set_matrix(params.a_nu_sigma_f_s, zero_energy)
    set_matrix(params.a_nu_sigma_f_gr, zero_energy)
    set_matrix(params.a_D_s, zero_energy)
    set_matrix(params.a_D_gr, zero_energy)
    set_matrix(params.rod_shape, zero_energy)

    params.min_diffusion = 1e-6
    params.min_cross_section = 1e-6
    params.reference_multiplication_ratio = 1.0
    params.precursor_loop_efficiency = 1.0
    params.precursor_loop_tau = 1.0

    params.rho_s = 1800.0
    params.c_p_s = 1600.0
    params.A_s = 1.0
    params.rho_gr = 1700.0
    params.c_p_g = 1500.0
    params.A_gr = 1.0
    params.h_sgr = 2500.0
    params.P_sgr = 1.0
    params.k_gr = 25.0
    params.eta_s = 1.0
    params.eta_gr = 1.0
    params.err = 0.0
    params.bc_s0 = 900.0

    params.hx1_dx = 0.02
    params.hx1_hot_velocity = 1.0
    params.hx1_cold_velocity = 1.0
    params.hx1_hot_exchange_coeff = 1000.0
    params.hx1_cold_exchange_coeff = 1000.0

    params.hx2_dx = 0.02
    params.hx2_hot_velocity = 1.0
    params.hx2_cold_velocity = 1.0
    params.hx2_hot_exchange_coeff = 1000.0
    params.hx2_cold_exchange_coeff = 1000.0

    params.Ts_in = 900.0
    params.Ts_out = 930.0
    params.Tss_in = 650.0
    params.Tss_out = 700.0
    params.Tsss_in = 500.0
    params.Tsss_out = 540.0

    params.brayton_gamma = 1.4
    params.brayton_eta_c = 0.85
    params.brayton_eta_t = 0.88
    params.brayton_pi_c = 2.5
    params.brayton_pi_t = 2.2
    params.brayton_recuperator_efficiency = 0.9
    params.brayton_cooler_outlet_temp = 320.0
    params.brayton_min_heater_approach = 30.0
    params.brayton_mdot = 15.0
    params.c_p_sss = 1000.0
    return params


def make_precursor_delay_triplet(loop_tau: float, outer_dt: float) -> tuple[int, int, float]:
    delay_steps = float(loop_tau) / max(float(outer_dt), 1.0e-12)
    delay_newer = max(int(math.floor(delay_steps)), 0)
    delay_older = max(int(math.ceil(delay_steps)), delay_newer)
    interp_newer = delay_steps - delay_newer
    return delay_older, delay_newer, interp_newer


def populate_precursor_history(history: PrecursorHistory, loop_state) -> None:
    outlets = list(loop_state.get("outlets", []))
    recent = outlets[-K_MAX_LOOP_HISTORY:]
    for hist_idx, outlet in enumerate(recent):
        for group in range(K_PRECURSOR_GROUPS):
            history.outlet_history[group][hist_idx] = float(outlet[group])

    if recent:
        last_outlet = recent[-1]
    else:
        last_outlet = [0.0] * K_PRECURSOR_GROUPS
    for group in range(K_PRECURSOR_GROUPS):
        history.last_outlet[group] = float(last_outlet[group])

    history.valid_count = len(recent)
    history.write_index = len(recent) % K_MAX_LOOP_HISTORY if recent else 0


def _extract_or_default(params_dict, key: str, default):
    value = params_dict.get(key)
    return default if value is None else value


def create_model_core_state(params_dict) -> CoreStepState:
    import numpy as np

    n = int(params_dict["N"])
    if n != K_MAX_N:
        raise ValueError(f"Fixed n200 kernel requires N={K_MAX_N}, got {n}")

    state = CoreStepState()
    y_n = np.asarray(
        _extract_or_default(
            params_dict,
            "y_n_init",
            np.concatenate(
                [
                    np.asarray(params_dict["phi_1_0"], dtype=float),
                    np.asarray(params_dict["phi_2_0"], dtype=float),
                    np.asarray(params_dict["c0"], dtype=float),
                ]
            ),
        ),
        dtype=float,
    ).reshape(-1)
    phi1 = y_n[:n]
    phi2 = y_n[n : 2 * n]
    c_groups = y_n[2 * n :].reshape(K_PRECURSOR_GROUPS, n)

    y_th = np.asarray(
        _extract_or_default(
            params_dict,
            "y_th_init",
            np.concatenate(
                [
                    np.asarray(params_dict["initialS"], dtype=float),
                    np.asarray(params_dict["initialG"], dtype=float),
                ]
            ),
        ),
        dtype=float,
    ).reshape(-1)
    fuel = y_th[:n]
    graphite = y_th[n : 2 * n]

    set_vector(state.phi1, phi1.tolist())
    set_vector(state.phi2, phi2.tolist())
    state.kinetics_amplitude = float(params_dict.get("kinetics_amplitude", 1.0))
    kinetics_precursors = np.asarray(
        params_dict.get("kinetics_precursors", np.zeros(K_PRECURSOR_GROUPS, dtype=float)),
        dtype=float,
    ).reshape(-1)
    set_vector(state.kinetics_precursors, kinetics_precursors[:K_PRECURSOR_GROUPS].tolist())
    kinetics_beta_effective = np.asarray(
        params_dict.get("kinetics_beta_effective", params_dict["beta"]),
        dtype=float,
    ).reshape(-1)
    set_vector(state.kinetics_beta_effective, kinetics_beta_effective[:K_PRECURSOR_GROUPS].tolist())
    set_vector(state.fuel, fuel.tolist())
    set_vector(state.graphite, graphite.tolist())
    for group in range(K_PRECURSOR_GROUPS):
        set_vector(state.C[group], c_groups[group].tolist())

    populate_precursor_history(state.precursor_history, params_dict["precursor_loop_state"])
    return state


def create_model_bop_state(params_dict) -> BopStepState:
    import numpy as np

    nx = int(params_dict["Nx"])
    if nx != K_MAX_N:
        raise ValueError(f"Fixed n200 kernel requires Nx={K_MAX_N}, got {nx}")

    state = BopStepState()
    y_hx1 = np.asarray(
        _extract_or_default(
            params_dict,
            "y_hx1_init",
            np.concatenate(
                [
                    np.asarray(params_dict["u_init"], dtype=float),
                    np.asarray(params_dict["v_init"], dtype=float),
                ]
            ),
        ),
        dtype=float,
    ).reshape(-1)
    y_hx2 = np.asarray(
        _extract_or_default(
            params_dict,
            "y_hx2_init",
            np.concatenate(
                [
                    np.asarray(params_dict["u2_init"], dtype=float),
                    np.asarray(params_dict["v2_init"], dtype=float),
                ]
            ),
        ),
        dtype=float,
    ).reshape(-1)

    set_vector(state.hx1_hot, y_hx1[:nx].tolist())
    set_vector(state.hx1_cold, y_hx1[nx : 2 * nx].tolist())
    set_vector(state.hx2_hot, y_hx2[:nx].tolist())
    set_vector(state.hx2_cold, y_hx2[nx : 2 * nx].tolist())
    return state


def create_model_kernel_params(params_dict, hardware_substeps: int) -> KernelParams:
    import numpy as np

    params = KernelParams()
    params.N = int(params_dict["N"])
    params.Nx = int(params_dict["Nx"])
    if params.N != K_MAX_N or params.Nx != K_MAX_N:
        raise ValueError(f"Fixed n200 kernel requires N=Nx={K_MAX_N}, got N={params.N}, Nx={params.Nx}")

    params.hardware_substeps = int(hardware_substeps)
    params.inlet_mode = INLET_MODE_ENUM[str(params_dict.get("inlet_mode", "recirculate"))]
    params.core_inlet_mode = CORE_INLET_MODE_ENUM[str(params_dict.get("core_inlet_mode", "prescribed"))]
    params.use_graphite_axial_conduction = 1 if params_dict.get("use_graphite_axial_conduction", True) else 0
    params.point_kinetics_enabled = 1 if params_dict.get("point_kinetics_enabled", True) else 0
    params.external_reactivity_mode = EXTERNAL_REACTIVITY_MODE_ENUM[
        str(params_dict.get("external_reactivity_mode", "fission_source"))
    ]

    delay_older, delay_newer, interp_newer = make_precursor_delay_triplet(
        loop_tau=float(params_dict["precursor_loop_tau"]),
        outer_dt=float(params_dict.get("outer_dt", 1.0)),
    )
    params.precursor_delay_older = delay_older
    params.precursor_delay_newer = delay_newer
    params.precursor_interp_newer = interp_newer

    params.dz = float(params_dict["dz"])
    params.outer_dt = float(params_dict.get("outer_dt", 1.0))
    params.u_core = float(params_dict["u_core"])
    params.u_precursor = float(params_dict.get("u_precursor", params_dict["u_core"]))
    params.power_scale = float(params_dict["power_scale"])
    params.Beta = float(params_dict["Beta"])
    params.critical_fission_scale = float(params_dict.get("critical_fission_scale", 1.0))
    params.prompt_generation_time_s = float(params_dict.get("prompt_generation_time_s", 2.0e-4))
    params.external_reactivity = float(params_dict.get("external_reactivity", 0.0))
    params.brayton_available_heat_W = float(
        params_dict.get("brayton_available_heat_W", params_dict.get("nominal_total_power", 0.0))
    )

    set_vector(params.beta, np.asarray(params_dict["beta"], dtype=float).tolist())
    set_vector(params.lambda_i, np.asarray(params_dict["lambda_i"], dtype=float).tolist())
    kinetics_beta_effective = np.asarray(
        params_dict.get("kinetics_beta_effective", params_dict["beta"]),
        dtype=float,
    ).reshape(-1)
    set_vector(params.kinetics_beta_effective, kinetics_beta_effective[:K_PRECURSOR_GROUPS].tolist())
    set_vector(params.neutron_velocity, np.asarray(params_dict["neutron_velocity"], dtype=float).tolist())
    set_vector(params.nu, np.asarray(params_dict["nu"], dtype=float).tolist())
    set_vector(params.chi_p, np.asarray(params_dict["chi_p"], dtype=float).tolist())
    set_vector(params.chi_d, np.asarray(params_dict["chi_d"], dtype=float).tolist())
    set_vector(params.d_e, np.asarray(params_dict["d_e"], dtype=float).tolist())

    set_matrix(params.D_ref, np.asarray(params_dict["D_ref"], dtype=float).tolist())
    set_matrix(params.sigma_a_ref, np.asarray(params_dict["sigma_a_ref"], dtype=float).tolist())
    set_vector(params.sigma_s12_ref, np.asarray(params_dict["sigma_s12_ref"], dtype=float).tolist())
    set_matrix(params.nu_sigma_f_ref, np.asarray(params_dict["nu_sigma_f_ref"], dtype=float).tolist())
    set_matrix(params.transverse_buckling_sq, np.asarray(params_dict["transverse_buckling_sq"], dtype=float).tolist())
    set_matrix(params.a_sigma_a_s, np.asarray(params_dict["a_sigma_a_s"], dtype=float).tolist())
    set_matrix(params.a_sigma_a_gr, np.asarray(params_dict["a_sigma_a_gr"], dtype=float).tolist())
    set_vector(params.a_sigma_s12_s, np.asarray(params_dict["a_sigma_s12_s"], dtype=float).tolist())
    set_vector(params.a_sigma_s12_gr, np.asarray(params_dict["a_sigma_s12_gr"], dtype=float).tolist())
    set_matrix(params.a_nu_sigma_f_s, np.asarray(params_dict["a_nu_sigma_f_s"], dtype=float).tolist())
    set_matrix(params.a_nu_sigma_f_gr, np.asarray(params_dict["a_nu_sigma_f_gr"], dtype=float).tolist())
    set_matrix(params.a_D_s, np.asarray(params_dict["a_D_s"], dtype=float).tolist())
    set_matrix(params.a_D_gr, np.asarray(params_dict["a_D_gr"], dtype=float).tolist())
    set_matrix(params.rod_shape, np.asarray(params_dict["rod_shape"], dtype=float).tolist())
    set_vector(params.rod_sigma_a_amplitude, np.asarray(params_dict["rod_sigma_a_amplitude"], dtype=float).tolist())
    set_vector(
        params.external_reactivity_to_absorption,
        np.asarray(params_dict["external_reactivity_to_absorption"], dtype=float).tolist(),
    )

    set_vector(params.T_s_ref, np.asarray(params_dict["T_s_ref"], dtype=float).tolist())
    set_vector(params.T_gr_ref, np.asarray(params_dict["T_gr_ref"], dtype=float).tolist())
    set_vector(params.phi1_ref, np.asarray(params_dict["phi_1_0"], dtype=float).tolist())
    set_vector(params.phi2_ref, np.asarray(params_dict["phi_2_0"], dtype=float).tolist())
    set_vector(params.A_f, np.asarray(params_dict["A_f"], dtype=float).tolist())
    set_vector(params.z, np.asarray(params_dict["z"], dtype=float).tolist())

    params.min_diffusion = float(params_dict.get("min_diffusion", 1.0e-5))
    params.min_cross_section = float(params_dict.get("min_cross_section", 1.0e-6))
    params.reference_multiplication_ratio = float(params_dict["reference_multiplication_ratio"])
    params.precursor_loop_efficiency = float(params_dict["precursor_loop_efficiency"])
    params.precursor_loop_tau = float(params_dict["precursor_loop_tau"])

    params.rho_s = float(params_dict["rho_s"])
    params.c_p_s = float(params_dict["c_p_s"])
    params.A_s = float(params_dict["A_s"])
    params.rho_gr = float(params_dict["rho_gr"])
    params.c_p_g = float(params_dict["c_p_g"])
    params.A_gr = float(params_dict["A_gr"])
    params.h_sgr = float(params_dict["h_sgr"])
    params.P_sgr = float(params_dict["P_sgr"])
    params.k_gr = float(params_dict["k_gr"])
    params.eta_s = float(params_dict["eta_s"])
    params.eta_gr = float(params_dict["eta_gr"])
    params.err = float(params_dict.get("err", 0.0))
    params.bc_s0 = float(params_dict["bc_s0"])

    params.hx1_dx = float(params_dict["L_HX"]) / max(int(params_dict["Nx"]) - 1, 1)
    params.hx1_hot_velocity = -float(params_dict["V_he_s"])
    params.hx1_cold_velocity = float(params_dict["V_he_ss"])
    ua_hx = float(params_dict.get("UA_hx", params_dict["U_hx"]))
    params.hx1_hot_exchange_coeff = ua_hx / (
        float(params_dict["M_he_s"]) * float(params_dict["c_p_s"])
    )
    params.hx1_cold_exchange_coeff = ua_hx / (
        float(params_dict["M_he_ss"]) * float(params_dict["c_p_ss"])
    )

    params.hx2_dx = float(params_dict["L_HX2"]) / max(int(params_dict["Nx"]) - 1, 1)
    params.hx2_hot_velocity = -float(params_dict["V_he2_s"])
    params.hx2_cold_velocity = float(params_dict["V_he2_ss"])
    ua_hx2 = float(params_dict.get("UA2_hx", params_dict["U2_hx"]))
    params.hx2_hot_exchange_coeff = ua_hx2 / (
        float(params_dict["M_he2_s"]) * float(params_dict["c_p_ss"])
    )
    params.hx2_cold_exchange_coeff = ua_hx2 / (
        float(params_dict["M_he2_ss"]) * float(params_dict["c_p_sss"])
    )

    params.Ts_in = float(params_dict["Ts_in"])
    params.Ts_out = float(params_dict["Ts_out"])
    params.Tss_in = float(params_dict["Tss_in"])
    params.Tss_out = float(params_dict["Tss_out"])
    params.Tsss_in = float(params_dict["Tsss_in"])
    params.Tsss_out = float(params_dict["Tsss_out"])

    params.brayton_gamma = float(params_dict["brayton_gamma"])
    params.brayton_eta_c = float(params_dict["brayton_eta_c"])
    params.brayton_eta_t = float(params_dict["brayton_eta_t"])
    params.brayton_pi_c = float(params_dict["brayton_pi_c"])
    params.brayton_pi_t = float(params_dict["brayton_pi_t"])
    compressor_exponent = (params.brayton_gamma - 1.0) / max(params.brayton_gamma, 1.0e-12)
    turbine_exponent = -compressor_exponent
    params.brayton_compressor_temp_scale = math.pow(params.brayton_pi_c, compressor_exponent)
    params.brayton_turbine_temp_scale = math.pow(params.brayton_pi_t, turbine_exponent)
    params.brayton_recuperator_efficiency = float(params_dict["brayton_recuperator_efficiency"])
    params.brayton_cooler_outlet_temp = float(params_dict["brayton_cooler_outlet_temp"])
    params.brayton_min_heater_approach = float(params_dict["brayton_min_heater_approach"])
    params.brayton_mdot = float(params_dict["brayton_mdot"])
    params.c_p_sss = float(params_dict["c_p_sss"])
    return params


def ensure_capacity(name: str, blob: bytes) -> None:
    capacity = REGION_INFO[name]["byte_capacity"]
    if len(blob) > capacity:
        raise ValueError(f"{name} blob is {len(blob)} bytes but capacity is {capacity}")


def write_region_blob(out_dir: Path, name: str, blob: bytes) -> Path:
    ensure_capacity(name, blob)
    bin_path = out_dir / f"{name}.bin"
    hex_path = out_dir / f"{name}.hex32"
    bin_path.write_bytes(blob)
    write_hex32_file(hex_path, blob)
    return hex_path


def emit_plan(
    plan_path: Path,
    output_dir: Path,
    hex_paths: dict[str, Path],
    bitfile: str,
    ltxfile: str,
    poll_timeout_ms: int,
    poll_interval_ms: int,
    chunk_words: int,
    after_program_delay_ms: int,
    core_scalars: dict[str, float],
    bop_scalars: dict[str, float],
) -> None:
    core_entries = [
        make_control_entry(CORE_REG_OFFSETS["state"], tcl_hex32_words_for_u64(REGION_INFO["core_state"]["base"])),
        make_control_entry(CORE_REG_OFFSETS["params"], tcl_hex32_words_for_u64(REGION_INFO["core_params"]["base"])),
        make_control_entry(CORE_REG_OFFSETS["Ts_core_inlet"], tcl_hex32_words_for_f64(core_scalars["Ts_core_inlet"])),
        make_control_entry(CORE_REG_OFFSETS["rod_position"], tcl_hex32_words_for_f64(core_scalars["rod_position"])),
        make_control_entry(CORE_REG_OFFSETS["external_reactivity"], tcl_hex32_words_for_f64(core_scalars["external_reactivity"])),
        make_control_entry(CORE_REG_OFFSETS["boundary_out"], tcl_hex32_words_for_u64(REGION_INFO["core_boundary"]["base"])),
    ]
    bop_entries = [
        make_control_entry(BOP_REG_OFFSETS["state"], tcl_hex32_words_for_u64(REGION_INFO["bop_state"]["base"])),
        make_control_entry(BOP_REG_OFFSETS["params"], tcl_hex32_words_for_u64(REGION_INFO["bop_params"]["base"])),
        make_control_entry(BOP_REG_OFFSETS["Ts_HX1_L"], tcl_hex32_words_for_f64(bop_scalars["Ts_HX1_L"])),
        make_control_entry(BOP_REG_OFFSETS["Tss_HX1_0"], tcl_hex32_words_for_f64(bop_scalars["Tss_HX1_0"])),
        make_control_entry(BOP_REG_OFFSETS["Tss_HX2_L"], tcl_hex32_words_for_f64(bop_scalars["Tss_HX2_L"])),
        make_control_entry(BOP_REG_OFFSETS["Tsss_HX2_0"], tcl_hex32_words_for_f64(bop_scalars["Tsss_HX2_0"])),
        make_control_entry(BOP_REG_OFFSETS["boundary_out"], tcl_hex32_words_for_u64(REGION_INFO["bop_boundary"]["base"])),
    ]

    content = f"""array set MSR_VCU118_HOST_PLAN {{
    chunk_words {chunk_words}
    write_chunk_words {chunk_words}
    read_chunk_words 1
    poll_interval_ms {poll_interval_ms}
    default_timeout_ms {poll_timeout_ms}
    hw_server_url localhost:3121
    device_pattern xcvu9p*
    after_program_delay_ms {after_program_delay_ms}
    program_bitfile {{{bitfile}}}
    program_ltxfile {{{ltxfile}}}
}}

set MSR_VCU118_HOST_STEPS {{
    {{write_region core_state 0x{REGION_INFO["core_state"]["base"]:08X} {{{tcl_path(hex_paths["core_state"])}}}}}
    {{write_region core_params 0x{REGION_INFO["core_params"]["base"]:08X} {{{tcl_path(hex_paths["core_params"])}}}}}
    {{write_region core_boundary 0x{REGION_INFO["core_boundary"]["base"]:08X} {{{tcl_path(hex_paths["core_boundary"])}}}}}
    {{run_kernel core 0x{REGION_INFO["core_control"]["base"]:08X} {{{" ".join(core_entries)}}} {poll_timeout_ms}}}
    {{read_region core_boundary 0x{REGION_INFO["core_boundary"]["base"]:08X} 16 {{{tcl_path(output_dir / "core_boundary_out.hex32")}}}}}
    {{write_region bop_state 0x{REGION_INFO["bop_state"]["base"]:08X} {{{tcl_path(hex_paths["bop_state"])}}}}}
    {{write_region bop_params 0x{REGION_INFO["bop_params"]["base"]:08X} {{{tcl_path(hex_paths["bop_params"])}}}}}
    {{write_region bop_boundary 0x{REGION_INFO["bop_boundary"]["base"]:08X} {{{tcl_path(hex_paths["bop_boundary"])}}}}}
    {{run_kernel bop 0x{REGION_INFO["bop_control"]["base"]:08X} {{{" ".join(bop_entries)}}} {poll_timeout_ms}}}
    {{read_region bop_boundary 0x{REGION_INFO["bop_boundary"]["base"]:08X} 16 {{{tcl_path(output_dir / "bop_boundary_out.hex32")}}}}}
}}
"""
    plan_path.write_text(content, encoding="utf-8")


def prepare_smoke(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    core_state = create_default_core_state()
    bop_state = create_default_bop_state()
    params = create_default_kernel_params()
    zero_core_boundary = CoreStepBoundary()
    zero_bop_boundary = BopStepBoundary()

    hex_paths = {
        "core_state": write_region_blob(out_dir, "core_state", struct_bytes(core_state)),
        "core_params": write_region_blob(out_dir, "core_params", struct_bytes(params)),
        "core_boundary": write_region_blob(out_dir, "core_boundary", struct_bytes(zero_core_boundary)),
        "bop_state": write_region_blob(out_dir, "bop_state", struct_bytes(bop_state)),
        "bop_params": write_region_blob(out_dir, "bop_params", struct_bytes(params)),
        "bop_boundary": write_region_blob(out_dir, "bop_boundary", struct_bytes(zero_bop_boundary)),
    }

    metadata = {
        "core_state_size": ctypes.sizeof(CoreStepState),
        "bop_state_size": ctypes.sizeof(BopStepState),
        "kernel_params_size": ctypes.sizeof(KernelParams),
        "core_boundary_size": ctypes.sizeof(CoreStepBoundary),
        "bop_boundary_size": ctypes.sizeof(BopStepBoundary),
    }
    (out_dir / "layout_sizes.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    emit_plan(
        plan_path=out_dir / "smoke_plan.tcl",
        output_dir=out_dir,
        hex_paths=hex_paths,
        bitfile=args.bitfile or "",
        ltxfile=args.ltxfile or "",
        poll_timeout_ms=args.timeout_ms,
        poll_interval_ms=args.poll_interval_ms,
        chunk_words=args.chunk_words,
        after_program_delay_ms=args.after_program_delay_ms,
        core_scalars={
            "Ts_core_inlet": args.core_ts_core_inlet,
            "rod_position": args.core_rod_position,
            "external_reactivity": args.core_external_reactivity,
        },
        bop_scalars={
            "Ts_HX1_L": args.bop_ts_hx1_l,
            "Tss_HX1_0": args.bop_tss_hx1_0,
            "Tss_HX2_L": args.bop_tss_hx2_l,
            "Tsss_HX2_0": args.bop_tsss_hx2_0,
        },
    )
    print(f"Prepared smoke payload under: {out_dir}")
    print(f"Plan file: {out_dir / 'smoke_plan.tcl'}")


def prepare_offline_snapshot(args: argparse.Namespace) -> None:
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    python_dir = repo_root / "python"
    for path in (python_dir, repo_root):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
    from parameters import generate_parameters

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    model_params = generate_parameters(
        N=K_MAX_N,
        outer_dt=args.outer_dt,
        steady_state_steps=args.steady_state_steps,
        use_steady_state_initialization=True,
    )

    core_state = create_model_core_state(model_params)
    bop_state = create_model_bop_state(model_params)
    params = create_model_kernel_params(model_params, hardware_substeps=args.hardware_substeps)
    zero_core_boundary = CoreStepBoundary()
    zero_bop_boundary = BopStepBoundary()

    core_scalars = {
        "Ts_core_inlet": float(model_params["Ts_in"]),
        "rod_position": float(args.rod_position),
        "external_reactivity": float(args.external_reactivity),
    }
    bop_scalars = {
        "Ts_HX1_L": float(model_params["Ts_out"]),
        "Tss_HX1_0": float(model_params["Tss_in"]),
        "Tss_HX2_L": float(model_params["Tss_out"]),
        "Tsss_HX2_0": float(model_params["Tsss_in"]),
    }

    hex_paths = {
        "core_state": write_region_blob(out_dir, "core_state", struct_bytes(core_state)),
        "core_params": write_region_blob(out_dir, "core_params", struct_bytes(params)),
        "core_boundary": write_region_blob(out_dir, "core_boundary", struct_bytes(zero_core_boundary)),
        "bop_state": write_region_blob(out_dir, "bop_state", struct_bytes(bop_state)),
        "bop_params": write_region_blob(out_dir, "bop_params", struct_bytes(params)),
        "bop_boundary": write_region_blob(out_dir, "bop_boundary", struct_bytes(zero_bop_boundary)),
    }

    metadata = {
        "source": "parameters.generate_parameters",
        "core_state_size": ctypes.sizeof(CoreStepState),
        "bop_state_size": ctypes.sizeof(BopStepState),
        "kernel_params_size": ctypes.sizeof(KernelParams),
        "core_boundary_size": ctypes.sizeof(CoreStepBoundary),
        "bop_boundary_size": ctypes.sizeof(BopStepBoundary),
        "hardware_substeps": args.hardware_substeps,
        "core_scalars": core_scalars,
        "bop_scalars": bop_scalars,
        "steady_state_summary": model_params.get("steady_state_summary", {}),
    }
    (out_dir / "layout_sizes.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    emit_plan(
        plan_path=out_dir / "smoke_plan.tcl",
        output_dir=out_dir,
        hex_paths=hex_paths,
        bitfile=args.bitfile or "",
        ltxfile=args.ltxfile or "",
        poll_timeout_ms=args.timeout_ms,
        poll_interval_ms=args.poll_interval_ms,
        chunk_words=args.chunk_words,
        after_program_delay_ms=args.after_program_delay_ms,
        core_scalars=core_scalars,
        bop_scalars=bop_scalars,
    )
    print(f"Prepared offline snapshot under: {out_dir}")
    print(f"Plan file: {out_dir / 'smoke_plan.tcl'}")


def decode_boundary(args: argparse.Namespace) -> None:
    boundary_type = BOUNDARY_TYPES[args.kind]
    input_path = Path(args.input).resolve()
    if input_path.suffix.lower() == ".hex32":
        blob = read_hex32_file(input_path)
    else:
        blob = input_path.read_bytes()
    needed = ctypes.sizeof(boundary_type)
    if len(blob) < needed:
        raise ValueError(f"{input_path} has {len(blob)} bytes but {needed} are required for {args.kind} boundary")
    boundary = boundary_type.from_buffer_copy(blob[:needed])
    result = {field: getattr(boundary, field) for field, _ in boundary._fields_}
    print(json.dumps(result, indent=2, sort_keys=True))


def print_layout(_: argparse.Namespace) -> None:
    info = {
        "CoreStepState": ctypes.sizeof(CoreStepState),
        "BopStepState": ctypes.sizeof(BopStepState),
        "KernelParams": ctypes.sizeof(KernelParams),
        "CoreStepBoundary": ctypes.sizeof(CoreStepBoundary),
        "BopStepBoundary": ctypes.sizeof(BopStepBoundary),
    }
    print(json.dumps(info, indent=2, sort_keys=True))


def add_smoke_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--bitfile", default="")
    parser.add_argument("--ltxfile", default="")
    parser.add_argument("--timeout-ms", type=int, default=20000)
    parser.add_argument("--poll-interval-ms", type=int, default=10)
    parser.add_argument("--chunk-words", type=int, default=64)
    parser.add_argument("--after-program-delay-ms", type=int, default=2000)
    parser.add_argument("--core-ts-core-inlet", type=float, default=900.0)
    parser.add_argument("--core-rod-position", type=float, default=0.0)
    parser.add_argument("--core-external-reactivity", type=float, default=0.0)
    parser.add_argument("--bop-ts-hx1-l", type=float, default=930.0)
    parser.add_argument("--bop-tss-hx1-0", type=float, default=650.0)
    parser.add_argument("--bop-tss-hx2-l", type=float, default=640.0)
    parser.add_argument("--bop-tsss-hx2-0", type=float, default=500.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="First-pass host tooling for the VCU118 JTAG-AXI MSR image.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    smoke_parser = subparsers.add_parser("prepare-smoke", help="Generate a minimal smoke-test payload and Vivado plan.")
    add_smoke_args(smoke_parser)
    smoke_parser.set_defaults(func=prepare_smoke)

    offline_parser = subparsers.add_parser(
        "prepare-offline-snapshot",
        help="Generate a payload from the Python MSR steady-state model for the fixed n200 kernels.",
    )
    add_smoke_args(offline_parser)
    offline_parser.add_argument("--outer-dt", type=float, default=1.0)
    offline_parser.add_argument("--steady-state-steps", type=int, default=180)
    offline_parser.add_argument("--hardware-substeps", type=int, default=1)
    offline_parser.add_argument("--rod-position", type=float, default=0.0)
    offline_parser.add_argument("--external-reactivity", type=float, default=0.0)
    offline_parser.set_defaults(func=prepare_offline_snapshot)

    decode_parser = subparsers.add_parser("decode-boundary", help="Decode a core or bop boundary dump.")
    decode_parser.add_argument("--kind", choices=sorted(BOUNDARY_TYPES.keys()), required=True)
    decode_parser.add_argument("--input", required=True)
    decode_parser.set_defaults(func=decode_boundary)

    layout_parser = subparsers.add_parser("print-layout", help="Print struct sizes used by the host packer.")
    layout_parser.set_defaults(func=print_layout)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
