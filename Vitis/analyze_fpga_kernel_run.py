#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re
import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
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
from Vitis.vcu118 import msr_vcu118_host


CATEGORY_LABELS = {
    "axi_read": "AXI-Lite read",
    "axi_write": "AXI-Lite write",
    "partselect": "PartSelect",
    "spec_interface": "SpecInterface",
    "spec_bits": "SpecBitsMap",
    "spec_top": "SpecTopModule",
    "user_call": "User call",
    "other": "Other",
}

CORE_BOUNDARY_FIELDS = [
    "rho",
    "power_W",
    "phi_mid",
    "fuel_mid_K",
    "graphite_mid_K",
    "Ts_core_inlet_K",
    "Ts_core_outlet_K",
]

BOP_BOUNDARY_FIELDS = [
    "Ts_HX1_0_K",
    "Tss_HX1_L_K",
    "Tss_HX2_0_K",
    "Tsss_HX2_L_K",
    "Tsss_pp_0_K",
]


def extract_call_target(node_text: str) -> str | None:
    match = re.search(r"call\s+(?:fastcc\s+)?(?:[^@]+)@([A-Za-z0-9_]+)(?:<[^>]+>)?(?:\(|,)", node_text)
    if not match:
        return None
    callee = match.group(1)
    if callee.startswith("_ssdm_"):
        return None
    return callee


def classify_operation(node_text: str) -> str:
    if "_ssdm_op_Read" in node_text:
        return "axi_read"
    if "_ssdm_op_Write" in node_text:
        return "axi_write"
    if "_ssdm_op_PartSelect" in node_text:
        return "partselect"
    if "_ssdm_op_SpecInterface" in node_text:
        return "spec_interface"
    if "_ssdm_op_SpecBitsMap" in node_text:
        return "spec_bits"
    if "_ssdm_op_SpecTopModule" in node_text:
        return "spec_top"
    if extract_call_target(node_text):
        return "user_call"
    return "other"


