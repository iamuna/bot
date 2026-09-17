@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Terminal 3 - Full Self Test

set "PY=.venv\Scripts\python.exe"
if exist "%PY%" goto :deps

where py.exe >nul 2>nul
if errorlevel 1 goto :try_python
py -3 -m venv .venv
if errorlevel 1 goto :fail
goto :deps

:try_python
where python.exe >nul 2>nul
if errorlevel 1 goto :no_python
python -m venv .venv
if errorlevel 1 goto :fail

:deps
"%PY%" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :fail

for %%T in (
  self_test.py
  backtest_self_test.py
  backtest_guard_self_test.py
  backtest_selective_self_test.py
  backtest_efficiency_self_test.py
  backtest_oos_self_test.py
  backtest_v25_self_test.py
  backtest_v25_chronological_self_test.py
  backtest_progress_self_test.py
  portfolio_cap_self_test.py
) do (
  echo Running %%T...
  "%PY%" %%T
  if errorlevel 1 goto :fail
)

echo Running full CPU pipeline self-test...
"%PY%" backtest_full_cpu_runner.py --self-test
if errorlevel 1 goto :fail

echo.
echo ========================================
echo ALL CURRENT SELF TESTS PASSED
echo ========================================
pause
exit /b 0

:no_python
echo ERROR: Python was not found. Install Python 3.11+.

:fail
echo.
echo ========================================
echo SELF TEST FAILED
echo ========================================
pause
exit /b 1
