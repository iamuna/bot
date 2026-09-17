@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Terminal 3 v2.5B 90-Day Warmup Stability Check

set "PY=.venv\Scripts\python.exe"
if exist "%PY%" goto :deps

echo Local Python environment not found. Creating it...
where py.exe >nul 2>nul
if errorlevel 1 goto :try_python
py -3 -m venv .venv
if errorlevel 1 goto :venv_fail
goto :deps

:try_python
where python.exe >nul 2>nul
if errorlevel 1 goto :python_missing
python -m venv .venv
if errorlevel 1 goto :venv_fail

:deps
echo Installing/checking Python requirements...
"%PY%" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :pip_fail

echo.
echo Terminal 3 v2.5B warmup stability check
echo Candidate is FROZEN: 2h+ entries, same fees/slippage/risk/exit logic.
echo Methodology check: 13 already-seen windows with a 90-day warmup.
echo The oldest research window is intentionally omitted so this run does not
echo load any BTC history earlier than the original research run already used.
echo.

if "%~1"=="" (
  set /p "DATA=BTC 1-minute CSV path: "
) else (
  set "DATA=%~1"
)

"%PY%" -u backtest_v25_research.py "%DATA%" --workers 0 --windows 13 --warmup-days 90 --out backtest_results_v25b_stability_90d
set "RC=%ERRORLEVEL%"
goto :finish

:python_missing
echo ERROR: Python was not found on this PC.
set "RC=1"
goto :finish

:venv_fail
echo ERROR: Could not create the local Python environment.
set "RC=1"
goto :finish

:pip_fail
echo ERROR: Python requirements failed to install.
set "RC=1"

:finish
echo.
if "%RC%"=="0" echo v2.5B 90-day stability check finished successfully.
if not "%RC%"=="0" echo v2.5B stability check stopped with error code %RC%.
echo Results folder: backtest_results_v25b_stability_90d
echo.
pause
exit /b %RC%
