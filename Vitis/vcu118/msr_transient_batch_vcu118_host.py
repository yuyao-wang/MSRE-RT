#!/usr/bin/env python3
import argparse
import ctypes
import json
import struct
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_DIR = REPO_ROOT / "python"

import sys

for path in (PYTHON_DIR, REPO_ROOT):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from parameters import generate_parameters
from Vitis.vcu118 import msr_vcu118_host


K_MAX_N = msr_vcu118_host.K_MAX_N
K_PRECURSOR_GROUPS = msr_vcu118_host.K_PRECURSOR_GROUPS
K_MAX_LOOP_HISTORY = msr_vcu118_host.K_MAX_LOOP_HISTORY
K_MAX_DELAY_SLOTS = 32

double_array = msr_vcu118_host.double_array
double_matrix = msr_vcu118_host.double_matrix


REGION_INFO = {
    "tb_control": {"base": 0x44A00000},
    "tb_states": {"base": 0x40000000, "byte_capacity": 64 * 1024},
    "tb_delays": {"base": 0x40010000, "byte_capacity": 8 * 1024},
    "tb_params": {"base": 0x40020000, "byte_capacity": 128 * 1024},
    "tb_rod_positions": {"base": 0x40040000, "byte_capacity": 8 * 1024},
    "tb_external_reactivities": {"base": 0x40050000, "byte_capacity": 8 * 1024},
    "tb_final_diagnostics": {"base": 0x40060000, "byte_capacity": 4 * 1024},
}


TB_REG_OFFSETS = {
    "states": 0x10,
    "delays": 0x1C,
    "params": 0x28,
    "rod_positions": 0x34,
    "external_reactivities": 0x40,
    "final_diagnostics": 0x4C,
}


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


def make_control_arrays(step_count: int, outer_dt: float, insertion_pcm: float, insertion_time_s: float):
    rod_positions = [0.0] * step_count
    external_reactivities = []
    magnitude = insertion_pcm * 1.0e-5
    for step in range(step_count):
        current_time = float(step) * outer_dt
        external_reactivities.append(magnitude if current_time >= insertion_time_s else 0.0)
    return rod_positions, external_reactivities


def ensure_capacity(name: str, blob: bytes) -> None:
    capacity = REGION_INFO[name]["byte_capacity"]
    if len(blob) > capacity:
        raise ValueError(f"{name} blob is {len(blob)} bytes but capacity is {capacity}")


def write_hex32_file(path: Path, blob: bytes) -> int:
    return msr_vcu118_host.write_hex32_file(path, blob)


def write_region_blob(out_dir: Path, name: str, blob: bytes) -> Path:
    ensure_capacity(name, blob)
    bin_path = out_dir / f"{name}.bin"
    hex_path = out_dir / f"{name}.hex32"
    bin_path.write_bytes(blob)
    write_hex32_file(hex_path, blob)
    return hex_path


def tcl_path(path: Path) -> str:
    text = str(path)
    if len(text) >= 2 and text[1] == ":":
        return text.replace("\\", "/")
    return str(path.resolve()).replace("\\", "/")


def make_control_entry(offset: int, words) -> str:
    words_str = " ".join(words)
    return f"{{0x{offset:02X} {{{words_str}}}}}"


