@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Terminal 3 v2.5B Historical Holdout Reproduction

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
echo Terminal 3 v2.5B HISTORICAL HOLDOUT REPRODUCTION
echo The original untouched validation has already been completed and recorded.
echo This rerun is for reproducibility only; it is NOT new blind validation.
echo All result-affecting settings are hard-locked to the frozen v2.5B protocol.
echo.

if "%~1"=="" (
  set /p "DATA=BTC 1-minute CSV path: "
) else (
  set "DATA=%~1"
)

"%PY%" -u backtest_v25_final_validation.py "%DATA%" --workers 0 --out backtest_results_v25b_final_validation
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
if "%RC%"=="0" echo v2.5B holdout reproduction finished successfully.
if not "%RC%"=="0" echo v2.5B holdout reproduction stopped with error code %RC%.
echo Results folder: backtest_results_v25b_final_validation
echo.
pause
exit /b %RC%