def read_hex32_words(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def decode_double_words(lo_word: str, hi_word: str) -> float:
    lo = int(lo_word, 16)
    hi = int(hi_word, 16)
    return struct.unpack("<d", struct.pack("<II", lo, hi))[0]


def decode_boundary(words: list[str], fields: list[str]) -> dict[str, float]:
    needed = len(fields) * 2
    if len(words) < needed:
        raise ValueError(f"Need {needed} words for {len(fields)} doubles, got {len(words)}")
    values = [decode_double_words(words[idx], words[idx + 1]) for idx in range(0, needed, 2)]
    return dict(zip(fields, values))


def read_log_text(path: Path) -> str:
    raw = path.read_bytes()
    if b"\x00" in raw:
        try:
            return raw.decode("utf-16le")
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


def parse_csynth_summary(path: Path) -> dict[str, object]:
    root = ET.parse(path).getroot()

    def text(xp: str, default: str = "?") -> str:
        node = root.find(xp)
        return node.text.strip() if node is not None and node.text is not None else default

    def maybe_int(value: str) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def maybe_float(value: str) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    dsp_value = text("./AreaEstimates/Resources/DSP48E")
    if dsp_value == "?":
        dsp_value = text("./AreaEstimates/Resources/DSP")

    lat_min_raw = text("./PerformanceEstimates/SummaryOfOverallLatency/Best-caseLatency", "0")
    lat_max_raw = text("./PerformanceEstimates/SummaryOfOverallLatency/Worst-caseLatency", "0")
    estimated_clock_raw = text("./PerformanceEstimates/SummaryOfTimingAnalysis/EstimatedClockPeriod", "0")
    target_clock_raw = text("./UserAssignments/TargetClockPeriod", "0")

    return {
        "lat_min": maybe_int(lat_min_raw),
        "lat_max": maybe_int(lat_max_raw),
        "lat_min_raw": lat_min_raw,
        "lat_max_raw": lat_max_raw,
        "ii": text("./PerformanceEstimates/SummaryOfOverallLatency/PipelineInitiationInterval"),
        "pipeline": text("./PerformanceEstimates/SummaryOfOverallLatency/PipelineType"),
        "estimated_clock_ns": maybe_float(estimated_clock_raw),
        "estimated_clock_raw": estimated_clock_raw,
        "target_clock_ns": maybe_float(target_clock_raw),
        "target_clock_raw": target_clock_raw,
        "resources": {
            "BRAM_18K": text("./AreaEstimates/Resources/BRAM_18K"),
            "DSP": dsp_value,
            "FF": text("./AreaEstimates/Resources/FF"),
            "LUT": text("./AreaEstimates/Resources/LUT"),
            "URAM": text("./AreaEstimates/Resources/URAM"),
        },
    }


def parse_sched(path: Path) -> dict[str, object]:
    root = ET.parse(path).getroot()
    states = []
    for order_idx, state in enumerate(root.findall("./state_list/state"), start=1):
        operations = []
        categories = Counter()
        calls = Counter()
        for op_idx, op in enumerate(state.findall("operation"), start=1):
            node_text = " ".join((op.findtext("Node") or "").split())
            category = classify_operation(node_text)
            callee = extract_call_target(node_text)
            categories[category] += 1
            if callee:
                calls[callee] += 1
            operations.append(
                {
                    "op_index": op_idx,
                    "category": category,
                    "category_label": CATEGORY_LABELS.get(category, category),
                    "callee": callee or "",
                    "node_text": node_text,
                }
            )
        states.append(
            {
                "state_order": order_idx,
                "id": state.attrib.get("id", "?"),
                "st_id": state.attrib.get("st_id", "?"),
                "op_count": len(operations),
                "categories": categories,
                "calls": calls,
                "operations": operations,
            }
        )
    return {
        "name": root.findtext("name", default=path.stem),
        "state_count": len(states),
        "states": states,
    }


def export_schedule_csvs(schedule_path: Path, out_dir: Path) -> dict[str, str]:
    schedule = parse_sched(schedule_path)
    stem = schedule_path.name.replace(".sched.adb.xml", "")
    states_csv = out_dir / f"{stem}_states.csv"
    ops_csv = out_dir / f"{stem}_operations.csv"
    cycle_csv = out_dir / f"{stem}_cycle_trace.csv"

    with states_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["schedule_name", "state_order", "state_id", "st_id", "op_count", "categories", "calls"],
        )
        writer.writeheader()
        for state in schedule["states"]:
            writer.writerow(
                {
                    "schedule_name": schedule["name"],
                    "state_order": state["state_order"],
                    "state_id": state["id"],
                    "st_id": state["st_id"],
                    "op_count": state["op_count"],
                    "categories": json.dumps(dict(state["categories"]), sort_keys=True),
                    "calls": json.dumps(dict(state["calls"]), sort_keys=True),
                }
            )

    with ops_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "schedule_name",
                "state_order",
                "state_id",
                "st_id",
                "op_index",
                "category",
                "category_label",
                "callee",
                "node_text",
            ],
        )
        writer.writeheader()
        for state in schedule["states"]:
            for op in state["operations"]:
                writer.writerow(
                    {
                        "schedule_name": schedule["name"],
                        "state_order": state["state_order"],
                        "state_id": state["id"],
                        "st_id": state["st_id"],
                        "op_index": op["op_index"],
                        "category": op["category"],
                        "category_label": op["category_label"],
                        "callee": op["callee"],
                        "node_text": op["node_text"],
                    }
                )

    with cycle_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "schedule_name",
                "cycle_index",
                "state_id",
                "st_id",
                "op_count",
                "categories",
                "calls",
                "operators",
            ],
        )
        writer.writeheader()
        for state in schedule["states"]:
            operators = []
            for op in state["operations"]:
                operators.append(f"{op['category']}:{op['callee']}" if op["callee"] else op["category"])
            writer.writerow(
                {
                    "schedule_name": schedule["name"],
                    "cycle_index": state["state_order"],
                    "state_id": state["id"],
                    "st_id": state["st_id"],
                    "op_count": state["op_count"],
                    "categories": json.dumps(dict(state["categories"]), sort_keys=True),
                    "calls": json.dumps(dict(state["calls"]), sort_keys=True),
                    "operators": " | ".join(operators),
                }
            )

    return {
        "schedule_name": str(schedule["name"]),
        "state_count": str(schedule["state_count"]),
        "states_csv": str(states_csv),
        "operations_csv": str(ops_csv),
        "cycle_csv": str(cycle_csv),
    }


def parse_plan_inputs(path: Path) -> dict[str, float]:
    text = path.read_text(encoding="utf-8")

    def capture(label: str, pattern: str) -> dict[str, float]:
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            raise ValueError(f"Unable to parse {label} inputs from {path}")
        values = [decode_double_words(match.group(idx), match.group(idx + 1)) for idx in range(1, match.lastindex + 1, 2)]
        return values

    core_vals = capture(
        "core",
        r"\{run_kernel core .*?\{0x28 \{([0-9A-F]+) ([0-9A-F]+)\}\} "
        r"\{0x34 \{([0-9A-F]+) ([0-9A-F]+)\}\} "
        r"\{0x40 \{([0-9A-F]+) ([0-9A-F]+)\}\}",
    )
    bop_vals = capture(
        "bop",
        r"\{run_kernel bop .*?\{0x28 \{([0-9A-F]+) ([0-9A-F]+)\}\} "
        r"\{0x34 \{([0-9A-F]+) ([0-9A-F]+)\}\} "
        r"\{0x40 \{([0-9A-F]+) ([0-9A-F]+)\}\} "
        r"\{0x4C \{([0-9A-F]+) ([0-9A-F]+)\}\}",
    )
    return {
        "Ts_core_inlet_K": core_vals[0],
        "rod_position": core_vals[1],
        "external_reactivity": core_vals[2],
        "Ts_HX1_L_K": bop_vals[0],
        "Tss_HX1_0_K": bop_vals[1],
        "Tss_HX2_L_K": bop_vals[2],
        "Tsss_HX2_0_K": bop_vals[3],
    }


