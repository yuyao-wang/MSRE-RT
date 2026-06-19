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
DEFAULT_LOCAL_OUT_ROOT = REPO_ROOT / "vitis" / "analysis_artifacts" / "remote_vcu118_board_runs"
TIMING_PATTERNS = {
    "program_ms": re.compile(r"PROGRAM_TIMING DURATION_MS=(?P<value>\S+)"),
    "plan_ms": re.compile(r"PLAN_TIMING DURATION_MS=(?P<value>\S+)"),
}
KERNEL_PATTERN = re.compile(r"KERNEL_TIMING LABEL=(?P<label>\S+) .* TOTAL_MS=(?P<value>\S+)")
WRITE_PATTERN = re.compile(r"WRITE_TIMING LABEL=(?P<label>\S+) .* DURATION_MS=(?P<value>\S+)")
READ_PATTERN = re.compile(r"READ_TIMING LABEL=(?P<label>\S+) .* DURATION_MS=(?P<value>\S+)")


def run_command(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )


def expect_ssh(expect_path: Path, remote_command: str) -> subprocess.CompletedProcess[str]:
    return run_command(["expect", str(expect_path), remote_command], cwd=REPO_ROOT)


def expect_scp_from(expect_path: Path, remote_spec: str, local_path: Path) -> subprocess.CompletedProcess[str]:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    return run_command(["expect", str(expect_path), remote_spec, str(local_path)], cwd=REPO_ROOT)


def clean_expect_output(text: str) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("spawn "):
            continue
        if "password:" in line:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def make_status_command(build_root: str) -> str:
    synth_log = rf"{build_root}\tbv\tbv.runs\tb_batch_0_0_synth_1\runme.log"
    top_log = rf"{build_root}\tbv\tbv.runs\synth_1\runme.log"
    impl_log = rf"{build_root}\tbv\tbv.runs\impl_1\runme.log"
    bit_path = rf"{build_root}\outputs\tbv.bit"
    ltx_path = rf"{build_root}\outputs\tbv.ltx"
    return (
        "powershell -NoProfile -Command "
        "\""
        f"$bit='{bit_path}'; "
        f"$ltx='{ltx_path}'; "
        f"$synth='{synth_log}'; "
        f"$top='{top_log}'; "
        f"$impl='{impl_log}'; "
        "$procs=Get-Process vivado -ErrorAction SilentlyContinue | Select-Object Id,CPU,StartTime; "
        "if ($procs) { Write-Host '--- VIVADO'; $procs | Format-Table -AutoSize }; "
        "Write-Host ('STATUS BIT=' + [int](Test-Path $bit) + ' LTX=' + [int](Test-Path $ltx)); "
        "Write-Host '--- SYNTH_SUB'; "
        "if (Test-Path $synth) { Get-Item $synth | Select-Object FullName,Length,LastWriteTime | Format-List; Get-Content -Tail 25 $synth } else { Write-Host 'SYNTH_SUB_PENDING' }; "
        "Write-Host '--- SYNTH_TOP'; "
        "if (Test-Path $top) { Get-Item $top | Select-Object FullName,Length,LastWriteTime | Format-List; Get-Content -Tail 25 $top } else { Write-Host 'SYNTH_TOP_PENDING' }; "
        "Write-Host '--- IMPL'; "
        "if (Test-Path $impl) { Get-Item $impl | Select-Object FullName,Length,LastWriteTime | Format-List; Get-Content -Tail 25 $impl } else { Write-Host 'IMPL_PENDING' }; "
        "\""
    )


def make_board_run_command(helper_bat: str, plan_file: str) -> str:
    return (
        "powershell -NoProfile -Command "
        "\""
        f"& '{helper_bat}' '{plan_file}'"
        "\""
    )


def make_decode_command(diag_path: Path) -> list[str]:
    return [
        sys.executable,
        str(REPO_ROOT / "vitis" / "vcu118" / "msr_transient_batch_vcu118_host.py"),
        "decode-final-diagnostics",
        "--input",
        str(diag_path),
    ]


def scp_remote_path(path: str) -> str:
    return path.replace("\\", "/")


def parse_status_ready(status_text: str) -> bool:
    return "STATUS BIT=1 LTX=1" in status_text


def parse_timing(stdout_text: str) -> dict[str, object]:
    result: dict[str, object] = {"kernels": {}, "writes_ms": {}, "reads_ms": {}}
    for key, pattern in TIMING_PATTERNS.items():
        match = pattern.search(stdout_text)
        if match:
            result[key] = float(match.group("value"))
    for match in KERNEL_PATTERN.finditer(stdout_text):
        result["kernels"][match.group("label")] = float(match.group("value"))
    for match in WRITE_PATTERN.finditer(stdout_text):
        result["writes_ms"][match.group("label")] = float(match.group("value"))
    for match in READ_PATTERN.finditer(stdout_text):
        result["reads_ms"][match.group("label")] = float(match.group("value"))
    return result


