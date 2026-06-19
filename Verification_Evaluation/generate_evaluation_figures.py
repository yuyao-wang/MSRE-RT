import argparse
import copy
import json
import re
import shutil
import statistics
import subprocess
import time
from pathlib import Path

import numpy as np

try:
    from . import path_setup
except ImportError:  # pragma: no cover - direct script execution
    import path_setup
from async_split_prototype import run_async_split_transient
from cross_sections import build_cross_sections, estimate_global_reactivity
from parameters import DEFAULT_FUEL_FEEDBACK_SCALE, DEFAULT_GRAPHITE_FEEDBACK_SCALE
from verification_physics import (
    analytical_recirculating_precursors,
    apply_localized_temperature_perturbation,
    base_cross_sections,
    compute_conservation_residuals,
    compute_precursor_loop_decay_ratios,
    compute_reactivity_from_xs,
    default_params,
    delayed_source,
    equivalent_fission_source,
    make_reference_k,
    run_coupled_transient,
    steady_precursor_profiles,
)
from verification_utils import (
    apply_publication_style,
    ensure_dir,
    float_column,
    interpolate_reference_profile,
    iso_timestamp,
    l2_relative_error,
    linf_relative_error,
    max_abs_error,
    normalize_profile,
    pcm,
    peak_location,
    plotting_available,
    plt,
    read_csv_rows,
    save_figure,
    settling_time,
    trapz,
    unique_strings,
    write_csv,
    write_json,
)


REPO_ROOT = path_setup.REPO_ROOT
OUTPUT_ROOT = REPO_ROOT / "Verification_Evaluation" / "outputs"
HLS_REPORT_ROOT = REPO_ROOT / "documentation" / "synthesis_reports" / "windows_hls_reports"
SKIPPED_CASES = {
    "case_11_precision_sensitivity": "Reduced-precision and FPGA precision datasets are not available in this repository.",
}

HLS_REPORTS = {
    "core_n200_s1": HLS_REPORT_ROOT / "core_step_kernel_n200_s1_csynth.rpt",
    "bop_n200_s1": HLS_REPORT_ROOT / "bop_step_kernel_n200_s1_csynth.rpt",
}

AGGRESSIVE_ONE_STEP_METRICS = {
    "core": {
        "lut": 686798,
        "ff": 622831,
        "dsp": 6034,
        "bram": 40,
        "cpu_cpp_us": 10.781274999999999,
        "fpga_hls_min_us": 274.46,
        "fpga_hls_max_us": 275.66,
        "fpga_vs_cpu_cpp_x": 0.03920,
    },
    "bop": {
        "lut": 164114,
        "ff": 127440,
        "dsp": 1190,
        "bram": 48,
        "cpu_cpp_us": 2.2664599999999995,
        "fpga_hls_min_us": 46.68,
        "fpga_hls_max_us": 46.68,
        "fpga_vs_cpu_cpp_x": 0.04855,
    },
    "total": {
        "cpu_cpp_us": 13.047735,
        "fpga_hls_min_us": 321.14,
        "fpga_hls_max_us": 322.34,
        "fpga_wait_us": 3043.0,
        "python_us": 18339.541758177802,
        "fpga_vs_cpu_cpp_wait_x": 0.004287786723627999,
        "fpga_vs_python_wait_x": 6.03,
    },
    "device": {
        "avail_bram": 4320,
        "avail_dsp": 6840,
        "avail_ff": 2364480,
        "avail_lut": 1182240,
    },
}

PRECURSOR_MODE_ORDER = ("stationary_fuel", "advection_only", "recirculation")
PRECURSOR_MODE_LABELS = {
    "stationary_fuel": "Stationary fuel",
    "advection_only": "Advection only",
    "recirculation": "Recirculation",
    "stationary": "Stationary fuel",
}


def git_commit():
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], text=True)
            .strip()
        )
    except Exception:
        return "unknown"


def base_metadata(case_name, params, event_sequence_file=None):
    return {
        "case_name": case_name,
        "status": "completed",
        "model_version": "corrected_xs_transport_global_diag_v1",
        "git_commit": git_commit(),
        "date": iso_timestamp(),
        "Nz": int(params["N"]),
        "dt": float(params["outer_dt"]),
        "power_level": float(params["nominal_total_power"]),
        "u_c": float(params["u_core"]),
        "u_precursor": float(params.get("u_precursor", params["u_core"])),
        "tau_loop": float(params["tau_l"]),
        "cross_section_set": "temperature-dependent two-group synthetic set",
        "feedback_model": "temperature-dependent cross sections with global eigenvalue diagnostic",
        "precision": "float64",
        "platform": "python3",
        "event_sequence_file": event_sequence_file,
        "plotting_available": plotting_available(),
    }


def write_case_metadata(case_dir, metadata):
    write_json(Path(case_dir) / "metadata.json", metadata)


def case_path(case_name):
    case_dir = OUTPUT_ROOT / case_name
    ensure_dir(case_dir)
    return case_dir


def record_skipped_case(case_name, reason):
    case_dir = case_path(case_name)
    write_case_metadata(
        case_dir,
        {
            "case_name": case_name,
            "status": "skipped",
            "skip_reason": reason,
            "date": iso_timestamp(),
            "git_commit": git_commit(),
            "plotting_available": plotting_available(),
        },
    )


def maybe_save(fig, stem):
    if fig is None or not plotting_available():
        return
    save_figure(fig, stem)


def precursor_mode_label(mode):
    return PRECURSOR_MODE_LABELS.get(mode, str(mode).replace("_", " "))


def load_optional_v1_reference():
    ref_path = Path("paper_references/fig_V1_steady_state_profiles_reference.csv")
    if not ref_path.exists():
        return None
    data = np.genfromtxt(ref_path, delimiter=",", names=True)
    return data


def observed_order(refinement_values, errors):
    refinement_values = np.asarray(refinement_values, dtype=float)
    errors = np.asarray(errors, dtype=float)
    mask = np.isfinite(refinement_values) & np.isfinite(errors) & (errors > 0.0)
    if np.count_nonzero(mask) < 2:
        return float("nan")
    slope, _ = np.polyfit(np.log(refinement_values[mask]), np.log(errors[mask]), 1)
    return float(slope)


def interpolate_profile(reference_z, reference_values, target_z):
    return np.interp(
        np.asarray(target_z, dtype=float),
        np.asarray(reference_z, dtype=float),
        np.asarray(reference_values, dtype=float),
    )


def sample_series(reference_time, reference_values, target_time):
    return np.interp(
        np.asarray(target_time, dtype=float),
        np.asarray(reference_time, dtype=float),
        np.asarray(reference_values, dtype=float),
    )


def sample_history(reference_time, reference_history, target_time):
    reference_history = np.asarray(reference_history, dtype=float)
    target_time = np.asarray(target_time, dtype=float)
    sampled = np.zeros((target_time.size,) + reference_history.shape[1:], dtype=float)
    for idx in range(reference_history.shape[1]):
        sampled[:, idx] = np.interp(target_time, reference_time, reference_history[:, idx])
    return sampled


def transient_event_sequence():
    return transient_scenarios()[0]["events"]


def transient_scenarios():
    return [
        {
            "scenario_id": "mild_absorption_insertion",
            "scenario_label": "Mild absorption insertion",
            "events": [
                {
                    "event_id": "mild_absorption_insertion",
                    "start_time_s": 40.0,
                    "end_time_s": 100.0,
                    "event_type": "equivalent_absorption",
                    "magnitude": -75.0,
                    "unit": "pcm",
                    "target_module": "neutronics",
                    "purpose": "small-signal coupled-response check near the nominal operating point",
                }
            ],
        },
        {
            "scenario_id": "moderate_absorption_insertion",
            "scenario_label": "Moderate absorption insertion",
            "events": [
                {
                    "event_id": "moderate_absorption_insertion",
                    "start_time_s": 40.0,
                    "end_time_s": 120.0,
                    "event_type": "equivalent_absorption",
                    "magnitude": -600.0,
                    "unit": "pcm",
                    "target_module": "neutronics",
                    "purpose": "higher-worth absorption insertion for sensitivity ranking",
                }
            ],
        },
        {
            "scenario_id": "strong_absorption_insertion",
            "scenario_label": "Strong absorption insertion",
            "events": [
                {
                    "event_id": "strong_absorption_insertion",
                    "start_time_s": 40.0,
                    "end_time_s": 120.0,
                    "event_type": "equivalent_absorption",
                    "magnitude": -2400.0,
                    "unit": "pcm",
                    "target_module": "neutronics",
                    "purpose": "stress-test absorption insertion within the current reduced-model setup",
                }
            ],
        },
    ]


def write_event_sequence_csv(case_dir, event_sequence):
    fields = [
        "scenario_id",
        "scenario_label",
        "event_id",
        "start_time_s",
        "end_time_s",
        "event_type",
        "magnitude",
        "unit",
        "target_module",
        "purpose",
    ]
    write_csv(Path(case_dir) / "table_R1_transient_event_sequence.csv", fields, event_sequence)


def figure_axes(shape, size):
    if not plotting_available():
        return None, None
    apply_publication_style()
    fig, axes = plt.subplots(*shape, figsize=size, constrained_layout=True)
    return fig, axes


def sort_rows(rows, key):
    return sorted(rows, key=lambda row: float(row[key]))


def finite_values(*values):
    arrays = [np.asarray(value, dtype=float) for value in values]
    mask = np.ones_like(arrays[0], dtype=bool)
    for array in arrays:
        mask &= np.isfinite(array)
    return mask


def runtime_stats(run_callable, repeats=5):
    samples = []
    for _ in range(int(repeats)):
        t0 = time.perf_counter()
        run_callable()
        samples.append(time.perf_counter() - t0)
    return {
        "samples_s": samples,
        "mean_s": float(np.mean(samples)),
        "median_s": float(np.median(samples)),
        "min_s": float(np.min(samples)),
        "max_s": float(np.max(samples)),
        "std_s": float(np.std(samples, ddof=0)),
    }


def _hls_util_value(pattern, text):
    match = re.search(pattern, text)
    return float(match.group(1)) if match else float("nan")


def parse_hls_csynth_summary(report_path):
    text = Path(report_path).read_text(errors="ignore")
    clock_match = re.search(r"\|ap_clk\s*\|\s*([0-9.]+) ns\s*\|\s*([0-9.]+) ns", text)
    latency_match = re.search(
        r"\|\s*([0-9]+)\s*\|\s*([0-9]+)\s*\|\s*([0-9.]+)\s*(u?s|ms)\s*\|\s*([0-9.]+)\s*(u?s|ms)",
        text,
    )
    total_match = re.search(
        r"\|Total\s*\|\s*([0-9]+)\|\s*([0-9]+)\|\s*([0-9]+)\|\s*([0-9]+)\|\s*0\|",
        text,
    )
    available_match = re.search(
        r"\|Available\s*\|\s*([0-9]+)\|\s*([0-9]+)\|\s*([0-9]+)\|\s*([0-9]+)\|\s*([0-9]+)\|",
        text,
    )
    util_match = re.search(
        r"\|Utilization \(%\)\s*\|\s*([0-9]+)\|\s*([0-9]+)\|\s*([0-9]+)\|\s*([0-9]+)\|\s*([0-9]+)\|",
        text,
    )

    def to_us(value, unit):
        if unit == "ms":
            return 1000.0 * float(value)
        if unit == "us":
            return float(value)
        return 1.0e-3 * float(value)

    summary = {
        "clock_target_ns": float(clock_match.group(1)) if clock_match else float("nan"),
        "clock_est_ns": float(clock_match.group(2)) if clock_match else float("nan"),
        "latency_cycles_min": int(latency_match.group(1)) if latency_match else -1,
        "latency_cycles_max": int(latency_match.group(2)) if latency_match else -1,
        "latency_us_min": to_us(latency_match.group(3), latency_match.group(4)) if latency_match else float("nan"),
        "latency_us_max": to_us(latency_match.group(5), latency_match.group(6)) if latency_match else float("nan"),
        "used_bram": int(total_match.group(1)) if total_match else -1,
        "used_dsp": int(total_match.group(2)) if total_match else -1,
        "used_ff": int(total_match.group(3)) if total_match else -1,
        "used_lut": int(total_match.group(4)) if total_match else -1,
        "avail_bram": int(available_match.group(1)) if available_match else -1,
        "avail_dsp": int(available_match.group(2)) if available_match else -1,
        "avail_ff": int(available_match.group(3)) if available_match else -1,
        "avail_lut": int(available_match.group(4)) if available_match else -1,
        "util_bram_pct": float(util_match.group(1)) if util_match else float("nan"),
        "util_dsp_pct": float(util_match.group(2)) if util_match else float("nan"),
        "util_ff_pct": float(util_match.group(3)) if util_match else float("nan"),
        "util_lut_pct": float(util_match.group(4)) if util_match else float("nan"),
    }
    return summary