def parse_status_log(path: Path) -> dict[str, object]:
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.*)", line.strip())
        if not match:
            continue
        entries.append((datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S"), match.group(2)))
    start_idx = 0
    for idx, (_, message) in enumerate(entries):
        if message == "START clean snapshot retry":
            start_idx = idx
    entries = entries[start_idx:]
    result: dict[str, object] = {}
    if entries:
        result["first_timestamp"] = entries[0][0].isoformat(sep=" ")
        result["last_timestamp"] = entries[-1][0].isoformat(sep=" ")
        result["total_seconds"] = (entries[-1][0] - entries[0][0]).total_seconds()
    for _, message in entries:
        if "=" in message:
            key, value = message.split("=", 1)
            result[key] = value
    return result


def parse_run_log(path: Path) -> dict[str, object]:
    result: dict[str, object] = {"kernel_timings": {}, "write_timings": [], "read_timings": []}
    text = read_log_text(path).replace("\x00", "")

    for match in re.finditer(
        r"KERNEL_TIMING LABEL=(\w+) REG_WRITE_MS=([0-9.]+) AP_START_WRITE_MS=([0-9.]+) "
        r"EXEC_WAIT_MS=([0-9.]+) TOTAL_MS=([0-9.]+) POLLS=(\d+) FINAL_AP_CTRL=(0x[0-9A-F]+)",
        text,
    ):
        result["kernel_timings"][match.group(1)] = {
            "reg_write_ms": float(match.group(2)),
            "ap_start_write_ms": float(match.group(3)),
            "exec_wait_ms": float(match.group(4)),
            "total_ms": float(match.group(5)),
            "polls": int(match.group(6)),
            "final_ap_ctrl": match.group(7),
        }

    for match in re.finditer(
        r"WRITE_TIMING BASE=(0x[0-9A-F]+) WORDS=(\d+) DURATION_MS=([0-9.]+)",
        text,
    ):
        result["write_timings"].append(
            {
                "base": match.group(1),
                "words": int(match.group(2)),
                "duration_ms": float(match.group(3)),
            }
        )

    for match in re.finditer(
        r"READ_TIMING BASE=(0x[0-9A-F]+) WORDS=(\d+) DURATION_MS=([0-9.]+)",
        text,
    ):
        result["read_timings"].append(
            {
                "base": match.group(1),
                "words": int(match.group(2)),
                "duration_ms": float(match.group(3)),
            }
        )

    for label in ("PROGRAM_TIMING", "HW_OPEN_TIMING", "PLAN_TIMING"):
        match = re.search(rf"{label} DURATION_MS=([0-9.]+)", text)
        if match:
            result[label.lower()] = float(match.group(1))

    return result


def build_python_reference() -> dict[str, float]:
    params = generate_parameters(N=200, outer_dt=1.0, steady_state_steps=180, use_steady_state_initialization=True)
    run = run_coupled_transient(params, 1, diagnostic_mode="state")
    return extract_python_reference(run, params)


def extract_python_reference(run: dict[str, object], params: dict[str, object]) -> dict[str, float]:
    return {
        "rho": 0.0,
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


def run_python_reference_timed(repeats: int, warmup: int) -> dict[str, object]:
    base_params = generate_parameters(N=200, outer_dt=1.0, steady_state_steps=180, use_steady_state_initialization=True)
    samples_us = []
    last_reference = None

    for iter_idx in range(warmup + repeats):
        params = copy.deepcopy(base_params)
        start = time.perf_counter()
        run = run_coupled_transient(params, 1, diagnostic_mode="state")
        elapsed_us = (time.perf_counter() - start) * 1.0e6
        if iter_idx >= warmup:
            samples_us.append(elapsed_us)
            last_reference = extract_python_reference(run, params)

    if not samples_us or last_reference is None:
        raise RuntimeError("python reference timing did not produce any samples")

    return {
        "reference": last_reference,
        "timing": {
            "repeats": repeats,
            "warmup": warmup,
            "min_us": min(samples_us),
            "max_us": max(samples_us),
            "avg_us": sum(samples_us) / len(samples_us),
        },
    }


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prepare_cpu_snapshot(
    out_dir: Path,
    core_state_hex: Path,
    core_params_hex: Path,
    bop_state_hex: Path,
    bop_params_hex: Path,
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for name, src in (
        ("core_state", core_state_hex),
        ("core_params", core_params_hex),
        ("bop_state", bop_state_hex),
        ("bop_params", bop_params_hex),
    ):
        blob = msr_vcu118_host.read_hex32_file(src)
        bin_path = out_dir / f"{name}.bin"
        bin_path.write_bytes(blob)
        artifacts[name] = {
            "hex_path": str(src),
            "bin_path": str(bin_path),
            "size_bytes": len(blob),
            "sha256": sha256_hex(blob),
        }
    return artifacts


def compile_cpu_runner(source_path: Path, binary_path: Path) -> None:
    compile_cmd = [
        "c++",
        "-O3",
        "-DNDEBUG",
        "-std=c++17",
        "-DMSR_MAX_STATE_N=200",
        "-DMSR_FIXED_CORE_N=200",
        "-DMSR_FIXED_BOP_NX=200",
        "-DMSR_FIXED_HARDWARE_SUBSTEPS=1",
        str(source_path),
        "-o",
        str(binary_path),
    ]
    subprocess.run(compile_cmd, check=True, cwd=REPO_ROOT)


def parse_key_value_output(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def run_cpu_runner(
    binary_path: Path,
    snapshot_dir: Path,
    plan_inputs: dict[str, float],
    repeats: int,
    warmup: int,
) -> dict[str, object]:
    cmd = [
        str(binary_path),
        str(snapshot_dir / "core_state.bin"),
        str(snapshot_dir / "core_params.bin"),
        str(snapshot_dir / "bop_state.bin"),
        str(snapshot_dir / "bop_params.bin"),
        str(plan_inputs["Ts_core_inlet_K"]),
        str(plan_inputs["rod_position"]),
        str(plan_inputs["external_reactivity"]),
        str(plan_inputs["Ts_HX1_L_K"]),
        str(plan_inputs["Tss_HX1_0_K"]),
        str(plan_inputs["Tss_HX2_L_K"]),
        str(plan_inputs["Tsss_HX2_0_K"]),
        str(repeats),
        str(warmup),
    ]
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=REPO_ROOT)
    parsed = parse_key_value_output(completed.stdout)
    return {
        "raw_stdout": completed.stdout,
        "timing": {
            "repeats": int(parsed["timing.repeats"]),
            "warmup": int(parsed["timing.warmup"]),
            "core_min_us": float(parsed["timing.core.min_us"]),
            "core_max_us": float(parsed["timing.core.max_us"]),
            "core_avg_us": float(parsed["timing.core.avg_us"]),
            "bop_min_us": float(parsed["timing.bop.min_us"]),
            "bop_max_us": float(parsed["timing.bop.max_us"]),
            "bop_avg_us": float(parsed["timing.bop.avg_us"]),
            "checksum": float(parsed["timing.checksum"]),
        },
        "reference": {
            "rho": float(parsed["core.rho"]),
            "power_W": float(parsed["core.power"]),
            "phi_mid": float(parsed["core.phi_mid"]),
            "fuel_mid_K": float(parsed["core.fuel_mid"]),
            "graphite_mid_K": float(parsed["core.graphite_mid"]),
            "Ts_core_inlet_K": float(parsed["core.Ts_core_inlet"]),
            "Ts_core_outlet_K": float(parsed["core.Ts_core_outlet"]),
            "Ts_HX1_0_K": float(parsed["bop.Ts_HX1_0"]),
            "Tss_HX1_L_K": float(parsed["bop.Tss_HX1_L"]),
            "Tss_HX2_0_K": float(parsed["bop.Tss_HX2_0"]),
            "Tsss_HX2_L_K": float(parsed["bop.Tsss_HX2_L"]),
            "Tsss_pp_0_K": float(parsed["bop.Tsss_pp_0"]),
        },
    }


def build_cpu_speedup_rows(
    core_csynth: dict[str, object],
    bop_csynth: dict[str, object],
    board_clock_ns: float,
    run_log: dict[str, object],
    cpu_run: dict[str, object],
) -> list[dict[str, object]]:
    rows = []
    kernel_specs = [
        ("core", core_csynth, cpu_run["timing"]["core_avg_us"]),
        ("bop", bop_csynth, cpu_run["timing"]["bop_avg_us"]),
    ]
    for label, csynth, cpu_avg_us in kernel_specs:
        hls_mid_us = ((csynth["lat_min"] + csynth["lat_max"]) * 0.5 * board_clock_ns) / 1000.0
        wait_ms = run_log.get("kernel_timings", {}).get(label, {}).get("exec_wait_ms")
        rows.append(
            {
                "kernel": label,
                "cpu_avg_us": cpu_avg_us,
                "fpga_hls_mid_us": hls_mid_us,
                "fpga_wait_us": None if wait_ms is None else wait_ms * 1000.0,
                "fpga_vs_cpu_hls_speedup": cpu_avg_us / hls_mid_us if hls_mid_us else 0.0,
                "fpga_vs_cpu_wait_speedup": None if wait_ms is None else cpu_avg_us / (wait_ms * 1000.0),
            }
        )
    total_cpu_avg_us = cpu_run["timing"]["core_avg_us"] + cpu_run["timing"]["bop_avg_us"]
    total_hls_mid_us = sum(row["fpga_hls_mid_us"] for row in rows)
    total_wait_us = None
    if all(row["fpga_wait_us"] is not None for row in rows):
        total_wait_us = sum(row["fpga_wait_us"] for row in rows if row["fpga_wait_us"] is not None)
    rows.append(
        {
            "kernel": "total_core_plus_bop",
            "cpu_avg_us": total_cpu_avg_us,
            "fpga_hls_mid_us": total_hls_mid_us,
            "fpga_wait_us": total_wait_us,
            "fpga_vs_cpu_hls_speedup": total_cpu_avg_us / total_hls_mid_us if total_hls_mid_us else 0.0,
            "fpga_vs_cpu_wait_speedup": None if total_wait_us is None else total_cpu_avg_us / total_wait_us,
        }
    )
    return rows


def build_python_speedup_rows(
    core_csynth: dict[str, object],
    bop_csynth: dict[str, object],
    board_clock_ns: float,
    run_log: dict[str, object],
    python_run: dict[str, object],
) -> list[dict[str, object]]:
    total_hls_mid_us = ((core_csynth["lat_min"] + core_csynth["lat_max"]) * 0.5 * board_clock_ns) / 1000.0
    total_hls_mid_us += ((bop_csynth["lat_min"] + bop_csynth["lat_max"]) * 0.5 * board_clock_ns) / 1000.0

    total_wait_us = None
    kernel_timings = run_log.get("kernel_timings", {})
    if "core" in kernel_timings and "bop" in kernel_timings:
        total_wait_us = 1000.0 * (
            kernel_timings["core"]["exec_wait_ms"] + kernel_timings["bop"]["exec_wait_ms"]
        )

    python_avg_us = python_run["timing"]["avg_us"]
    return [
        {
            "reference": "coupled_one_step",
            "python_avg_us": python_avg_us,
            "fpga_hls_mid_us": total_hls_mid_us,
            "fpga_wait_us": total_wait_us,
            "fpga_vs_python_hls_speedup": python_avg_us / total_hls_mid_us if total_hls_mid_us else 0.0,
            "fpga_vs_python_wait_speedup": None if total_wait_us is None else python_avg_us / total_wait_us,
        }
    ]


def parse_resource_int(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text or text == "?":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def build_hls_delta_rows(
    current_core: dict[str, object],
    current_bop: dict[str, object],
    baseline_core: dict[str, object] | None,
    baseline_bop: dict[str, object] | None,
    board_clock_ns: float,
) -> list[dict[str, object]]:
    if baseline_core is None or baseline_bop is None:
        return []

    def mid_us(summary: dict[str, object]) -> float:
        return ((summary["lat_min"] + summary["lat_max"]) * 0.5 * board_clock_ns) / 1000.0

    rows = []
    for kernel, current, baseline in (
        ("core", current_core, baseline_core),
        ("bop", current_bop, baseline_bop),
    ):
        row = {
            "kernel": kernel,
            "baseline_mid_us": mid_us(baseline),
            "current_mid_us": mid_us(current),
            "latency_ratio": mid_us(current) / mid_us(baseline) if mid_us(baseline) else 0.0,
        }
        for resource in ("LUT", "FF", "DSP", "BRAM_18K"):
            baseline_value = parse_resource_int(baseline["resources"].get(resource))
            current_value = parse_resource_int(current["resources"].get(resource))
            row[f"{resource.lower()}_ratio"] = (
                None if baseline_value in (None, 0) or current_value is None else current_value / baseline_value
            )
        rows.append(row)
    return rows


def compare_metrics(board: dict[str, float], reference: dict[str, float], metric_names: list[str]) -> list[dict[str, object]]:
    rows = []
    for name in metric_names:
        board_value = board[name]
        ref_value = reference[name]
        diff = board_value - ref_value
        rel = 0.0 if ref_value == 0 else diff / ref_value
        rows.append(
            {
                "metric": name,
                "board": board_value,
                "reference": ref_value,
                "abs_diff": diff,
                "rel_diff": rel,
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def format_float(value: float) -> str:
    return f"{value:.12f}"


def write_report(
    out_path: Path,
    plan_inputs: dict[str, float],
    status_log: dict[str, object],
    run_log: dict[str, object],
    cpu_run: dict[str, object],
    python_run: dict[str, object],
    cpu_speedup_rows: list[dict[str, object]],
    python_speedup_rows: list[dict[str, object]],
    hls_delta_rows: list[dict[str, object]],
    core_rows: list[dict[str, object]],
    bop_rows: list[dict[str, object]],
    core_cpu_rows: list[dict[str, object]],
    bop_cpu_rows: list[dict[str, object]],
    core_csynth: dict[str, object],
    bop_csynth: dict[str, object],
    board_clock_ns: float,
    schedule_exports: list[dict[str, str]],
) -> None:
    def hls_time_range_us(summary: dict[str, object]) -> tuple[float, float]:
        return (
            summary["lat_min"] * board_clock_ns / 1000.0,
            summary["lat_max"] * board_clock_ns / 1000.0,
        )

    core_time_us = hls_time_range_us(core_csynth)
    bop_time_us = hls_time_range_us(bop_csynth)
    lines = []
    lines.append("# FPGA vs Software One-Step Comparison")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append("- Board run: remote `offline_snapshot` clean retry on VCU118 split-kernel image.")
    lines.append("- CPU one-step kernel reference: local `msr_vcu118_sw_timed.cpp` compiled for `N=200`, `hardware_substeps=1` on the same snapshot bytes.")
    lines.append("- Physics reference: local `generate_parameters(..., steady_state_steps=180)` + `run_coupled_transient(..., 1)`.")
    lines.append("- Python timing below is monolithic one-step `run_coupled_transient(..., 1)` timing; it is compared against combined `core+bop` FPGA time, not per-kernel split timings.")
    lines.append("- HLS cycle summary below is from the aggressive resynthesis captured on `2026-06-17`.")
    lines.append("- The aggressive HLS resource numbers are independent per-kernel estimates. Their DSP counts sum to `7224`, which exceeds the VCU118 limit of `6840`, so they are not a simultaneous-placement claim.")
    lines.append("- Schedule state/operator CSVs are synthesis-schedule artifacts, not live on-board waveforms.")
    lines.append("")
    lines.append("## Remote Run Inputs")
    lines.append("")
    for key, value in plan_inputs.items():
        lines.append(f"- `{key}` = `{value:.12f}`")
    lines.append("")
    lines.append("## Board vs CPU Kernel")
    lines.append("")
    lines.append("| Metric | Board | CPU Kernel | Abs Diff | Rel Diff |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for row in core_cpu_rows + bop_cpu_rows:
        lines.append(
            f"| `{row['metric']}` | {row['board']:.12f} | {row['reference']:.12f} | "
            f"{row['abs_diff']:.3e} | {row['rel_diff']:.3e} |"
        )
    lines.append("")
    lines.append("## Board vs Physics Reference")
    lines.append("")
    lines.append("| Metric | Board | Physics Ref | Abs Diff | Rel Diff |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for row in core_rows + bop_rows:
        lines.append(
            f"| `{row['metric']}` | {row['board']:.12f} | {row['reference']:.12f} | "
            f"{row['abs_diff']:.3e} | {row['rel_diff']:.3e} |"
        )
    lines.append("")
    lines.append("## HLS Cycle Summary")
    lines.append("")
    lines.append("| Kernel | Latency (cycles) | HLS Est. Clock (ns) | Latency at deployed 20 ns clock (us) | LUT | FF | DSP | BRAM |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    lines.append(
        f"| `core_step_kernel_n200_s1` | {core_csynth['lat_min']}..{core_csynth['lat_max']} | "
        f"{core_csynth['estimated_clock_ns']:.3f} | "
        f"{core_time_us[0]:.3f}..{core_time_us[1]:.3f} | {core_csynth['resources']['LUT']} | "
        f"{core_csynth['resources']['FF']} | {core_csynth['resources']['DSP']} | {core_csynth['resources']['BRAM_18K']} |"
    )
    lines.append(
        f"| `bop_step_kernel_n200_s1` | {bop_csynth['lat_min']}..{bop_csynth['lat_max']} | "
        f"{bop_csynth['estimated_clock_ns']:.3f} | "
        f"{bop_time_us[0]:.3f}..{bop_time_us[1]:.3f} | {bop_csynth['resources']['LUT']} | "
        f"{bop_csynth['resources']['FF']} | {bop_csynth['resources']['DSP']} | {bop_csynth['resources']['BRAM_18K']} |"
    )
    lines.append("")
    lines.append(f"Note: the last latency column is computed as cycles × `{board_clock_ns:.1f} ns` for comparison with the deployed board clock; it is not derived from the HLS-estimated clock.")
    lines.append("")
    if hls_delta_rows:
        lines.append("## Aggressive HLS Delta vs Previous Build")
        lines.append("")
        lines.append("| Kernel | Previous HLS Mid (us) | New HLS Mid (us) | New/Prev | LUT x | FF x | DSP x | BRAM x |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        for row in hls_delta_rows:
            lut_ratio = "-" if row["lut_ratio"] is None else f"{row['lut_ratio']:.2f}x"
            ff_ratio = "-" if row["ff_ratio"] is None else f"{row['ff_ratio']:.2f}x"
            dsp_ratio = "-" if row["dsp_ratio"] is None else f"{row['dsp_ratio']:.2f}x"
            bram_ratio = "-" if row["bram_18k_ratio"] is None else f"{row['bram_18k_ratio']:.2f}x"
            lines.append(
                f"| `{row['kernel']}` | {row['baseline_mid_us']:.3f} | {row['current_mid_us']:.3f} | "
                f"{row['latency_ratio']:.4f}x | {lut_ratio} | {ff_ratio} | {dsp_ratio} | {bram_ratio} |"
            )
        lines.append("")
    lines.append("## Python vs FPGA Timing")
    lines.append("")
    lines.append("| Reference | Python Avg (us) | FPGA HLS Mid (us) | FPGA Wait (us) | FPGA/Python Speedup from HLS | FPGA/Python Speedup from Wait |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for row in python_speedup_rows:
        wait_us = "-" if row["fpga_wait_us"] is None else f"{row['fpga_wait_us']:.3f}"
        wait_speedup = "-" if row["fpga_vs_python_wait_speedup"] is None else f"{row['fpga_vs_python_wait_speedup']:.5f}x"
        lines.append(
            f"| `{row['reference']}` | {row['python_avg_us']:.3f} | {row['fpga_hls_mid_us']:.3f} | "
            f"{wait_us} | {row['fpga_vs_python_hls_speedup']:.5f}x | {wait_speedup} |"
        )
    lines.append("")
    lines.append("## Remote Host Timing")
    lines.append("")
    if status_log:
        if "total_seconds" in status_log:
            lines.append(f"- `clean_retry_status.log` total wall time: `{status_log['total_seconds']:.3f} s`")
        if "CHECK_BIT" in status_log:
            lines.append(f"- Bitstream: `{status_log['CHECK_BIT']}`")
    if cpu_run:
        lines.append(
            f"- CPU timed runner: repeats `{cpu_run['timing']['repeats']}`, warmup `{cpu_run['timing']['warmup']}`, "
            f"checksum `{cpu_run['timing']['checksum']:.6f}`"
        )
    if python_run:
        lines.append(
            f"- Python timed reference: repeats `{python_run['timing']['repeats']}`, warmup `{python_run['timing']['warmup']}`, "
            f"avg `{python_run['timing']['avg_us']:.3f} us`"
        )
    kernel_timings = run_log.get("kernel_timings", {})
    if kernel_timings:
        lines.append("")
        lines.append("| Kernel | Reg Write (ms) | AP Start Write (ms) | Exec Wait (ms) | Total (ms) | Polls |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        for label in sorted(kernel_timings):
            timing = kernel_timings[label]
            lines.append(
                f"| `{label}` | {timing['reg_write_ms']:.3f} | {timing['ap_start_write_ms']:.3f} | "
                f"{timing['exec_wait_ms']:.3f} | {timing['total_ms']:.3f} | {timing['polls']} |"
            )
    else:
        lines.append("- No `KERNEL_TIMING` lines were present in the provided run log yet.")
    lines.append("")
    lines.append("## Schedule Artifacts")
    lines.append("")
    for item in schedule_exports:
        lines.append(
            f"- `{item['schedule_name']}`: {item['state_count']} states, "
            f"states CSV `{item['states_csv']}`, ops CSV `{item['operations_csv']}`, cycle trace CSV `{item['cycle_csv']}`"
        )
    lines.append("")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare remote FPGA one-step kernel results against local software reference.")
    parser.add_argument("--board-core", type=Path, default=Path("/private/tmp/remote_snapshot_20260617/core_boundary_out_clean.hex32"))
    parser.add_argument("--board-bop", type=Path, default=Path("/private/tmp/remote_snapshot_20260617/bop_boundary_out_clean.hex32"))
    parser.add_argument("--plan", type=Path, default=Path("/private/tmp/remote_snapshot_20260617/remote_run_clean_plan.tcl"))
    parser.add_argument("--status-log", type=Path, default=Path("/private/tmp/remote_snapshot_20260617/clean_retry_status.log"))
    parser.add_argument("--run-log", type=Path, default=Path("/private/tmp/remote_snapshot_20260617/clean_retry_run.log"))
    parser.add_argument("--core-state-hex", type=Path, default=Path("/private/tmp/remote_snapshot_20260617/core_state.hex32"))
    parser.add_argument("--core-params-hex", type=Path, default=Path("/private/tmp/remote_snapshot_20260617/core_params.hex32"))
    parser.add_argument("--bop-state-hex", type=Path, default=Path("/private/tmp/remote_snapshot_20260617/bop_state.hex32"))
    parser.add_argument("--bop-params-hex", type=Path, default=Path("/private/tmp/remote_snapshot_20260617/bop_params.hex32"))
    parser.add_argument("--core-csynth", type=Path, default=Path("/private/tmp/core_step_kernel_n200_s1_csynth_aggressive_20260617.xml"))
    parser.add_argument("--core-design", type=Path, default=Path("/private/tmp/core_step_kernel_n200_s1.design.xml"))
    parser.add_argument("--core-sched", type=Path, default=Path("/private/tmp/core_step_kernel_n200_s1.sched.adb.xml"))
    parser.add_argument("--bop-csynth", type=Path, default=Path("/private/tmp/bop_step_kernel_n200_s1_csynth_aggressive_20260617.xml"))
    parser.add_argument("--bop-design", type=Path, default=Path("/private/tmp/bop_step_kernel_n200_s1.design.xml"))
    parser.add_argument("--bop-sched", type=Path, default=Path("/private/tmp/bop_step_kernel_n200_s1.sched.adb.xml"))
    parser.add_argument("--baseline-core-csynth", type=Path, default=Path("/private/tmp/core_step_kernel_n200_s1_csynth.xml"))
    parser.add_argument("--baseline-bop-csynth", type=Path, default=Path("/private/tmp/bop_step_kernel_n200_s1_csynth.xml"))
    parser.add_argument(
        "--extra-sched",
        type=Path,
        nargs="*",
        default=[
            Path("/private/tmp/cross_sections_kernel.sched.adb.xml"),
            Path("/private/tmp/neutronics_kernel.sched.adb.xml"),
            Path("/private/tmp/thermal_kernel.sched.adb.xml"),
            Path("/private/tmp/hx_kernel.sched.adb.xml"),
        ],
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=VITIS_DIR / "analysis_artifacts" / "fpga_compare_20260617",
    )
    parser.add_argument("--cpu-runner-src", type=Path, default=VITIS_DIR / "vcu118" / "msr_vcu118_sw_timed.cpp")
    parser.add_argument("--cpu-runner-bin", type=Path, default=Path("/private/tmp/msr_vcu118_sw_timed_n200_s1"))
    parser.add_argument("--cpu-snapshot-dir", type=Path, default=Path("/private/tmp/fpga_cpu_snapshot_remote_20260617"))
    parser.add_argument("--cpu-repeats", type=int, default=200)
    parser.add_argument("--cpu-warmup", type=int, default=20)
    parser.add_argument("--python-repeats", type=int, default=20)
    parser.add_argument("--python-warmup", type=int, default=2)
    parser.add_argument("--board-clock-ns", type=float, default=20.0, help="Board fabric clock period in ns.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    board_core = decode_boundary(read_hex32_words(args.board_core), CORE_BOUNDARY_FIELDS)
    board_bop = decode_boundary(read_hex32_words(args.board_bop), BOP_BOUNDARY_FIELDS)
    python_run = run_python_reference_timed(args.python_repeats, args.python_warmup)
    python_ref = python_run["reference"]
    plan_inputs = parse_plan_inputs(args.plan)
    status_log = parse_status_log(args.status_log) if args.status_log.exists() else {}
    run_log = parse_run_log(args.run_log) if args.run_log.exists() else {}
    cpu_snapshot = prepare_cpu_snapshot(
        args.cpu_snapshot_dir,
        args.core_state_hex,
        args.core_params_hex,
        args.bop_state_hex,
        args.bop_params_hex,
    )
    compile_cpu_runner(args.cpu_runner_src, args.cpu_runner_bin)
    cpu_run = run_cpu_runner(
        args.cpu_runner_bin,
        args.cpu_snapshot_dir,
        plan_inputs,
        args.cpu_repeats,
        args.cpu_warmup,
    )

    core_rows = compare_metrics(
        board_core,
        python_ref,
        ["rho", "power_W", "phi_mid", "fuel_mid_K", "graphite_mid_K", "Ts_core_outlet_K"],
    )
    bop_rows = compare_metrics(
        board_bop,
        python_ref,
        ["Ts_HX1_0_K", "Tss_HX1_L_K", "Tss_HX2_0_K", "Tsss_HX2_L_K", "Tsss_pp_0_K"],
    )
    core_cpu_rows = compare_metrics(
        board_core,
        cpu_run["reference"],
        ["rho", "power_W", "phi_mid", "fuel_mid_K", "graphite_mid_K", "Ts_core_outlet_K"],
    )
    bop_cpu_rows = compare_metrics(
        board_bop,
        cpu_run["reference"],
        ["Ts_HX1_0_K", "Tss_HX1_L_K", "Tss_HX2_0_K", "Tsss_HX2_L_K", "Tsss_pp_0_K"],
    )

    write_csv(args.out_dir / "core_numeric_compare.csv", core_rows)
    write_csv(args.out_dir / "bop_numeric_compare.csv", bop_rows)
    write_csv(args.out_dir / "core_cpu_numeric_compare.csv", core_cpu_rows)
    write_csv(args.out_dir / "bop_cpu_numeric_compare.csv", bop_cpu_rows)

    core_csynth = parse_csynth_summary(args.core_csynth)
    bop_csynth = parse_csynth_summary(args.bop_csynth)
    baseline_core_csynth = parse_csynth_summary(args.baseline_core_csynth) if args.baseline_core_csynth.exists() else None
    baseline_bop_csynth = parse_csynth_summary(args.baseline_bop_csynth) if args.baseline_bop_csynth.exists() else None
    cpu_speedup_rows = build_cpu_speedup_rows(core_csynth, bop_csynth, args.board_clock_ns, run_log, cpu_run)
    python_speedup_rows = build_python_speedup_rows(core_csynth, bop_csynth, args.board_clock_ns, run_log, python_run)
    hls_delta_rows = build_hls_delta_rows(
        core_csynth,
        bop_csynth,
        baseline_core_csynth,
        baseline_bop_csynth,
        args.board_clock_ns,
    )
    write_csv(args.out_dir / "timing_speedup_compare.csv", cpu_speedup_rows)
    write_csv(args.out_dir / "python_timing_speedup_compare.csv", python_speedup_rows)
    write_csv(args.out_dir / "hls_delta_compare.csv", hls_delta_rows)

    schedule_exports = []
    for sched_path in [args.core_sched, args.bop_sched, *args.extra_sched]:
        if sched_path.exists():
            schedule_exports.append(export_schedule_csvs(sched_path, args.out_dir))

    summary = {
        "plan_inputs": plan_inputs,
        "board_core": board_core,
        "board_bop": board_bop,
        "python_reference": python_ref,
        "python_run": python_run,
        "cpu_snapshot": cpu_snapshot,
        "cpu_run": cpu_run,
        "core_rows": core_rows,
        "bop_rows": bop_rows,
        "core_cpu_rows": core_cpu_rows,
        "bop_cpu_rows": bop_cpu_rows,
        "cpu_speedup_rows": cpu_speedup_rows,
        "python_speedup_rows": python_speedup_rows,
        "hls_delta_rows": hls_delta_rows,
        "core_csynth": core_csynth,
        "bop_csynth": bop_csynth,
        "status_log": status_log,
        "run_log": run_log,
        "schedule_exports": schedule_exports,
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    write_report(
        args.out_dir / "report.md",
        plan_inputs,
        status_log,
        run_log,
        cpu_run,
        python_run,
        cpu_speedup_rows,
        python_speedup_rows,
        hls_delta_rows,
        core_rows,
        bop_rows,
        core_cpu_rows,
        bop_cpu_rows,
        core_csynth,
        bop_csynth,
        args.board_clock_ns,
        schedule_exports,
    )

    print(f"Wrote analysis to: {args.out_dir}")
    print(f"Report: {args.out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