def ensure_success(result: subprocess.CompletedProcess[str], what: str) -> str:
    stdout = clean_expect_output(result.stdout)
    stderr = result.stderr.strip()
    if result.returncode != 0:
        parts = [f"{what} failed with exit code {result.returncode}."]
        if stdout:
            parts.append(stdout)
        if stderr:
            parts.append(stderr)
        raise RuntimeError("\n".join(parts))
    return stdout


def choose_output_dir(root: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = root / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch a remote Vivado build and immediately run the VCU118 board test when bit/ltx are ready.")
    parser.add_argument("--remote-host", default="yuyao@10.231.225.121")
    parser.add_argument("--ssh-expect", default="/tmp/codex_ssh_run.expect")
    parser.add_argument("--scp-expect", default="/tmp/codex_scp.expect")
    parser.add_argument("--remote-build-root", default=r"C:\Users\yuyao\w\b6")
    parser.add_argument("--remote-helper-bat", default=r"C:\Users\yuyao\w\vcu118\windows_vivado_run_jtag_axi_host.bat")
    parser.add_argument("--remote-plan", default=r"C:\Users\yuyao\w\tbv_b6_snapshot\resident_batch_plan.tcl")
    parser.add_argument("--remote-diagnostics", default=r"C:\Users\yuyao\w\tbv_b6_snapshot\tb_final_diagnostics_out.hex32")
    parser.add_argument("--poll-sec", type=int, default=300)
    parser.add_argument("--max-polls", type=int, default=0)
    parser.add_argument("--local-out-root", default=str(DEFAULT_LOCAL_OUT_ROOT))
    args = parser.parse_args()

    ssh_expect = Path(args.ssh_expect)
    scp_expect = Path(args.scp_expect)
    out_dir = choose_output_dir(Path(args.local_out_root).resolve())
    status_log = out_dir / "status.log"

    print(f"Local output directory: {out_dir}")
    print(f"Polling remote build root: {args.remote_build_root}")
    sys.stdout.flush()

    polls = 0
    while True:
        polls += 1
        timestamp = datetime.now().isoformat(timespec="seconds")
        status_result = expect_ssh(ssh_expect, make_status_command(args.remote_build_root))
        status_text = ensure_success(status_result, "remote status poll")
        with status_log.open("a", encoding="utf-8") as fh:
            fh.write(f"===== poll {polls} {timestamp} =====\n")
            fh.write(status_text)
            fh.write("\n")
        print(f"[{timestamp}] poll={polls} ready={parse_status_ready(status_text)}")
        print(status_text)
        sys.stdout.flush()

        if parse_status_ready(status_text):
            break
        if args.max_polls and polls >= args.max_polls:
            raise RuntimeError(f"bitstream was not ready after {polls} polls")
        time.sleep(args.poll_sec)

    board_start = datetime.now().isoformat(timespec="seconds")
    board_result = expect_ssh(ssh_expect, make_board_run_command(args.remote_helper_bat, args.remote_plan))
    board_stdout = ensure_success(board_result, "remote board run")
    board_log = out_dir / "board_run.log"
    board_log.write_text(board_stdout + "\n", encoding="utf-8")
    print(f"[{board_start}] board run completed")
    print(board_stdout)
    sys.stdout.flush()

    local_diag = out_dir / "tb_final_diagnostics_out.hex32"
    remote_diag_spec = f"{args.remote_host}:{scp_remote_path(args.remote_diagnostics)}"
    scp_result = expect_scp_from(scp_expect, remote_diag_spec, local_diag)
    ensure_success(scp_result, "diagnostics download")

    decode_result = run_command(make_decode_command(local_diag), cwd=REPO_ROOT)
    decode_stdout = decode_result.stdout.strip()
    if decode_result.returncode != 0:
        raise RuntimeError(f"diagnostics decode failed with exit code {decode_result.returncode}.\n{decode_stdout}\n{decode_result.stderr.strip()}")
    diagnostics = json.loads(decode_stdout)
    (out_dir / "final_diagnostics.json").write_text(json.dumps(diagnostics, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    timings = parse_timing(board_stdout)
    summary = {
        "remote_build_root": args.remote_build_root,
        "remote_plan": args.remote_plan,
        "poll_sec": args.poll_sec,
        "poll_count": polls,
        "timings": timings,
        "diagnostics": diagnostics,
        "artifacts": {
            "status_log": str(status_log),
            "board_run_log": str(board_log),
            "diagnostics_hex32": str(local_diag),
            "diagnostics_json": str(out_dir / "final_diagnostics.json"),
        },
    }
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("SUMMARY_JSON=" + str(summary_path))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
