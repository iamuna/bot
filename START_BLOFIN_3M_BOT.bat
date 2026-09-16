@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Terminal 3.0 BloFin 3m Bot

echo ============================================================
echo        TERMINAL 3.0 - BLOFIN BTC 3M BOT
echo ============================================================
echo.

if exist ".venv\Scripts\python.exe" goto :deps

set "PY_EXE="
where py.exe >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY_EXE=py -3"
)
if not defined PY_EXE (
  where python.exe >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY_EXE=python"
  )
)

if not defined PY_EXE (
  echo Python 3.10+ was not found.
  echo Downloading Python 3.13.15 from python.org...
  set "PY_INSTALLER=%TEMP%\python-3.13.15-amd64.exe"
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.13.15/python-3.13.15-amd64.exe' -OutFile '%PY_INSTALLER%'"
  if errorlevel 1 goto :fail
  start /wait "Python Installer" "%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_test=0 Shortcuts=0
  if errorlevel 1 goto :fail
  del /q "%PY_INSTALLER%" >nul 2>nul
  set "PY_EXE=%LocalAppData%\Programs\Python\Python313\python.exe"
)

echo Creating private Python environment...
%PY_EXE% -m venv .venv
if errorlevel 1 goto :fail

:deps
set "PY=.venv\Scripts\python.exe"
"%PY%" -c "import flask,requests" >nul 2>nul
if errorlevel 1 (
  echo Installing dependencies...
  "%PY%" -m pip install --disable-pip-version-check -r requirements.txt
  if errorlevel 1 goto :fail
)

echo Running offline self-test...
"%PY%" self_test.py
if errorlevel 1 goto :fail

echo.
echo Starting bot in the mode configured in .env.
echo The default configuration is PAPER mode.
set "AUTO_OPEN_BROWSER=1"
"%PY%" app.py
pause
exit /b %ERRORLEVEL%

:fail
echo.
echo ERROR: Setup or self-test failed.
echo Check the message above, then run this file again.
pause
exit /b 1
