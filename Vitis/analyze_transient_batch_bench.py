#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import ctypes
import json
import struct
import subprocess
import sys
import time
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


K_MAX_N = msr_vcu118_host.K_MAX_N
K_PRECURSOR_GROUPS = msr_vcu118_host.K_PRECURSOR_GROUPS
K_MAX_LOOP_HISTORY = msr_vcu118_host.K_MAX_LOOP_HISTORY
K_MAX_DELAY_SLOTS = 32


double_array = msr_vcu118_host.double_array
double_matrix = msr_vcu118_host.double_matrix


class DelayLine(ctypes.Structure):
    _fields_ = [
        ("data", double_array(K_MAX_DELAY_SLOTS)),
        ("head", ctypes.c_int),
        ("size", ctypes.c_int),
        ("delay_steps", ctypes.c_int),
    ]


class DelayBundle(ctypes.Structure):
    _fields_ = [
        ("hx_c", DelayLine),
        ("c_hx", DelayLine),
        ("r_hx", DelayLine),
        ("hx_r", DelayLine),
        ("r_pp", DelayLine),
        ("pp_r", DelayLine),
    ]


class StepState(ctypes.Structure):
    _fields_ = [
        ("phi1", double_array(K_MAX_N)),
        ("phi2", double_array(K_MAX_N)),
        ("C", double_matrix(K_PRECURSOR_GROUPS, K_MAX_N)),
        ("kinetics_amplitude", ctypes.c_double),
        ("kinetics_precursors", double_array(K_PRECURSOR_GROUPS)),
        ("kinetics_beta_effective", double_array(K_PRECURSOR_GROUPS)),
        ("fuel", double_array(K_MAX_N)),
        ("graphite", double_array(K_MAX_N)),
        ("hx1_hot", double_array(K_MAX_N)),
        ("hx1_cold", double_array(K_MAX_N)),
        ("hx2_hot", double_array(K_MAX_N)),
        ("hx2_cold", double_array(K_MAX_N)),
        ("Ts_HX1_0", ctypes.c_double),
        ("Tss_HX2_0", ctypes.c_double),
        ("Tsss_pp_0", ctypes.c_double),
        ("precursor_history", msr_vcu118_host.PrecursorHistory),
    ]


class StepDiagnostics(ctypes.Structure):
    _fields_ = [
        ("phi_mid", ctypes.c_double),
        ("rho", ctypes.c_double),
        ("power", ctypes.c_double),
        ("fuel_mid", ctypes.c_double),
        ("graphite_mid", ctypes.c_double),
        ("core_inlet", ctypes.c_double),
        ("core_outlet", ctypes.c_double),
        ("hx1_hot_outlet", ctypes.c_double),
        ("hx1_cold_outlet", ctypes.c_double),
        ("hx2_hot_outlet", ctypes.c_double),
        ("hx2_cold_outlet", ctypes.c_double),
        ("brayton_return", ctypes.c_double),
    ]


def parse_key_value_output(text: str) -> dict[str, float]:
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