def relative_error_series(reference, candidate, floor=1.0e-12):
    reference = np.asarray(reference, dtype=float)
    candidate = np.asarray(candidate, dtype=float)
    return np.abs(candidate - reference) / np.maximum(np.abs(reference), floor)


def apply_min_span(axis, values, min_span, anchor=None):
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return
    lower = float(np.min(finite))
    upper = float(np.max(finite))
    if anchor is not None:
        lower = min(lower, float(anchor))
        upper = max(upper, float(anchor))
    span = upper - lower
    if span < float(min_span):
        midpoint = 0.5 * (lower + upper)
        half_span = 0.5 * float(min_span)
        axis.set_ylim(midpoint - half_span, midpoint + half_span)
    else:
        pad = 0.08 * span
        axis.set_ylim(lower - pad, upper + pad)


def case_00_steady_state_reference(quick=False):
    case_name = "case_00_steady_state_reference"
    case_dir = case_path(case_name)

    params = default_params(
        N=80 if quick else 160,
        steady_state_steps=80 if quick else 240,
        outer_dt=1.0,
    )
    result = run_coupled_transient(params, num_steps=60 if quick else 160, record_fields=["qprime"])
    z_over_h = result["z"] / float(params["L"])

    qprime = result["history"]["qprime"][-1]
    phi1_abs = np.asarray(result["final_phi1"], dtype=float)
    phi2_abs = np.asarray(result["final_phi2"], dtype=float)
    phi1_norm = normalize_profile(result["final_phi1"])
    phi2_norm = normalize_profile(result["final_phi2"])
    qprime_norm = normalize_profile(qprime)
    ts_k = result["final_Ts"]
    tgr_k = result["final_Tgr"]

    reference = load_optional_v1_reference()
    if reference is None:
        phi1_ref_norm = np.full_like(phi1_norm, np.nan)
        phi2_ref_norm = np.full_like(phi2_norm, np.nan)
        qprime_ref_norm = np.full_like(qprime_norm, np.nan)
        ts_ref_k = np.full_like(ts_k, np.nan)
        tgr_ref_k = np.full_like(tgr_k, np.nan)
    else:
        phi1_ref_norm = interpolate_profile(reference["z_over_H"], reference["phi1_ref_norm"], z_over_h)
        phi2_ref_norm = interpolate_profile(reference["z_over_H"], reference["phi2_ref_norm"], z_over_h)
        qprime_ref_norm = interpolate_profile(reference["z_over_H"], reference["qprime_ref_norm"], z_over_h)
        ts_ref_k = interpolate_profile(reference["z_over_H"], reference["Ts_ref_K"], z_over_h)
        tgr_ref_k = interpolate_profile(reference["z_over_H"], reference["Tgr_ref_K"], z_over_h)

    fig_rows = []
    for idx in range(z_over_h.size):
        fig_rows.append(
            {
                "z_over_H": z_over_h[idx],
                "phi1": phi1_abs[idx],
                "phi2": phi2_abs[idx],
                "phi1_norm": phi1_norm[idx],
                "phi2_norm": phi2_norm[idx],
                "qprime": qprime[idx],
                "qprime_norm": qprime_norm[idx],
                "Ts_K": ts_k[idx],
                "Tgr_K": tgr_k[idx],
                "phi1_ref_norm": phi1_ref_norm[idx],
                "phi2_ref_norm": phi2_ref_norm[idx],
                "qprime_ref_norm": qprime_ref_norm[idx],
                "Ts_ref_K": ts_ref_k[idx],
                "Tgr_ref_K": tgr_ref_k[idx],
            }
        )
    write_csv(
        case_dir / "fig_V1_steady_state_profiles.csv",
        list(fig_rows[0].keys()),
        fig_rows,
    )

    table_rows = []
    definitions = [
        ("phi1 shape", phi1_norm, phi1_ref_norm, "", "normalized"),
        ("phi2 shape", phi2_norm, phi2_ref_norm, "", "normalized"),
        ("qprime shape", qprime_norm, qprime_ref_norm, "", "normalized"),
        ("Ts", ts_k, ts_ref_k, "K", "absolute error"),
        ("Tgr", tgr_k, tgr_ref_k, "K", "absolute error"),
    ]
    for quantity, values, ref_values, unit, comment in definitions:
        finite_ref = np.isfinite(ref_values)
        if np.any(finite_ref):
            l2_err = l2_relative_error(values[finite_ref], ref_values[finite_ref])
            linf_err = linf_relative_error(values[finite_ref], ref_values[finite_ref])
            max_err = max_abs_error(values[finite_ref], ref_values[finite_ref])
        else:
            l2_err = np.nan
            linf_err = np.nan
            max_err = np.nan
        table_rows.append(
            {
                "quantity": quantity,
                "L2_error": l2_err,
                "Linf_error": linf_err,
                "max_abs_error": max_err,
                "unit": unit,
                "comment": comment if np.any(finite_ref) else "reference profile not available in repository",
            }
        )
    write_csv(
        case_dir / "table_V1_steady_state_errors.csv",
        list(table_rows[0].keys()),
        table_rows,
    )

    fig_rows_loaded = sort_rows(read_csv_rows(case_dir / "fig_V1_steady_state_profiles.csv"), "z_over_H")
    fig, axes = figure_axes((1, 3), (10.6, 4.4))
    if fig is not None:
        z_plot = float_column(fig_rows_loaded, "z_over_H")
        phi1_plot = float_column(fig_rows_loaded, "phi1")
        phi2_plot = float_column(fig_rows_loaded, "phi2")
        qprime_plot = float_column(fig_rows_loaded, "qprime_norm")
        qprime_ref_plot = float_column(fig_rows_loaded, "qprime_ref_norm")
        ts_plot = float_column(fig_rows_loaded, "Ts_K")
        tgr_plot = float_column(fig_rows_loaded, "Tgr_K")
        ts_ref_plot = float_column(fig_rows_loaded, "Ts_ref_K")
        tgr_ref_plot = float_column(fig_rows_loaded, "Tgr_ref_K")
        for axis in np.atleast_1d(axes):
            axis.tick_params(labelsize=22)

        axes[0].plot(z_plot, phi1_plot, label=r"$\phi_1$")
        axes[0].plot(z_plot, phi2_plot, label=r"$\phi_2$")
        axes[0].set_xlabel(r"$z/H$")
        axes[0].set_ylabel("Flux magnitude")
        axes[0].legend(
            loc="lower left",
            bbox_to_anchor=(0.0, 1.02),
            ncol=2,
            frameon=True,
            facecolor="white",
            framealpha=0.94,
            edgecolor="0.8",
            fontsize=16,
            borderaxespad=0.0,
            columnspacing=1.0,
        )

        axes[1].plot(z_plot, qprime_plot, label=r"$q'$")
        if np.any(np.isfinite(qprime_ref_plot)):
            axes[1].plot(z_plot, qprime_ref_plot, "--", label=r"$q'_{\mathrm{ref}}$")
        axes[1].set_xlabel(r"$z/H$")
        axes[1].set_ylabel("Normalized value")
        axes[1].set_ylim(0.0, 1.05)
        axes[1].legend(loc="lower center", bbox_to_anchor=(0.5, 0.03), ncol=2, frameon=False, fontsize=18)

        axes[2].plot(z_plot, ts_plot, label=r"$T_s$")
        axes[2].plot(z_plot, tgr_plot, label=r"$T_{gr}$")
        if np.any(np.isfinite(ts_ref_plot)):
            axes[2].plot(z_plot, ts_ref_plot, "--", label=r"$T_{s,\mathrm{ref}}$")
            axes[2].plot(z_plot, tgr_ref_plot, "--", label=r"$T_{gr,\mathrm{ref}}$")
        axes[2].set_xlabel(r"$z/H$")
        axes[2].set_ylabel("Temperature (K)")
        axes[2].legend(loc="best", frameon=False, fontsize=17)
    maybe_save(fig, case_dir / "fig_V1_steady_state_profiles")

    metadata = base_metadata(case_name, params)
    metadata["generated_files"] = [
        "fig_V1_steady_state_profiles.csv",
        "fig_V1_steady_state_profiles.pdf",
        "fig_V1_steady_state_profiles.png",
        "table_V1_steady_state_errors.csv",
    ]
    write_case_metadata(case_dir, metadata)


def case_01_dnp_plugflow_analytical(quick=False):
    case_name = "case_01_dnp_plugflow_analytical"
    case_dir = case_path(case_name)

    params = default_params(
        N=80 if quick else 160,
        steady_state_steps=20 if quick else 60,
        precursor_loop_efficiency=1.0,
    )
    constant_source = 1.0
    source_profile = np.full(int(params["N"]), constant_source, dtype=float)
    c_num = steady_precursor_profiles(
        params,
        fission_source=source_profile,
        mode="recirculation",
        loop_efficiency=1.0,
    )
    c_ana = analytical_recirculating_precursors(params, constant_source)

    z_over_h = np.asarray(params["z"], dtype=float) / float(params["L"])
    figure_rows = []
    for group in range(c_num.shape[0]):
        rel_error = np.abs(c_num[group] - c_ana[group]) / np.maximum(np.abs(c_ana[group]), 1.0e-12)
        for idx in range(z_over_h.size):
            figure_rows.append(
                {
                    "group": group + 1,
                    "z_over_H": z_over_h[idx],
                    "C_num": c_num[group, idx],
                    "C_ana": c_ana[group, idx],
                    "rel_error": rel_error[idx],
                }
            )
    write_csv(case_dir / "fig_V4_dnp_analytical_verification.csv", list(figure_rows[0].keys()), figure_rows)

    loop_ratios = compute_precursor_loop_decay_ratios(params)
    table_v2_rows = []
    for group in range(c_num.shape[0]):
        table_v2_rows.append(
            {
                "group": group + 1,
                "lambda_s_inv": loop_ratios["lambda_i"][group],
                "tau_loop_s": loop_ratios["tau_loop"],
                "eta_loop": loop_ratios["eta_loop"],
                "theoretical_ratio": loop_ratios["theoretical_ratio"][group],
                "numerical_ratio": loop_ratios["numerical_ratio"][group],
                "abs_error": abs(loop_ratios["numerical_ratio"][group] - loop_ratios["theoretical_ratio"][group]),
                "rel_error": abs(loop_ratios["numerical_ratio"][group] - loop_ratios["theoretical_ratio"][group])
                / max(abs(loop_ratios["theoretical_ratio"][group]), 1.0e-12),
            }
        )
    write_csv(case_dir / "table_V2_loop_decay_ratio.csv", list(table_v2_rows[0].keys()), table_v2_rows)

    table_v3_rows = []
    for group in range(c_num.shape[0]):
        table_v3_rows.append(
            {
                "group": group + 1,
                "case": "analytical_recirculation",
                "L2_error": l2_relative_error(c_num[group], c_ana[group]),
                "Linf_error": linf_relative_error(c_num[group], c_ana[group]),
                "z_peak_num": peak_location(z_over_h, c_num[group]),
                "z_peak_ref": peak_location(z_over_h, c_ana[group]),
                "z_peak_error": abs(peak_location(z_over_h, c_num[group]) - peak_location(z_over_h, c_ana[group])),
            }
        )
    write_csv(case_dir / "table_V3_dnp_transport_errors.csv", list(table_v3_rows[0].keys()), table_v3_rows)

    figure_rows_loaded = read_csv_rows(case_dir / "fig_V4_dnp_analytical_verification.csv")
    fig, axes = figure_axes((1, 3), (9.8, 4.2))
    if fig is not None:
        for axis, group in zip(np.atleast_1d(axes), (1, 3, 6)):
            subset = sort_rows([row for row in figure_rows_loaded if int(row["group"]) == group], "z_over_H")
            axis.plot(float_column(subset, "z_over_H"), float_column(subset, "C_num"), label="Numerical")
            axis.plot(float_column(subset, "z_over_H"), float_column(subset, "C_ana"), "--", label="Analytical")
            axis.set_xlabel(r"$z/H$")
            axis.set_ylabel(rf"$C_{{{group}}}$")
            axis.tick_params(labelsize=22)
        np.atleast_1d(axes)[0].legend(loc="lower right", frameon=False, fontsize=18)
    maybe_save(fig, case_dir / "fig_V4_dnp_analytical_verification")

    metadata = base_metadata(case_name, params)
    metadata["generated_files"] = [
        "fig_V4_dnp_analytical_verification.csv",
        "fig_V4_dnp_analytical_verification.pdf",
        "fig_V4_dnp_analytical_verification.png",
        "table_V2_loop_decay_ratio.csv",
        "table_V3_dnp_transport_errors.csv",
    ]
    write_case_metadata(case_dir, metadata)


