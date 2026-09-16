@echo off
setlocal
cd /d "%~dp0"
title Terminal 3.0 BloFin Multi-Timeframe Bot

set PYEXE=
where py >nul 2>nul && set PYEXE=py
if not defined PYEXE (where python >nul 2>nul && set PYEXE=python)
if not defined PYEXE (
  echo Python was not found. Please install Python 3.11+ and run this file again.
  pause
  exit /b 1
)

if not exist .venv (
  %PYEXE% -m venv .venv
  if errorlevel 1 goto :fail
)
call .venv\Scripts\activate.bat
python -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :fail
python app.py
exit /b %errorlevel%

:fail
echo.
echo Startup failed. Run RUN_SELF_TEST.bat and review the error above.
pause
exit /b 1
