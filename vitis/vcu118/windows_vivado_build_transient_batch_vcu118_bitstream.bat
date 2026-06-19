@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "VITIS_ROOT=%%~fI"
if "%MSR_SHORT_DRIVE%"=="" set "MSR_SHORT_DRIVE=X:"

if /I not "%~d0"=="%MSR_SHORT_DRIVE%" (
  subst %MSR_SHORT_DRIVE% "%VITIS_ROOT%" >nul 2>&1
  if not exist "%MSR_SHORT_DRIVE%\vcu118\%~nx0" (
    echo ERROR: failed to map %VITIS_ROOT% to %MSR_SHORT_DRIVE%
    exit /b 1
  )
  call "%MSR_SHORT_DRIVE%\vcu118\%~nx0"
  exit /b %errorlevel%
)

if "%VIVADO_ROOT%"=="" set "VIVADO_ROOT=C:\Xilinx\Vivado\2023.2"
if not exist "%VIVADO_ROOT%\bin\vivado.bat" (
  echo ERROR: vivado.bat not found under %VIVADO_ROOT%
  exit /b 1
)

if "%XILINXD_LICENSE_FILE%"=="" if exist "%USERPROFILE%\license\Xilinx.lic" (
  set "XILINXD_LICENSE_FILE=%USERPROFILE%\license\Xilinx.lic"
)

set "PACK_DIR=%~dp0..\hls_export_work\transient_batch_bench_600x1_10ns_sharedfp\solution1\impl\ip"
if not exist "%PACK_DIR%\component.xml" (
  pushd "%PACK_DIR%"
  call pack.bat
  set "PACK_STATUS=%errorlevel%"
  popd
  if not "%PACK_STATUS%"=="0" exit /b %PACK_STATUS%
)

call "%VIVADO_ROOT%\settings64.bat" >nul 2>&1
call "%VIVADO_ROOT%\bin\vivado.bat" -mode batch -notrace -source "%~dp0vivado_build_transient_batch_vcu118_bitstream.tcl"
exit /b %errorlevel%