def emit_plan(
    plan_path: Path,
    output_dir: Path,
    plan_root: Path,
    hex_paths: dict[str, Path],
    bitfile: str,
    ltxfile: str,
    poll_timeout_ms: int,
    poll_interval_ms: int,
    chunk_words: int,
    after_program_delay_ms: int,
) -> None:
    plan_files = {
        name: plan_root / path.name
        for name, path in hex_paths.items()
    }
    diagnostics_out = plan_root / "tb_final_diagnostics_out.hex32"
    entries = [
        make_control_entry(TB_REG_OFFSETS["states"], msr_vcu118_host.tcl_hex32_words_for_u64(REGION_INFO["tb_states"]["base"])),
        make_control_entry(TB_REG_OFFSETS["delays"], msr_vcu118_host.tcl_hex32_words_for_u64(REGION_INFO["tb_delays"]["base"])),
        make_control_entry(TB_REG_OFFSETS["params"], msr_vcu118_host.tcl_hex32_words_for_u64(REGION_INFO["tb_params"]["base"])),
        make_control_entry(
            TB_REG_OFFSETS["rod_positions"],
            msr_vcu118_host.tcl_hex32_words_for_u64(REGION_INFO["tb_rod_positions"]["base"]),
        ),
        make_control_entry(
            TB_REG_OFFSETS["external_reactivities"],
            msr_vcu118_host.tcl_hex32_words_for_u64(REGION_INFO["tb_external_reactivities"]["base"]),
        ),
        make_control_entry(
            TB_REG_OFFSETS["final_diagnostics"],
            msr_vcu118_host.tcl_hex32_words_for_u64(REGION_INFO["tb_final_diagnostics"]["base"]),
        ),
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
    {{write_region tb_states 0x{REGION_INFO["tb_states"]["base"]:08X} {{{tcl_path(plan_files["tb_states"])}}}}}
    {{write_region tb_delays 0x{REGION_INFO["tb_delays"]["base"]:08X} {{{tcl_path(plan_files["tb_delays"])}}}}}
    {{write_region tb_params 0x{REGION_INFO["tb_params"]["base"]:08X} {{{tcl_path(plan_files["tb_params"])}}}}}
    {{write_region tb_rod_positions 0x{REGION_INFO["tb_rod_positions"]["base"]:08X} {{{tcl_path(plan_files["tb_rod_positions"])}}}}}
    {{write_region tb_external_reactivities 0x{REGION_INFO["tb_external_reactivities"]["base"]:08X} {{{tcl_path(plan_files["tb_external_reactivities"])}}}}}
    {{write_region tb_final_diagnostics 0x{REGION_INFO["tb_final_diagnostics"]["base"]:08X} {{{tcl_path(plan_files["tb_final_diagnostics"])}}}}}
    {{run_kernel transient_batch 0x{REGION_INFO["tb_control"]["base"]:08X} {{{" ".join(entries)}}} {poll_timeout_ms}}}
    {{read_region tb_final_diagnostics 0x{REGION_INFO["tb_final_diagnostics"]["base"]:08X} 24 {{{tcl_path(diagnostics_out)}}}}}
}}
"""
    plan_path.write_text(content, encoding="utf-8")


def prepare_bench_snapshot(args: argparse.Namespace) -> None:
    if args.step_count != 600:
        raise ValueError("The bench kernel is fixed to step_count=600")
    if args.scenario_count != 1:
        raise ValueError("The bench kernel is fixed to scenario_count=1")

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_root = Path(args.plan_root) if args.plan_root else out_dir

    params = generate_parameters(
        N=K_MAX_N,
        outer_dt=args.outer_dt,
        steady_state_steps=args.steady_state_steps,
        use_steady_state_initialization=True,
    )
    params["reactivity_insertion_pcm"] = float(args.insertion_pcm)
    params["reactivity_insertion_time_s"] = float(args.insertion_time_s)

    state = make_step_state(params)
    delays = make_delay_bundle(params)
    kernel_params = msr_vcu118_host.create_model_kernel_params(params, hardware_substeps=args.hardware_substeps)
    rod_positions, external_reactivities = make_control_arrays(
        step_count=args.step_count,
        outer_dt=float(params["outer_dt"]),
        insertion_pcm=args.insertion_pcm,
        insertion_time_s=args.insertion_time_s,
    )
    zero_diag = StepDiagnostics()

    hex_paths = {
        "tb_states": write_region_blob(out_dir, "tb_states", msr_vcu118_host.struct_bytes(state)),
        "tb_delays": write_region_blob(out_dir, "tb_delays", msr_vcu118_host.struct_bytes(delays)),
        "tb_params": write_region_blob(out_dir, "tb_params", msr_vcu118_host.struct_bytes(kernel_params)),
        "tb_rod_positions": write_region_blob(
            out_dir,
            "tb_rod_positions",
            b"".join(struct.pack("<d", value) for value in rod_positions),
        ),
        "tb_external_reactivities": write_region_blob(
            out_dir,
            "tb_external_reactivities",
            b"".join(struct.pack("<d", value) for value in external_reactivities),
        ),
        "tb_final_diagnostics": write_region_blob(out_dir, "tb_final_diagnostics", msr_vcu118_host.struct_bytes(zero_diag)),
    }

    metadata = {
        "step_count": args.step_count,
        "scenario_count": args.scenario_count,
        "hardware_substeps": args.hardware_substeps,
        "insertion_pcm": args.insertion_pcm,
        "insertion_time_s": args.insertion_time_s,
        "state_size": ctypes.sizeof(StepState),
        "delay_size": ctypes.sizeof(DelayBundle),
        "params_size": ctypes.sizeof(msr_vcu118_host.KernelParams),
        "final_diagnostics_size": ctypes.sizeof(StepDiagnostics),
    }
    (out_dir / "layout_sizes.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    emit_plan(
        plan_path=out_dir / "resident_batch_plan.tcl",
        output_dir=out_dir,
        plan_root=plan_root,
        hex_paths=hex_paths,
        bitfile=args.bitfile or "",
        ltxfile=args.ltxfile or "",
        poll_timeout_ms=args.timeout_ms,
        poll_interval_ms=args.poll_interval_ms,
        chunk_words=args.chunk_words,
        after_program_delay_ms=args.after_program_delay_ms,
    )
    print(f"Prepared resident batch payload under: {out_dir}")
    print(f"Plan file: {out_dir / 'resident_batch_plan.tcl'}")


def decode_final_diagnostics(args: argparse.Namespace) -> None:
    input_path = Path(args.input).resolve()
    if input_path.suffix.lower() == ".hex32":
        blob = msr_vcu118_host.read_hex32_file(input_path)
    else:
        blob = input_path.read_bytes()
    needed = ctypes.sizeof(StepDiagnostics)
    if len(blob) < needed:
        raise ValueError(f"{input_path} has {len(blob)} bytes but {needed} are required")
    diag = StepDiagnostics.from_buffer_copy(blob[:needed])
    result = {field: getattr(diag, field) for field, _ in diag._fields_}
    print(json.dumps(result, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and decode VCU118 resident transient-batch payloads.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prep = subparsers.add_parser("prepare-bench-snapshot", help="Generate BRAM payloads and a JTAG-AXI plan for the fixed 600x1 resident batch kernel.")
    prep.add_argument("--out-dir", required=True)
    prep.add_argument("--plan-root", default="")
    prep.add_argument("--bitfile", default="")
    prep.add_argument("--ltxfile", default="")
    prep.add_argument("--timeout-ms", type=int, default=120000)
    prep.add_argument("--poll-interval-ms", type=int, default=20)
    prep.add_argument("--chunk-words", type=int, default=64)
    prep.add_argument("--after-program-delay-ms", type=int, default=2000)
    prep.add_argument("--outer-dt", type=float, default=1.0)
    prep.add_argument("--steady-state-steps", type=int, default=180)
    prep.add_argument("--hardware-substeps", type=int, default=32)
    prep.add_argument("--step-count", type=int, default=600)
    prep.add_argument("--scenario-count", type=int, default=1)
    prep.add_argument("--insertion-pcm", type=float, default=0.0)
    prep.add_argument("--insertion-time-s", type=float, default=300.0)
    prep.set_defaults(func=prepare_bench_snapshot)

    decode = subparsers.add_parser("decode-final-diagnostics", help="Decode a final diagnostics dump from .hex32 or .bin.")
    decode.add_argument("--input", required=True)
    decode.set_defaults(func=decode_final_diagnostics)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
