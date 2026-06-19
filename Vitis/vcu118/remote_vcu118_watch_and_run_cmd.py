#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VITIS_DIR = REPO_ROOT / "Vitis"
DEFAULT_LOCAL_OUT_ROOT = VITIS_DIR / "analysis_artifacts" / "remote_vcu118_board_runs_cmd"
PROGRAM_RE = re.compile(r"PROGRAM_TIMING DURATION_MS=(?P<value>\S+)")
PLAN_RE = re.compile(r"PLAN_TIMING DURATION_MS=(?P<value>\S+)")
KERNEL_RE = re.compile(r"KERNEL_TIMING LABEL=(?P<label>\S+) .* TOTAL_MS=(?P<value>\S+)")


def run_command(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=str(REPO_ROOT), text=True, capture_output=True, check=False)


def clean_expect_output(text: str) -> str:
    lines = []
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if line.startswith("spawn "):
            continue
        if "password:" in line:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def ssh_cmd(expect_path: Path, remote_cmd: str, allow_nonzero: bool = False) -> str:
    result = run_command(["expect", str(expect_path), remote_cmd])
    output = clean_expect_output(result.stdout)
    if result.returncode != 0 and not allow_nonzero:
        raise RuntimeError(f"remote command failed with exit code {result.returncode}: {remote_cmd}\n{output}\n{result.stderr.strip()}")
    return output


def scp_from(expect_path: Path, remote_host: str, remote_path: str, local_path: Path) -> None:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    remote_posix_path = remote_path.replace("\\", "/")
    result = run_command(["expect", str(expect_path), f"{remote_host}:{remote_posix_path}", str(local_path)])
    output = clean_expect_output(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(f"scp failed with exit code {result.returncode}\n{output}\n{result.stderr.strip()}")


def cmd_if_exists(path: str, marker: str) -> str:
    return f'cmd /c "if exist {path} echo {marker}"'


def cmd_find(path: str, word: str) -> str:
    return f'cmd /c "if exist {path} findstr /I {word} {path}"'


def decode_final_diagnostics(input_path: Path) -> dict[str, object]:
    result = run_command([
        sys.executable,
        str(VITIS_DIR / "vcu118" / "msr_transient_batch_vcu118_host.py"),
        "decode-final-diagnostics",
        "--input",
        str(input_path),
    ])
    if result.returncode != 0:
        raise RuntimeError(f"diagnostics decode failed\n{result.stdout}\n{result.stderr}")
    return json.loads(result.stdout)


def parse_timing(text: str) -> dict[str, object]:
    timings: dict[str, object] = {"kernels": {}}
    program = PROGRAM_RE.search(text)
    if program:
        timings["program_ms"] = float(program.group("value"))
    plan = PLAN_RE.search(text)
    if plan:
        timings["plan_ms"] = float(plan.group("value"))
    for match in KERNEL_RE.finditer(text):
        timings["kernels"][match.group("label")] = float(match.group("value"))
    return timings


def choose_output_dir(root: Path) -> Path:
    out = root / datetime.now().strftime("%Y%m%d_%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="CMD-only remote watcher for VCU118 Vivado build and JTAG timing run.")
    parser.add_argument("--remote-host", default="yuyao@10.231.225.121")
    parser.add_argument("--ssh-expect", default="/tmp/codex_ssh_run.expect")
    parser.add_argument("--scp-expect", default="/tmp/codex_scp.expect")
    parser.add_argument("--remote-build-root", default=r"C:\Users\yuyao\w\b7t1")
    parser.add_argument("--remote-helper-bat", default=r"C:\Users\yuyao\w\vcu118\windows_vivado_run_jtag_axi_host.bat")
    parser.add_argument("--remote-plan", default=r"C:\Users\yuyao\w\tbv_b7t1_snapshot\resident_batch_plan.tcl")
    parser.add_argument("--remote-diagnostics", default=r"C:\Users\yuyao\w\tbv_b7t1_snapshot\tb_final_diagnostics_out.hex32")
    parser.add_argument("--poll-sec", type=int, default=300)
    parser.add_argument("--local-out-root", default=str(DEFAULT_LOCAL_OUT_ROOT))
    args = parser.parse_args()

    ssh_expect = Path(args.ssh_expect)
    scp_expect = Path(args.scp_expect)
    out_dir = choose_output_dir(Path(args.local_out_root).resolve())
    status_log = out_dir / "status.log"
    bit = rf"{args.remote_build_root}\outputs\tbv.bit"
    ltx = rf"{args.remote_build_root}\outputs\tbv.ltx"
    batch_log = rf"{args.remote_build_root}\tbv\tbv.runs\tb_batch_0_0_synth_1\runme.log"
    synth1_log = rf"{args.remote_build_root}\tbv\tbv.runs\synth_1\runme.log"

    print(f"Local output directory: {out_dir}")
    print(f"Polling remote build root: {args.remote_build_root}")
    poll = 0
    while True:
        poll += 1
        stamp = datetime.now().isoformat(timespec="seconds")
        bit_ready = "BIT_READY" in ssh_cmd(ssh_expect, cmd_if_exists(bit, "BIT_READY"))
        ltx_ready = "LTX_READY" in ssh_cmd(ssh_expect, cmd_if_exists(ltx, "LTX_READY"))
        synth1_ready = "SYNTH1_LOG_READY" in ssh_cmd(ssh_expect, cmd_if_exists(synth1_log, "SYNTH1_LOG_READY"))
        tasklist = ssh_cmd(ssh_expect, 'cmd /c "tasklist | findstr /I vivado.exe"')
        failed = ssh_cmd(ssh_expect, cmd_find(batch_log, "failed"), allow_nonzero=True)
        errors = ssh_cmd(ssh_expect, cmd_find(batch_log, "ERROR"), allow_nonzero=True)
        memory = ssh_cmd(ssh_expect, cmd_find(batch_log, "memory"), allow_nonzero=True)
        status = {
            "poll": poll,
            "timestamp": stamp,
            "bit_ready": bit_ready,
            "ltx_ready": ltx_ready,
            "synth1_ready": synth1_ready,
            "tasklist": tasklist,
            "failed_lines": failed,
            "error_lines": errors,
            "memory_lines": memory,
        }
        with status_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(status, ensure_ascii=True) + "\n")
        print(json.dumps(status, ensure_ascii=True, indent=2))
        sys.stdout.flush()

        if bit_ready and ltx_ready:
            break
        if "out of memory" in (failed + "\n" + errors).lower() or "synth_design failed" in failed.lower():
            raise RuntimeError("Vivado synthesis failure detected; see status log.")
        time.sleep(args.poll_sec)

    board_cmd = f'cmd /c "{args.remote_helper_bat} {args.remote_plan}"'
    board_output = ssh_cmd(ssh_expect, board_cmd)
    board_log = out_dir / "board_run.log"
    board_log.write_text(board_output + "\n", encoding="utf-8")

    diag_hex = out_dir / "tb_final_diagnostics_out.hex32"
    scp_from(scp_expect, args.remote_host, args.remote_diagnostics, diag_hex)
    diagnostics = decode_final_diagnostics(diag_hex)
    summary = {
        "remote_build_root": args.remote_build_root,
        "remote_plan": args.remote_plan,
        "timings": parse_timing(board_output),
        "diagnostics": diagnostics,
        "artifacts": {
            "status_log": str(status_log),
            "board_run_log": str(board_log),
            "diagnostics_hex32": str(diag_hex),
        },
    }
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("SUMMARY_JSON=" + str(summary_path))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
