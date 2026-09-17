@echo off
setlocal
cd /d "%~dp0"
title Terminal 3.0 v2.4 Backtester

echo ========================================
echo Terminal 3.0 v2.4 Adaptive Backtester
echo ========================================
echo.

if "%~1"=="" (
  echo Drag a 1-minute BTC OHLCV CSV onto this file
  echo or run:
  echo   RUN_BACKTEST_V24.bat path\to\btc_1m.csv
  echo.
  pause
  exit /b 1
)

set PY=.venv\Scripts\python.exe
if not exist "%PY%" (
  echo Local Python environment not found. Creating it...
  where py.exe >nul 2>nul && (py -3 -m venv .venv) || (python -m venv .venv)
  if errorlevel 1 goto :fail
)

"%PY%" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :fail

echo Running backtest on:
echo %~1
echo.
"%PY%" backtest_v24.py "%~1" --out backtest_results
if errorlevel 1 goto :fail

echo.
echo Backtest complete. Results are in backtest_results\
pause
exit /b 0

:fail
echo.
echo BACKTEST FAILED. Review the error above.
pause
exit /b 1
