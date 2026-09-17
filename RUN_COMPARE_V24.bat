@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Terminal 3.0 v2.4 Backtest Comparison

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
echo Starting the v2.4 launcher...
echo This window is configured to stay open on success OR failure.
echo.
"%PY%" -u launcher_v24.py %*
set "RC=%ERRORLEVEL%"
goto :finish

:python_missing
echo.
echo ERROR: Python was not found on this PC.
set "RC=1"
goto :finish

:venv_fail
echo.
echo ERROR: Could not create the local Python environment.
set "RC=1"
goto :finish

:pip_fail
echo.
echo ERROR: Python requirements failed to install.
set "RC=1"
goto :finish

:finish
echo.
if "%RC%"=="0" echo Launcher finished successfully.
if not "%RC%"=="0" echo Launcher stopped with error code %RC%.
echo.
echo DO NOT CLOSE THIS WINDOW YET if you need to show me an error.
echo Press any key when you are finished reading or taking a screenshot.
pause >nul
exit /b %RC%