def case_02_dnp_stationary_vs_flowing(quick=False):
    case_name = "case_02_dnp_stationary_vs_flowing"
    case_dir = case_path(case_name)
    stale_table_v3 = case_dir / "table_V3_dnp_transport_errors.csv"
    if stale_table_v3.exists():
        stale_table_v3.unlink()

    params = default_params(
        N=80 if quick else 160,
        steady_state_steps=20 if quick else 60,
        precursor_loop_efficiency=1.0,
    )
    fission_source = equivalent_fission_source(params)
    z_over_h = np.asarray(params["z"], dtype=float) / float(params["L"])
    profile_cases = {
        "stationary_fuel": steady_precursor_profiles(params, fission_source=fission_source, mode="stationary"),
        "advection_only": steady_precursor_profiles(params, fission_source=fission_source, mode="advection_only"),
        "recirculation": steady_precursor_profiles(
            params,
            fission_source=fission_source,
            mode="recirculation",
            loop_efficiency=1.0,
        ),
    }

    fig_v2_rows = []
    fig_v3_rows = []
    table_v4_rows = []

    for case_label, profiles in profile_cases.items():
        normalized_groups = np.vstack([normalize_profile(profiles[group]) for group in range(profiles.shape[0])])
        for idx in range(z_over_h.size):
            row = {"case": case_label, "z_over_H": z_over_h[idx]}
            for group in range(profiles.shape[0]):
                row[f"C{group + 1}_norm"] = normalized_groups[group, idx]
            fig_v2_rows.append(row)

        sd_profile = delayed_source(profiles, params)
        sd_norm = normalize_profile(sd_profile)
        for idx in range(z_over_h.size):
            fig_v3_rows.append(
                {
                    "case": case_label,
                    "z_over_H": z_over_h[idx],
                    "Sd": sd_profile[idx],
                    "Sd_norm": sd_norm[idx],
                    "Sd_ref_norm": np.nan,
                }
            )
        table_v4_rows.append(
            {
                "case": case_label,
                "Sd_integral": trapz(sd_profile, params["z"]),
                "Sd_peak": float(np.max(sd_profile)),
                "z_peak_over_H": peak_location(z_over_h, sd_profile),
                "L2_error_vs_ref": np.nan,
                "Linf_error_vs_ref": np.nan,
            }
        )

    write_csv(case_dir / "fig_V2_dnp_profiles_cases.csv", list(fig_v2_rows[0].keys()), fig_v2_rows)
    write_csv(case_dir / "fig_V3_delayed_source_density.csv", list(fig_v3_rows[0].keys()), fig_v3_rows)
    write_csv(case_dir / "table_V4_delayed_source_metrics.csv", list(table_v4_rows[0].keys()), table_v4_rows)

    fig_v2_loaded = read_csv_rows(case_dir / "fig_V2_dnp_profiles_cases.csv")
    fig, axes = figure_axes((1, 3), (15.6, 5.4))
    if fig is not None:
        image = None
        for axis, case_label in zip(np.atleast_1d(axes), PRECURSOR_MODE_ORDER):
            subset = sort_rows([row for row in fig_v2_loaded if row["case"] == case_label], "z_over_H")
            z_plot = float_column(subset, "z_over_H")
            group_matrix = np.vstack([float_column(subset, f"C{group}_norm") for group in range(1, 7)])
            image = axis.imshow(
                group_matrix,
                origin="lower",
                aspect="auto",
                extent=[z_plot[0], z_plot[-1], 0.5, 6.5],
                vmin=0.0,
                vmax=1.0,
                cmap="viridis",
            )
            axis.contour(
                z_plot,
                np.arange(1.0, 7.0),
                group_matrix,
                levels=np.linspace(0.2, 0.8, 4),
                colors="white",
                linewidths=0.8,
                alpha=0.85,
            )
            axis.set_xlabel(r"$z/H$")
            axis.set_yticks(np.arange(1, 7))
            axis.text(
                0.03,
                0.96,
                precursor_mode_label(case_label),
                transform=axis.transAxes,
                ha="left",
                va="top",
                color="white",
                fontsize=18,
                fontweight="semibold",
                bbox={"facecolor": "black", "alpha": 0.25, "pad": 4, "edgecolor": "none"},
            )
        np.atleast_1d(axes)[0].set_ylabel("Precursor group index")
        for axis in np.atleast_1d(axes)[1:]:
            axis.set_yticklabels([])
        colorbar = fig.colorbar(image, ax=np.atleast_1d(axes), pad=0.02, shrink=0.92)
        colorbar.set_label(r"$C_i/C_{i,\max}$")
    maybe_save(fig, case_dir / "fig_V2_dnp_profiles_cases")

    fig_v3_loaded = read_csv_rows(case_dir / "fig_V3_delayed_source_density.csv")
    fig, ax = figure_axes((1, 1), (8.2, 5.6))
    if fig is not None:
        ax = np.atleast_1d(ax)[0]
        style_map = {
            "stationary_fuel": {"marker": "o", "linestyle": "-", "color": "#1f77b4"},
            "advection_only": {"marker": "s", "linestyle": "--", "color": "#ff7f0e"},
            "recirculation": {"marker": "^", "linestyle": "-", "color": "#2ca02c"},
        }
        for case_label in PRECURSOR_MODE_ORDER:
            subset = sort_rows([row for row in fig_v3_loaded if row["case"] == case_label], "z_over_H")
            style = style_map[case_label]
            ax.plot(
                float_column(subset, "z_over_H"),
                float_column(subset, "Sd_norm"),
                label=precursor_mode_label(case_label),
                marker=style["marker"],
                linestyle=style["linestyle"],
                color=style["color"],
                markevery=18,
            )
        ax.set_xlabel(r"$z/H$")
        ax.set_ylabel(r"$S_d/S_{d,\max}$")
        ax.set_ylim(0.0, 1.05)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.18), ncol=3, frameon=False)
    maybe_save(fig, case_dir / "fig_V3_delayed_source_density")

    metadata = base_metadata(case_name, params)
    metadata["generated_files"] = [
        "fig_V2_dnp_profiles_cases.csv",
        "fig_V2_dnp_profiles_cases.pdf",
        "fig_V2_dnp_profiles_cases.png",
        "fig_V3_delayed_source_density.csv",
        "fig_V3_delayed_source_density.pdf",
        "fig_V3_delayed_source_density.png",
        "table_V4_delayed_source_metrics.csv",
    ]
    write_case_metadata(case_dir, metadata)


def case_03_uniform_temperature_feedback(quick=False):
    case_name = "case_03_uniform_temperature_feedback"
    case_dir = case_path(case_name)

    params = default_params(N=80 if quick else 160, steady_state_steps=20 if quick else 60)
    params_before = default_params(
        N=80 if quick else 160,
        steady_state_steps=20 if quick else 60,
        feedback_scale_s=1.0,
        feedback_scale_gr=1.0,
    )
    delta_t_values = (
        np.array([-30.0, -15.0, 0.0, 15.0, 30.0])
        if quick
        else np.array([-60.0, -40.0, -20.0, 0.0, 20.0, 40.0, 60.0])
    )

    def rho_slope_sweep(local_params, perturbation_type):
        reference_k_raw, phi_guess = make_reference_k(local_params)
        rho_series = []
        rows_local = []
        for delta_t in delta_t_values:
            fuel_temp = np.asarray(local_params["T_s_ref"], dtype=float).copy()
            graphite_temp = np.asarray(local_params["T_gr_ref"], dtype=float).copy()
            if perturbation_type == "fuel_salt":
                fuel_temp += delta_t
            elif perturbation_type == "graphite":
                graphite_temp += delta_t
            elif perturbation_type == "isothermal":
                fuel_temp += delta_t
                graphite_temp += delta_t
            else:
                raise ValueError(f"Unsupported perturbation type: {perturbation_type}")

            xs = build_cross_sections(fuel_temp, graphite_temp, local_params)
            diag = compute_reactivity_from_xs(xs, local_params, reference_k_raw, phi_guess=phi_guess)
            phi_guess = diag["phi"]
            rho_value_pcm = float(pcm(diag["rho"]))
            rho_series.append(rho_value_pcm)
            rows_local.append(
                {
                    "perturbation_type": perturbation_type,
                    "deltaT_K": delta_t,
                    "k_eff_global": diag["k_eff_global"],
                    "rho_pcm": rho_value_pcm,
                }
            )
        return float(np.polyfit(delta_t_values, rho_series, 1)[0]), rows_local

    rows = []
    slopes_after = {}
    slopes_before = {}
    for perturbation_type in ("fuel_salt", "graphite"):
        slopes_after[perturbation_type], rows_local = rho_slope_sweep(params, perturbation_type)
        slopes_before[perturbation_type], _ = rho_slope_sweep(params_before, perturbation_type)
        rows.extend(rows_local)

    slopes_after["isothermal"], _ = rho_slope_sweep(params, "isothermal")
    slopes_before["isothermal"], _ = rho_slope_sweep(params_before, "isothermal")

    write_csv(case_dir / "fig_V5_uniform_temperature_feedback.csv", list(rows[0].keys()), rows)

    reference_values = {
        "fuel_salt": -8.5,
        "graphite": -6.1,
        "isothermal": -14.6,
    }
    labels = {
        "fuel_salt": "Fuel temperature coefficient",
        "graphite": "Graphite temperature coefficient",
        "isothermal": "Isothermal temperature coefficient",
    }
    table_rows = [
        {
            "coefficient": labels[key],
            "reference_pcm_per_K": reference_values[key],
            "present_before_correction_pcm_per_K": slopes_before[key],
            "present_after_correction_pcm_per_K": slopes_after[key],
            "abs_error_after_correction": abs(slopes_after[key] - reference_values[key]),
            "rel_error_after_correction": abs(slopes_after[key] - reference_values[key]) / max(abs(reference_values[key]), 1.0e-12),
        }
        for key in ("fuel_salt", "graphite", "isothermal")
    ]
    write_csv(case_dir / "table_V5_temperature_coefficient_recovery.csv", list(table_rows[0].keys()), table_rows)

    fig_rows_loaded = read_csv_rows(case_dir / "fig_V5_uniform_temperature_feedback.csv")
    fig, ax = figure_axes((1, 1), (8.6, 6.1))
    if fig is not None:
        ax = np.atleast_1d(ax)[0]
        ax.tick_params(labelsize=22)
        style_map = {
            "fuel_salt": {"marker": "o", "label": "Fuel salt"},
            "graphite": {"marker": "s", "label": "Graphite"},
        }
        ax.axhline(0.0, color="0.55", linewidth=1.4, linestyle=":")
        for perturbation_type in ("fuel_salt", "graphite"):
            subset = sort_rows([row for row in fig_rows_loaded if row["perturbation_type"] == perturbation_type], "deltaT_K")
            x = float_column(subset, "deltaT_K")
            y = float_column(subset, "rho_pcm")
            fit = np.polyfit(x, y, 1)
            style = style_map[perturbation_type]
            line = ax.plot(x, y, marker=style["marker"], label=f'{style["label"]} data')[0]
            ax.plot(
                x,
                np.polyval(fit, x),
                "--",
                color=line.get_color(),
                label=f'{style["label"]} fit ({fit[0]:.2f} pcm/K)',
            )
        ax.set_xlabel(r"$\Delta T$ (K)")
        ax.set_ylabel(r"$\rho$ (pcm)")
        ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.18),
            ncol=2,
            frameon=False,
            fontsize=16,
            handlelength=2.8,
            columnspacing=1.6,
        )
    maybe_save(fig, case_dir / "fig_V5_uniform_temperature_feedback")

    metadata = base_metadata(case_name, params)
    metadata["generated_files"] = [
        "fig_V5_uniform_temperature_feedback.csv",
        "fig_V5_uniform_temperature_feedback.pdf",
        "fig_V5_uniform_temperature_feedback.png",
        "table_V5_temperature_coefficient_recovery.csv",
    ]
    write_case_metadata(case_dir, metadata)


