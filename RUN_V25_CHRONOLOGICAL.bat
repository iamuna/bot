@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Terminal 3 v2.5B Continuous Chronological Audit

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
echo Terminal 3 v2.5B CONTINUOUS CHRONOLOGICAL HISTORICAL AUDIT
echo This is NOT a blind validation run. The historical data is already consumed.
echo It uses one 90-day warm-up, then replays the rest of the dataset with no state resets.
echo Strategy/cost/risk settings are hard-locked to frozen v2.5B values.
echo.
echo NOTE: Full-history replay can take several hours. Progress and ETA will be shown.
echo.

if "%~1"=="" (
  set /p "DATA=BTC 1-minute CSV path: "
) else (
  set "DATA=%~1"
)

"%PY%" -u backtest_v25_chronological.py "%DATA%" --workers 0 --out backtest_results_v25b_chronological
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
if "%RC%"=="0" echo v2.5B chronological audit finished successfully.
if not "%RC%"=="0" echo v2.5B chronological audit stopped with error code %RC%.
echo Results folder: backtest_results_v25b_chronological
echo.
pause
exit /b %RC%
