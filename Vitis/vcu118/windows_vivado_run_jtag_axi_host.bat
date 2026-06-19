@echo off
setlocal

if "%~1"=="" (
  echo Usage: %~nx0 path\to\plan.tcl
  exit /b 1
)

if "%VIVADO_ROOT%"=="" set "VIVADO_ROOT=C:\Xilinx\Vivado\2023.2"
if not exist "%VIVADO_ROOT%\bin\vivado.bat" (
  echo ERROR: vivado.bat not found under %VIVADO_ROOT%
  exit /b 1
)

set "PLAN_FILE=%~f1"
if not exist "%PLAN_FILE%" (
  echo ERROR: plan file does not exist: %PLAN_FILE%
  exit /b 1
)

call "%VIVADO_ROOT%\settings64.bat" >nul 2>&1
call "%VIVADO_ROOT%\bin\vivado.bat" -mode batch -notrace -source "%~dp0vivado_jtag_axi_host.tcl" -tclargs "%PLAN_FILE%"
exit /b %errorlevel%