def compile_batch_runner(binary_path: Path, hardware_substeps: int, point_kinetics_solver: int) -> None:
    cmd = [
        "c++",
        "-O3",
        "-DNDEBUG",
        "-std=c++17",
        "-DMSR_CROSS_SECTION_LANE_FACTOR=2",
        "-DMSR_NEUTRONICS_LANE_FACTOR=2",
        "-DMSR_THERMAL_LANE_FACTOR=4",
        "-DMSR_HEAT_EXCHANGER_LANE_FACTOR=2",
        "-DMSR_FIXED_CORE_N=200",
        "-DMSR_FIXED_BOP_NX=200",
        f"-DMSR_FIXED_HARDWARE_SUBSTEPS={hardware_substeps}",
        "-DMSR_MAX_STATE_N=200",
        "-DMSR_MAX_TRANSIENT_STEPS=600",
        "-DMSR_MAX_BATCH_SCENARIOS=1",
        "-DMSR_BATCH_BENCH_STEP_COUNT=600",
        "-DMSR_BATCH_BENCH_SCENARIO_COUNT=1",
        "-DMSR_RESIDENT_THERMAL_FLOAT=1",
        "-DMSR_RESIDENT_HISTORY_FLOAT=1",
        "-DMSR_BATCH_CONTROL_FLOAT=1",
        "-DMSR_PRECURSOR_ANALYTIC_UPDATE=0",
        f"-DMSR_POINT_KINETICS_SOLVER={point_kinetics_solver}",
    ]
    cmd.extend(
        [
            str(VITIS_DIR / "vcu118" / "msr_transient_batch_sw_timed.cpp"),
            "-o",
            str(binary_path),
        ]
    )
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def compile_same_init_plain_runner(binary_path: Path, hardware_substeps: int, point_kinetics_solver: int) -> None:
    cmd = [
        "c++",
        "-O3",
        "-DNDEBUG",
        "-std=c++17",
        "-DMSR_CROSS_SECTION_LANE_FACTOR=2",
        "-DMSR_NEUTRONICS_LANE_FACTOR=2",
        "-DMSR_THERMAL_LANE_FACTOR=4",
        "-DMSR_HEAT_EXCHANGER_LANE_FACTOR=2",
        "-DMSR_FIXED_CORE_N=200",
        "-DMSR_FIXED_BOP_NX=200",
        f"-DMSR_FIXED_HARDWARE_SUBSTEPS={hardware_substeps}",
        "-DMSR_MAX_STATE_N=200",
        "-DMSR_MAX_TRANSIENT_STEPS=600",
        "-DMSR_MAX_BATCH_SCENARIOS=1",
        "-DMSR_BATCH_BENCH_STEP_COUNT=600",
        "-DMSR_BATCH_BENCH_SCENARIO_COUNT=1",
        "-DMSR_RESIDENT_THERMAL_FLOAT=1",
        "-DMSR_RESIDENT_HISTORY_FLOAT=1",
        "-DMSR_BATCH_CONTROL_FLOAT=1",
        "-DMSR_PRECURSOR_ANALYTIC_UPDATE=0",
        f"-DMSR_POINT_KINETICS_SOLVER={point_kinetics_solver}",
        str(VITIS_DIR / "vcu118" / "msr_transient_batch_plain_timed.cpp"),
        "-o",
        str(binary_path),
    ]
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def make_delay_line(values, delay_time: float, outer_dt: float) -> DelayLine:
    line = DelayLine()
    values = list(values)
    if len(values) > K_MAX_DELAY_SLOTS:
        raise ValueError(f"delay line length {len(values)} exceeds {K_MAX_DELAY_SLOTS}")
    for idx, value in enumerate(values):
        line.data[idx] = float(value)
    line.head = 0
    line.size = len(values)
    line.delay_steps = max(int(round(float(delay_time) / max(float(outer_dt), 1.0e-12))), 0)
    return line


def make_delay_bundle(params: dict[str, object]) -> DelayBundle:
    outer_dt = float(params["outer_dt"])
    bundle = DelayBundle()
    bundle.hx_c = make_delay_line(params.get("buffer_hx_c_init", []), float(params["tau_hx_c"]), outer_dt)
    bundle.c_hx = make_delay_line(params.get("buffer_c_hx_init", []), float(params["tau_c_hx"]), outer_dt)
    bundle.r_hx = make_delay_line(params.get("buffer_r_hx_init", []), float(params["tau_r_hx"]), outer_dt)
    bundle.hx_r = make_delay_line(params.get("buffer_hx_r_init", []), float(params["tau_hx_r"]), outer_dt)
    bundle.r_pp = make_delay_line(params.get("buffer_r_pp_init", []), float(params["tau_r_pp"]), outer_dt)
    bundle.pp_r = make_delay_line(params.get("buffer_pp_r_init", []), float(params["tau_pp_r"]), outer_dt)
    return bundle


