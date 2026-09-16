@echo off
setlocal
cd /d "%~dp0"
title Terminal 3.0 BloFin Bot - Self Test

echo ========================================
echo Terminal 3.0 BloFin Bot - Self Test
echo ========================================
echo.

set PYEXE=
where py.exe >nul 2>nul && set PYEXE=py -3
if not defined PYEXE (
  where python.exe >nul 2>nul && set PYEXE=python
)
if not defined PYEXE (
  echo ERROR: Python was not found.
  echo Install Python 3.11+ and run this file again.
  goto :fail
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating local Python environment...
  %PYEXE% -m venv .venv
  if errorlevel 1 goto :fail
) else (
  echo [1/3] Local Python environment found.
)

echo [2/3] Installing/repairing required packages...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :fail

echo [3/3] Running bot self-test...
echo.
".venv\Scripts\python.exe" self_test.py
if errorlevel 1 goto :fail

echo.
echo ========================================
echo SELF CHECK PASSED
 echo The local environment and offline bot tests are OK.
echo ========================================
pause
exit /b 0

:fail
echo.
echo ========================================
echo SELF CHECK FAILED
 echo Review the error above. The test did not pass.
echo ========================================
pause
exit /b 1
