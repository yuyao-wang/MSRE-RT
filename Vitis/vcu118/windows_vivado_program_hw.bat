@echo off
setlocal

if "%~1"=="" (
  echo Usage: %~nx0 path\to\design.bit [path\to\design.ltx]
  exit /b 1
)

if "%VIVADO_ROOT%"=="" set "VIVADO_ROOT=C:\Xilinx\Vivado\2023.2"
if not exist "%VIVADO_ROOT%\bin\vivado.bat" (
  echo ERROR: vivado.bat not found under %VIVADO_ROOT%
  exit /b 1
)

set "BITFILE=%~f1"
set "LTXFILE="
if not "%~2"=="" set "LTXFILE=%~f2"

call "%VIVADO_ROOT%\settings64.bat" >nul 2>&1

if "%LTXFILE%"=="" (
  call "%VIVADO_ROOT%\bin\vivado.bat" -mode batch -notrace -source "%~dp0vivado_program_hw.tcl" -tclargs "%BITFILE%"
) else (
  call "%VIVADO_ROOT%\bin\vivado.bat" -mode batch -notrace -source "%~dp0vivado_program_hw.tcl" -tclargs "%BITFILE%" "%LTXFILE%"
)

exit /b %errorlevel%
