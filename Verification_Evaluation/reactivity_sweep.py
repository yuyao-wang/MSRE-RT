#!/usr/bin/env python3

import copy
from pathlib import Path

import numpy as np

import path_setup  # noqa: F401
from main import run_simulation
from parameters import generate_parameters
from verification_utils import apply_publication_style, ensure_dir, save_figure, write_csv, write_json, plt


OUTPUT_DIR = Path("Verification_Evaluation/outputs/case_10_transient_application_corrected")
INSERTION_TIME_S = 300.0
END_TIME_S = 600.0
TIME_SPAN = END_TIME_S
MAIN_ZOOM_START_S = 299.5
MAIN_ZOOM_END_S = 301.0
APPENDIX_WINDOW_START_S = 299.5
APPENDIX_WINDOW_END_S = 320.0
CONVERGENCE_END_TIME_S = 301.0
BASELINE_DT_S = 0.25
CONVERGENCE_DTS = [0.5, 0.25, 0.125, 0.0625]

CASE_DEFINITIONS = [
    {"id": "zero", "label": "0 pcm", "pcm": 0.0, "index": 100},
    {"id": "m075", "label": "-75 pcm", "pcm": -75.0, "index": 101},
    {"id": "m600", "label": "-600 pcm", "pcm": -600.0, "index": 102},
    {"id": "m2400", "label": "-2400 pcm", "pcm": -2400.0, "index": 103},
]

CASE_COLORS = {
    "zero": "#4d4d4d",
    "m075": "#1f77b4",
    "m600": "#ff7f0e",
    "m2400": "#d62728",
}

DT_COLORS = {
    0.5: "#1f77b4",
    0.25: "#2ca02c",
    0.125: "#d62728",
    0.0625: "#9467bd",
}


def make_case_params(insertion_pcm, outer_dt=BASELINE_DT_S, end_time_s=END_TIME_S):
    params = generate_parameters(N=160, steady_state_steps=240, outer_dt=outer_dt)
    params["steady_state_steps"] = 240
    params["steady_state_outer_iterations"] = 12
    params["steady_state_tolerance"] = 2.0e-4
    params["feedback_reactivity_mode"] = "linear_coefficients"
    params["point_kinetics_correction_mode"] = "absolute"
    params["time_span"] = int(round(float(end_time_s) / outer_dt))
    params["selected_step"] = params["time_span"] - 1
    params["verbose"] = False
    params["log_every"] = 100
    if insertion_pcm == 0.0:
        params["reactivity_schedule_pcm"] = [(0.0, 0.0)]
    else:
        params["reactivity_schedule_pcm"] = [(0.0, 0.0), (INSERTION_TIME_S, float(insertion_pcm))]
    return params


def run_case(case_def, outer_dt=BASELINE_DT_S, sim_index=None, end_time_s=END_TIME_S):
    params = make_case_params(case_def["pcm"], outer_dt=outer_dt, end_time_s=end_time_s)
    result = run_simulation(copy.deepcopy(params), sim_index if sim_index is not None else case_def["index"])
    diagnostics = result["system_diagnostics"]
    return {
        "case": case_def,
        "params": params,
        "result": result,
        "time_s": np.asarray(diagnostics["time"], dtype=float),
        "power_W": np.asarray(diagnostics["core_power"], dtype=float),
        "ts_out_K": np.asarray(diagnostics["core_outlet"], dtype=float),
        "effective_beta": np.asarray(diagnostics["effective_beta"], dtype=float),
        "effective_beta_groups": np.vstack([
            np.asarray(diagnostics[f"effective_beta_group_{group_idx}"], dtype=float)
            for group_idx in range(1, 7)
        ]),
        "inserted_rho_pcm": np.asarray(diagnostics["reactivity_inserted_pcm"], dtype=float),
        "feedback_rho_pcm": np.asarray(diagnostics["feedback_reactivity_pcm"], dtype=float),
        "feedback_fuel_delta_K": np.asarray(diagnostics["feedback_fuel_delta_K"], dtype=float),
        "feedback_graphite_delta_K": np.asarray(diagnostics["feedback_graphite_delta_K"], dtype=float),
    }


def baseline_index(time_s):
    indices = np.where(time_s < INSERTION_TIME_S)[0]
    if indices.size == 0:
        raise ValueError("No baseline samples exist before insertion time.")
    return int(indices[-1])


def first_inserted_index(time_s):
    indices = np.where(time_s >= INSERTION_TIME_S)[0]
    if indices.size == 0:
        raise ValueError("No samples exist at or after insertion time.")
    return int(indices[0])


def window_mask(time_s, duration_s):
    return (time_s >= INSERTION_TIME_S) & (time_s <= INSERTION_TIME_S + duration_s)