def make_step_state(params: dict[str, object]) -> StepState:
    core_state = msr_vcu118_host.create_model_core_state(params)
    bop_state = msr_vcu118_host.create_model_bop_state(params)

    state = StepState()
    msr_vcu118_host.set_vector(state.phi1, list(core_state.phi1))
    msr_vcu118_host.set_vector(state.phi2, list(core_state.phi2))
    for group in range(K_PRECURSOR_GROUPS):
        msr_vcu118_host.set_vector(state.C[group], list(core_state.C[group]))
    state.kinetics_amplitude = float(core_state.kinetics_amplitude)
    msr_vcu118_host.set_vector(state.kinetics_precursors, list(core_state.kinetics_precursors))
    msr_vcu118_host.set_vector(state.kinetics_beta_effective, list(core_state.kinetics_beta_effective))
    msr_vcu118_host.set_vector(state.fuel, list(core_state.fuel))
    msr_vcu118_host.set_vector(state.graphite, list(core_state.graphite))
    msr_vcu118_host.set_vector(state.hx1_hot, list(bop_state.hx1_hot))
    msr_vcu118_host.set_vector(state.hx1_cold, list(bop_state.hx1_cold))
    msr_vcu118_host.set_vector(state.hx2_hot, list(bop_state.hx2_hot))
    msr_vcu118_host.set_vector(state.hx2_cold, list(bop_state.hx2_cold))
    state.Ts_HX1_0 = float(params["Ts_in"])
    state.Tss_HX2_0 = float(params["Tss_in"])
    state.Tsss_pp_0 = float(params["Tsss_in"])
    ctypes.memmove(
        ctypes.addressof(state.precursor_history),
        ctypes.addressof(core_state.precursor_history),
        ctypes.sizeof(msr_vcu118_host.PrecursorHistory),
    )
    return state


def make_control_arrays(step_count: int, outer_dt: float, insertion_pcm: float, insertion_time_s: float) -> tuple[list[float], list[float]]:
    rod_positions = [0.0] * step_count
    external_reactivities = []
    magnitude = insertion_pcm * 1.0e-5
    for step in range(step_count):
        current_time = float(step) * outer_dt
        external_reactivities.append(magnitude if current_time >= insertion_time_s else 0.0)
    return rod_positions, external_reactivities


def write_blob(path: Path, blob: bytes) -> None:
    path.write_bytes(blob)


def read_struct_array(path: Path, struct_type, count: int):
    blob = path.read_bytes()
    expected = ctypes.sizeof(struct_type) * count
    if len(blob) != expected:
        raise ValueError(f"{path} expected {expected} bytes, got {len(blob)}")
    values = []
    for idx in range(count):
        offset = idx * ctypes.sizeof(struct_type)
        values.append(struct_type.from_buffer_copy(blob[offset : offset + ctypes.sizeof(struct_type)]))
    return values


