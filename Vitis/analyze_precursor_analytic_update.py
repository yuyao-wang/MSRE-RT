#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VITIS_DIR = REPO_ROOT / "Vitis"
PYTHON_DIR = REPO_ROOT / "python"
VERIFICATION_DIR = REPO_ROOT / "Verification_Evaluation"
for path in (PYTHON_DIR, VERIFICATION_DIR, REPO_ROOT):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from parameters import generate_parameters
from verification_physics import run_coupled_transient
from Vitis.analyze_fpga_kernel_run import parse_csynth_summary
from Vitis.vcu118 import msr_vcu118_host


METRICS = [
    "power_W",
    "phi_mid",
    "fuel_mid_K",
    "graphite_mid_K",
    "Ts_core_outlet_K",
    "Ts_HX1_0_K",
    "Tss_HX1_L_K",
    "Tss_HX2_0_K",
    "Tsss_HX2_L_K",
    "Tsss_pp_0_K",
]


def write_snapshot(out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    params_dict = generate_parameters(N=200, outer_dt=1.0, steady_state_steps=180, use_steady_state_initialization=True)
    core_state = msr_vcu118_host.create_model_core_state(params_dict)
    bop_state = msr_vcu118_host.create_model_bop_state(params_dict)
    kernel_params = msr_vcu118_host.create_model_kernel_params(params_dict, hardware_substeps=1)

    paths = {
        "core_state": out_dir / "core_state.bin",
        "core_params": out_dir / "core_params.bin",
        "bop_state": out_dir / "bop_state.bin",
        "bop_params": out_dir / "bop_params.bin",
    }
    paths["core_state"].write_bytes(msr_vcu118_host.struct_bytes(core_state))
    paths["core_params"].write_bytes(msr_vcu118_host.struct_bytes(kernel_params))
    paths["bop_state"].write_bytes(msr_vcu118_host.struct_bytes(bop_state))
    paths["bop_params"].write_bytes(msr_vcu118_host.struct_bytes(kernel_params))

    scalars = {
        "Ts_core_inlet": float(params_dict["Ts_in"]),
        "rod_position": 0.0,
        "external_reactivity": 0.0,
        "Ts_HX1_L": float(params_dict["Ts_out"]),
        "Tss_HX1_0": float(params_dict["Tss_in"]),
        "Tss_HX2_L": float(params_dict["Tss_out"]),
        "Tsss_HX2_0": float(params_dict["Tsss_in"]),
    }
    return {
        "paths": {key: str(value) for key, value in paths.items()},
        "scalars": scalars,
        "steady_state_summary": params_dict.get("steady_state_summary", {}),
    }


def compile_runner(binary_path: Path, analytic: bool) -> None:
    cmd = [
        "c++",
        "-O3",
        "-DNDEBUG",
        "-std=c++17",
        "-DMSR_MAX_STATE_N=200",
        "-DMSR_FIXED_CORE_N=200",
        "-DMSR_FIXED_BOP_NX=200",
        "-DMSR_FIXED_HARDWARE_SUBSTEPS=1",
        f"-DMSR_PRECURSOR_ANALYTIC_UPDATE={1 if analytic else 0}",
        str(VITIS_DIR / "vcu118" / "msr_vcu118_sw_timed.cpp"),
        "-o",
        str(binary_path),
    ]
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def parse_runner_output(text: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        try:
            values[key.strip()] = float(value.strip())
        except ValueError:
            continue
    return values


def run_runner_once(
    binary_path: Path,
    snapshot: dict[str, object],
    repeats: int,
    warmup: int,
) -> tuple[str, dict[str, float]]:
    paths = snapshot["paths"]
    scalars = snapshot["scalars"]
    cmd = [
        str(binary_path),
        paths["core_state"],
        paths["core_params"],
        paths["bop_state"],
        paths["bop_params"],
        str(scalars["Ts_core_inlet"]),
        str(scalars["rod_position"]),
        str(scalars["external_reactivity"]),
        str(scalars["Ts_HX1_L"]),
        str(scalars["Tss_HX1_0"]),
        str(scalars["Tss_HX2_L"]),
        str(scalars["Tsss_HX2_0"]),
        str(repeats),
        str(warmup),
    ]
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=REPO_ROOT)
    return completed.stdout, parse_runner_output(completed.stdout)


def summarize_runner_samples(runs: list[tuple[str, dict[str, float]]]) -> dict[str, object]:
    core_avgs = [parsed["timing.core.avg_us"] for _, parsed in runs]
    bop_avgs = [parsed["timing.bop.avg_us"] for _, parsed in runs]
    selected_index = min(
        range(len(runs)),
        key=lambda idx: abs(runs[idx][1]["timing.core.avg_us"] - statistics.median(core_avgs)),
    )
    selected_stdout, parsed = runs[selected_index]
    return {
        "stdout": selected_stdout,
        "sample_count": len(runs),
        "sample_core_avg_us": core_avgs,
        "sample_bop_avg_us": bop_avgs,
        "timing": {
            "core_avg_us": statistics.median(core_avgs),
            "bop_avg_us": statistics.median(bop_avgs),
            "total_avg_us": statistics.median(core_avgs) + statistics.median(bop_avgs),
        },
        "metrics": {
            "power_W": parsed["core.power"],
            "phi_mid": parsed["core.phi_mid"],
            "fuel_mid_K": parsed["core.fuel_mid"],
            "graphite_mid_K": parsed["core.graphite_mid"],
            "Ts_core_outlet_K": parsed["core.Ts_core_outlet"],
            "Ts_HX1_0_K": parsed["bop.Ts_HX1_0"],
            "Tss_HX1_L_K": parsed["bop.Tss_HX1_L"],
            "Tss_HX2_0_K": parsed["bop.Tss_HX2_0"],
            "Tsss_HX2_L_K": parsed["bop.Tsss_HX2_L"],
            "Tsss_pp_0_K": parsed["bop.Tsss_pp_0"],
        },
    }


def run_variants_interleaved(
    baseline_bin: Path,
    analytic_bin: Path,
    snapshot: dict[str, object],
    repeats: int,
    warmup: int,
    samples: int,
) -> tuple[dict[str, object], dict[str, object]]:
    baseline_runs: list[tuple[str, dict[str, float]]] = []
    analytic_runs: list[tuple[str, dict[str, float]]] = []

    for sample_idx in range(samples):
        if sample_idx % 2 == 0:
            order = [("baseline", baseline_bin), ("analytic", analytic_bin)]
        else:
            order = [("analytic", analytic_bin), ("baseline", baseline_bin)]

        for label, binary_path in order:
            run = run_runner_once(binary_path, snapshot, repeats, warmup)
            if label == "baseline":
                baseline_runs.append(run)
            else:
                analytic_runs.append(run)

    return summarize_runner_samples(baseline_runs), summarize_runner_samples(analytic_runs)


def physics_reference() -> dict[str, float]:
    params = generate_parameters(N=200, outer_dt=1.0, steady_state_steps=180, use_steady_state_initialization=True)
    run = run_coupled_transient(params, 1, diagnostic_mode="state")
    return {
        "power_W": float(run["power_W"][0]),
        "phi_mid": float(run["final_phi1"][100] + run["final_phi2"][100]),
        "fuel_mid_K": float(run["final_Ts"][100]),
        "graphite_mid_K": float(run["final_Tgr"][100]),
        "Ts_core_outlet_K": float(run["Ts_out_K"][0]),
        "Ts_HX1_0_K": float(run["diagnostics"]["hx1_hot_out"][0]),
        "Tss_HX1_L_K": float(run["diagnostics"]["hx1_cold_out"][0]),
        "Tss_HX2_0_K": float(run["diagnostics"]["hx2_hot_out"][0]),
        "Tsss_HX2_L_K": float(run["diagnostics"]["hx2_cold_out"][0]),
        "Tsss_pp_0_K": float(params["last_power_plant"]["T2r"]),
    }


def compare_to_reference(reference: dict[str, float], variant: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    metrics = variant["metrics"]
    for metric in METRICS:
        value = metrics[metric]
        ref = reference[metric]
        abs_err = abs(value - ref)
        rel_err = 0.0 if ref == 0.0 else abs_err / abs(ref)
        rows.append(
            {
                "metric": metric,
                "value": value,
                "reference": ref,
                "abs_error": abs_err,
                "rel_error": rel_err,
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    headers = list(rows[0].keys())
    with path.open("w", encoding="utf-8") as fh:
        fh.write(",".join(headers) + "\n")
        for row in rows:
            fh.write(",".join(str(row[key]) for key in headers) + "\n")


def build_report(
    out_path: Path,
    snapshot: dict[str, object],
    baseline: dict[str, object],
    analytic: dict[str, object],
    reference: dict[str, float],
    baseline_rows: list[dict[str, object]],
    analytic_rows: list[dict[str, object]],
    csynth_delta: dict[str, object] | None,
) -> None:
    def fmt_latency(min_value: object, max_value: object) -> str:
        if min_value is None or max_value is None:
            return "undef"
        return f"{min_value}..{max_value}"

    lines = [
        "# Analytic Precursor Update",
        "",
        "## Timing",
        "",
        f"- Timing statistic: median of `{baseline['sample_count']}` alternating baseline/analytic runner invocations",
        f"- Baseline core avg: `{baseline['timing']['core_avg_us']:.6f} us`",
        f"- Analytic core avg: `{analytic['timing']['core_avg_us']:.6f} us`",
        f"- Core speedup: `{baseline['timing']['core_avg_us'] / analytic['timing']['core_avg_us']:.6f}x`",
        f"- Baseline total avg: `{baseline['timing']['total_avg_us']:.6f} us`",
        f"- Analytic total avg: `{analytic['timing']['total_avg_us']:.6f} us`",
        f"- Total speedup: `{baseline['timing']['total_avg_us'] / analytic['timing']['total_avg_us']:.6f}x`",
        "",
        "## Accuracy vs Physics Reference",
        "",
        "| Metric | Baseline Abs Err | Analytic Abs Err | Analytic/Baseline |",
        "| --- | ---: | ---: | ---: |",
    ]
    for base_row, ana_row in zip(baseline_rows, analytic_rows):
        ratio = 0.0 if base_row["abs_error"] == 0.0 else ana_row["abs_error"] / base_row["abs_error"]
        lines.append(
            f"| `{base_row['metric']}` | {base_row['abs_error']:.6e} | {ana_row['abs_error']:.6e} | {ratio:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Reference Snapshot",
            "",
            f"- `Ts_core_inlet` = `{snapshot['scalars']['Ts_core_inlet']:.12f}`",
            f"- `Ts_HX1_L` = `{snapshot['scalars']['Ts_HX1_L']:.12f}`",
            f"- `Tss_HX1_0` = `{snapshot['scalars']['Tss_HX1_0']:.12f}`",
            f"- `Tss_HX2_L` = `{snapshot['scalars']['Tss_HX2_L']:.12f}`",
            f"- `Tsss_HX2_0` = `{snapshot['scalars']['Tsss_HX2_0']:.12f}`",
            "",
        ]
    )
    if csynth_delta is not None:
        latency_ratio = csynth_delta["latency_ratio"]
        lines.extend(
            [
                "## Core HLS Delta",
                "",
                f"- Baseline latency: `{fmt_latency(csynth_delta['baseline_lat_min'], csynth_delta['baseline_lat_max'])}` cycles",
                f"- Analytic latency: `{fmt_latency(csynth_delta['analytic_lat_min'], csynth_delta['analytic_lat_max'])}` cycles",
                f"- Baseline estimated clock: `{csynth_delta['baseline_estimated_clock_ns']:.3f} ns`",
                f"- Analytic estimated clock: `{csynth_delta['analytic_estimated_clock_ns']:.3f} ns`",
                f"- Estimated clock ratio: `{csynth_delta['clock_ratio']:.6f}x`",
                (
                    f"- Mid-latency ratio: `{latency_ratio:.6f}x`"
                    if latency_ratio is not None
                    else "- Mid-latency ratio: `undef`"
                ),
                f"- LUT: `{csynth_delta['baseline_lut']}` -> `{csynth_delta['analytic_lut']}` (`{csynth_delta['lut_ratio']:.6f}x`)",
                f"- FF: `{csynth_delta['baseline_ff']}` -> `{csynth_delta['analytic_ff']}` (`{csynth_delta['ff_ratio']:.6f}x`)",
                f"- DSP: `{csynth_delta['baseline_dsp']}` -> `{csynth_delta['analytic_dsp']}` (`{csynth_delta['dsp_ratio']:.6f}x`)",
                f"- BRAM18K: `{csynth_delta['baseline_bram']}` -> `{csynth_delta['analytic_bram']}` (`{csynth_delta['bram_ratio']:.6f}x`)",
                "",
            ]
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_csynth_delta(baseline_path: Path, analytic_path: Path) -> dict[str, object]:
    baseline = parse_csynth_summary(baseline_path)
    analytic = parse_csynth_summary(analytic_path)

    def parse_resource(summary: dict[str, object], name: str) -> int:
        return int(str(summary["resources"][name]).replace(",", ""))

    def ratio(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else float("inf")

    baseline_lut = parse_resource(baseline, "LUT")
    baseline_ff = parse_resource(baseline, "FF")
    baseline_dsp = parse_resource(baseline, "DSP")
    baseline_bram = parse_resource(baseline, "BRAM_18K")
    analytic_lut = parse_resource(analytic, "LUT")
    analytic_ff = parse_resource(analytic, "FF")
    analytic_dsp = parse_resource(analytic, "DSP")
    analytic_bram = parse_resource(analytic, "BRAM_18K")

    latency_ratio = None
    if (
        baseline["lat_min"] is not None
        and baseline["lat_max"] is not None
        and analytic["lat_min"] is not None
        and analytic["lat_max"] is not None
    ):
        baseline_mid = 0.5 * (baseline["lat_min"] + baseline["lat_max"])
        analytic_mid = 0.5 * (analytic["lat_min"] + analytic["lat_max"])
        latency_ratio = analytic_mid / baseline_mid

    return {
        "baseline_lat_min": baseline["lat_min"],
        "baseline_lat_max": baseline["lat_max"],
        "baseline_lat_min_raw": baseline["lat_min_raw"],
        "baseline_lat_max_raw": baseline["lat_max_raw"],
        "analytic_lat_min": analytic["lat_min"],
        "analytic_lat_max": analytic["lat_max"],
        "analytic_lat_min_raw": analytic["lat_min_raw"],
        "analytic_lat_max_raw": analytic["lat_max_raw"],
        "baseline_estimated_clock_ns": baseline["estimated_clock_ns"],
        "analytic_estimated_clock_ns": analytic["estimated_clock_ns"],
        "clock_ratio": analytic["estimated_clock_ns"] / baseline["estimated_clock_ns"],
        "latency_ratio": latency_ratio,
        "baseline_lut": baseline_lut,
        "analytic_lut": analytic_lut,
        "lut_ratio": ratio(analytic_lut, baseline_lut),
        "baseline_ff": baseline_ff,
        "analytic_ff": analytic_ff,
        "ff_ratio": ratio(analytic_ff, baseline_ff),
        "baseline_dsp": baseline_dsp,
        "analytic_dsp": analytic_dsp,
        "dsp_ratio": ratio(analytic_dsp, baseline_dsp),
        "baseline_bram": baseline_bram,
        "analytic_bram": analytic_bram,
        "bram_ratio": ratio(analytic_bram, baseline_bram),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare RK4 precursor update against analytic precursor update.")
    parser.add_argument("--out-dir", type=Path, default=VITIS_DIR / "analysis_artifacts" / "precursor_analytic_update_20260618")
    parser.add_argument("--snapshot-dir", type=Path, default=Path("/private/tmp/msr_precursor_snapshot"))
    parser.add_argument("--baseline-bin", type=Path, default=Path("/private/tmp/msr_vcu118_sw_timed_baseline"))
    parser.add_argument("--analytic-bin", type=Path, default=Path("/private/tmp/msr_vcu118_sw_timed_analytic"))
    parser.add_argument("--repeats", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--baseline-core-csynth", type=Path, default=Path("/private/tmp/core_step_kernel_n200_s1_csynth.xml"))
    parser.add_argument("--analytic-core-csynth", type=Path, default=Path("/private/tmp/core_step_kernel_n200_s1_csynth_analytic_20260618.xml"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    snapshot = write_snapshot(args.snapshot_dir)
    compile_runner(args.baseline_bin, analytic=False)
    compile_runner(args.analytic_bin, analytic=True)

    baseline, analytic = run_variants_interleaved(
        args.baseline_bin,
        args.analytic_bin,
        snapshot,
        args.repeats,
        args.warmup,
        args.samples,
    )
    reference = physics_reference()

    baseline_rows = compare_to_reference(reference, baseline)
    analytic_rows = compare_to_reference(reference, analytic)
    comparison_rows = []
    for base_row, ana_row in zip(baseline_rows, analytic_rows):
        comparison_rows.append(
            {
                "metric": base_row["metric"],
                "baseline_abs_error": base_row["abs_error"],
                "analytic_abs_error": ana_row["abs_error"],
                "analytic_over_baseline_error": 0.0 if base_row["abs_error"] == 0.0 else ana_row["abs_error"] / base_row["abs_error"],
            }
        )

    timing_rows = [
        {"variant": "baseline", **baseline["timing"]},
        {"variant": "analytic", **analytic["timing"]},
    ]
    timing_rows.append(
        {
            "variant": "speedup",
            "core_avg_us": baseline["timing"]["core_avg_us"] / analytic["timing"]["core_avg_us"],
            "bop_avg_us": baseline["timing"]["bop_avg_us"] / analytic["timing"]["bop_avg_us"],
            "total_avg_us": baseline["timing"]["total_avg_us"] / analytic["timing"]["total_avg_us"],
        }
    )

    csynth_delta = None
    if args.baseline_core_csynth.exists() and args.analytic_core_csynth.exists():
        csynth_delta = build_csynth_delta(args.baseline_core_csynth, args.analytic_core_csynth)

    write_csv(args.out_dir / "timing_compare.csv", timing_rows)
    write_csv(args.out_dir / "baseline_vs_physics.csv", baseline_rows)
    write_csv(args.out_dir / "analytic_vs_physics.csv", analytic_rows)
    write_csv(args.out_dir / "analytic_error_delta.csv", comparison_rows)
    if csynth_delta is not None:
        write_csv(args.out_dir / "core_csynth_delta.csv", [csynth_delta])

    summary = {
        "snapshot": snapshot,
        "baseline": baseline,
        "analytic": analytic,
        "reference": reference,
        "baseline_rows": baseline_rows,
        "analytic_rows": analytic_rows,
        "comparison_rows": comparison_rows,
        "csynth_delta": csynth_delta,
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    build_report(args.out_dir / "report.md", snapshot, baseline, analytic, reference, baseline_rows, analytic_rows, csynth_delta)

    print(f"Wrote analysis to: {args.out_dir}")
    print(f"Report: {args.out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
