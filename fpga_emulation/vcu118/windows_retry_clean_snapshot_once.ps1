param(
    [string]$CleanBuildRoot = "C:\Users\yuyao\MSR1DPython_vitis\b_clean",
    [string]$SnapshotDir = "C:\Users\yuyao\MSR1DPython_vitis\b\offline_snapshot",
    [string]$HostDir = "C:\Users\yuyao\MSR1DPython_vitis\vcu118",
    [string]$VivadoRoot = "C:\Xilinx\Vivado\2023.2"
)

$ErrorActionPreference = "Stop"

$bitPath = Join-Path $CleanBuildRoot "outputs\msr_split_vcu118.bit"
$planPath = Join-Path $SnapshotDir "remote_run_clean_plan.tcl"
$statusLog = Join-Path $SnapshotDir "clean_retry_status.log"
$runLog = Join-Path $SnapshotDir "clean_retry_run.log"
$coreOut = Join-Path $SnapshotDir "core_boundary_out_clean.hex32"
$bopOut = Join-Path $SnapshotDir "bop_boundary_out_clean.hex32"
$vivadoBatch = Join-Path $HostDir "windows_vivado_run_jtag_axi_host.bat"
$implLog = Join-Path $CleanBuildRoot "msr_split_vcu118\msr_split_vcu118.runs\impl_1\runme.log"
$synthLog = Join-Path $CleanBuildRoot "msr_split_vcu118\msr_split_vcu118.runs\synth_1\runme.log"

function Write-Status {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "$timestamp $Message"
    Add-Content -Path $statusLog -Value $line -Encoding ASCII
    Write-Output $line
}

function Append-LogTail {
    param(
        [string]$Label,
        [string]$Path
    )

    if (Test-Path $Path) {
        Write-Status "$Label=$Path"
        Get-Content -Tail 20 $Path | Add-Content -Path $statusLog -Encoding ASCII
    } else {
        Write-Status "$Label`_MISSING=$Path"
    }
}

New-Item -ItemType Directory -Force -Path $SnapshotDir | Out-Null

Write-Status "START clean snapshot retry"
Write-Status "CHECK_BIT=$bitPath"

if (-not (Test-Path $planPath)) {
    Write-Status "PLAN_MISSING=$planPath"
    exit 3
}

if (-not (Test-Path $vivadoBatch)) {
    Write-Status "HOST_BATCH_MISSING=$vivadoBatch"
    exit 4
}

if (-not (Test-Path $bitPath)) {
    Write-Status "BIT_MISSING=$bitPath"
    Append-LogTail -Label "SYNTH_LOG" -Path $synthLog
    Append-LogTail -Label "IMPL_LOG" -Path $implLog
    exit 2
}

Write-Status "BIT_READY=$bitPath"
Remove-Item -ErrorAction SilentlyContinue $coreOut, $bopOut, $runLog

$env:VIVADO_ROOT = $VivadoRoot
Write-Status "RUN_HOST_PLAN=$planPath"

& $vivadoBatch $planPath *> $runLog
$rc = $LASTEXITCODE
Write-Status "HOST_EXIT_CODE=$rc"

if ($rc -ne 0) {
    Append-LogTail -Label "RUN_LOG" -Path $runLog
    exit $rc
}

$coreExists = Test-Path $coreOut
$bopExists = Test-Path $bopOut
Write-Status "CORE_OUT_EXISTS=$coreExists PATH=$coreOut"
Write-Status "BOP_OUT_EXISTS=$bopExists PATH=$bopOut"

if (-not $coreExists -or -not $bopExists) {
    Append-LogTail -Label "RUN_LOG" -Path $runLog
    exit 5
}

Write-Status "SUCCESS clean bit programmed and offline snapshot rerun completed"
exit 0