def run_plain_cpp(steps: int, insertion_pcm: float, insertion_time_s: float, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(REPO_ROOT / "cpp" / "build" / "msr_plain"),
        str(steps),
        str(out_dir),
        str(insertion_pcm),
        str(insertion_time_s),
    ]
    start = time.perf_counter()
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=REPO_ROOT)
    elapsed_s = time.perf_counter() - start

    with (out_dir / "centerline_trace.csv").open("r", encoding="utf-8") as fh:
        centerline_rows = list(csv.DictReader(fh))
    last_row = centerline_rows[-1]

    axial = {"z": [], "phi": [], "fuel_temp": [], "graphite_temp": [], "C": [[] for _ in range(K_PRECURSOR_GROUPS)]}
    with (out_dir / "axial_state.csv").open("r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            axial["z"].append(float(row["z"]))
            axial["phi"].append(float(row["phi"]))
            axial["fuel_temp"].append(float(row["fuel_temp"]))
            axial["graphite_temp"].append(float(row["graphite_temp"]))
            for group in range(K_PRECURSOR_GROUPS):
                axial["C"][group].append(float(row[f"C{group + 1}"]))

    return {
        "stdout": completed.stdout,
        "elapsed_s": elapsed_s,
        "final": {
            "phi_mid": float(last_row["phi_mid"]),
            "rho": float(last_row["rho"]),
            "power": float(last_row["power"]),
            "fuel_mid": float(last_row["fuel_mid"]),
            "graphite_mid": float(last_row["graphite_mid"]),
            "core_inlet": float(last_row["core_inlet"]),
            "core_outlet": float(last_row["core_outlet"]),
            "hx1_hot_outlet": float(last_row["hx1_hot_outlet"]),
            "hx1_cold_outlet": float(last_row["hx1_cold_outlet"]),
            "hx2_hot_outlet": float(last_row["hx2_hot_outlet"]),
            "hx2_cold_outlet": float(last_row["hx2_cold_outlet"]),
            "brayton_return": float(last_row["brayton_return"]),
        },
        "axial": axial,
    }


def run_python_reference(params: dict[str, object], steps: int, insertion_pcm: float, insertion_time_s: float) -> dict[str, object]:
    event_sequence = None
    if abs(insertion_pcm) > 0.0:
        event_sequence = [
            {
                "start_time_s": float(insertion_time_s),
                "event_type": "equivalent_absorption",
                "magnitude": float(insertion_pcm),
            }
        ]

    run = run_coupled_transient(params, steps, event_sequence=event_sequence, diagnostic_mode="state")
    axial = {
        "phi": [float(run["final_phi1"][idx] + run["final_phi2"][idx]) for idx in range(K_MAX_N)],
        "fuel_temp": [float(run["final_Ts"][idx]) for idx in range(K_MAX_N)],
        "graphite_temp": [float(run["final_Tgr"][idx]) for idx in range(K_MAX_N)],
        "C": [
            [float(run["final_C"][group][idx]) for idx in range(K_MAX_N)]
            for group in range(K_PRECURSOR_GROUPS)
        ],
    }
    final = {
        "phi_mid": float(run["final_phi1"][K_MAX_N // 2] + run["final_phi2"][K_MAX_N // 2]),
        "rho": (
            float(run["external_rho_pcm"][-1]) * 1.0e-5
            if "external_rho_pcm" in run
            else float(run["rho_pcm"][-1]) * 1.0e-5
        ),
        "power": float(run["power_W"][-1]),
        "fuel_mid": float(run["final_Ts"][K_MAX_N // 2]),
        "graphite_mid": float(run["final_Tgr"][K_MAX_N // 2]),
        "core_inlet": float(run["Ts_in_K"][-1]),
        "core_outlet": float(run["Ts_out_K"][-1]),
        "hx1_hot_outlet": float(run["diagnostics"]["hx1_hot_out"][-1]),
        "hx1_cold_outlet": float(run["diagnostics"]["hx1_cold_out"][-1]),
        "hx2_hot_outlet": float(run["diagnostics"]["hx2_hot_out"][-1]),
        "hx2_cold_outlet": float(run["diagnostics"]["hx2_cold_out"][-1]),
        "brayton_return": float(run["diagnostics"]["brayton_T2r"][-1]),
    }
    return {"final": final, "axial": axial}


def compare_metrics(reference: dict[str, float], actual: dict[str, float]) -> list[dict[str, float | str]]:
    rows = []
    for key, ref in reference.items():
        value = actual[key]
        abs_error = abs(value - ref)
        rel_error = 0.0 if ref == 0.0 else abs_error / abs(ref)
        rows.append({"metric": key, "reference": ref, "value": value, "abs_error": abs_error, "rel_error": rel_error})
    return rows


def compare_state(reference: dict[str, object], state: StepState) -> list[dict[str, float | str]]:
    phi = [float(state.phi1[idx] + state.phi2[idx]) for idx in range(K_MAX_N)]
    fuel = [float(state.fuel[idx]) for idx in range(K_MAX_N)]
    graphite = [float(state.graphite[idx]) for idx in range(K_MAX_N)]

    rows: list[dict[str, float | str]] = []
    series = [
        ("phi", reference["phi"], phi),
        ("fuel_temp", reference["fuel_temp"], fuel),
        ("graphite_temp", reference["graphite_temp"], graphite),
    ]
    for group in range(K_PRECURSOR_GROUPS):
        series.append((f"C{group + 1}", reference["C"][group], [float(state.C[group][idx]) for idx in range(K_MAX_N)]))

    for name, ref_values, actual_values in series:
        max_abs_error = max(abs(actual - ref) for ref, actual in zip(ref_values, actual_values))
        rms_error = (
            sum((actual - ref) * (actual - ref) for ref, actual in zip(ref_values, actual_values)) / max(len(ref_values), 1)
        ) ** 0.5
        rows.append({"series": name, "max_abs_error": max_abs_error, "rms_error": rms_error})
    return rows


def state_to_reference(state: StepState) -> dict[str, object]:
    return {
        "phi": [float(state.phi1[idx] + state.phi2[idx]) for idx in range(K_MAX_N)],
        "fuel_temp": [float(state.fuel[idx]) for idx in range(K_MAX_N)],
        "graphite_temp": [float(state.graphite[idx]) for idx in range(K_MAX_N)],
        "C": [
            [float(state.C[group][idx]) for idx in range(K_MAX_N)]
            for group in range(K_PRECURSOR_GROUPS)
        ],
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    headers = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def build_report(
    path: Path,
    runner_values: dict[str, float],
    plain_cpp: dict[str, object],
    same_init_plain: dict[str, object],
    python_reference: dict[str, object],
    same_init_metric_rows: list[dict[str, object]],
    metric_rows: list[dict[str, object]],
    same_init_state_rows: list[dict[str, object]],
    state_rows: list[dict[str, object]],
    csynth: dict[str, object] | None,
    point_kinetics_solver: int,
) -> None:
    full_program_speedup = plain_cpp["elapsed_s"] * 1.0e6 / runner_values["timing.total.avg_us"]
    same_init_speedup = same_init_plain["runner_values"]["timing.total.avg_us"] / runner_values["timing.total.avg_us"]
    lines = [
        "# Resident Transient Batch Benchmark",
        "",
        "## CPU Baselines",
        "",
        f"- Point kinetics solver macro: `MSR_POINT_KINETICS_SOLVER={point_kinetics_solver}`",
        f"- Plain C++ total wall time: `{plain_cpp['elapsed_s']:.6f} s`",
        f"- Plain C++ per-step wall time: `{plain_cpp['elapsed_s'] * 1.0e6 / runner_values['timing.step_count']:.3f} us`",
        f"- Resident batch vs full-program plain C++ speedup: `{full_program_speedup:.3f}x`",
        f"- Same-init plain C++ total avg: `{same_init_plain['runner_values']['timing.total.avg_us']:.3f} us`",
        f"- Same-init plain C++ per-step avg: `{same_init_plain['runner_values']['timing.per_step.avg_us']:.3f} us`",
        f"- Resident batch vs same-init plain C++ speedup: `{same_init_speedup:.3f}x`",
        "",
        "## Batch Runner",
        "",
        f"- Resident batch CPU proxy total avg: `{runner_values['timing.total.avg_us']:.3f} us`",
        f"- Resident batch CPU proxy per-step avg: `{runner_values['timing.per_step.avg_us']:.3f} us`",
        "",
        "## Final Diagnostics Error vs Same-Init Plain C++",
        "",
        "| Metric | Abs Error | Rel Error |",
        "| --- | ---: | ---: |",
    ]
    for row in same_init_metric_rows:
        lines.append(f"| `{row['metric']}` | {row['abs_error']:.6e} | {row['rel_error']:.6e} |")

    lines.extend(
        [
            "",
            "## Final Diagnostics Error vs Python Reference",
            "",
            "| Metric | Abs Error | Rel Error |",
            "| --- | ---: | ---: |",
        ]
    )
    for row in metric_rows:
        lines.append(f"| `{row['metric']}` | {row['abs_error']:.6e} | {row['rel_error']:.6e} |")

    lines.extend(
        [
            "",
            "## Final Axial State Error vs Same-Init Plain C++",
            "",
            "| Series | Max Abs Error | RMS Error |",
            "| --- | ---: | ---: |",
        ]
    )
    for row in same_init_state_rows:
        lines.append(f"| `{row['series']}` | {row['max_abs_error']:.6e} | {row['rms_error']:.6e} |")

    lines.extend(
        [
            "",
            "## Final Axial State Error vs Python Reference",
            "",
            "| Series | Max Abs Error | RMS Error |",
            "| --- | ---: | ---: |",
        ]
    )
    for row in state_rows:
        lines.append(f"| `{row['series']}` | {row['max_abs_error']:.6e} | {row['rms_error']:.6e} |")

    if csynth is not None and csynth["lat_min"] is not None and csynth["lat_max"] is not None and csynth["estimated_clock_ns"] is not None:
        hls_mid_cycles = 0.5 * (csynth["lat_min"] + csynth["lat_max"])
        hls_mid_us = hls_mid_cycles * csynth["estimated_clock_ns"] / 1000.0
        speedup = plain_cpp["elapsed_s"] * 1.0e6 / hls_mid_us
        lines.extend(
            [
                "",
                "## FPGA Estimate",
                "",
                f"- HLS latency: `{csynth['lat_min']}..{csynth['lat_max']}` cycles",
                f"- Estimated clock: `{csynth['estimated_clock_ns']:.3f} ns`",
                f"- Estimated total FPGA time: `{hls_mid_us:.3f} us`",
                f"- FPGA vs plain C++ speedup: `{speedup:.3f}x`",
                f"- Resources: `LUT={csynth['resources']['LUT']}`, `FF={csynth['resources']['FF']}`, `DSP={csynth['resources']['DSP']}`, `BRAM_18K={csynth['resources']['BRAM_18K']}`",
            ]
        )

    path.write_text("\n".join(lines), encoding="utf-8")


def diag_to_metrics(diag: StepDiagnostics) -> dict[str, float]:
    return {
        "phi_mid": float(diag.phi_mid),
        "rho": float(diag.rho),
        "power": float(diag.power),
        "fuel_mid": float(diag.fuel_mid),
        "graphite_mid": float(diag.graphite_mid),
        "core_inlet": float(diag.core_inlet),
        "core_outlet": float(diag.core_outlet),
        "hx1_hot_outlet": float(diag.hx1_hot_outlet),
        "hx1_cold_outlet": float(diag.hx1_cold_outlet),
        "hx2_hot_outlet": float(diag.hx2_hot_outlet),
        "hx2_cold_outlet": float(diag.hx2_cold_outlet),
        "brayton_return": float(diag.brayton_return),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark resident transient batch kernel against plain C++.")
    parser.add_argument("--out-dir", type=Path, default=VITIS_DIR / "analysis_artifacts" / "transient_batch_bench_20260618")
    parser.add_argument("--steps", type=int, default=600)
    parser.add_argument("--hardware-substeps", type=int, default=1)
    parser.add_argument("--insertion-pcm", type=float, default=250.0)
    parser.add_argument("--insertion-time-s", type=float, default=300.0)
    parser.add_argument("--runner-repeats", type=int, default=1)
    parser.add_argument("--runner-warmup", type=int, default=0)
    parser.add_argument("--csynth", type=Path, default=Path("/private/tmp/msr_transient_batch_bench_600x1_csynth.xml"))
    parser.add_argument("--point-kinetics-solver", type=int, default=0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    params = generate_parameters(N=200, outer_dt=1.0, steady_state_steps=180, use_steady_state_initialization=True)
    params["reactivity_insertion_pcm"] = args.insertion_pcm
    params["reactivity_insertion_time_s"] = args.insertion_time_s

    state = make_step_state(params)
    delays = make_delay_bundle(params)
    kernel_params = msr_vcu118_host.create_model_kernel_params(params, hardware_substeps=args.hardware_substeps)
    rod_positions, external_reactivities = make_control_arrays(
        step_count=args.steps,
        outer_dt=float(params["outer_dt"]),
        insertion_pcm=args.insertion_pcm,
        insertion_time_s=args.insertion_time_s,
    )

    state_path = args.out_dir / "states.bin"
    delays_path = args.out_dir / "delays.bin"
    params_path = args.out_dir / "params.bin"
    rod_path = args.out_dir / "rod_positions.bin"
    rho_path = args.out_dir / "external_reactivities.bin"
    final_state_path = args.out_dir / "final_states.bin"
    final_diag_path = args.out_dir / "final_diags.bin"
    plain_same_init_state_path = args.out_dir / "plain_same_init_final_states.bin"
    plain_same_init_diag_path = args.out_dir / "plain_same_init_final_diags.bin"
    runner_bin = args.out_dir / "msr_transient_batch_sw_timed"
    plain_same_init_runner_bin = args.out_dir / "msr_transient_batch_plain_timed"

    write_blob(state_path, msr_vcu118_host.struct_bytes(state))
    write_blob(delays_path, msr_vcu118_host.struct_bytes(delays))
    write_blob(params_path, msr_vcu118_host.struct_bytes(kernel_params))
    rod_path.write_bytes(b"".join(struct.pack("<d", value) for value in rod_positions))
    rho_path.write_bytes(b"".join(struct.pack("<d", value) for value in external_reactivities))

    compile_batch_runner(runner_bin, hardware_substeps=args.hardware_substeps, point_kinetics_solver=args.point_kinetics_solver)
    compile_same_init_plain_runner(
        plain_same_init_runner_bin,
        hardware_substeps=args.hardware_substeps,
        point_kinetics_solver=args.point_kinetics_solver,
    )
    runner_cmd = [
        str(runner_bin),
        str(state_path),
        str(delays_path),
        str(params_path),
        str(rod_path),
        str(rho_path),
        str(args.steps),
        "1",
        str(args.runner_repeats),
        str(args.runner_warmup),
        str(final_state_path),
        str(final_diag_path),
    ]
    runner_completed = subprocess.run(runner_cmd, check=True, capture_output=True, text=True, cwd=REPO_ROOT)
    runner_values = parse_key_value_output(runner_completed.stdout)

    plain_same_init_cmd = [
        str(plain_same_init_runner_bin),
        str(state_path),
        str(delays_path),
        str(params_path),
        str(rod_path),
        str(rho_path),
        str(args.steps),
        "1",
        str(args.runner_repeats),
        str(args.runner_warmup),
        str(plain_same_init_state_path),
        str(plain_same_init_diag_path),
    ]
    plain_same_init_completed = subprocess.run(
        plain_same_init_cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    plain_same_init_values = parse_key_value_output(plain_same_init_completed.stdout)

    final_state = read_struct_array(final_state_path, StepState, 1)[0]
    final_diag = read_struct_array(final_diag_path, StepDiagnostics, 1)[0]
    plain_same_init_state = read_struct_array(plain_same_init_state_path, StepState, 1)[0]
    plain_same_init_diag = read_struct_array(plain_same_init_diag_path, StepDiagnostics, 1)[0]

    plain_cpp = run_plain_cpp(
        steps=args.steps,
        insertion_pcm=args.insertion_pcm,
        insertion_time_s=args.insertion_time_s,
        out_dir=args.out_dir / "plain_cpp",
    )
    python_reference = run_python_reference(
        params=params,
        steps=args.steps,
        insertion_pcm=args.insertion_pcm,
        insertion_time_s=args.insertion_time_s,
    )

    actual_metrics = diag_to_metrics(final_diag)
    plain_same_init_metrics = diag_to_metrics(plain_same_init_diag)
    same_init_metric_rows = compare_metrics(plain_same_init_metrics, actual_metrics)
    metric_rows = compare_metrics(python_reference["final"], actual_metrics)
    same_init_state_rows = compare_state(state_to_reference(plain_same_init_state), final_state)
    state_rows = compare_state(python_reference["axial"], final_state)

    csynth = parse_csynth_summary(args.csynth) if args.csynth.exists() else None

    write_csv(args.out_dir / "final_metric_compare.csv", metric_rows)
    write_csv(args.out_dir / "final_state_compare.csv", state_rows)

    summary = {
        "runner_stdout": runner_completed.stdout,
        "runner_values": runner_values,
        "plain_cpp": plain_cpp,
        "plain_same_init_stdout": plain_same_init_completed.stdout,
        "plain_same_init": {
            "runner_values": plain_same_init_values,
            "final": plain_same_init_metrics,
        },
        "python_reference": python_reference,
        "same_init_metric_rows": same_init_metric_rows,
        "metric_rows": metric_rows,
        "same_init_state_rows": same_init_state_rows,
        "state_rows": state_rows,
        "csynth": csynth,
        "point_kinetics_solver": args.point_kinetics_solver,
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    build_report(
        args.out_dir / "report.md",
        runner_values,
        plain_cpp,
        summary["plain_same_init"],
        python_reference,
        same_init_metric_rows,
        metric_rows,
        same_init_state_rows,
        state_rows,
        csynth,
        args.point_kinetics_solver,
    )

    print(f"Wrote analysis to: {args.out_dir}")
    print(f"Report: {args.out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