def nearest_index(time_s, target_time_s):
    return int(np.argmin(np.abs(np.asarray(time_s, dtype=float) - float(target_time_s))))


def compute_prompt_metrics(case_result):
    time_s = case_result["time_s"]
    power_W = case_result["power_W"]
    beta_eff = case_result["effective_beta"]
    rho_pcm = float(case_result["case"]["pcm"])

    idx_pre = baseline_index(time_s)
    idx_post = first_inserted_index(time_s)
    power_pre = max(float(power_W[idx_pre]), 1.0e-12)
    beta_pre = float(beta_eff[idx_pre])
    rho_abs = abs(rho_pcm) * 1.0e-5
    prompt_jump_estimate = beta_pre / max(beta_pre + rho_abs, 1.0e-12)

    first_sample_ratio = float(power_W[idx_post] / power_pre)
    signed_rel_diff_pct = 100.0 * (
        first_sample_ratio - prompt_jump_estimate
    ) / max(abs(prompt_jump_estimate), 1.0e-12)

    return {
        "case": case_result["case"]["label"],
        "insertion_pcm": rho_pcm,
        "outer_dt_s": float(case_result["params"]["outer_dt"]),
        "beta_eff_pre": beta_pre,
        "prompt_jump_est_P_over_P0": prompt_jump_estimate,
        "first_sample_time_s": float(time_s[idx_post]),
        "first_sample_P_over_P0": first_sample_ratio,
        "first_sample_drop_pct": float(100.0 * (1.0 - first_sample_ratio)),
        "first_sample_vs_prompt_est_rel_diff_pct": signed_rel_diff_pct,
        "first_sample_vs_prompt_est_abs_rel_diff_pct": abs(signed_rel_diff_pct),
    }


def compute_convergence_metrics(case_result):
    time_s = case_result["time_s"]
    power_W = case_result["power_W"]
    beta_eff = case_result["effective_beta"]
    rho_pcm = float(case_result["case"]["pcm"])
    idx_pre = baseline_index(time_s)
    idx_post = first_inserted_index(time_s)
    power_pre = max(float(power_W[idx_pre]), 1.0e-12)
    ratio = power_W / power_pre
    beta_pre = float(beta_eff[idx_pre])
    rho_abs = abs(rho_pcm) * 1.0e-5
    prompt_jump_estimate = beta_pre / max(beta_pre + rho_abs, 1.0e-12)
    first_sample_ratio = float(ratio[idx_post])
    signed_rel_diff_pct = 100.0 * (
        first_sample_ratio - prompt_jump_estimate
    ) / max(abs(prompt_jump_estimate), 1.0e-12)

    return {
        "outer_dt_s": float(case_result["params"]["outer_dt"]),
        "sample_time_s": float(time_s[idx_post]),
        "beta_eff_pre": beta_pre,
        "prompt_jump_est_P_over_P0": prompt_jump_estimate,
        "first_sample_P_over_P0": first_sample_ratio,
        "first_sample_vs_prompt_est_rel_diff_pct": signed_rel_diff_pct,
        "first_sample_vs_prompt_est_abs_rel_diff_pct": abs(signed_rel_diff_pct),
    }


def write_history_csv(case_results):
    rows = []
    time_s = case_results["zero"]["time_s"]
    for idx, time_value in enumerate(time_s):
        row = {"time_s": float(time_value)}
        zero_power = case_results["zero"]["power_W"][idx]
        zero_ts_out = case_results["zero"]["ts_out_K"][idx]
        for case_id, case_result in case_results.items():
            power_W = case_result["power_W"][idx]
            power_pre = case_result["power_W"][baseline_index(case_result["time_s"])]
            row[f"{case_id}_power_MW"] = float(power_W / 1.0e6)
            row[f"{case_id}_power_norm"] = float(power_W / max(power_pre, 1.0e-12))
            row[f"{case_id}_delta_power_MW_vs_zero"] = float((power_W - zero_power) / 1.0e6)
            row[f"{case_id}_ts_out_K"] = float(case_result["ts_out_K"][idx])
            row[f"{case_id}_delta_ts_out_K_vs_zero"] = float(case_result["ts_out_K"][idx] - zero_ts_out)
            row[f"{case_id}_rho_pcm"] = float(case_result["inserted_rho_pcm"][idx])
            row[f"{case_id}_feedback_rho_pcm"] = float(case_result["feedback_rho_pcm"][idx])
            row[f"{case_id}_feedback_fuel_delta_K"] = float(case_result["feedback_fuel_delta_K"][idx])
            row[f"{case_id}_feedback_graphite_delta_K"] = float(case_result["feedback_graphite_delta_K"][idx])
            for group_idx in range(6):
                row[f"{case_id}_beta_group_{group_idx + 1}"] = float(
                    case_result["effective_beta_groups"][group_idx, idx]
                )
        rows.append(row)
    write_csv(OUTPUT_DIR / "figure_data_reactivity_step_histories.csv", list(rows[0].keys()), rows)


