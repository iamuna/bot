@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Terminal 3.0 v2.4 Backtest Comparison

set "LOG=%~dp0backtest_launcher.log"
>"%LOG%" echo Terminal 3.0 v2.4 launcher log
>>"%LOG%" echo Started: %DATE% %TIME%

echo ========================================
echo Terminal 3.0 v2.4 Backtest Comparison
echo Base vs Guarded - Live Progress + ETA
echo ========================================
echo.

set "INPUT=%~1"
if not defined INPUT goto :ask_input
goto :have_input

:ask_input
echo No data file was passed to the launcher.
echo.
echo Paste the full path below, or drag the ZIP into this window.
set /p "INPUT=BTC 1-minute CSV/ZIP path: "
if not defined INPUT goto :no_input
if "%INPUT:~0,1%"=="^"" set "INPUT=%INPUT:~1,-1%"

:have_input
if not exist "%INPUT%" goto :file_missing

set "DAYS=%~2"
if not defined DAYS set "DAYS=180"
set "LEVERAGE=%~3"
if not defined LEVERAGE set "LEVERAGE=30"

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
echo Leverage setting: %LEVERAGE%x
echo Gross exposure cap: 3.15x account equity
echo Portfolio margin budget: 45%% of account equity
echo Fee assumption: 6 bps per side
echo Slippage assumption: 1 bp per side
echo NOTE: liquidation mechanics are not modeled in this research pass.
echo.
>>"%LOG%" echo Input: %INPUT%
>>"%LOG%" echo Days: %DAYS%
>>"%LOG%" echo Leverage: %LEVERAGE%x

echo Starting comparison. Progress will update about once per second.
echo.
"%PY%" -u backtest_progress_runner.py "%INPUT%" --last-days %DAYS% --fee-bps 6 --slippage-bps 1 --leverage %LEVERAGE% --gross-cap-x 3.15 --portfolio-margin-pct 45 --out backtest_results --mode compare
if errorlevel 1 goto :compare_fail

echo.
echo ========================================
echo BOTH BACKTESTS COMPLETE
echo Base results:    backtest_results\base\
echo Guarded results: backtest_results\guarded\
echo ========================================
>>"%LOG%" echo SUCCESS: both backtests completed
goto :finish_ok

:no_input
echo.
echo ERROR: No input file selected.
>>"%LOG%" echo ERROR: No input file selected.
goto :finish_fail

:file_missing
echo.
echo ERROR: File not found:
echo "%INPUT%"
>>"%LOG%" echo ERROR: File not found: %INPUT%
goto :finish_fail

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

:compare_fail
echo.
echo ERROR: v2.4 comparison failed.
>>"%LOG%" echo ERROR: comparison failed
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