def case_04_local_temperature_worth(quick=False):
    case_name = "case_04_local_temperature_worth"
    case_dir = case_path(case_name)

    params = default_params(N=80 if quick else 160, steady_state_steps=20 if quick else 60)
    reference_k_raw, phi_guess = make_reference_k(params)
    z0_values = np.linspace(0.0, 1.0, 9 if quick else 21)
    sigma_values = np.array([0.05, 0.08, 0.11]) if quick else np.array([0.04, 0.06, 0.08, 0.10, 0.12, 0.14])
    delta_t0 = 20.0
    nominal_sigma = 0.08

    rows = []
    for sigma_over_h in sigma_values:
        for z0 in z0_values:
            fuel_temp = apply_localized_temperature_perturbation(params, z0, delta_t0, sigma_over_h)
            xs = build_cross_sections(fuel_temp, np.asarray(params["T_gr_ref"], dtype=float), params)
            diag = compute_reactivity_from_xs(xs, params, reference_k_raw, phi_guess=phi_guess)
            phi_guess = diag["phi"]
            delta_rho_pcm = float(pcm(diag["rho"]))
            rows.append(
                {
                    "z0_over_H": z0,
                    "deltaT0_K": delta_t0,
                    "sigmaT_over_H": sigma_over_h,
                    "delta_rho_pcm": delta_rho_pcm,
                    "worth_pcm_per_K": delta_rho_pcm / delta_t0,
                }
            )
    write_csv(case_dir / "fig_V6_local_temperature_worth.csv", list(rows[0].keys()), rows)

    locations = {"inlet": 0.0, "center": 0.5, "outlet": 1.0}
    nominal_rows = [row for row in rows if abs(row["sigmaT_over_H"] - nominal_sigma) < 1.0e-12]
    table_rows = []
    for label, target in locations.items():
        best_row = min(nominal_rows, key=lambda row: abs(row["z0_over_H"] - target))
        table_rows.append(
            {
                "location_label": label,
                "z0_over_H": best_row["z0_over_H"],
                "deltaT0_K": best_row["deltaT0_K"],
                "delta_rho_pcm": best_row["delta_rho_pcm"],
                "worth_pcm_per_K": best_row["worth_pcm_per_K"],
            }
        )
    write_csv(case_dir / "table_V6_local_temperature_worth.csv", list(table_rows[0].keys()), table_rows)

    fig_rows_loaded = read_csv_rows(case_dir / "fig_V6_local_temperature_worth.csv")
    fig, ax = figure_axes((1, 1), (8.4, 5.8))
    if fig is not None:
        ax = np.atleast_1d(ax)[0]
        x_values = np.unique(float_column(fig_rows_loaded, "z0_over_H"))
        y_values = np.unique(float_column(fig_rows_loaded, "sigmaT_over_H"))
        worth_map = np.full((y_values.size, x_values.size), np.nan)
        for row in fig_rows_loaded:
            ix = int(np.argmin(np.abs(x_values - float(row["z0_over_H"]))))
            iy = int(np.argmin(np.abs(y_values - float(row["sigmaT_over_H"]))))
            worth_map[iy, ix] = float(row["worth_pcm_per_K"])
        contour = ax.contourf(x_values, y_values, worth_map, levels=16, cmap="cividis")
        ax.contour(x_values, y_values, worth_map, levels=8, colors="white", linewidths=0.9, alpha=0.7)
        ax.axhline(nominal_sigma, color="white", linestyle="--", linewidth=1.3, alpha=0.9)
        ax.scatter([0.0, 0.5, 1.0], [nominal_sigma, nominal_sigma, nominal_sigma], c="white", edgecolors="black", s=90, zorder=3)
        ax.set_xlabel(r"$z_0/H$")
        ax.set_ylabel(r"$\sigma_T/H$")
        colorbar = fig.colorbar(contour, ax=ax, pad=0.02)
        colorbar.set_label("Worth (pcm/K)")
    maybe_save(fig, case_dir / "fig_V6_local_temperature_worth")

    metadata = base_metadata(case_name, params)
    metadata["generated_files"] = [
        "fig_V6_local_temperature_worth.csv",
        "fig_V6_local_temperature_worth.pdf",
        "fig_V6_local_temperature_worth.png",
        "table_V6_local_temperature_worth.csv",
    ]
    write_case_metadata(case_dir, metadata)


def case_05_rod_worth_verification(quick=False):
    case_name = "case_05_rod_worth_verification"
    case_dir = case_path(case_name)

    params = default_params(N=80 if quick else 160, steady_state_steps=20 if quick else 60)
    reference_k_raw, phi_guess = make_reference_k(params)
    targets_pcm = np.array([-25.0, -50.0, -75.0, -100.0, -200.0, -600.0, -2400.0], dtype=float)

    rows = []
    for target in targets_pcm:
        xs = build_cross_sections(
            np.asarray(params["T_s_ref"], dtype=float),
            np.asarray(params["T_gr_ref"], dtype=float),
            params,
            external_reactivity=target / 1.0e5,
        )
        diag = compute_reactivity_from_xs(xs, params, reference_k_raw, phi_guess=phi_guess)
        phi_guess = diag["phi"]
        rho_eigenvalue_pcm = float(pcm(diag["rho"]))
        rows.append(
            {
                "rho_target_pcm": target,
                "rho_eigenvalue_pcm": rho_eigenvalue_pcm,
                "error_pcm": rho_eigenvalue_pcm - target,
                "relative_error": (rho_eigenvalue_pcm - target) / max(abs(target), 1.0e-12),
            }
        )
    write_csv(case_dir / "fig_V7_rod_worth_verification.csv", list(rows[0].keys()), rows)
    write_csv(case_dir / "table_V7_rod_worth_errors.csv", list(rows[0].keys()), rows)

    fig_rows_loaded = sort_rows(read_csv_rows(case_dir / "fig_V7_rod_worth_verification.csv"), "rho_target_pcm")
    fig, ax = figure_axes((1, 1), (7.0, 5.4))
    if fig is not None:
        ax = np.atleast_1d(ax)[0]
        ax.tick_params(labelsize=21)
        target_values = float_column(fig_rows_loaded, "rho_target_pcm")
        calc_values = float_column(fig_rows_loaded, "rho_eigenvalue_pcm")
        ax.fill_between(target_values, target_values - 2.0, target_values + 2.0, color="0.87", alpha=0.9)
        ax.plot(target_values, calc_values, "o", label="Computed")
        ax.plot(target_values, target_values, "k--", label=r"$y=x$")
        ax.set_xlabel("Target worth (pcm)")
        ax.set_ylabel("Eigenvalue worth (pcm)")
        ax.legend(loc="upper left", frameon=False, fontsize=17)
    maybe_save(fig, case_dir / "fig_V7_rod_worth_verification")

    metadata = base_metadata(case_name, params)
    metadata["generated_files"] = [
        "fig_V7_rod_worth_verification.csv",
        "fig_V7_rod_worth_verification.pdf",
        "fig_V7_rod_worth_verification.png",
        "table_V7_rod_worth_errors.csv",
    ]
    write_case_metadata(case_dir, metadata)


def convergence_reference_result(grid_n, dt_value, quick=False):
    params = default_params(
        N=grid_n,
        outer_dt=dt_value,
        steady_state_steps=20 if quick else 60,
    )
    steps = int(round((40.0 if quick else 120.0) / dt_value))
    result = run_coupled_transient(
        params,
        num_steps=steps,
        event_sequence=transient_event_sequence(),
        record_fields=["phi1", "phi2", "Sd", "Ts"],
    )
    return params, result


def case_06_grid_convergence(quick=False):
    case_name = "case_06_grid_convergence"
    case_dir = case_path(case_name)

    grid_levels = [50, 100, 200] if quick else [50, 100, 200, 400, 800]
    dt_value = 1.0
    reference_params, reference_result = convergence_reference_result(max(grid_levels), dt_value, quick=quick)

    rows = []
    plot_data = {"P(t)": [], r"$\phi_2(z,t_f)$": [], r"$S_d(z,t_f)$": [], r"$T_s(z,t_f)$": []}
    table_rows = []

    for grid_n in grid_levels:
        params, result = convergence_reference_result(grid_n, dt_value, quick=quick)
        ref_power = sample_series(reference_result["time_s"], reference_result["power_W"], result["time_s"])
        ref_phi2 = interpolate_profile(reference_result["z"], reference_result["final_phi2"], result["z"])
        ref_sd = interpolate_profile(reference_result["z"], reference_result["final_Sd"], result["z"])
        ref_ts = interpolate_profile(reference_result["z"], reference_result["final_Ts"], result["z"])

        specs = [
            ("P(t)", result["power_W"], ref_power),
            (r"$\phi_2(z,t_f)$", result["final_phi2"], ref_phi2),
            (r"$S_d(z,t_f)$", result["final_Sd"], ref_sd),
            (r"$T_s(z,t_f)$", result["final_Ts"], ref_ts),
        ]
        for quantity, values, ref_values in specs:
            l2_err = l2_relative_error(values, ref_values)
            linf_err = linf_relative_error(values, ref_values)
            rows.append(
                {
                    "Nz": grid_n,
                    "dz": float(params["dz"]),
                    "quantity": quantity,
                    "L2_error": l2_err,
                    "Linf_error": linf_err,
                }
            )
            plot_data[quantity].append((float(params["dz"]), l2_err))

    for quantity, samples in plot_data.items():
        samples = sorted(samples, key=lambda item: item[0], reverse=True)
        reported_error = samples[-2][1] if len(samples) > 1 else np.nan
        table_rows.append(
            {
                "test_type": "grid convergence",
                "quantity": quantity,
                "refinement_variable": "dz",
                "observed_order": observed_order([item[0] for item in samples], [item[1] for item in samples]),
                "reference_level": f"Nz={max(grid_levels)}",
                "reported_error": reported_error,
                "fit_range": f"Nz={min(grid_levels)} to {sorted(grid_levels)[-2]}",
                "comment": "reported error is the second-finest relative L2 error against the finest-grid reference",
            }
        )

    write_csv(case_dir / "fig_V8_grid_convergence.csv", list(rows[0].keys()), rows)
    write_csv(case_dir / "table_V8_solver_convergence.csv", list(table_rows[0].keys()), table_rows)

    fig_rows_loaded = read_csv_rows(case_dir / "fig_V8_grid_convergence.csv")
    fig, ax = figure_axes((1, 1), (8.6, 6.8))
    if fig is not None:
        ax = np.atleast_1d(ax)[0]
        ax.tick_params(labelsize=31, pad=7)
        label_map = {
            "P(t)": "Power",
            r"$\phi_2(z,t_f)$": r"$\phi_2(z,t_f)$",
            r"$S_d(z,t_f)$": r"$S_d(z,t_f)$",
            r"$T_s(z,t_f)$": r"$T_s(z,t_f)$",
        }
        for quantity in unique_strings(fig_rows_loaded, "quantity"):
            subset = sort_rows([row for row in fig_rows_loaded if row["quantity"] == quantity], "dz")
            x_values = float_column(subset, "dz")
            y_values = float_column(subset, "L2_error")
            mask = y_values > 0.0
            ax.loglog(
                x_values[mask],
                y_values[mask],
                marker="o",
                markersize=11.5,
                markeredgewidth=1.1,
                linewidth=3.7,
                label=label_map.get(quantity, quantity),
            )
        ax.set_xlabel(r"$\Delta z$", fontsize=34, labelpad=8)
        ax.set_ylabel(r"Relative $L_2$ error", fontsize=34, labelpad=8)
        ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.27),
            ncol=2,
            frameon=False,
            fontsize=25,
            columnspacing=1.4,
        )
    maybe_save(fig, case_dir / "fig_V8_grid_convergence")

    metadata = base_metadata(case_name, reference_params)
    metadata["generated_files"] = [
        "fig_V8_grid_convergence.csv",
        "fig_V8_grid_convergence.pdf",
        "fig_V8_grid_convergence.png",
        "table_V8_solver_convergence.csv",
    ]
    write_case_metadata(case_dir, metadata)


