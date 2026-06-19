@echo off
setlocal

if "%VITIS_HLS_ROOT%"=="" set "VITIS_HLS_ROOT=C:\Xilinx\Vitis_HLS\2023.2"
if not exist "%VITIS_HLS_ROOT%\bin\vitis_hls.bat" (
  echo ERROR: vitis_hls.bat not found under %VITIS_HLS_ROOT%
  exit /b 1
)

call "%VITIS_HLS_ROOT%\settings64.bat" >nul 2>&1
call "%VITIS_HLS_ROOT%\bin\vitis_hls.bat" -f "%~dp0hls_export_core_step_n200_s1_10ns_lowlane.tcl"
if errorlevel 1 exit /b %errorlevel%
call "%VITIS_HLS_ROOT%\bin\vitis_hls.bat" -f "%~dp0hls_export_bop_step_n200_s1_10ns_lowlane.tcl"
exit /b %errorlevel%