def make_prompt_response_figure(case_results, prompt_metric_rows):
    if plt is None:
        return
    apply_publication_style()
    fig, axes = plt.subplots(2, 1, figsize=(11.5, 8.8), constrained_layout=False)
    fig.subplots_adjust(left=0.12, right=0.98, bottom=0.11, top=0.95, hspace=0.34)

    for case_id, case_result in case_results.items():
        if case_id == "zero":
            continue
        mask = (case_result["time_s"] >= MAIN_ZOOM_START_S) & (case_result["time_s"] <= MAIN_ZOOM_END_S)
        power_pre = case_result["power_W"][baseline_index(case_result["time_s"])]
        axes[0].plot(
            case_result["time_s"][mask],
            case_result["power_W"][mask] / max(power_pre, 1.0e-12),
            label=case_result["case"]["label"],
            color=CASE_COLORS[case_id],
            marker="o",
            markersize=7,
        )

    axes[0].axvline(INSERTION_TIME_S, color="0.35", linestyle=":", linewidth=1.4)
    axes[0].set_xlim(MAIN_ZOOM_START_S, MAIN_ZOOM_END_S)
    axes[0].set_ylabel(r"$P/P_0$")
    axes[0].set_xlabel("Time (s)")
    axes[0].legend(loc="upper right", frameon=True, facecolor="white", framealpha=0.92)

    labels = [row["case"] for row in prompt_metric_rows]
    estimates = np.asarray([row["prompt_jump_est_P_over_P0"] for row in prompt_metric_rows], dtype=float)
    samples = np.asarray([row["first_sample_P_over_P0"] for row in prompt_metric_rows], dtype=float)
    rel_diffs = np.asarray(
        [row["first_sample_vs_prompt_est_rel_diff_pct"] for row in prompt_metric_rows],
        dtype=float,
    )
    x = np.arange(len(labels))
    width = 0.34
    axes[1].bar(
        x - width / 2,
        estimates,
        width=width,
        label="Prompt-jump estimate",
        color="#737373",
    )
    axes[1].bar(
        x + width / 2,
        samples,
        width=width,
        label="Simulated first sample",
        color=[CASE_COLORS["m075"], CASE_COLORS["m600"], CASE_COLORS["m2400"]],
    )
    for idx, rel_diff in enumerate(rel_diffs):
        y_text = max(estimates[idx], samples[idx]) + 0.035
        axes[1].text(
            x[idx],
            y_text,
            f"{rel_diff:+.1f}%",
            ha="center",
            va="bottom",
            fontsize=15,
            fontweight="semibold",
        )
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels)
    axes[1].set_ylabel(r"$P/P_0$")
    axes[1].set_ylim(0.0, max(0.82, float(np.max([estimates.max(), samples.max()])) + 0.12))
    axes[1].legend(loc="upper right", frameon=True, facecolor="white", framealpha=0.92)
    save_figure(fig, OUTPUT_DIR / "figure_14_prompt_response_main")


def make_appendix_early_window_figure(case_results):
    if plt is None:
        return
    apply_publication_style()
    fig, axes = plt.subplots(2, 1, figsize=(11.5, 8.8), constrained_layout=False)
    fig.subplots_adjust(left=0.12, right=0.98, bottom=0.10, top=0.93, hspace=0.30)

    for case_id, case_result in case_results.items():
        if case_id == "zero":
            continue
        mask = (
            (case_result["time_s"] >= APPENDIX_WINDOW_START_S)
            & (case_result["time_s"] <= APPENDIX_WINDOW_END_S)
        )
        power_pre = case_result["power_W"][baseline_index(case_result["time_s"])]
        axes[0].plot(
            case_result["time_s"][mask],
            case_result["power_W"][mask] / max(power_pre, 1.0e-12),
            label=case_result["case"]["label"],
            color=CASE_COLORS[case_id],
        )
        axes[1].plot(
            case_result["time_s"][mask],
            case_result["feedback_rho_pcm"][mask],
            label=case_result["case"]["label"],
            color=CASE_COLORS[case_id],
        )

    for axis in axes:
        axis.axvline(INSERTION_TIME_S, color="0.35", linestyle=":", linewidth=1.4)
        axis.set_xlim(APPENDIX_WINDOW_START_S, APPENDIX_WINDOW_END_S)
    axes[0].set_title("Early-window sensitivity")
    axes[0].set_ylabel(r"$P/P_0$")
    axes[1].set_ylabel(r"$\rho_T$ (pcm)")
    axes[1].set_xlabel("Time (s)")
    axes[0].legend(loc="upper right", frameon=True, facecolor="white", framealpha=0.92)
    save_figure(fig, OUTPUT_DIR / "figure_15_early_window_sensitivity")