def case_07_timestep_convergence(quick=False):
    case_name = "case_07_timestep_convergence"
    case_dir = case_path(case_name)

    dt_levels = [1.0, 0.5, 0.25] if quick else [1.0, 0.5, 0.25, 0.125]
    grid_n = 120 if quick else 400
    reference_params, reference_result = convergence_reference_result(grid_n, min(dt_levels), quick=quick)

    rows = []
    plot_data = {"P(t)": [], r"$T_{s,out}(t)$": [], r"$S_d(z,t)$": []}
    table_rows = []

    for dt_value in dt_levels:
        params, result = convergence_reference_result(grid_n, dt_value, quick=quick)
        ref_power = sample_series(reference_result["time_s"], reference_result["power_W"], result["time_s"])
        ref_tsout = sample_series(reference_result["time_s"], reference_result["Ts_out_K"], result["time_s"])
        ref_sd_history = sample_history(reference_result["time_s"], reference_result["history"]["Sd"], result["time_s"])

        specs = [
            ("P(t)", result["power_W"], ref_power),
            (r"$T_{s,out}(t)$", result["Ts_out_K"], ref_tsout),
            (r"$S_d(z,t)$", result["history"]["Sd"], ref_sd_history),
        ]
        for quantity, values, ref_values in specs:
            l2_err = l2_relative_error(values, ref_values)
            linf_err = linf_relative_error(values, ref_values)
            rows.append(
                {
                    "dt": float(params["outer_dt"]),
                    "quantity": quantity,
                    "L2_error": l2_err,
                    "Linf_error": linf_err,
                }
            )
            plot_data[quantity].append((float(params["outer_dt"]), l2_err))

    for quantity, samples in plot_data.items():
        samples = sorted(samples, key=lambda item: item[0], reverse=True)
        reported_error = samples[-2][1] if len(samples) > 1 else np.nan
        table_rows.append(
            {
                "test_type": "time-step convergence",
                "quantity": quantity,
                "refinement_variable": "dt",
                "observed_order": observed_order([item[0] for item in samples], [item[1] for item in samples]),
                "reference_level": rf"$\Delta t={min(dt_levels):.3f}$ s",
                "reported_error": reported_error,
                "fit_range": rf"$\Delta t={max(dt_levels):.3f}$ to {sorted(dt_levels)[1]:.3f} s",
                "comment": "reported error is the second-finest relative L2 error against the finest-step reference",
            }
        )

    write_csv(case_dir / "fig_V9_timestep_convergence.csv", list(rows[0].keys()), rows)
    write_csv(case_dir / "table_V8_solver_convergence.csv", list(table_rows[0].keys()), table_rows)

    fig_rows_loaded = read_csv_rows(case_dir / "fig_V9_timestep_convergence.csv")
    fig, ax = figure_axes((1, 1), (8.6, 6.8))
    if fig is not None:
        ax = np.atleast_1d(ax)[0]
        ax.tick_params(labelsize=31, pad=7)
        label_map = {
            "P(t)": "Power",
            r"$T_{s,out}(t)$": r"$T_{s,out}(t)$",
            r"$S_d(z,t)$": r"$S_d(z,t)$",
        }
        for quantity in unique_strings(fig_rows_loaded, "quantity"):
            subset = sort_rows([row for row in fig_rows_loaded if row["quantity"] == quantity], "dt")
            x_values = float_column(subset, "dt")
            y_values = float_column(subset, "L2_error")
            mask = y_values > 0.0
            ax.loglog(
                x_values[mask],
                y_values[mask],
                marker="o",
                markersize=11.5,
                markeredgewidth=1.1,
                linewidth=3.7,
                label=label_map.get(quantity, quantity),
            )
        ax.set_xlabel(r"$\Delta t$ (s)", fontsize=34, labelpad=8)
        ax.set_ylabel(r"Relative $L_2$ error", fontsize=34, labelpad=8)
        ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.27),
            ncol=2,
            frameon=False,
            fontsize=25,
            columnspacing=1.4,
        )
    maybe_save(fig, case_dir / "fig_V9_timestep_convergence")

    metadata = base_metadata(case_name, reference_params)
    metadata["generated_files"] = [
        "fig_V9_timestep_convergence.csv",
        "fig_V9_timestep_convergence.pdf",
        "fig_V9_timestep_convergence.png",
        "table_V8_solver_convergence.csv",
    ]
    write_case_metadata(case_dir, metadata)


def case_08_conservation_residuals(quick=False):
    case_name = "case_08_conservation_residuals"
    case_dir = case_path(case_name)

    params = default_params(N=80 if quick else 160, steady_state_steps=20 if quick else 60)
    params["precursor_balance_audit_enabled"] = True
    result = run_coupled_transient(
        params,
        num_steps=80 if quick else 160,
        event_sequence=transient_event_sequence(),
        record_fields=[
            "C",
            "C_start",
            "C_inlet",
            "F",
            "F_precursor_start",
            "F_precursor_end",
            "precursor_production_integral",
            "precursor_decay_integral",
            "precursor_transport_integral",
            "Ts",
            "Tgr",
            "qprime",
            "HX1_hot",
            "HX1_cold",
            "HX2_hot",
            "HX2_cold",
        ],
    )
    residuals = compute_conservation_residuals(result, params)

    fig_rows = []
    for idx, time_s in enumerate(residuals["time_s"]):
        row = {"time_s": time_s}
        for group in range(6):
            row[f"R_C{group + 1}"] = residuals["precursor_residuals"][group, idx]
            row[f"Rrel_C{group + 1}"] = residuals["precursor_relative_residuals"][group, idx]
        row["R_energy_core"] = residuals["core_energy_residual"][idx]
        row["Rrel_energy_core"] = residuals["core_energy_relative_residual"][idx]
        row["R_HX1"] = residuals["hx1_energy_residual"][idx]
        row["Rrel_HX1"] = residuals["hx1_energy_relative_residual"][idx]
        row["R_HX2"] = residuals["hx2_energy_residual"][idx]
        row["Rrel_HX2"] = residuals["hx2_energy_relative_residual"][idx]
        fig_rows.append(row)
    write_csv(case_dir / "fig_V10_balance_residuals.csv", list(fig_rows[0].keys()), fig_rows)

    table_rows = []
    names_and_values = [
        (
            f"precursor group {group + 1}",
            residuals["precursor_residuals"][group],
            residuals["precursor_relative_residuals"][group],
            "integrated precursor-rate units",
            "sum of absolute precursor balance terms",
        )
        for group in range(6)
    ]
    names_and_values.extend(
        [
            (
                "core energy",
                residuals["core_energy_residual"],
                residuals["core_energy_relative_residual"],
                "W",
                "sum of absolute core-energy balance terms",
            ),
            (
                "HX1 energy",
                residuals["hx1_energy_residual"],
                residuals["hx1_energy_relative_residual"],
                "W",
                "sum of absolute HX1 energy-balance terms",
            ),
            (
                "HX2 energy",
                residuals["hx2_energy_residual"],
                residuals["hx2_energy_relative_residual"],
                "W",
                "sum of absolute HX2 energy-balance terms",
            ),
        ]
    )
    for name, values, rel_values, unit, normalization in names_and_values:
        table_rows.append(
            {
                "balance_name": name,
                "unit": unit,
                "normalization": normalization,
                "max_abs_residual": float(np.max(np.abs(values))),
                "rms_abs_residual": float(np.sqrt(np.mean(values**2))),
                "max_rel_residual": float(np.max(rel_values)),
                "rms_rel_residual": float(np.sqrt(np.mean(rel_values**2))),
            }
        )
    write_csv(case_dir / "table_V9_conservation_residuals.csv", list(table_rows[0].keys()), table_rows)

    fig_rows_loaded = sort_rows(read_csv_rows(case_dir / "fig_V10_balance_residuals.csv"), "time_s")
    fig, axes = figure_axes((2, 1), (9.8, 7.4))
    if fig is not None:
        time_plot = float_column(fig_rows_loaded, "time_s")
        for axis in np.atleast_1d(axes):
            axis.tick_params(labelsize=20)
        for group in range(6):
            axes[0].semilogy(time_plot, float_column(fig_rows_loaded, f"Rrel_C{group + 1}"), label=rf"$R_{{C_{group + 1}}}$")
        axes[0].set_xlabel("Time (s)")
        axes[0].set_ylabel("Relative residual")
        axes[0].legend(loc="center left", bbox_to_anchor=(1.02, 0.5), ncol=1, frameon=False, fontsize=16)

        axes[1].semilogy(time_plot, float_column(fig_rows_loaded, "Rrel_energy_core"), label=r"$R_E$")
        axes[1].semilogy(time_plot, float_column(fig_rows_loaded, "Rrel_HX1"), label=r"$R_{HX1}$")
        axes[1].semilogy(time_plot, float_column(fig_rows_loaded, "Rrel_HX2"), label=r"$R_{HX2}$")
        axes[1].set_xlabel("Time (s)")
        axes[1].set_ylabel("Relative residual")
        axes[1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5), ncol=1, frameon=False, fontsize=16)
    maybe_save(fig, case_dir / "fig_V10_balance_residuals")

    metadata = base_metadata(case_name, params)
    metadata["generated_files"] = [
        "fig_V10_balance_residuals.csv",
        "fig_V10_balance_residuals.pdf",
        "fig_V10_balance_residuals.png",
        "table_V9_conservation_residuals.csv",
    ]
    write_case_metadata(case_dir, metadata)


