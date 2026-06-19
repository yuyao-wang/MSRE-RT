@echo off
setlocal

if "%VIVADO_ROOT%"=="" set "VIVADO_ROOT=C:\Xilinx\Vivado\2023.2"
if not exist "%VIVADO_ROOT%\bin\vivado.bat" (
  echo ERROR: vivado.bat not found under %VIVADO_ROOT%
  exit /b 1
)

call "%VIVADO_ROOT%\settings64.bat" >nul 2>&1
call "%VIVADO_ROOT%\bin\vivado.bat" -mode batch -notrace -source "%~dp0vivado_build_vcu118_bitstream.tcl"
exit /b %errorlevel%
