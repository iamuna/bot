@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Terminal 3.0 v2.4 Backtest Comparison

set "LOG=%~dp0backtest_launcher.log"
>"%LOG%" echo Terminal 3.0 v2.4 launcher log
>>"%LOG%" echo Started: %DATE% %TIME%

echo ========================================
echo Terminal 3.0 v2.4 Backtest Comparison
echo Base vs Guarded
echo ========================================
echo.

set "INPUT=%~1"
if defined INPUT goto :input_ready

echo No data file was passed to the launcher.
echo.
echo Paste the full path below, or drag the ZIP into this window, then press Enter.
set /p "INPUT=BTC 1-minute CSV/ZIP path: "

rem This line is intentionally OUTSIDE a parenthesized block. CMD expands
rem percent variables before executing a block, which broke the previous prompt.
set "INPUT=%INPUT:"=%"

:input_ready
if not defined INPUT (
  echo.
  echo ERROR: No input file selected.
  >>"%LOG%" echo ERROR: No input file selected.
  goto :finish_fail
)

if not exist "%INPUT%" (
  echo.
  echo ERROR: File not found:
  echo "%INPUT%"
  >>"%LOG%" echo ERROR: File not found: %INPUT%
  goto :finish_fail
)

set "DAYS=%~2"
if not defined DAYS set "DAYS=180"

set "PY=.venv\Scripts\python.exe"
if exist "%PY%" goto :deps

echo Local Python environment not found. Creating it...
>>"%LOG%" echo Creating .venv
where py.exe >nul 2>nul
if not errorlevel 1 (
  py -3 -m venv .venv
  if errorlevel 1 goto :python_fail
  goto :deps
)

where python.exe >nul 2>nul
if errorlevel 1 goto :python_missing
python -m venv .venv
if errorlevel 1 goto :python_fail

:deps
echo Installing/checking Python requirements...
>>"%LOG%" echo Installing requirements
"%PY%" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :pip_fail

echo.
echo Data file:
echo "%INPUT%"
echo Research window: most recent %DAYS% days
echo Fee assumption: 6 bps per side
echo Slippage assumption: 1 bp per side
echo.
>>"%LOG%" echo Input: %INPUT%
>>"%LOG%" echo Days: %DAYS%

echo Running BASE v2.4 backtest...
"%PY%" backtest_v24.py "%INPUT%" --last-days %DAYS% --fee-bps 6 --slippage-bps 1 --out backtest_results\base
if errorlevel 1 goto :base_fail

echo.
echo Running GUARDED v2.4 backtest on the same data...
"%PY%" backtest_v24_guarded.py "%INPUT%" --last-days %DAYS% --fee-bps 6 --slippage-bps 1 --out backtest_results\guarded
if errorlevel 1 goto :guard_fail

echo.
echo ========================================
echo BOTH BACKTESTS COMPLETE
echo Base results:    backtest_results\base\
echo Guarded results: backtest_results\guarded\
echo ========================================
>>"%LOG%" echo SUCCESS: both backtests completed
goto :finish_ok

:python_missing
echo.
echo ERROR: Python was not found on this PC.
echo Install Python 3, then run this launcher again.
>>"%LOG%" echo ERROR: Python not found
goto :finish_fail

:python_fail
echo.
echo ERROR: Could not create the local Python environment.
>>"%LOG%" echo ERROR: venv creation failed
goto :finish_fail

:pip_fail
echo.
echo ERROR: Python requirements failed to install.
>>"%LOG%" echo ERROR: pip install failed
goto :finish_fail

:base_fail
echo.
echo ERROR: BASE v2.4 backtest failed.
>>"%LOG%" echo ERROR: base backtest failed
goto :finish_fail

:guard_fail
echo.
echo ERROR: GUARDED v2.4 backtest failed.
>>"%LOG%" echo ERROR: guarded backtest failed
goto :finish_fail

:finish_ok
echo.
echo This window will stay open until you press a key.
echo Launcher log: "%LOG%"
pause
exit /b 0

:finish_fail
echo.
echo The window is being kept open so you can read the error.
echo Launcher log: "%LOG%"
echo.
pause
exit /b 1