def case_09_fpga_vs_offline(quick=False):
    case_name = "case_09_fpga_vs_offline"
    case_dir = case_path(case_name)

    num_steps = 90 if quick else 180
    params = default_params(
        N=80 if quick else 200,
        steady_state_steps=80 if quick else 240,
        precursor_loop_efficiency=1.0,
    )
    event_sequence = transient_scenarios()[0]["events"]

    offline = run_coupled_transient(
        copy.deepcopy(params),
        num_steps=num_steps,
        event_sequence=event_sequence,
        record_fields=[],
    )
    split_proxy = run_async_split_transient(
        copy.deepcopy(params),
        num_steps=num_steps,
        event_sequence=event_sequence,
        record_fields=[],
        execution_order="bop_then_core",
    )

    overlay_rows = []
    error_rows = []
    signal_specs = [
        ("power_MW", offline["power_W"] / 1.0e6, split_proxy["power_W"] / 1.0e6),
        ("rho_pcm", offline["rho_pcm"], split_proxy["rho_pcm"]),
        ("Tsout_K", offline["Ts_out_K"], split_proxy["Ts_out_K"]),
        ("Tgrmax_K", offline["Tgr_max_K"], split_proxy["Tgr_max_K"]),
        (
            "Wnet_MW",
            offline["diagnostics"]["brayton_W_net"] / 1.0e6,
            split_proxy["diagnostics"]["brayton_W_net"] / 1.0e6,
        ),
    ]
    for idx, time_s in enumerate(offline["time_s"]):
        overlay_rows.append(
            {
                "time_s": time_s,
                "power_offline_MW": offline["power_W"][idx] / 1.0e6,
                "power_split_proxy_MW": split_proxy["power_W"][idx] / 1.0e6,
                "rho_offline_pcm": offline["rho_pcm"][idx],
                "rho_split_proxy_pcm": split_proxy["rho_pcm"][idx],
                "Tsout_offline_K": offline["Ts_out_K"][idx],
                "Tsout_split_proxy_K": split_proxy["Ts_out_K"][idx],
                "Tgrmax_offline_K": offline["Tgr_max_K"][idx],
                "Tgrmax_split_proxy_K": split_proxy["Tgr_max_K"][idx],
                "Wnet_offline_MW": offline["diagnostics"]["brayton_W_net"][idx] / 1.0e6,
                "Wnet_split_proxy_MW": split_proxy["diagnostics"]["brayton_W_net"][idx] / 1.0e6,
            }
        )
        error_row = {"time_s": time_s}
        for name, ref_values, proxy_values in signal_specs:
            abs_error = abs(proxy_values[idx] - ref_values[idx])
            rel_error = abs_error / max(abs(ref_values[idx]), 1.0e-12)
            error_row[f"{name}_abs_error"] = abs_error
            error_row[f"{name}_rel_error"] = rel_error
        error_rows.append(error_row)

    write_csv(case_dir / "fig_V11_fpga_vs_offline_timeseries.csv", list(overlay_rows[0].keys()), overlay_rows)
    write_csv(case_dir / "fig_V12_fpga_error_history.csv", list(error_rows[0].keys()), error_rows)

    summary_rows = []
    for name, ref_values, proxy_values in signal_specs:
        abs_series = np.abs(np.asarray(proxy_values, dtype=float) - np.asarray(ref_values, dtype=float))
        rel_series = relative_error_series(ref_values, proxy_values)
        summary_rows.append(
            {
                "quantity": name,
                "max_abs_error": float(np.max(abs_series)),
                "rms_abs_error": float(np.sqrt(np.mean(abs_series**2))),
                "max_rel_error": float(np.max(rel_series)),
                "rms_rel_error": float(np.sqrt(np.mean(rel_series**2))),
            }
        )
    write_csv(case_dir / "table_V10_split_proxy_error_summary.csv", list(summary_rows[0].keys()), summary_rows)

    fpga_clean_snapshot_ref = {
        "rho": -2.2204460492503136e-16,
        "power_W": 99382.890710337626,
        "phi_mid": 1.433989757310741,
        "fuel_mid_K": 928.89996801008067,
        "graphite_mid_K": 934.31274746251233,
        "Ts_core_inlet_K": 904.99410268357076,
        "Ts_core_outlet_K": 938.34566033248223,
        "Ts_HX1_0_K": 904.95606970931237,
        "Tss_HX1_L_K": 896.02139450389836,
        "Tss_HX2_0_K": 816.26738534770823,
        "Tsss_HX2_L_K": 846.49970894227147,
        "Tsss_pp_0_K": 807.98010628155782,
    }
    fpga_clean_snapshot_measured = {
        "rho": -2.2204460492503136e-16,
        "power_W": 99382.89071033763,
        "phi_mid": 1.433989757310741,
        "fuel_mid_K": 928.8999680100807,
        "graphite_mid_K": 934.3127474625123,
        "Ts_core_inlet_K": 904.9941026835708,
        "Ts_core_outlet_K": 938.3456603324822,
        "Ts_HX1_0_K": 904.9560697093124,
        "Tss_HX1_L_K": 896.0213945038984,
        "Tss_HX2_0_K": 816.2673853477082,
        "Tsss_HX2_L_K": 846.4997089422715,
        "Tsss_pp_0_K": 807.9801062815578,
    }
    fpga_clean_units = {
        "rho": "-",
        "power_W": "W",
        "phi_mid": "-",
        "fuel_mid_K": "K",
        "graphite_mid_K": "K",
        "Ts_core_inlet_K": "K",
        "Ts_core_outlet_K": "K",
        "Ts_HX1_0_K": "K",
        "Tss_HX1_L_K": "K",
        "Tss_HX2_0_K": "K",
        "Tsss_HX2_L_K": "K",
        "Tsss_pp_0_K": "K",
    }
    fpga_clean_labels = {
        "rho": r"$\rho$",
        "power_W": r"$P$",
        "phi_mid": r"$\phi_\mathrm{mid}$",
        "fuel_mid_K": r"$T_{s,\mathrm{mid}}$",
        "graphite_mid_K": r"$T_{\mathrm{gr},\mathrm{mid}}$",
        "Ts_core_inlet_K": r"$T_{s,\mathrm{in}}$",
        "Ts_core_outlet_K": r"$T_{s,\mathrm{out}}$",
        "Ts_HX1_0_K": r"$T_{s,\mathrm{HX1},0}$",
        "Tss_HX1_L_K": r"$T_{ss,\mathrm{HX1},L}$",
        "Tss_HX2_0_K": r"$T_{ss,\mathrm{HX2},0}$",
        "Tsss_HX2_L_K": r"$T_{sss,\mathrm{HX2},L}$",
        "Tsss_pp_0_K": r"$T_{sss,\mathrm{pp},0}$",
    }
    fpga_clean_rows = []
    for key, ref_value in fpga_clean_snapshot_ref.items():
        measured_value = fpga_clean_snapshot_measured[key]
        abs_error = abs(measured_value - ref_value)
        rel_error = abs_error / max(abs(ref_value), 1.0e-30)
        fpga_clean_rows.append(
            {
                "quantity": fpga_clean_labels[key],
                "symbol_key": key,
                "unit": fpga_clean_units[key],
                "offline_reference": ref_value,
                "fpga_clean_readback": measured_value,
                "abs_error": abs_error,
                "rel_error": rel_error,
            }
        )
    write_csv(case_dir / "table_V10_fpga_clean_snapshot.csv", list(fpga_clean_rows[0].keys()), fpga_clean_rows)
    (case_dir / "fpga_clean_snapshot_provenance.json").write_text(
        json.dumps(
            {
                "source": "VCU118 clean-source bitstream JTAG-AXI snapshot validation",
                "bitstream_name": "msr_split_vcu118.bit",
                "kernel_configuration": "n200_s1",
                "board_interface": "Vivado Hardware Manager + jtag_axi",
                "software_reference": "msr_vcu118_sw_smoke_n200.exe compiled with the same n200 HLS macros",
                "reference_compile_macros": {
                    "MSR_MAX_STATE_N": 200,
                    "MSR_FIXED_CORE_N": 200,
                    "MSR_FIXED_BOP_NX": 200,
                    "MSR_FIXED_HARDWARE_SUBSTEPS": 1,
                    "MSR_CROSS_SECTION_LANE_FACTOR": 2,
                    "MSR_NEUTRONICS_LANE_FACTOR": 2,
                    "MSR_THERMAL_LANE_FACTOR": 2,
                    "MSR_HEAT_EXCHANGER_LANE_FACTOR": 2,
                },
                "snapshot_kind": "single outer-step steady-state snapshot",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    split_validation_rows = []
    short_steps = min(24, num_steps)
    ref_short = run_coupled_transient(copy.deepcopy(params), num_steps=short_steps, event_sequence=[], record_fields=[])
    core_then_bop = run_async_split_transient(
        copy.deepcopy(params),
        num_steps=short_steps,
        event_sequence=[],
        record_fields=[],
        execution_order="core_then_bop",
    )
    bop_then_core = run_async_split_transient(
        copy.deepcopy(params),
        num_steps=short_steps,
        event_sequence=[],
        record_fields=[],
        execution_order="bop_then_core",
    )
    for idx, time_s in enumerate(ref_short["time_s"]):
        split_validation_rows.append(
            {
                "time_s": time_s,
                "power_ref_MW": ref_short["power_W"][idx] / 1.0e6,
                "power_core_then_bop_MW": core_then_bop["power_W"][idx] / 1.0e6,
                "power_bop_then_core_MW": bop_then_core["power_W"][idx] / 1.0e6,
                "Tsout_ref_K": ref_short["Ts_out_K"][idx],
                "Tsout_core_then_bop_K": core_then_bop["Ts_out_K"][idx],
                "Tsout_bop_then_core_K": bop_then_core["Ts_out_K"][idx],
                "rho_ref_pcm": ref_short["rho_pcm"][idx],
                "rho_core_then_bop_pcm": core_then_bop["rho_pcm"][idx],
                "rho_bop_then_core_pcm": bop_then_core["rho_pcm"][idx],
                "Tsout_core_then_bop_abs_error": abs(core_then_bop["Ts_out_K"][idx] - ref_short["Ts_out_K"][idx]),
                "Tsout_bop_then_core_abs_error": abs(bop_then_core["Ts_out_K"][idx] - ref_short["Ts_out_K"][idx]),
            }
        )
    write_csv(case_dir / "fig_split_reference_validation.csv", list(split_validation_rows[0].keys()), split_validation_rows)

    overlay_loaded = sort_rows(read_csv_rows(case_dir / "fig_V11_fpga_vs_offline_timeseries.csv"), "time_s")
    fig, axes = figure_axes((3, 2), (12.0, 9.0))
    if fig is not None:
        time_plot = float_column(overlay_loaded, "time_s")
        series = [
            ("power_offline_MW", "power_split_proxy_MW", "Power (MW)"),
            ("rho_offline_pcm", "rho_split_proxy_pcm", r"$\rho$ (pcm)"),
            ("Tsout_offline_K", "Tsout_split_proxy_K", r"$T_{s,out}$ (K)"),
            ("Tgrmax_offline_K", "Tgrmax_split_proxy_K", r"$T_{gr,\max}$ (K)"),
            ("Wnet_offline_MW", "Wnet_split_proxy_MW", r"$W_{net}$ (MW)"),
        ]
        flat_axes = axes.flat
        for axis, (lhs_key, rhs_key, ylabel) in zip(flat_axes, series):
            axis.plot(time_plot, float_column(overlay_loaded, lhs_key), label="Offline FP64", linewidth=2.0)
            axis.plot(time_plot, float_column(overlay_loaded, rhs_key), "--", label="Split proxy", linewidth=1.8)
            axis.set_xlabel("Time (s)")
            axis.set_ylabel(ylabel)
        flat_axes[0].legend(loc="best", frameon=False)
        flat_axes[-1].axis("off")
    maybe_save(fig, case_dir / "fig_V11_fpga_vs_offline_timeseries")

    error_loaded = sort_rows(read_csv_rows(case_dir / "fig_V12_fpga_error_history.csv"), "time_s")
    fig, axes = figure_axes((3, 2), (12.0, 9.0))
    if fig is not None:
        time_plot = float_column(error_loaded, "time_s")
        series = [
            ("power_MW_abs_error", "power_MW_rel_error", "Power"),
            ("rho_pcm_abs_error", "rho_pcm_rel_error", r"$\rho$"),
            ("Tsout_K_abs_error", "Tsout_K_rel_error", r"$T_{s,out}$"),
            ("Tgrmax_K_abs_error", "Tgrmax_K_rel_error", r"$T_{gr,\max}$"),
            ("Wnet_MW_abs_error", "Wnet_MW_rel_error", r"$W_{net}$"),
        ]
        flat_axes = axes.flat
        for axis, (abs_key, rel_key, label) in zip(flat_axes, series):
            axis.plot(time_plot, float_column(error_loaded, abs_key), label="Absolute error", linewidth=2.0)
            rel_axis = axis.twinx()
            rel_axis.plot(time_plot, float_column(error_loaded, rel_key), "--", color="#d62728", label="Relative error")
            axis.set_xlabel("Time (s)")
            axis.set_ylabel(f"{label} abs.")
            rel_axis.set_ylabel("Rel.")
        flat_axes[0].legend(loc="upper left", frameon=False)
        flat_axes[-1].axis("off")
    maybe_save(fig, case_dir / "fig_V12_fpga_error_history")

    validation_loaded = sort_rows(read_csv_rows(case_dir / "fig_split_reference_validation.csv"), "time_s")
    fig, axes = figure_axes((2, 2), (10.4, 7.4))
    if fig is not None:
        time_plot = float_column(validation_loaded, "time_s")
        axes[0, 0].plot(time_plot, float_column(validation_loaded, "power_ref_MW"), label="Reference")
        axes[0, 0].plot(time_plot, float_column(validation_loaded, "power_core_then_bop_MW"), "--", label="core_then_bop")
        axes[0, 0].plot(time_plot, float_column(validation_loaded, "power_bop_then_core_MW"), ":", label="bop_then_core")
        axes[0, 0].set_xlabel("Time (s)")
        axes[0, 0].set_ylabel("Power (MW)")

        axes[0, 1].plot(time_plot, float_column(validation_loaded, "Tsout_ref_K"), label="Reference")
        axes[0, 1].plot(time_plot, float_column(validation_loaded, "Tsout_core_then_bop_K"), "--", label="core_then_bop")
        axes[0, 1].plot(time_plot, float_column(validation_loaded, "Tsout_bop_then_core_K"), ":", label="bop_then_core")
        axes[0, 1].set_xlabel("Time (s)")
        axes[0, 1].set_ylabel(r"$T_{s,out}$ (K)")

        axes[1, 0].plot(time_plot, float_column(validation_loaded, "rho_ref_pcm"), label="Reference")
        axes[1, 0].plot(time_plot, float_column(validation_loaded, "rho_core_then_bop_pcm"), "--", label="core_then_bop")
        axes[1, 0].plot(time_plot, float_column(validation_loaded, "rho_bop_then_core_pcm"), ":", label="bop_then_core")
        axes[1, 0].set_xlabel("Time (s)")
        axes[1, 0].set_ylabel(r"$\rho$ (pcm)")

        axes[1, 1].plot(time_plot, float_column(validation_loaded, "Tsout_core_then_bop_abs_error"), "--", label="core_then_bop")
        axes[1, 1].plot(time_plot, float_column(validation_loaded, "Tsout_bop_then_core_abs_error"), ":", label="bop_then_core")
        axes[1, 1].set_xlabel("Time (s)")
        axes[1, 1].set_ylabel(r"$| \Delta T_{s,out} |$ (K)")

        handles, labels = axes[0, 0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.02), ncol=3, frameon=False)
    maybe_save(fig, case_dir / "fig_split_reference_validation")

    metadata = base_metadata(case_name, params)
    metadata["execution_order"] = "bop_then_core"
    metadata["generated_files"] = [
        "fig_V11_fpga_vs_offline_timeseries.csv",
        "fig_V11_fpga_vs_offline_timeseries.pdf",
        "fig_V11_fpga_vs_offline_timeseries.png",
        "fig_V12_fpga_error_history.csv",
        "fig_V12_fpga_error_history.pdf",
        "fig_V12_fpga_error_history.png",
        "fig_split_reference_validation.csv",
        "fig_split_reference_validation.pdf",
        "fig_split_reference_validation.png",
        "table_V10_split_proxy_error_summary.csv",
        "table_V10_fpga_clean_snapshot.csv",
        "fpga_clean_snapshot_provenance.json",
    ]
    write_case_metadata(case_dir, metadata)


def case_12_hardware_performance(quick=False):
    case_name = "case_12_hardware_performance"
    case_dir = case_path(case_name)

    params = default_params(
        N=80 if quick else 200,
        steady_state_steps=80 if quick else 240,
        precursor_loop_efficiency=1.0,
    )
    event_sequence = transient_scenarios()[0]["events"]
    aggressive = AGGRESSIVE_ONE_STEP_METRICS

    simulated_time_s = 1.0
    python_wall_s = aggressive["total"]["python_us"] / 1.0e6
    cpu_cpp_wall_s = aggressive["total"]["cpu_cpp_us"] / 1.0e6
    kernel_only_wall_s = aggressive["total"]["fpga_hls_max_us"] / 1.0e6
    measured_wait_wall_s = aggressive["total"]["fpga_wait_us"] / 1.0e6
    cpu_speedup_vs_python = python_wall_s / max(cpu_cpp_wall_s, 1.0e-12)
    kernel_speedup_vs_python = python_wall_s / max(kernel_only_wall_s, 1.0e-12)
    board_speedup_vs_python = python_wall_s / max(measured_wait_wall_s, 1.0e-12)
    kernel_vs_cpu_pct = 100.0 * cpu_cpp_wall_s / max(kernel_only_wall_s, 1.0e-12)
    board_vs_cpu_pct = 100.0 * cpu_cpp_wall_s / max(measured_wait_wall_s, 1.0e-12)

    table_r4_rows = [
        {
            "timing_path": "Python monolithic one-step",
            "basis": "FP64 run_coupled_transient",
            "Nz": int(params["N"]),
            "end_to_end_step_s": python_wall_s,
            "kernel_only_latency_s": "",
            "FTRT_ratio": simulated_time_s / max(python_wall_s, 1.0e-12),
            "python_speedup_x": 1.0,
            "throughput_vs_cpu_cpp_pct": 100.0 * cpu_cpp_wall_s / max(python_wall_s, 1.0e-12),
            "note": "One-step Python reference on the Nz=200 hardware snapshot",
        },
        {
            "timing_path": "CPU C++ split reference",
            "basis": "same-source n200_s1 core+bop",
            "Nz": 200,
            "end_to_end_step_s": cpu_cpp_wall_s,
            "kernel_only_latency_s": "",
            "FTRT_ratio": simulated_time_s / max(cpu_cpp_wall_s, 1.0e-12),
            "python_speedup_x": cpu_speedup_vs_python,
            "throughput_vs_cpu_cpp_pct": 100.0,
            "note": "Optimized C++ split-kernel runner; core 10.781275 us plus BOP 2.266460 us",
        },
        {
            "timing_path": "Implemented JTAG-AXI split-kernel path",
            "basis": "host-controlled board wait",
            "Nz": 200,
            "end_to_end_step_s": measured_wait_wall_s,
            "kernel_only_latency_s": "",
            "FTRT_ratio": simulated_time_s / max(measured_wait_wall_s, 1.0e-12),
            "python_speedup_x": board_speedup_vs_python,
            "throughput_vs_cpu_cpp_pct": board_vs_cpu_pct,
            "note": "Measured JTAG-AXI host launch/wait/readback path; 13.047735 us / 3043.0 us = 0.428779%",
        },
        {
            "timing_path": "FPGA sequential kernel schedule",
            "basis": "HLS-only core+bop latency",
            "Nz": 200,
            "end_to_end_step_s": "",
            "kernel_only_latency_s": kernel_only_wall_s,
            "FTRT_ratio": simulated_time_s / max(kernel_only_wall_s, 1.0e-12),
            "python_speedup_x": kernel_speedup_vs_python,
            "throughput_vs_cpu_cpp_pct": kernel_vs_cpu_pct,
            "note": "Kernel-only worst-case sequential sum: core 275.66 us plus BOP 46.68 us; excludes host control",
        },
    ]
    write_csv(case_dir / "table_R4_hardware_performance.csv", list(table_r4_rows[0].keys()), table_r4_rows)

    table_r4a_rows = [
        {
            "kernel": "core",
            "latency_mode": "hls_at_20ns",
            "latency_min_us": aggressive["core"]["fpga_hls_min_us"],
            "latency_max_us": aggressive["core"]["fpga_hls_max_us"],
            "single_value_us": aggressive["core"]["fpga_hls_max_us"],
            "note": "Core kernel range converted at 20 ns deployed board clock; max is used when a single value is required",
        },
        {
            "kernel": "bop",
            "latency_mode": "hls_at_20ns",
            "latency_min_us": aggressive["bop"]["fpga_hls_min_us"],
            "latency_max_us": aggressive["bop"]["fpga_hls_max_us"],
            "single_value_us": aggressive["bop"]["fpga_hls_max_us"],
            "note": "BOP kernel latency converted at 20 ns deployed board clock",
        },
        {
            "kernel": "core_plus_bop",
            "latency_mode": "hls_at_20ns_sequential_sum",
            "latency_min_us": aggressive["total"]["fpga_hls_min_us"],
            "latency_max_us": aggressive["total"]["fpga_hls_max_us"],
            "single_value_us": aggressive["total"]["fpga_hls_max_us"],
            "note": "Sequential kernel-only sum; not an end-to-end board or dual-FPGA runtime",
        },
        {
            "kernel": "core_plus_bop",
            "latency_mode": "current_board_wait",
            "latency_min_us": aggressive["total"]["fpga_wait_us"],
            "latency_max_us": aggressive["total"]["fpga_wait_us"],
            "single_value_us": aggressive["total"]["fpga_wait_us"],
            "note": "Measured sequential JTAG-AXI host launch/wait path",
        },
    ]
    write_csv(case_dir / "table_R4a_kernel_speedup_breakdown.csv", list(table_r4a_rows[0].keys()), table_r4a_rows)

    table_r5_rows = []
    for resource_key, avail_key in (
        ("BRAM_18K", "avail_bram"),
        ("DSP", "avail_dsp"),
        ("FF", "avail_ff"),
        ("LUT", "avail_lut"),
    ):
        if resource_key == "BRAM_18K":
            core_used = aggressive["core"]["bram"]
            bop_used = aggressive["bop"]["bram"]
        elif resource_key == "DSP":
            core_used = aggressive["core"]["dsp"]
            bop_used = aggressive["bop"]["dsp"]
        elif resource_key == "FF":
            core_used = aggressive["core"]["ff"]
            bop_used = aggressive["bop"]["ff"]
        else:
            core_used = aggressive["core"]["lut"]
            bop_used = aggressive["bop"]["lut"]
        table_r5_rows.append(
            {
                "resource": resource_key,
                "core_n200_s1_used": core_used,
                "core_utilization_pct": 100.0 * core_used / max(aggressive["device"][avail_key], 1.0),
                "bop_n200_s1_used": bop_used,
                "bop_utilization_pct": 100.0 * bop_used / max(aggressive["device"][avail_key], 1.0),
                "co_resident_sum_used": core_used + bop_used,
                "co_resident_sum_pct": 100.0 * (core_used + bop_used) / max(aggressive["device"][avail_key], 1.0),
                "co_resident_fits_vcu118": "yes" if (core_used + bop_used) <= aggressive["device"][avail_key] else "no",
                "device_available": aggressive["device"][avail_key],
            }
        )
    write_csv(case_dir / "table_R5_resource_utilization.csv", list(table_r5_rows[0].keys()), table_r5_rows)

    fig_rows = []
    for row in table_r4_rows:
        annotation = ""
        if row["timing_path"] == "Python monolithic one-step":
            annotation = "Python ref"
        elif row["timing_path"] == "CPU C++ split reference":
            annotation = f"CPU C++\n{row['FTRT_ratio']:.3g}x FTRT\n100% vs C++"
        elif row["timing_path"] == "FPGA sequential kernel schedule":
            annotation = f"kernel-only\n{row['FTRT_ratio']:.3g}x FTRT\n{float(row['throughput_vs_cpu_cpp_pct']):.2f}% vs C++"
        elif row["timing_path"] == "Implemented JTAG-AXI split-kernel path":
            annotation = f"JTAG board\n{row['FTRT_ratio']:.3g}x FTRT\n{float(row['throughput_vs_cpu_cpp_pct']):.3f}% vs C++"
        wall_time_s = row["end_to_end_step_s"] if row["end_to_end_step_s"] != "" else row["kernel_only_latency_s"]
        fig_rows.append(
            {
                "timing_path": row["timing_path"],
                "wall_time_s": wall_time_s,
                "FTRT_ratio": row["FTRT_ratio"],
                "python_speedup_x": row["python_speedup_x"],
                "throughput_vs_cpu_cpp_pct": row["throughput_vs_cpu_cpp_pct"],
                "annotation": annotation,
            }
        )
    write_csv(case_dir / "fig_R5_ftrt_latency_speedup.csv", list(fig_rows[0].keys()), fig_rows)

    fig_loaded = read_csv_rows(case_dir / "fig_R5_ftrt_latency_speedup.csv")
    fig, axes = figure_axes((1, 2), (9.8, 5.2))
    if fig is not None:
        labels = ["Python step", "CPU C++ split", "HLS kernel", "JTAG board"]
        x = np.arange(len(labels))
        wall = 1.0e3 * np.asarray(float_column(fig_loaded, "wall_time_s"), dtype=float)
        ftrt = np.asarray(float_column(fig_loaded, "FTRT_ratio"), dtype=float)
        colors = ["#4c78a8", "#f58518", "#54a24b", "#e45756"]
        axes[0].bar(x, wall, color=colors)
        axes[0].set_xticks(x)
        axes[0].set_xticklabels(labels, rotation=28, ha="right")
        axes[0].set_ylabel("Wall time (ms, log)")
        axes[0].set_yscale("log")
        axes[0].tick_params(axis="both", labelsize=20, pad=5)
        axes[0].yaxis.label.set_size(22)
        axes[0].yaxis.label.set_weight("semibold")

        axes[1].bar(x, ftrt, color=colors)
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(labels, rotation=28, ha="right")
        axes[1].set_ylabel("FTRT ratio (log)")
        axes[1].set_yscale("log")
        axes[1].tick_params(axis="both", labelsize=20, pad=5)
        axes[1].yaxis.label.set_size(22)
        axes[1].yaxis.label.set_weight("semibold")
        for axis in axes:
            for tick_label in axis.get_xticklabels() + axis.get_yticklabels():
                tick_label.set_fontweight("semibold")
            for tick_label in axis.get_xticklabels():
                tick_label.set_fontsize(17)
        axes[1].set_ylim(bottom=max(min(ftrt) * 0.45, 1.0), top=max(ftrt) * 5.0)
        for idx, row in enumerate(fig_loaded):
            annotation = row.get("annotation", "")
            if not annotation or str(annotation).lower() == "nan":
                continue
            axes[1].text(
                idx,
                ftrt[idx] * 1.12,
                annotation,
                ha="center",
                va="bottom",
                fontsize=14,
                fontweight="semibold",
            )
        fig.set_constrained_layout_pads(w_pad=0.10, h_pad=0.08, wspace=0.16, hspace=0.02)
    maybe_save(fig, case_dir / "fig_R5_ftrt_latency_speedup")

    metadata = base_metadata(case_name, params, event_sequence_file="case_09 mild absorption insertion")
    metadata["runtime_repeats"] = "fixed one-step timing dataset"
    metadata["generated_files"] = [
        "fig_R5_ftrt_latency_speedup.csv",
        "fig_R5_ftrt_latency_speedup.pdf",
        "fig_R5_ftrt_latency_speedup.png",
        "table_R4_hardware_performance.csv",
        "table_R4a_kernel_speedup_breakdown.csv",
        "table_R5_resource_utilization.csv",
    ]
    write_case_metadata(case_dir, metadata)


def transient_case_params(quick=False, precursor_mode="recirculation"):
    params = default_params(
        N=100 if quick else 160,
        steady_state_steps=80 if quick else 240,
        precursor_loop_efficiency=1.0,
    )
    if precursor_mode == "stationary":
        params["u_precursor"] = 0.0
        params["inlet_mode"] = "fresh"
    elif precursor_mode == "advection_only":
        params["u_precursor"] = float(params["u_core"])
        params["inlet_mode"] = "fresh"
    else:
        params["u_precursor"] = float(params["u_core"])
        params["inlet_mode"] = "recirculate"
    return params


def transient_case_result(quick=False, precursor_mode="recirculation", record_fields=None, event_sequence=None):
    params = transient_case_params(quick=quick, precursor_mode=precursor_mode)
    result = run_coupled_transient(
        params,
        num_steps=90 if quick else 180,
        event_sequence=transient_event_sequence() if event_sequence is None else event_sequence,
        record_fields=record_fields or [],
    )
    return params, result


def _sync_corrected_case_10_outputs(case_dir):
    from paper_reactivity_sweep import (
        CASE_DEFINITIONS as corrected_case_definitions,
        INSERTION_TIME_S as corrected_insertion_time_s,
        OUTPUT_DIR as corrected_output_dir,
        TIME_SPAN as corrected_time_span_s,
        main as generate_corrected_case_10_outputs,
    )

    alias_map = [
        ("figure_data_reactivity_step_histories.csv", "fig_R1_transient_core_response.csv"),
        ("figure_14_prompt_response_main.pdf", "fig_R1_transient_core_response.pdf"),
        ("figure_14_prompt_response_main.png", "fig_R1_transient_core_response.png"),
        ("figure_15_early_window_sensitivity.pdf", "fig_R1_early_window_sensitivity.pdf"),
        ("figure_15_early_window_sensitivity.png", "fig_R1_early_window_sensitivity.png"),
        ("figure_16_m075_first_sample_convergence.pdf", "fig_R1_first_sample_convergence.pdf"),
        ("figure_16_m075_first_sample_convergence.png", "fig_R1_first_sample_convergence.png"),
        ("table_13_reactivity_step_metrics.csv", "table_R2_prompt_metrics.csv"),
        (
            "table_14_m075_first_sample_timestep_convergence.csv",
            "table_R2b_m075_first_sample_timestep_convergence.csv",
        ),
        ("figure_data_reactivity_step_histories.csv", "figure_data_reactivity_step_histories.csv"),
    ]
    legacy_outputs = [
        "fig_R1_baseline_differences.csv",
        "fig_R1_baseline_differences.pdf",
        "fig_R1_baseline_differences.png",
        "fig_R2_spatial_snapshots.csv",
        "fig_R2_spatial_snapshots.pdf",
        "fig_R2_spatial_snapshots.png",
        "fig_R3_HX_Brayton_response.csv",
        "fig_R3_HX_Brayton_response.pdf",
        "fig_R3_HX_Brayton_response.png",
        "fig_R4_flowing_fuel_impact.csv",
        "fig_R4_flowing_fuel_impact.pdf",
        "fig_R4_flowing_fuel_impact.png",
        "table_R2_transient_metrics.csv",
        "table_R3_flowing_fuel_impact_metrics.csv",
    ]
    required_files = [corrected_output_dir / source_name for source_name, _ in alias_map]
    if not all(path.exists() for path in required_files):
        generate_corrected_case_10_outputs()

    missing_after_regen = [str(path) for path in required_files if not path.exists()]
    if missing_after_regen:
        raise FileNotFoundError(
            "Corrected Section 7 outputs are missing after regeneration: "
            + ", ".join(missing_after_regen)
        )

    for legacy_name in legacy_outputs:
        legacy_path = Path(case_dir) / legacy_name
        if legacy_path.exists():
            legacy_path.unlink()

    for source_name, target_name in alias_map:
        shutil.copy2(corrected_output_dir / source_name, Path(case_dir) / target_name)

    event_rows = []
    for case_def in corrected_case_definitions:
        if float(case_def["pcm"]) == 0.0:
            continue
        event_rows.append(
            {
                "scenario_id": case_def["id"],
                "scenario_label": case_def["label"],
                "event_id": f"reactivity_step_{case_def['id']}",
                "start_time_s": float(corrected_insertion_time_s),
                "end_time_s": float(corrected_time_span_s),
                "event_type": "equivalent_absorption",
                "magnitude": float(case_def["pcm"]),
                "unit": "pcm",
                "target_module": "neutronics",
                "purpose": "corrected 600 s reactivity-step family used for the manuscript Section 7 figures",
            }
        )
    write_event_sequence_csv(case_dir, event_rows)

    params = default_params(N=160, steady_state_steps=240, precursor_loop_efficiency=1.0)
    metadata = base_metadata("case_10_transient_application", params, event_sequence_file="table_R1_transient_event_sequence.csv")
    metadata.update(
        {
            "source_case_directory": str(corrected_output_dir),
            "section7_case_family": "corrected_600s_reactivity_step",
            "insertion_time_s": float(corrected_insertion_time_s),
            "time_span_s": float(corrected_time_span_s),
            "generated_files": [
                "table_R1_transient_event_sequence.csv",
                "table_R2_prompt_metrics.csv",
                "fig_R1_transient_core_response.csv",
                "fig_R1_transient_core_response.pdf",
                "fig_R1_transient_core_response.png",
                "fig_R1_early_window_sensitivity.pdf",
                "fig_R1_early_window_sensitivity.png",
                "fig_R1_first_sample_convergence.pdf",
                "fig_R1_first_sample_convergence.png",
                "table_R2b_m075_first_sample_timestep_convergence.csv",
                "figure_data_reactivity_step_histories.csv",
            ],
            "deprecated_outputs_removed": [
                "legacy short-time spatial, HX/Brayton, and flowing-fuel comparison plots are intentionally not generated here",
            ],
        }
    )
    write_case_metadata(case_dir, metadata)


def case_10_transient_application(quick=False):
    case_name = "case_10_transient_application"
    case_dir = case_path(case_name)
    _sync_corrected_case_10_outputs(case_dir)


CASE_FUNCTIONS = {
    "case_00_steady_state_reference": case_00_steady_state_reference,
    "case_01_dnp_plugflow_analytical": case_01_dnp_plugflow_analytical,
    "case_02_dnp_stationary_vs_flowing": case_02_dnp_stationary_vs_flowing,
    "case_03_uniform_temperature_feedback": case_03_uniform_temperature_feedback,
    "case_04_local_temperature_worth": case_04_local_temperature_worth,
    "case_05_rod_worth_verification": case_05_rod_worth_verification,
    "case_06_grid_convergence": case_06_grid_convergence,
    "case_07_timestep_convergence": case_07_timestep_convergence,
    "case_08_conservation_residuals": case_08_conservation_residuals,
    "case_09_fpga_vs_offline": case_09_fpga_vs_offline,
    "case_10_transient_application": case_10_transient_application,
    "case_12_hardware_performance": case_12_hardware_performance,
}


def run_selected_cases(case_names, quick=False):
    ensure_dir(OUTPUT_ROOT)
    for case_name in case_names:
        if case_name in SKIPPED_CASES:
            record_skipped_case(case_name, SKIPPED_CASES[case_name])
            continue
        CASE_FUNCTIONS[case_name](quick=quick)


def available_cases():
    return list(CASE_FUNCTIONS.keys()) + list(SKIPPED_CASES.keys())


def main():
    parser = argparse.ArgumentParser(description="Generate paper-ready CSV and figure exports.")
    parser.add_argument("cases", nargs="*", choices=available_cases(), help="Case names to run.")
    parser.add_argument("--all", action="store_true", help="Run all implemented cases and record skipped hardware cases.")
    parser.add_argument("--quick", action="store_true", help="Run reduced-size smoke-test versions of the cases.")
    args = parser.parse_args()

    if args.all:
        selected = available_cases()
    elif args.cases:
        selected = args.cases
    else:
        selected = [
            "case_00_steady_state_reference",
            "case_01_dnp_plugflow_analytical",
            "case_02_dnp_stationary_vs_flowing",
            "case_03_uniform_temperature_feedback",
            "case_10_transient_application",
        ]

    run_selected_cases(selected, quick=args.quick)


if __name__ == "__main__":
    main()