def make_first_sample_convergence_figure(convergence_rows):
    if plt is None:
        return
    apply_publication_style()
    fig, ax = plt.subplots(1, 1, figsize=(8.6, 5.8), constrained_layout=True)
    rows = sorted(convergence_rows, key=lambda row: float(row["outer_dt_s"]))
    dts = np.asarray([row["outer_dt_s"] for row in rows], dtype=float)
    samples = np.asarray([row["first_sample_P_over_P0"] for row in rows], dtype=float)
    ax.plot(
        dts,
        samples,
        color=CASE_COLORS["m075"],
        marker="o",
        linewidth=3.0,
    )
    ax.set_xscale("log", base=2)
    ax.invert_xaxis()
    ax.set_xticks(dts)
    ax.set_xticklabels([f"{dt:g}" for dt in dts])
    ax.set_xlabel(r"$\Delta t$ (s)")
    ax.set_ylabel(r"First-sample $P/P_0$")
    save_figure(fig, OUTPUT_DIR / "figure_16_m075_first_sample_convergence")


def main():
    ensure_dir(OUTPUT_DIR)

    case_results = {}
    for case_def in CASE_DEFINITIONS:
        case_results[case_def["id"]] = run_case(case_def, outer_dt=BASELINE_DT_S)

    prompt_metric_rows = [
        compute_prompt_metrics(case_results[case_def["id"]])
        for case_def in CASE_DEFINITIONS
        if case_def["id"] != "zero"
    ]
    write_csv(OUTPUT_DIR / "table_13_reactivity_step_metrics.csv", list(prompt_metric_rows[0].keys()), prompt_metric_rows)
    write_history_csv(case_results)
    make_prompt_response_figure(case_results, prompt_metric_rows)
    make_appendix_early_window_figure(case_results)

    mild_case = {"id": "m075", "label": "-75 pcm", "pcm": -75.0, "index": 201}
    convergence_results = {}
    convergence_rows = []
    for offset, outer_dt in enumerate(CONVERGENCE_DTS):
        case_result = run_case(
            mild_case,
            outer_dt=outer_dt,
            sim_index=201 + offset,
            end_time_s=CONVERGENCE_END_TIME_S,
        )
        convergence_results[outer_dt] = case_result
        convergence_rows.append(compute_convergence_metrics(case_result))

    finest_row = min(convergence_rows, key=lambda row: float(row["outer_dt_s"]))
    finest_sample = float(finest_row["first_sample_P_over_P0"])
    for row in convergence_rows:
        row["first_sample_rel_diff_vs_0p0625s_pct"] = 100.0 * (
            float(row["first_sample_P_over_P0"]) - finest_sample
        ) / max(abs(finest_sample), 1.0e-12)

    write_csv(
        OUTPUT_DIR / "table_14_m075_first_sample_timestep_convergence.csv",
        list(convergence_rows[0].keys()),
        convergence_rows,
    )
    make_first_sample_convergence_figure(convergence_rows)

    metadata = {
        "insertion_time_s": INSERTION_TIME_S,
        "end_time_s": END_TIME_S,
        "baseline_outer_dt_s": BASELINE_DT_S,
        "main_zoom_start_s": MAIN_ZOOM_START_S,
        "main_zoom_end_s": MAIN_ZOOM_END_S,
        "appendix_window_start_s": APPENDIX_WINDOW_START_S,
        "appendix_window_end_s": APPENDIX_WINDOW_END_S,
        "convergence_end_time_s": CONVERGENCE_END_TIME_S,
        "grid_points": 160,
        "convergence_outer_dt_s": CONVERGENCE_DTS,
        "generated_files": [
            "table_13_reactivity_step_metrics.csv",
            "table_14_m075_first_sample_timestep_convergence.csv",
            "figure_14_prompt_response_main.png",
            "figure_14_prompt_response_main.pdf",
            "figure_15_early_window_sensitivity.png",
            "figure_15_early_window_sensitivity.pdf",
            "figure_16_m075_first_sample_convergence.png",
            "figure_16_m075_first_sample_convergence.pdf",
            "figure_data_reactivity_step_histories.csv",
        ],
        "cases": [{key: value for key, value in case_def.items() if key != "index"} for case_def in CASE_DEFINITIONS],
    }
    write_json(OUTPUT_DIR / "metadata.json", metadata)


if __name__ == "__main__":
    main()
