@echo off
setlocal

if "%PYTHON_EXE%"=="" set "PYTHON_EXE=py -3"
set "HOST_DIR=%~dp0"
set "SMOKE_DIR=%HOST_DIR%host_smoke"

if not exist "%SMOKE_DIR%" mkdir "%SMOKE_DIR%"

%PYTHON_EXE% "%HOST_DIR%msr_vcu118_host.py" prepare-smoke --out-dir "%SMOKE_DIR%" %*
if errorlevel 1 exit /b %errorlevel%

call "%HOST_DIR%windows_vivado_run_jtag_axi_host.bat" "%SMOKE_DIR%\smoke_plan.tcl"
if errorlevel 1 exit /b %errorlevel%

echo --- CORE BOUNDARY ---
%PYTHON_EXE% "%HOST_DIR%msr_vcu118_host.py" decode-boundary --kind core --input "%SMOKE_DIR%\core_boundary_out.hex32"
if errorlevel 1 exit /b %errorlevel%

echo --- BOP BOUNDARY ---
%PYTHON_EXE% "%HOST_DIR%msr_vcu118_host.py" decode-boundary --kind bop --input "%SMOKE_DIR%\bop_boundary_out.hex32"
exit /b %errorlevel%
